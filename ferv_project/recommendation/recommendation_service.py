"""
recommendation_service.py
--------------------------
RecommendationService — orchestrator for the three recommendation pipelines:
  - Pipeline A: one-shot recommendation from a free-text prompt
  - Pipeline B: node-based recommendation, seeded by the user's in_graph nodes
  - Pipeline C: exploratory recommendation, seeded by a perturbed profile vector

Each pipeline ends with N GraphNode rows in 'recommendation' status and an
LlmInteractionLog row capturing the inputs, raw LLM response, and outcome.
"""

import hashlib
import logging
import struct

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from graph.models import GraphNode
from places.models import Place
from recommendation import vector_utils
from recommendation.llm_client import LlmClient, RecommendationOutput
from recommendation.models import LlmInteractionLog, PlaceEmbedding
from recommendation.prompt_builder import PromptBuilder
from recommendation.embedding_service import EmbeddingService
from recommendation.retriever import Retriever

log = logging.getLogger(__name__)

RECOMMENDATION_K = 12  # retrieval breadth (candidates passed to LLM)
RECOMMENDATION_N = 4   # final picks returned to the user

NODE_BASED_K_PRIME = 50   # per-anchor retrieval breadth
NODE_BASED_K = 20         # distilled candidates after RRF
NODE_BASED_N = 5          # final picks returned to the user
RRF_C = 60                # RRF constant (Cormack/Buettcher/Clarke default)

EXPLORATORY_K = 200          # broad retrieval set (perturbed query vector)
EXPLORATORY_K_TOP = 180      # exclusion zone — top of the broad set is dropped
EXPLORATORY_MARGIN_SIZE = EXPLORATORY_K - EXPLORATORY_K_TOP  # 20
EXPLORATORY_D = 5            # direction-decoding probe size (logging only)
EXPLORATORY_N = 5            # final picks
EXPLORATORY_SCALE = 1.0      # TODO: empirically tune per embedding model


def _candidates_block(candidates: list[dict]) -> str:
    """Format candidate places into the block injected into the prompt template."""
    lines = []
    for c in candidates:
        place = c["place"]
        tags = ", ".join(t.tag for t in place.tags.all())
        summary = place.editorial_summary or "No description available."
        document = place.document.text if hasattr(place, "document") else "No document available."
        lines.append(
            f"place_id: {place.place_id}\n"
            f"  name: {place.name}\n"
            f"  neighborhood: {place.neighborhood or 'unknown'}\n"
            f"  rating: {place.rating}\n"
            f"  tags: {tags}\n"
            f"  summary: {summary}\n"
            f"  document: {document}"
        )
    return "\n\n".join(lines)


def _anchor_vectors(places: list[Place], vector_class: type) -> dict[int, list[float]]:
    """
    Return {place.pk: vector} for every place that has a PlaceEmbedding row
    pointing at the given VectorClass. Places without an embedding are absent
    from the result; the caller decides how to react.

    Two queries total regardless of len(places).
    """
    if not places:
        return {}
    ct = ContentType.objects.get_for_model(vector_class)
    place_embs = list(
        PlaceEmbedding.objects.filter(
            place__in=places, content_type=ct
        ).values("place_id", "object_id")
    )
    if not place_embs:
        return {}
    vector_id_to_place_id = {pe["object_id"]: pe["place_id"] for pe in place_embs}
    rows = vector_class.objects.filter(id__in=list(vector_id_to_place_id.keys())).values(
        "id", "vector"
    )
    return {
        vector_id_to_place_id[row["id"]]: list(row["vector"]) for row in rows
    }


class RecommendationService:
    def recommend_one_shot(self, user, prompt_text: str) -> list:
        """
        Run Pipeline A for a single user request.
        Returns a list of GraphNode instances with status='recommendation'.
        Raises on LLM validation failure.
        """
        embedder = EmbeddingService()
        retriever = Retriever()
        builder = PromptBuilder()
        llm = LlmClient()

        # Step 1 — embed the prompt (not persisted)
        query_vector = embedder.embed(prompt_text)

        # Step 2 — retrieve candidates, exclude user's existing nodes
        candidates = retriever.get_candidates(
            query_vector, top_k=RECOMMENDATION_K, exclude_user=user
        )
        if not candidates:
            log.warning("No candidates found for user %s with prompt: %s", user.id, prompt_text)
            return []

        # Step 3 — build profile text
        profile_text = user.get_profile_as_prompt_text()
        
        # Step 4 — assemble prompt
        candidates_block = _candidates_block(candidates)
        n = min(RECOMMENDATION_N, len(candidates))
        prompt, prompt_version = builder.build(
            "recommendation_v1",
            prompt_text=prompt_text,
            profile_text=profile_text or "No profile available.",
            candidates_block=candidates_block,
            candidate_count=len(candidates),
            n=n,
        )

        # Step 5 — LLM call
        input_payload = {
            "prompt_text": prompt_text,
            "profile_snapshot": profile_text,
            "candidate_place_ids": [c["place"].place_id for c in candidates],
            "n": n,
        }
        raw_response = ""
        parsed_output = None
        outcome = "success"
        try:
            parsed, raw_response = llm.send(prompt, RecommendationOutput)
            parsed_output = parsed
        except ValueError as e:
            outcome = "validation_error"
            LlmInteractionLog.objects.create(
                user=user,
                workflow="recommendation",
                prompt_version=prompt_version,
                embedding_model=embedder.model_name,
                language_model=llm.model_name,
                input_payload=input_payload,
                raw_llm_response=str(e),
                parsed_output=None,
                outcome=outcome,
            )
            raise

        # Step 6 — validate place_ids are from candidate set
        candidate_place_map = {c["place"].place_id: c["place"] for c in candidates}
        picks = parsed["recommendations"]
        unknown = [p["place_id"] for p in picks if p["place_id"] not in candidate_place_map]
        if unknown:
            raise ValueError(f"LLM returned unknown place_ids: {unknown}")

        # Step 7 — create GraphNode rows
        nodes = []
        for pick in picks:
            place = candidate_place_map[pick["place_id"]]
            node, _ = GraphNode.objects.get_or_create(
                user=user,
                place=place,
                defaults={
                    "status": "recommendation",
                    "rationale": pick["rationale"][:255],
                },
            )
            nodes.append(node)

        # Step 8 — log interaction
        LlmInteractionLog.objects.create(
            user=user,
            workflow="recommendation",
            prompt_version=prompt_version,
            embedding_model=embedder.model_name,
            language_model=llm.model_name,
            input_payload=input_payload,
            raw_llm_response=raw_response,
            parsed_output=parsed_output,
            outcome=outcome,
        )

        return nodes

    def recommend_node_based(self, user, node_ids: list[int]) -> list:
        """
        Pipeline B — Node-based recommendation.

        Given a list of the user's existing in_graph GraphNode IDs, run one
        similarity query per anchor node, fuse the ranked lists with
        Reciprocal Rank Fusion, and ask the LLM to pick N candidates that
        extend the pattern set by the anchors.
        """
        if not isinstance(node_ids, list) or not node_ids:
            raise ValueError(f"node_ids must be a non-empty list, got {node_ids!r}")
        if not all(isinstance(nid, int) and not isinstance(nid, bool) for nid in node_ids):
            raise ValueError(f"node_ids must be a list of ints, got {node_ids!r}")

        embedder = EmbeddingService()
        retriever = Retriever()
        builder = PromptBuilder()
        llm = LlmClient()

        # Step 1 — fetch anchor nodes (must all belong to user, status=in_graph).
        unique_ids = list(dict.fromkeys(node_ids))  # preserve order, dedupe
        anchor_nodes = list(
            GraphNode.objects.filter(
                id__in=unique_ids, user=user, status__in=["in_graph", "visited"]
            ).select_related("place")
        )
        if len(anchor_nodes) != len(unique_ids):
            found_ids = {n.pk for n in anchor_nodes}
            missing = [nid for nid in unique_ids if nid not in found_ids]
            raise ValueError(
                f"node_ids missing, not owned by user, or not in_graph: {missing}"
            )

        # Step 2 — resolve each anchor place's embedding vector.
        anchor_places = [n.place for n in anchor_nodes]
        place_id_to_vector = _anchor_vectors(anchor_places, embedder.vector_class)
        missing_embeddings = [
            p.place_id for p in anchor_places if p.pk not in place_id_to_vector
        ]
        if missing_embeddings:
            raise ValueError(
                f"anchor places without an embedding: {missing_embeddings}"
            )

        # Step 3 — n independent similarity queries, one per anchor.
        per_anchor_lists: list[list[str]] = []
        per_anchor_candidates: dict[str, dict] = {}
        per_anchor_log: list[dict] = []
        for node in anchor_nodes:
            vec = place_id_to_vector[node.place.pk]
            results = retriever.get_candidates(
                vec, top_k=NODE_BASED_K_PRIME, exclude_user=user
            )
            ranked_ids = [c["place"].place_id for c in results]
            per_anchor_lists.append(ranked_ids)
            per_anchor_log.append(
                {
                    "anchor_node_id": node.pk,
                    "anchor_place_id": node.place.place_id,
                    "ranked_place_ids": ranked_ids,
                }
            )
            for c in results:
                # Keep the first sighting; later anchors don't overwrite.
                per_anchor_candidates.setdefault(c["place"].place_id, c)

        # Step 4 — RRF fuse the per-anchor lists, take top-K.
        fused = vector_utils.reciprocal_rank_fusion(per_anchor_lists, c=RRF_C)
        fused_top = fused[:NODE_BASED_K]
        if not fused_top:
            log.warning(
                "Pipeline B produced no candidates for user %s with anchors %s",
                user.id, [n.pk for n in anchor_nodes],
            )
            return []

        # Step 5 — materialize candidate dicts in fused order.
        candidates = [per_anchor_candidates[str(pid)] for pid, _score in fused_top]
        fused_log = [
            {"place_id": pid, "rrf_score": score} for pid, score in fused_top
        ]

        # Step 6 — profile + prompt assembly.
        profile_text = user.get_profile_as_prompt_text()
        anchors_block = _candidates_block([{"place": p} for p in anchor_places])
        candidates_block = _candidates_block(candidates)
        n = min(NODE_BASED_N, len(candidates))
        prompt, prompt_version = builder.build(
            "node_based_recommendation_v1",
            anchors_block=anchors_block,
            profile_text=profile_text or "No profile available.",
            candidates_block=candidates_block,
            candidate_count=len(candidates),
            n=n,
        )

        # Step 7 — LLM call.
        input_payload = {
            "anchor_node_ids": [n.pk for n in anchor_nodes],
            "anchor_place_ids": [p.place_id for p in anchor_places],
            "per_anchor_retrieval": per_anchor_log,
            "fused_top_k": fused_log,
            "profile_snapshot": profile_text,
            "n": n,
        }
        raw_response = ""
        parsed_output = None
        outcome = "success"
        try:
            parsed, raw_response = llm.send(prompt, RecommendationOutput)
            parsed_output = parsed
        except ValueError as e:
            outcome = "validation_error"
            LlmInteractionLog.objects.create(
                user=user,
                workflow="node_based_recommendation",
                prompt_version=prompt_version,
                embedding_model=embedder.model_name,
                language_model=llm.model_name,
                input_payload=input_payload,
                raw_llm_response=str(e),
                parsed_output=None,
                outcome=outcome,
            )
            raise

        # Step 8 — validate picks ⊆ fused candidate set.
        candidate_place_map = {c["place"].place_id: c["place"] for c in candidates}
        picks = parsed["recommendations"]
        unknown = [p["place_id"] for p in picks if p["place_id"] not in candidate_place_map]
        if unknown:
            outcome = "validation_error"
            LlmInteractionLog.objects.create(
                user=user,
                workflow="node_based_recommendation",
                prompt_version=prompt_version,
                embedding_model=embedder.model_name,
                language_model=llm.model_name,
                input_payload=input_payload,
                raw_llm_response=raw_response,
                parsed_output=parsed_output,
                outcome=outcome,
            )
            raise ValueError(
                f"LLM returned place_ids outside the fused candidate set: {unknown}"
            )

        # Step 9 — create GraphNode rows atomically.
        with transaction.atomic():
            nodes = []
            for pick in picks:
                place = candidate_place_map[pick["place_id"]]
                node, _ = GraphNode.objects.get_or_create(
                    user=user,
                    place=place,
                    defaults={
                        "status": "recommendation",
                        "rationale": pick["rationale"][:255],
                    },
                )
                nodes.append(node)

        # Step 10 — log success.
        LlmInteractionLog.objects.create(
            user=user,
            workflow="node_based_recommendation",
            prompt_version=prompt_version,
            embedding_model=embedder.model_name,
            language_model=llm.model_name,
            input_payload=input_payload,
            raw_llm_response=raw_response,
            parsed_output=parsed_output,
            outcome=outcome,
        )

        return nodes

    def recommend_exploratory(self, user, heat: float) -> list:
        """
        Pipeline C — Exploratory recommendation.

        Perturbs the user's profile embedding by `heat * EXPLORATORY_SCALE`
        along a random unit direction, retrieves a broad neighborhood of the
        perturbed vector, drops the closest K_TOP, and asks the LLM to pick
        coherent stretches from the remaining margin block.
        """
        if not isinstance(heat, (int, float)) or not (0.0 <= float(heat) <= 1.0):
            raise ValueError(f"heat must be a number in [0, 1], got {heat!r}")
        heat = float(heat)

        embedder = EmbeddingService()
        retriever = Retriever()
        builder = PromptBuilder()
        llm = LlmClient()

        # Step 1 — profile text + ephemeral profile embedding
        profile_text = user.get_profile_as_prompt_text() or "No profile available."
        profile_vector = embedder.embed(profile_text)

        # Step 2 — random direction + perturbed query vector
        direction = vector_utils.random_unit_vector(len(profile_vector))
        perturbation_magnitude = heat * EXPLORATORY_SCALE
        query_vector = vector_utils.vector_add_scaled(
            profile_vector, direction, perturbation_magnitude
        )

        # Step 3 — direction decoding (logging only; not used for candidates)
        direction_probes = retriever.get_candidates(
            direction, top_k=EXPLORATORY_D, exclude_user=None
        )
        direction_label_ids = [c["place"].place_id for c in direction_probes]

        # Step 4 — broad retrieval against the perturbed query, exclude user's nodes
        broad = retriever.get_candidates(
            query_vector, top_k=EXPLORATORY_K, exclude_user=user
        )
        broad_place_ids = [c["place"].place_id for c in broad]
        top_place_ids = broad_place_ids[:EXPLORATORY_K_TOP]
        margin = broad[EXPLORATORY_K_TOP:]
        margin_place_ids = [c["place"].place_id for c in margin]

        if len(margin) == 0:
            raise ValueError(
                "not enough candidates for exploratory recommendation: "
                f"broad set has {len(broad)} rows, need more than {EXPLORATORY_K_TOP}"
            )

        # Step 5 — assemble prompt
        candidates_block = _candidates_block(margin)
        n = min(EXPLORATORY_N, len(margin))
        prompt, prompt_version = builder.build(
            "exploratory_recommendation_v1",
            profile_text=profile_text,
            candidates_block=candidates_block,
            candidate_count=len(margin),
            n=n,
        )

        # Step 6 — LLM call
        input_payload = {
            "heat": heat,
            "perturbation_magnitude": perturbation_magnitude,
            "profile_snapshot": profile_text,
            "profile_embedding_hash": _vector_hash(profile_vector),
            "direction_vector": direction,
            "direction_decoded_place_ids": direction_label_ids,
            "broad_candidate_place_ids": broad_place_ids,
            "top_candidate_place_ids": top_place_ids,
            "margin_candidate_place_ids": margin_place_ids,
            "n": n,
        }
        raw_response = ""
        parsed_output = None
        outcome = "success"
        try:
            parsed, raw_response = llm.send(prompt, RecommendationOutput)
            parsed_output = parsed
        except ValueError as e:
            outcome = "validation_error"
            LlmInteractionLog.objects.create(
                user=user,
                workflow="exploratory_recommendation",
                prompt_version=prompt_version,
                embedding_model=embedder.model_name,
                language_model=llm.model_name,
                input_payload=input_payload,
                raw_llm_response=str(e),
                parsed_output=None,
                outcome=outcome,
            )
            raise

        # Step 7 — validate picks come from the margin block
        margin_place_map = {c["place"].place_id: c["place"] for c in margin}
        picks = parsed["recommendations"]
        unknown = [p["place_id"] for p in picks if p["place_id"] not in margin_place_map]
        if unknown:
            outcome = "validation_error"
            LlmInteractionLog.objects.create(
                user=user,
                workflow="exploratory_recommendation",
                prompt_version=prompt_version,
                embedding_model=embedder.model_name,
                language_model=llm.model_name,
                input_payload=input_payload,
                raw_llm_response=raw_response,
                parsed_output=parsed_output,
                outcome=outcome,
            )
            raise ValueError(
                f"LLM returned place_ids outside the margin block: {unknown}"
            )

        # Step 8 — create GraphNode rows atomically
        with transaction.atomic():
            nodes = []
            for pick in picks:
                place = margin_place_map[pick["place_id"]]
                node, _ = GraphNode.objects.get_or_create(
                    user=user,
                    place=place,
                    defaults={
                        "status": "recommendation",
                        "rationale": pick["rationale"][:255],
                    },
                )
                nodes.append(node)

        # Step 9 — log success
        LlmInteractionLog.objects.create(
            user=user,
            workflow="exploratory_recommendation",
            prompt_version=prompt_version,
            embedding_model=embedder.model_name,
            language_model=llm.model_name,
            input_payload=input_payload,
            raw_llm_response=raw_response,
            parsed_output=parsed_output,
            outcome=outcome,
        )

        return nodes


def _vector_hash(vector: list[float]) -> str:
    """Stable sha256 of a float vector — keeps the log row small."""
    packed = struct.pack(f"{len(vector)}f", *vector)
    return hashlib.sha256(packed).hexdigest()
