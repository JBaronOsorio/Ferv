"""
retriever.py
------------
Retriever — read-only pgvector queries over the PlaceEmbedding / GFK structure.
Resolves which `EmbeddingVector` subclass to query via the embedding-providers
registry; does not need an API key or client.
"""

import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from pgvector.django import L2Distance

from graph.models import GraphNode
from recommendation.embedding_providers import vector_class_for
from recommendation.models import PlaceEmbedding

log = logging.getLogger(__name__)


class Retriever:
    """
    Always queries the vector class that matches the configured embedding model.
    """

    def __init__(self, config_key: str = "default"):
        cfg = settings.RECOMMENDATION_CONFIGS[config_key]["embedding_model"]
        self._vector_class = vector_class_for(cfg)

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

        fetch_n = top_k * 3
        top_vectors = list(
            VectorClass.objects.annotate(distance=L2Distance("vector", query_vector))
            .order_by("distance")
            .values("id", "distance")[:fetch_n]
        )

        if not top_vectors:
            return []

        vector_id_to_distance = {v["id"]: v["distance"] for v in top_vectors}

        place_embeddings = list(
            PlaceEmbedding.objects.filter(
                content_type=ct, object_id__in=list(vector_id_to_distance.keys())
            ).select_related("place")
            .prefetch_related("place__tags", "place__document")
        )

        excluded_place_ids: set = set()
        if exclude_user is not None:
            excluded_place_ids = set(
                GraphNode.objects.filter(user=exclude_user).values_list(
                    "place_id", flat=True
                )
            )

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

        in_graph_nodes = list(
            GraphNode.objects.filter(user=user, status="in_graph").select_related(
                "place"
            )
        )
        if not in_graph_nodes:
            return []

        in_graph_place_ids = [n.place.pk for n in in_graph_nodes]
        place_embs = PlaceEmbedding.objects.filter(
            place_id__in=in_graph_place_ids, content_type=ct
        )
        place_id_to_vector_id = {pe.place.pk: pe.object_id for pe in place_embs}

        vector_ids = list(place_id_to_vector_id.values())
        distance_map = dict(
            VectorClass.objects.filter(id__in=vector_ids)
            .annotate(distance=L2Distance("vector", new_vector))
            .values_list("id", "distance")
        )

        def node_distance(node):
            vid = place_id_to_vector_id.get(node.place_id)
            return distance_map.get(vid, float("inf")) if vid else float("inf")

        sorted_nodes = sorted(in_graph_nodes, key=node_distance)
        return sorted_nodes[:top_n]
