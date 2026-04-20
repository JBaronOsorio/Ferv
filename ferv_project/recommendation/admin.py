from django.contrib import admin
from .models import PlaceEmbedding, GeminiEmbeddingVector, GeminiEmbeddingVectorLarge, OpenAIEmbeddingVector, LlmInteractionLog

# Register your models here.
admin.site.register(PlaceEmbedding)
admin.site.register(GeminiEmbeddingVector)
admin.site.register(OpenAIEmbeddingVector)
admin.site.register(GeminiEmbeddingVectorLarge)
admin.site.register(LlmInteractionLog)