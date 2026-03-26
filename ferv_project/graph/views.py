"""
views.py
--------
Graph API endpoints.

GET /graph/                    → renders the graph template
GET /api/graph/?q=<query>      → builds and returns graph JSON
"""

import logging
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from recommendation.services import RecommendationService
from recommendation.graph_builder import GraphBuilder

log = logging.getLogger(__name__)


def index(request):
    return render(request, 'graph/index.html')


class GraphAPIView(APIView):
    """
    Accepts a text query, runs the recommendation service,
    builds the graph with LLM-generated edges, and returns
    nodes + edges as JSON for the frontend visualization.
    """

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        top_k = int(request.query_params.get('top_k', 5))

        if not query:
            return Response(
                {"error": "Query parameter 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Step 1 — Get recommended places
            svc = RecommendationService()
            results = svc.recommend(query, top_k=top_k)
            place_ids = [r['place_id'] for r in results]

            # Step 2 — Build graph with LLM edges
            builder = GraphBuilder()
            graph = builder.build(place_ids)

            return Response({
                "query": query,
                "top_k": top_k,
                "graph": graph,
            })

        except Exception as e:
            log.error("Graph build error: %s", e)
            return Response(
                {"error": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )