from typing import Any, Protocol, cast

from .base import LlmProvider


class _GenAiResponse(Protocol):
    text: str | None


class _GenAiModels(Protocol):
    def generate_content(
        self,
        *,
        model: str,
        contents: Any,
        config: Any | None = None,
    ) -> _GenAiResponse: ...


class GeminiProvider(LlmProvider):
    def __init__(self, model_name: str, api_key: str):
        from google import genai

        super().__init__(model_name, api_key)
        self._client = genai.Client(api_key=api_key)
        self._models = cast(_GenAiModels, self._client.models)

    def generate(self, prompt: str) -> str:
        response = self._models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        if response.text is None:
            raise ValueError("Gemini response text is empty.")
        return response.text
