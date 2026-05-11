from .base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str, api_key: str, vector_class: type):
        from openai import OpenAI

        super().__init__(model_name, api_key, vector_class)
        self._client = OpenAI(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        text = text.replace("\n", " ").strip()
        response = self._client.embeddings.create(
            input=text, model=self.model_name
        )
        return response.data[0].embedding
