from .base import LlmProvider


class OpenAIProvider(LlmProvider):
    def __init__(self, model_name: str, api_key: str):
        from openai import OpenAI

        super().__init__(model_name, api_key)
        self._client = OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        text = response.choices[0].message.content
        if text is None:
            raise ValueError("OpenAI response text is empty.")
        return text
