"""
views.py
--------
Graph views and API endpoints.

GET  /graph/                    → graph template
GET  /graph/welcome/            → featured places (login required)
GET  /graph/map/                → interactive map (login required)
POST /graph/add-node/           → Pipeline B: promote recommendation to in_graph
GET  /api/graph/?q=<query>      → legacy: one-shot recommend + build graph JSON
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST, require_http_methods
from places.models import Place
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import GraphNodeSerializer, GraphEdgeSerializer
from .models import GraphNode, GraphEdge

log = logging.getLogger(__name__)


def index(request):
    return render(request, 'graph/index.html')


@login_required
def welcome(request):
    featured_places = Place.objects.prefetch_related('images', 'tags').order_by('-rating')[:8]
    return render(request, 'graph/welcome.html', {'featured_places': featured_places})


@login_required
def map_view(request):
    return render(request, 'graph/map.html')


@login_required
@require_POST
def add_node(request):
    """
    POST /graph/add-node/
    Body JSON: { "node_id": <int> }

    Promotes a recommendation-status GraphNode to in_graph via Pipeline B.
    Returns edge IDs created and confirmation.
    """
    try:
        body = json.loads(request.body)
        node_id = body.get('node_id')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    if node_id is None:
        return JsonResponse({'error': 'node_id is required.'}, status=400)

    try:
        from recommendation.graph_builder import GraphBuilder
        edge_ids = GraphBuilder().add_to_graph(request.user, node_id)
        return JsonResponse({'edge_ids': edge_ids}, status=200)
    except Exception as e:
        log.error("add_node error for node_id=%s: %s", node_id, e)
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def one_shot_recommendation(request, query):
    """
    GET /graph/api/one_shot_recommendation/<query>
    Legacy endpoint for quick testing of the recommendation service without the full graph.
    Returns top 5 recommendations for the query.
    """
    
    try:
        from recommendation.recommendation_service import RecommendationService
        svc = RecommendationService()
        results = svc.recommend_one_shot(user=request.user, prompt_text=query)
        serialized_nodes = GraphNodeSerializer(results, many=True).data
        return JsonResponse({'query': query, 'results': serialized_nodes}, status=200)
    
    except Exception as e:
        log.error("one_shot_recommendation error for query=%s: %s", query, e)
        return JsonResponse({'error': 'Internal server error.'}, status=500)

@login_required
def fetch_graph(request):
    """
    GET /graph/api/fetch_graph/
    Returns the full graph (nodes and edges) for the logged-in user.
    """

    query = request.GET.get('q', None)

    if query:
        # Con query → llama al servicio de recomendación para sugerir lugares nuevos
        from recommendation.recommendation_service import RecommendationService
        svc = RecommendationService()
        nodes = svc.recommend_one_shot(user=request.user, prompt_text=query)
    else:
        # Sin query → solo devuelve el mapa guardado del usuario
        nodes = GraphNode.objects.filter(
            user=request.user
        ).select_related('place').prefetch_related('place__tags')

    # Los edges siempre son los del mapa personal (in_graph)
    edges = GraphEdge.objects.filter(user=request.user).select_related('from_node', 'to_node')


    serialized_nodes = GraphNodeSerializer(nodes, many=True).data
    serialized_edges = GraphEdgeSerializer(edges, many=True).data

    print(f"fetch_graph: returning {(serialized_nodes)} nodes and {(serialized_edges)} edges for user {request.user.username}")

    return JsonResponse({'nodes': serialized_nodes, 'edges': serialized_edges}, status=200)


@login_required
@require_http_methods(["DELETE"])
def delete_node(request, node_id):
    """
    DELETE /graph/api/delete_node/<node_id>
    Elimina un GraphNode del mapa del usuario y sus edges asociados.
    Los GraphEdge se eliminan automáticamente por CASCADE.

    Retorna: { "status": "ok" }
    Errores: 404 si no existe, 403 si no pertenece al usuario
    """
    try:
        node = GraphNode.objects.get(id=node_id)
    except GraphNode.DoesNotExist:
        return JsonResponse({'error': 'Nodo no encontrado.'}, status=404)

    if node.user != request.user:
        return JsonResponse({'error': 'No tienes permiso para eliminar este nodo.'}, status=403)

    node.delete()  # CASCADE elimina los GraphEdge automáticamente
    return JsonResponse({'status': 'ok'}, status=200)