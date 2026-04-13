"""
views.py
--------
Graph API endpoints.

GET /graph/                    → renders the graph template
GET /api/graph/?q=<query>      → builds and returns graph JSON
"""

import logging
import json
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from recommendation.services import RecommendationService
from recommendation.graph_builder import GraphBuilder

log = logging.getLogger(__name__)

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from places.models import Place
from graph.models import UserNode
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required






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

@login_required
def welcome(request):
    featured_places = Place.objects.prefetch_related('images', 'tags').order_by('-rating')[:8]
    return render(request, 'graph/welcome.html', {
        'featured_places': featured_places,
    })



@login_required
def map_view(request):
    """Renders the interactive node map."""
    return render(request, 'graph/map.html')


@login_required
@require_POST
def add_node(request):
    """
    POST /graph/add-node/
    Body JSON: { "place_id": "<google_place_id>" }

    Adds a place to the authenticated user's personal map.
    Returns 200 if added, 409 if already exists, 404 if place unknown.
    """
    try:
        body = json.loads(request.body)
        place_id = body.get('place_id', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'JSON inválido.'}, status=400)

    if not place_id:
        return JsonResponse({'error': 'place_id es requerido.'}, status=400)

    try:
        place = Place.objects.get(place_id=place_id)
    except Place.DoesNotExist:
        return JsonResponse({'error': 'Lugar no encontrado.'}, status=404)

    node, created = UserNode.objects.get_or_create(user=request.user, place=place)

    if created:
        return JsonResponse({'message': f'"{place.name}" agregado a tu mapa.'}, status=200)
    else:
        return JsonResponse({'error': f'"{place.name}" ya está en tu mapa.'}, status=409)