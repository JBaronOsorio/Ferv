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

import logging

from graph.models import GraphNode
from places.models import Place
from recommendation.llm_client import LlmClient, RecommendationOutput
from recommendation.models import LlmInteractionLog
from recommendation.prompt_builder import PromptBuilder
from recommendation.services import EmbeddingService, Retriever

log = logging.getLogger(__name__)

RECOMMENDATION_K = 20  # retrieval breadth (candidates passed to LLM)
RECOMMENDATION_N = 5   # final picks returned to the user


def _candidates_block(candidates: list[dict]) -> str:
    """Format candidate places into the block injected into the prompt template."""
    lines = []
    for c in candidates:
        place = c["place"]
        tags = ", ".join(t.tag for t in place.tags.all())
        summary = place.editorial_summary or "No description available."
        lines.append(
            f"place_id: {place.place_id}\n"
            f"  name: {place.name}\n"
            f"  neighborhood: {place.neighborhood or 'unknown'}\n"
            f"  rating: {place.rating}\n"
            f"  tags: {tags}\n"
            f"  summary: {summary}"
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
        #profile_text = user.get_profile_as_prompt_text()
        profile_text = "John likes italian food, is vegan, is bothered by loud places"

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

        log.info(
            "recommend_one_shot: user=%s created %d recommendation nodes", user.id, len(nodes)
        )
        return nodes
