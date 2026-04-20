"""
services.py
-----------
EmbeddingService  — converts text to a vector; configurable provider via settings.
Retriever         — read-only pgvector queries over PlaceEmbedding/GFK structure.
"""

import logging
import os

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from pgvector.django import L2Distance

from graph.models import GraphNode
from places.models import Place
from recommendation.models import (
    GeminiEmbeddingVector,
    GeminiEmbeddingVectorLarge,
    OpenAIEmbeddingVector,
    PlaceEmbedding,
)

log = logging.getLogger(__name__)


def _vector_class_for(model_key: str):
    """Return the EmbeddingVector subclass that matches the given model name."""
    model_key = model_key.lower()
    VectorClass = None
    
    if "gemini" in model_key and "large" in model_key:
        VectorClass = GeminiEmbeddingVectorLarge
    elif "gemini" in model_key:
        VectorClass = GeminiEmbeddingVector
    elif "openai" in model_key:
        VectorClass = OpenAIEmbeddingVector
    else:
        raise ValueError(f"Unsupported embedding model_key: {model_key}")
    
    return VectorClass


class EmbeddingService:
    """
    Provider-agnostic embedding service.
    Reads provider config from settings.RECOMMENDATION_CONFIGS[config_key].
    """

    def __init__(self, config_key: str = "default"):
        cfg = settings.RECOMMENDATION_CONFIGS[config_key]["embedding_model"]
        self.model_key: str = cfg["model_key"]
        self.model_name: str = cfg["name"]
        self.dimensions: int = cfg["dimensions"]
        api_key = os.getenv(cfg["api_key_env_var"])

        if "gemini" in self.model_key.lower():
            
            import google.generativeai as genai
            if not api_key:
                raise ValueError(f"{cfg['api_key_env_var']} is not set.")
            
            genai.configure(api_key=api_key) # type: ignore
            self._genai = genai
            self._provider = "gemini"
        elif "openai" in self.model_key.lower():
            
            from openai import OpenAI
            if not api_key:
                raise ValueError(f"{cfg['api_key_env_var']} is not set.")
            
            self._client = OpenAI(api_key=api_key)
            self._provider = "openai"
        else:
            raise ValueError(f"Unsupported embedding provider in model_key: {self.model_key}")

    def embed(self, text: str) -> list[float]:
        """Convert text to a vector using the configured provider."""
        
        text = text.replace("\n", " ").strip()
        
        if self._provider == "gemini":
            response = self._genai.embed_content(model=self.model_name, content=text) # type: ignore
            return response["embedding"]
        else:
            response = self._client.embeddings.create(input=text, model=self.model_name)
            return response.data[0].embedding

    def embed_and_persist(self, place: Place, text: str) -> PlaceEmbedding:
        """
        Embed text and persist via the GFK model structure.
        Used for ad-hoc online embedding; the pipeline uses the cache instead.
        """
        vector = self.embed(text)
        VectorClass = _vector_class_for(self.model_key)
        ct = ContentType.objects.get_for_model(VectorClass)

        try:
            pe = PlaceEmbedding.objects.get(place=place)
            # Update the existing vector object in place
            VectorClass.objects.filter(id=pe.object_id).update(
                vector=vector, model_name=self.model_name
            )
        except PlaceEmbedding.DoesNotExist:
            vector_obj = VectorClass.objects.create(
                vector=vector, model_name=self.model_name
            )
            pe = PlaceEmbedding.objects.create(
                place=place, content_type=ct, object_id=vector_obj.pk
            )

        return pe


class Retriever:
    """
    Read-only pgvector queries over the PlaceEmbedding / GFK structure.
    Always queries the vector class that matches the configured embedding model.
    """

    def __init__(self, config_key: str = "default"):
        cfg = settings.RECOMMENDATION_CONFIGS[config_key]["embedding_model"]
        self.model_key: str = cfg["model_key"]
        self._vector_class = _vector_class_for(cfg["model_key"])

    def get_candidates(
        self, query_vector: list[float], top_k: int = 20, exclude_user=None
    ) -> list[dict]:
        """
        Return top_k places closest to query_vector, excluding any place already
        linked to exclude_user in any GraphNode status.

        Returns list[{"place": Place, "distance": float}] ordered by ascending distance.
        """
        VectorClass = self._vector_class
        ct = ContentType.objects.get_for_model(VectorClass)

        # Step 1: get top (top_k * 3) vector IDs with distances for filtering headroom
        fetch_n = top_k * 3
        top_vectors = list(
            VectorClass.objects.annotate(distance=L2Distance("vector", query_vector))
            .order_by("distance")
            .values("id", "distance")[:fetch_n]
        )

        if not top_vectors:
            return []

        vector_id_to_distance = {v["id"]: v["distance"] for v in top_vectors}

        # Step 2: resolve vector IDs → PlaceEmbedding → Place
        place_embeddings = list(
            PlaceEmbedding.objects.filter(
                content_type=ct, object_id__in=list(vector_id_to_distance.keys())
            ).select_related("place")
            .prefetch_related("place__tags", "place__document")
        )

        # Step 3: build exclusion set from user's existing graph nodes
        excluded_place_ids: set = set()
        if exclude_user is not None:
            excluded_place_ids = set(
                GraphNode.objects.filter(user=exclude_user).values_list(
                    "place_id", flat=True
                )
            )

        # Step 4: sort by distance, filter, cap at top_k
        # pe.place is already loaded via select_related; use pe.place.pk
        # to avoid Pyright's blind spot on Django's auto-created _id attributes.
        place_embeddings.sort(
            key=lambda pe: vector_id_to_distance.get(pe.object_id, float("inf"))
        )
        candidates = []
        for pe in place_embeddings:
            if pe.place.pk in excluded_place_ids:
                continue
            candidates.append(
                {
                    "place": pe.place,
                    "distance": vector_id_to_distance[pe.object_id],
                }
            )
            if len(candidates) >= top_k:
                break

        return candidates

    def get_similar_in_graph_nodes(
        self, new_node: GraphNode, user, top_n: int = 8
    ) -> list:
        """
        Return top_n in_graph GraphNodes for user, sorted by embedding similarity
        to new_node's place. Used in Pipeline B (add-to-graph).
        """
        VectorClass = self._vector_class
        ct = ContentType.objects.get_for_model(VectorClass)

        # Get the new node's place vector
        try:
            new_pe = PlaceEmbedding.objects.get(place=new_node.place, content_type=ct)
            new_vector_obj = VectorClass.objects.get(id=new_pe.object_id)
            new_vector = new_vector_obj.vector
        except (PlaceEmbedding.DoesNotExist, VectorClass.DoesNotExist):
            log.warning(
                "No embedding found for new node place %s — returning empty candidates.",
                new_node.place.place_id,
            )
            return []

        # Get all in_graph nodes for the user
        in_graph_nodes = list(
            GraphNode.objects.filter(user=user, status="in_graph").select_related(
                "place"
            )
        )
        if not in_graph_nodes:
            return []

        # Resolve their embeddings
        in_graph_place_ids = [n.place.pk for n in in_graph_nodes]
        place_embs = PlaceEmbedding.objects.filter(
            place_id__in=in_graph_place_ids, content_type=ct
        )
        place_id_to_vector_id = {pe.place.pk: pe.object_id for pe in place_embs}

        # Get distances for those vector objects
        vector_ids = list(place_id_to_vector_id.values())
        distance_map = dict(
            VectorClass.objects.filter(id__in=vector_ids)
            .annotate(distance=L2Distance("vector", new_vector))
            .values_list("id", "distance")
        )

        # Sort nodes by distance, skip nodes without embeddings
        def node_distance(node):
            vid = place_id_to_vector_id.get(node.place_id)
            return distance_map.get(vid, float("inf")) if vid else float("inf")

        sorted_nodes = sorted(in_graph_nodes, key=node_distance)
        return sorted_nodes[:top_n]
