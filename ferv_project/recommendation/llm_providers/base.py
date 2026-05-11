from abc import ABC, abstractmethod


class LlmProvider(ABC):
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Return the raw text completion for `prompt`. Raise ValueError if empty."""
