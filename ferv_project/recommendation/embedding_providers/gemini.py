from .base import EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str, api_key: str, vector_class: type):
        from google import genai

        super().__init__(model_name, api_key, vector_class)
        self._client = genai.Client(api_key=api_key)

    def embed(self, text: str) -> list[float]:
        text = text.replace("\n", " ").strip()
        response = self._client.models.embed_content(
            model=self.model_name, contents=text
        )
        values = response.embeddings[0].values  # type: ignore[index]
        if values is None:
            raise ValueError("Gemini returned an empty embedding.")
        return values
