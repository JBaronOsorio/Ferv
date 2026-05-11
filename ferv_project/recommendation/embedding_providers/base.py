from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """
    Contract for an embedding backend. Each provider knows how to talk to its
    API *and* which `EmbeddingVector` subclass its output should be persisted as.
    """

    def __init__(self, model_name: str, api_key: str, vector_class: type):
        self.model_name = model_name
        self.vector_class = vector_class

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Convert text to a vector. Raise ValueError on empty/missing output."""
