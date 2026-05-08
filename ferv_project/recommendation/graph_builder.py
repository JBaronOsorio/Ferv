"""
graph_builder.py
----------------
GraphBuilder — Pipeline B orchestrator.

Workflow:
  1. Load the recommendation-status GraphNode (verify it belongs to this user)
  2. Retrieve top-N similar in_graph nodes for the user via vector similarity
  3. If no in_graph nodes exist: transition status only, no LLM call
  4. Assemble user profile text
  5. Build prompt via PromptBuilder
  6. Call LLM via LlmClient, validate response
  7. Security-verify all returned node IDs belong to this user
  8. In a transaction: create GraphEdge rows + transition node to in_graph
  9. Log interaction to LlmInteractionLog
"""

import logging

from django.db import transaction

from graph.models import GraphEdge, GraphNode
from recommendation.llm_client import EdgeBuildingOutput, LlmClient
from recommendation.models import LlmInteractionLog
from recommendation.prompt_builder import PromptBuilder
from recommendation.services import Retriever

log = logging.getLogger(__name__)

EDGE_CANDIDATE_N = 8  # max in_graph nodes passed as candidates for edge building


def _node_block(node: GraphNode) -> str:
    """Format a single node's place as a prompt block."""
    place = node.place
    tags = ", ".join(t.tag for t in place.tags.all())
    summary = place.editorial_summary or "No description available."
    document = place.document.text if hasattr(place, "document") else "No document available."
    return (
        f"node_id: {node.pk}\n"
        f"  place_id: {place.place_id}\n"
        f"  name: {place.name}\n"
        f"  neighborhood: {place.neighborhood or 'unknown'}\n"
        f"  rating: {place.rating}\n"
        f"  tags: {tags}\n"
        f"  summary: {summary}\n"
        f"  document: {document}"
    )


def _candidates_block(nodes: list) -> str:
    return "\n\n".join(_node_block(n) for n in nodes)


class GraphBuilder:
    def add_to_graph(self, user, node_id: int, target_status: str = "in_graph") -> list[int]:
        """
        Promote a GraphNode (recommendation or discovery status) to target_status.
        Returns list of created GraphEdge IDs.
        Raises on invalid node, wrong user/status, or LLM validation failure.
        """
        # Step 1 — load and validate the node
        try:
            node = GraphNode.objects.select_related("place").prefetch_related(
                "place__tags"
            ).get(id=node_id, user=user)
        except GraphNode.DoesNotExist:
            raise ValueError(f"GraphNode {node_id} not found for this user.")

        allowed_source_statuses = {"recommendation", "discovery"}
        if node.status not in allowed_source_statuses:
            raise ValueError(
                f"GraphNode {node_id} has status '{node.status}', expected one of {allowed_source_statuses}."
            )

        retriever = Retriever()

        # Step 2 — find similar in_graph nodes
        candidate_nodes = retriever.get_similar_in_graph_nodes(
            node, user, top_n=EDGE_CANDIDATE_N
        )

        # Step 3 — no existing in_graph nodes: transition only, skip LLM
        if not candidate_nodes:
            node.status = target_status
            node.save(update_fields=["status", "updated_at"])
            log.info(
                "add_to_graph: node %d → %s (no existing nodes, no edges)", node_id, target_status
            )
            return []

        builder = PromptBuilder()
        llm = LlmClient()

        # Step 4 — profile text
        profile_text = user.get_profile_as_prompt_text()

        # Step 5 — build prompt
        new_node_block = _node_block(node)
        candidates_block = _candidates_block(candidate_nodes)
        prompt, prompt_version = builder.build(
            "edge_building_v1",
            profile_text=profile_text or "No profile available.",
            new_node_id=node.pk,
            new_node_block=new_node_block,
            candidates_block=candidates_block,
        )

        # Step 6 — LLM call
        candidate_node_ids = {n.id for n in candidate_nodes}
        valid_node_ids = candidate_node_ids | {node.pk}

        input_payload = {
            "new_node_id": node.pk,
            "new_place_id": node.place.place_id,
            "candidate_node_ids": list(candidate_node_ids),
            "profile_snapshot": profile_text,
        }
        raw_response = ""
        parsed_output = None
        outcome = "success"

        try:
            parsed, raw_response = llm.send(prompt, EdgeBuildingOutput)
            parsed_output = parsed
        except ValueError as e:
            outcome = "validation_error"
            LlmInteractionLog.objects.create(
                user=user,
                workflow="edge_building",
                prompt_version=prompt_version,
                embedding_model=Retriever()._vector_class.__name__,
                language_model=llm.model_name,
                input_payload=input_payload,
                raw_llm_response=str(e),
                parsed_output=None,
                outcome=outcome,
            )
            raise

        edges_data = parsed["edges"]

        # Step 7 — security: verify all node IDs are from this user's graph
        returned_ids = {e["from_node_id"] for e in edges_data} | {
            e["to_node_id"] for e in edges_data
        }
        unauthorized = returned_ids - valid_node_ids
        if unauthorized:
            raise ValueError(
                f"LLM returned node IDs not belonging to this user: {unauthorized}"
            )

        # Step 8 — persist edges + transition node, atomically
        created_edge_ids = []
        with transaction.atomic():
            for edge_data in edges_data:
                edge, created = GraphEdge.objects.get_or_create(
                    from_node_id=edge_data["from_node_id"],
                    to_node_id=edge_data["to_node_id"],
                    defaults={
                        "user": user,
                        "weight": max(0.0, min(1.0, edge_data["weight"])),
                        "reason": edge_data["reason"][:255],
                        "reason_type": edge_data["reason_type"],
                    },
                )
                if created:
                    created_edge_ids.append(edge.pk)

            node.status = target_status
            node.save(update_fields=["status", "updated_at"])

        # Step 9 — log
        LlmInteractionLog.objects.create(
            user=user,
            workflow="edge_building",
            prompt_version=prompt_version,
            embedding_model=Retriever()._vector_class.__name__,
            language_model=llm.model_name,
            input_payload=input_payload,
            raw_llm_response=raw_response,
            parsed_output=parsed_output,
            outcome=outcome,
        )

        log.info(
            "add_to_graph: node %d → %s, %d edges created",
            node_id,
            target_status,
            len(created_edge_ids),
        )
        return created_edge_ids
