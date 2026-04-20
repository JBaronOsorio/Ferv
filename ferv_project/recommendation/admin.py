from django.contrib import admin
from .models import PlaceEmbedding, GeminiEmbeddingVector, OpenAIEmbeddingVector

# Register your models here.
admin.site.register(PlaceEmbedding)
admin.site.register(GeminiEmbeddingVector)
admin.site.register(OpenAIEmbeddingVector)