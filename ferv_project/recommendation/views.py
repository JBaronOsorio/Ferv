"""
views.py
--------
POST /api/recommendation/recommend/  → Pipeline A: one-shot recommendation
"""

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

log = logging.getLogger(__name__)


def _serialize_node(node) -> dict:
    place = node.place
    return {
        "node_id": node.id,
        "status": node.status,
        "rationale": node.rationale,
        "place": {
            "place_id": place.place_id,
            "name": place.name,
            "neighborhood": place.neighborhood,
            "rating": place.rating,
            "price_level": place.price_level,
            "editorial_summary": place.editorial_summary,
        },
    }


@login_required
@require_POST
def recommend(request):
    """
    POST /api/recommendation/recommend/
    Body JSON: { "prompt": "<free text>" }

    Runs Pipeline A for the authenticated user and returns N recommendation nodes.
    """
    try:
        body = json.loads(request.body)
        prompt_text = body.get("prompt", "").strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    if not prompt_text:
        return JsonResponse({"error": "prompt is required."}, status=400)

    try:
        from recommendation.recommendation_service import RecommendationService
        nodes = RecommendationService().recommend_one_shot(request.user, prompt_text)
        return JsonResponse({"nodes": [_serialize_node(n) for n in nodes]})
    except ValueError as e:
        log.error("recommend view error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)
    except Exception as e:
        log.error("recommend view unexpected error: %s", e)
        return JsonResponse({"error": "Internal server error."}, status=500)
