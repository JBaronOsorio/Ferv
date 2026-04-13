"""
services.py
-----------
EmbeddingService  — converts text to a vector using OpenAI.
RecommendationService — finds similar places given a query string.
"""

import logging
import os

from openai import OpenAI
from pgvector.django import L2Distance
from places.models import Place
from recommendation.models import PlaceEmbedding

log = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingService:
    """
    Thin wrapper around the OpenAI embeddings API.
    Converts any text string into a vector of 1536 floats.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in your .env file.")
        self.client = OpenAI(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        """
        Takes a text string and returns a vector [1536 floats].
        """
        text = text.replace("\n", " ").strip()
        response = self.client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL,
        )
        return response.data[0].embedding


class RecommendationService:
    """
    Finds the most similar places to a given query string.
    Uses cosine-like distance (L2) over stored pgvector embeddings.
    """

    def __init__(self):
        self.embedder = EmbeddingService()

    def recommend(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Takes a natural language query and returns the top_k
        most similar places as a list of dicts.
        """
        # 1. Embed the query
        query_vector = self.embedder.embed(query)

        # 2. Find the closest place embeddings in the DB
        results = (
            PlaceEmbedding.objects
            .annotate(distance=L2Distance("vector", query_vector))
            .order_by("distance")
            .select_related("place")[:top_k]
        )

        # 3. Format and return
        recommendations = []
        for result in results:
            recommendations.append({
                "place_id": result.place.place_id,
                "name": result.place.name,
                "neighborhood": result.place.neighborhood,
                "rating": result.place.rating,
                "distance": round(result.distance, 4),
            })

        return recommendations