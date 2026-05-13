"""
embedding_service.py
--------------------
EmbeddingService — converts text to a vector via a configurable provider, and
persists vectors through the GFK PlaceEmbedding structure.
"""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType

from places.models import Place
from recommendation.embedding_providers import EmbeddingProvider, build_embedding_provider
from recommendation.models import PlaceEmbedding


class EmbeddingService:
    """
    Provider-agnostic embedding service. Depends only on `EmbeddingProvider`.
    Reads provider config from settings.RECOMMENDATION_CONFIGS[config_key] when
    no explicit provider is injected.
    """

    def __init__(
        self,
        config_key: str = "default",
        provider: EmbeddingProvider | None = None,
    ):
        if provider is None:
            cfg = settings.RECOMMENDATION_CONFIGS[config_key]["embedding_model"]
            provider = build_embedding_provider(cfg)
        self._provider = provider

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def vector_class(self) -> type:
        return self._provider.vector_class

    def embed(self, text: str) -> list[float]:
        return self._provider.embed(text)

    def embed_and_persist(self, place: Place, text: str) -> PlaceEmbedding:
        """
        Embed text and persist via the GFK model structure.
        Used for ad-hoc online embedding; the pipeline uses the cache instead.
        """
        vector = self.embed(text)
        VectorClass = self._provider.vector_class
        ct = ContentType.objects.get_for_model(VectorClass)

        try:
            pe = PlaceEmbedding.objects.get(place=place)
            VectorClass.objects.filter(id=pe.object_id).update(
                vector=vector, model_name=self._provider.model_name
            )
        except PlaceEmbedding.DoesNotExist:
            vector_obj = VectorClass.objects.create(
                vector=vector, model_name=self._provider.model_name
            )
            pe = PlaceEmbedding.objects.create(
                place=place, content_type=ct, object_id=vector_obj.pk
            )

        return pe
