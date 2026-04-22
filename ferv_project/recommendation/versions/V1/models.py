from django.db import models
from pgvector.django import VectorField
from places.models import Place


class PlaceEmbedding(models.Model):
    """
    Stores the vector embedding for a place.
    Generated from PlaceDocument.text using OpenAI text-embedding-3-small.
    One embedding per place.
    """
    place = models.OneToOneField(
        Place,
        related_name='embedding',
        on_delete=models.CASCADE
    )
    vector = VectorField(dimensions=1536)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Embedding for {self.place.name}"
