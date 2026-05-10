"""
recommendation_service.py
--------------------------
RecommendationService — Pipeline A orchestrator.

Workflow:
  1. Embed the user's prompt text
  2. Retrieve top-K candidate places by vector similarity (excluding user's existing nodes)
  3. Assemble user profile text
  4. Build prompt via PromptBuilder
  5. Call LLM via LlmClient, validate response
  6. Create GraphNode rows (status='recommendation') for each LLM-selected place
  7. Log interaction to LlmInteractionLog
"""

import hashlib
import logging
import struct

from django.db import transaction

from graph.models import GraphNode
from places.models import Place
from recommendation import vector_utils
from recommendation.llm_client import LlmClient, RecommendationOutput
from recommendation.models import LlmInteractionLog
from recommendation.prompt_builder import PromptBuilder
from recommendation.embedding_service import EmbeddingService
from recommendation.retriever import Retriever

log = logging.getLogger(__name__)

RECOMMENDATION_K = 12  # retrieval breadth (candidates passed to LLM)
RECOMMENDATION_N = 4   # final picks returned to the user

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
