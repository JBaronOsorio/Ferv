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
from collections import Counter

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from places.models import Place
from rest_framework import status
from .serializers import GraphNodeSerializer, GraphEdgeSerializer
from .models import GraphNode, GraphEdge
from django.contrib import messages

log = logging.getLogger(__name__)


def index(request):
    return render(request, 'graph/index.html')


@login_required
def welcome(request):
    featured_places = Place.objects.prefetch_related('images', 'tags').order_by('-rating')[:8]
    return render(request, 'graph/welcome.html', {'featured_places': featured_places})


@login_required
def map_view(request):
    if not request.user.profile_completed:
        messages.error(request, 'Debes completar tu perfil antes de acceder al mapa.')
        return redirect('user:profile_setup')
    else:
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
        edges = GraphEdge.objects.filter(id__in=edge_ids).select_related('from_node', 'to_node')
        edges_data = [
            {
                'source_id': e.from_node.id,
                'target_id': e.to_node.id,
                'weight': e.weight,
                'reason': e.reason,
            }
            for e in edges
        ]
        return JsonResponse({'edges': edges_data}, status=200)
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
        # Sin query → solo devuelve el mapa guardado del usuario (in_graph + visited)
        nodes = GraphNode.objects.filter(
            user=request.user,
            status__in=['in_graph', 'visited'],
        ).select_related('place').prefetch_related('place__tags')

    # Los edges siempre son los del mapa personal (in_graph + visited)
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


@login_required
def discovery_list(request):
    """
    GET /graph/api/discovery-list/
    Devuelve los nodos con status='discovery' del usuario.
    """
    nodes = GraphNode.objects.filter(
        user=request.user, status='discovery'
    ).select_related('place').prefetch_related('place__tags')
    serialized = GraphNodeSerializer(nodes, many=True).data
    return JsonResponse({'nodes': list(serialized)}, status=200)


@login_required
@require_POST
def add_to_discovery(request):
    """
    POST /graph/api/add-to-discovery/
    Body JSON: { "node_id": <int> }

    Mueve un GraphNode (recommendation o in_graph) a status='discovery'.
    Si ya está en discovery → 409.
    Si estaba in_graph → borra sus edges del mapa antes de moverlo.
    """
    try:
        body = json.loads(request.body)
        node_id = body.get('node_id')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    if node_id is None:
        return JsonResponse({'error': 'node_id is required.'}, status=400)

    try:
        node = GraphNode.objects.get(id=node_id, user=request.user)
    except GraphNode.DoesNotExist:
        return JsonResponse({'error': 'Nodo no encontrado.'}, status=404)

    if node.status == 'discovery':
        return JsonResponse({'error': 'El lugar ya está en tu lista de descubrimiento.'}, status=409)

    if node.status == 'in_graph':
        GraphEdge.objects.filter(Q(from_node=node) | Q(to_node=node)).delete()

    node.status = 'discovery'
    node.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'status': 'ok'}, status=200)


@login_required
def user_stats(request):
    """
    GET /graph/api/stats/
    Devuelve estadísticas de actividad del usuario:
    conteos por status, top tags y top barrios de nodos in_graph/visited.
    """
    nodes_qs = GraphNode.objects.filter(user=request.user)

    in_graph_count  = nodes_qs.filter(status='in_graph').count()
    visited_count   = nodes_qs.filter(status='visited').count()
    discovery_count = nodes_qs.filter(status='discovery').count()

    map_nodes = (
        nodes_qs.filter(status__in=['in_graph', 'visited'])
        .select_related('place')
        .prefetch_related('place__tags')
    )

    tag_counter = Counter()
    for node in map_nodes:
        for tag in node.place.tags.all():
            tag_counter[tag.tag] += 1
    top_tags = [{"tag": t, "count": c} for t, c in tag_counter.most_common(6)]

    top_neigh_qs = (
        nodes_qs.filter(status__in=['in_graph', 'visited'])
        .values('place__neighborhood')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )
    top_neighborhoods = [
        {"neighborhood": d['place__neighborhood'], "count": d['count']}
        for d in top_neigh_qs
        if d['place__neighborhood']
    ]

    return JsonResponse({
        "counts": {
            "in_graph":  in_graph_count,
            "visited":   visited_count,
            "discovery": discovery_count,
        },
        "top_tags":          top_tags,
        "top_neighborhoods": top_neighborhoods,
        "updated_at":        timezone.now().isoformat(),
    }, status=200)


@login_required
@require_http_methods(["PATCH"])
def toggle_favorite(request, node_id):
    """
    PATCH /graph/api/toggle-favorite/<node_id>/
    Invierte is_favorite en el GraphNode indicado.
    Retorna { "is_favorite": bool }.
    """
    try:
        node = GraphNode.objects.get(id=node_id, user=request.user)
    except GraphNode.DoesNotExist:
        return JsonResponse({'error': 'Nodo no encontrado.'}, status=404)

    node.is_favorite = not node.is_favorite
    node.save(update_fields=['is_favorite'])
    return JsonResponse({'is_favorite': node.is_favorite}, status=200)


@login_required
@require_http_methods(["PATCH"])
def mark_visited(request, node_id):
    """
    PATCH /graph/api/mark-visited/<node_id>/
    Mueve un nodo de discovery a visited, corriendo Pipeline B para crear edges.
    Retorna el nodo actualizado y los edges creados con source_id/target_id/weight/reason.
    """
    try:
        node = GraphNode.objects.get(id=node_id, user=request.user)
    except GraphNode.DoesNotExist:
        return JsonResponse({'error': 'Nodo no encontrado.'}, status=404)

    if node.status != 'discovery':
        return JsonResponse({'error': 'El nodo no está en la lista de descubrimiento.'}, status=400)

    try:
        from recommendation.graph_builder import GraphBuilder
        created_edge_ids = GraphBuilder().add_to_graph(request.user, node_id, target_status='visited')

        node.refresh_from_db()
        serialized_node = GraphNodeSerializer(node).data

        edges = GraphEdge.objects.filter(id__in=created_edge_ids).select_related('from_node', 'to_node')
        edges_data = [
            {
                'source_id': e.from_node.id,
                'target_id': e.to_node.id,
                'weight': e.weight,
                'reason': e.reason,
            }
            for e in edges
        ]

        return JsonResponse({'status': 'ok', 'node': serialized_node, 'edges': edges_data}, status=200)
    except Exception as e:
        log.error("mark_visited error for node_id=%s: %s", node_id, e)
        return JsonResponse({'error': str(e)}, status=400)