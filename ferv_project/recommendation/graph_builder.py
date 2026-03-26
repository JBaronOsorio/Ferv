"""
graph_builder.py
----------------
GraphBuilder service — takes a list of recommended places and a user profile,
calls the LLM once to generate all edges, and saves the graph to the DB.

Flow:
    1. Create GraphNodes for each recommended place
    2. Build a single prompt with all places + user profile
    3. Call OpenAI to generate edges as JSON
    4. Save GraphEdges to the DB
"""

import json
import logging
import os

from openai import OpenAI
from graph.models import GraphNode, GraphEdge
from places.models import Place

log = logging.getLogger(__name__)

# Simulated user profile — replace with request.user.profile when auth is merged
SIMULATED_USER = {
    "id": 1,
    "preferred_atmospheres": ["quiet", "intimate"],
    "preferred_activities": ["live_music", "gastronomy"],
    "budget_range": "medium"
}


class GraphBuilder:
    """
    Builds a personalized recommendation graph for a user.
    Creates GraphNodes for each place and GraphEdges between them
    using the LLM to generate meaningful connection reasons.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in your .env file.")
        self.client = OpenAI(api_key=api_key)

    def build(self, place_ids: list[str], user_profile: dict = None) -> dict:
        """
        Main entry point. Takes a list of place_ids from the recommendation
        service and builds a graph for the simulated user.

        Returns a dict with nodes and edges ready for the API response.
        """
        if user_profile is None:
            user_profile = SIMULATED_USER

        # ── Step 1: Get Place objects ─────────────────────────────────────
        places = list(
            Place.objects.filter(place_id__in=place_ids)
            .prefetch_related('tags', 'document')
        )

        if not places:
            log.warning("No places found for place_ids: %s", place_ids)
            return {"nodes": [], "edges": []}

        # ── Step 2: Create GraphNodes ─────────────────────────────────────
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_profile["id"])

        nodes = []
        place_node_map = {}  # place_id → GraphNode

        for place in places:
            node, _ = GraphNode.objects.get_or_create(
                user=user,
                place=place,
                defaults={"is_favorite": False}
            )
            nodes.append(node)
            place_node_map[place.place_id] = node

        log.info("Created/found %d graph nodes.", len(nodes))

        # ── Step 3: Call LLM to generate edges ───────────────────────────
        edges_data = self._generate_edges(places, user_profile)

        # ── Step 4: Save GraphEdges ───────────────────────────────────────
        edges = []
        for edge_data in edges_data:
            try:
                from_node = place_node_map.get(edge_data["from_place_id"])
                to_node = place_node_map.get(edge_data["to_place_id"])

                if not from_node or not to_node:
                    log.warning("Skipping edge — node not found: %s", edge_data)
                    continue

                edge, _ = GraphEdge.objects.get_or_create(
                    from_node=from_node,
                    to_node=to_node,
                    defaults={
                        "user": user,
                        "weight": edge_data.get("weight", 1.0),
                        "reason": edge_data.get("reason", ""),
                        "reason_type": edge_data.get("reason_type", "vibe_match"),
                    }
                )
                edges.append(edge)

            except Exception as e:
                log.error("Failed to save edge: %s — %s", edge_data, e)

        log.info("Created/found %d graph edges.", len(edges))

        # ── Step 5: Return graph structure ────────────────────────────────
        return self._serialize(nodes, edges)

    def _generate_edges(self, places: list, user_profile: dict) -> list[dict]:
        """
        Sends all places and user profile to the LLM in a single call.
        Returns a list of edge dicts with from_place_id, to_place_id,
        weight, reason, and reason_type.
        """
        # Build place summaries for the prompt
        place_summaries = []
        for place in places:
            tags = [t.tag for t in place.tags.all()]
            summary = (
                f"- place_id: {place.place_id}\n"
                f"  name: {place.name}\n"
                f"  neighborhood: {place.neighborhood}\n"
                f"  rating: {place.rating}\n"
                f"  tags: {', '.join(tags)}\n"
                f"  description: {place.editorial_summary or 'No description'}"
            )
            place_summaries.append(summary)

        prompt = f"""
You are a recommendation engine for a place discovery app in Medellín, Colombia.

Given these recommended places:
{chr(10).join(place_summaries)}

And this user profile:
- Preferred atmospheres: {user_profile.get('preferred_atmospheres', [])}
- Preferred activities: {user_profile.get('preferred_activities', [])}
- Budget range: {user_profile.get('budget_range', 'unknown')}

Generate meaningful connections between these places.
For each pair of related places, create an edge explaining why they are connected
from the perspective of this user's preferences.

Return ONLY a valid JSON array with this exact structure, no extra text:
[
  {{
    "from_place_id": "place_id_here",
    "to_place_id": "place_id_here",
    "weight": 0.85,
    "reason": "Short explanation of why these places are connected for this user",
    "reason_type": "vibe_match"
  }}
]

Rules:
- weight must be between 0.0 and 1.0 (higher = stronger connection)
- reason_type must be one of: vibe_match, category_overlap, atmosphere_match, activity_match
- Only create edges between genuinely related places
- Keep reasons concise (max 5 words, label style)
- Do not repeat the same pair twice
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            raw = raw.replace("```json", "").replace("```", "").strip()
            edges = json.loads(raw)
            log.info("LLM generated %d edges.", len(edges))
            return edges

        except Exception as e:
            log.error("LLM edge generation failed: %s", e)
            return []

    def _serialize(self, nodes: list, edges: list) -> dict:
        """
        Formats nodes and edges into a clean dict for the API response.
        """
        serialized_nodes = [
            {
                "id": node.id,
                "place_id": node.place.place_id,
                "name": node.place.name,
                "neighborhood": node.place.neighborhood,
                "rating": node.place.rating,
                "is_favorite": node.is_favorite,
            }
            for node in nodes
        ]

        serialized_edges = [
            {
                "from_node": edge.from_node.id,
                "to_node": edge.to_node.id,
                "weight": edge.weight,
                "reason": edge.reason,
                "reason_type": edge.reason_type,
            }
            for edge in edges
        ]

        return {
            "nodes": serialized_nodes,
            "edges": serialized_edges,
        }