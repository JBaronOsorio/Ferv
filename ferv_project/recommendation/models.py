from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from pgvector.django import VectorField

from places.models import Place

class EmbeddingVector(models.Model):
    """Base — holds metadata only, no vector field."""
    model_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_vector(self):
        raise NotImplementedError

class GeminiEmbeddingVector(EmbeddingVector):
    vector = VectorField(dimensions=768)

    def get_vector(self):
        return self.vector

class GeminiEmbeddingVectorLarge(EmbeddingVector):
    vector = VectorField(dimensions=3072)

    def get_vector(self):
        return self.vector

class OpenAIEmbeddingVector(EmbeddingVector):
    vector = VectorField(dimensions=1536)

    def get_vector(self):
        return self.vector

class PlaceEmbedding(models.Model):
    place = models.OneToOneField(Place, related_name='embedding', on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    embedding_vector = GenericForeignKey('content_type', 'object_id')


class LlmInteractionLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    workflow = models.CharField(max_length=60)        # 'recommendation' | 'edge_building'
    prompt_version = models.CharField(max_length=60)  # e.g. 'recommendation_v1'
    embedding_model = models.CharField(max_length=100)
    language_model = models.CharField(max_length=100)
    input_payload = models.JSONField()
    raw_llm_response = models.TextField()
    parsed_output = models.JSONField(null=True)
    outcome = models.CharField(max_length=60)         # 'success' | 'validation_error'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        get_latest_by = 'created_at'