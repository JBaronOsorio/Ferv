"""
embedding_providers
-------------------
Provider abstraction for the recommendation embedding layer.

Each registry entry binds a provider class to the `EmbeddingVector` subclass
its output is persisted into. `EmbeddingService` instantiates a full provider;
`Retriever` only resolves the vector class via `vector_class_for(cfg)` since
it does not need an API client.
"""

import os

from recommendation.models import (
    GeminiEmbeddingVector,
    GeminiEmbeddingVectorLarge,
    OpenAIEmbeddingVector,
)

from .base import EmbeddingProvider
from .gemini import GeminiEmbeddingProvider
from .openai import OpenAIEmbeddingProvider

PROVIDER_REGISTRY: dict[str, tuple[type[EmbeddingProvider], type]] = {
    "gemini-small": (GeminiEmbeddingProvider, GeminiEmbeddingVector),
    "gemini-large": (GeminiEmbeddingProvider, GeminiEmbeddingVectorLarge),
    "openai":       (OpenAIEmbeddingProvider, OpenAIEmbeddingVector),
}


def build_embedding_provider(cfg: dict) -> EmbeddingProvider:
    provider_cls, vector_class = PROVIDER_REGISTRY[cfg["provider"]]
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise ValueError(f"{cfg['api_key_env_var']} is not set.")
    return provider_cls(
        model_name=cfg["name"], api_key=api_key, vector_class=vector_class
    )


def vector_class_for(cfg: dict) -> type:
    """Resolve the EmbeddingVector subclass without instantiating an API client."""
    return PROVIDER_REGISTRY[cfg["provider"]][1]


__all__ = [
    "EmbeddingProvider",
    "PROVIDER_REGISTRY",
    "build_embedding_provider",
    "vector_class_for",
]
