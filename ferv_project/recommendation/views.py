"""
views.py
--------
REST API endpoint for the recommendation system.

GET /api/recommendation/?q=<query>&top_k=<int>

Returns a ranked list of places most similar to the query.
"""

import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from places.models import Place
from recommendation.serializers import RecommendationResultSerializer
from recommendation.services import RecommendationService

log = logging.getLogger(__name__)


class RecommendationView(APIView):
    """
    Accepts a text query and returns the top-K most similar places.
    Uses the RecommendationService to embed the query and search pgvector.
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
            svc = RecommendationService()
            results = svc.recommend(query, top_k=top_k)

            # Fetch full Place objects and attach distance
            place_ids = [r['place_id'] for r in results]
            distance_map = {r['place_id']: r['distance'] for r in results}

            places = Place.objects.filter(
                place_id__in=place_ids
            ).prefetch_related('tags')

            # Attach distance to each place object
            for place in places:
                place.distance = distance_map[place.place_id]

            # Sort by distance
            places = sorted(places, key=lambda p: p.distance)

            serializer = RecommendationResultSerializer(places, many=True)
            return Response({
                "query": query,
                "top_k": top_k,
                "results": serializer.data
            })

        except Exception as e:
            log.error("Recommendation error: %s", e)
            return Response(
                {"error": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
