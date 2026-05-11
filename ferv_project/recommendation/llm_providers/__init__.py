"""
llm_providers
-------------
Provider abstraction for the recommendation LLM layer.

`LlmProvider` is the contract `LlmClient` depends on. Concrete providers live
in sibling modules and register themselves in `PROVIDER_REGISTRY`. Adding a
new model means writing a `LlmProvider` subclass and registering it here — no
edits to `LlmClient` required.
"""

import os

from .base import LlmProvider
from .gemini import GeminiProvider
from .openai import OpenAIProvider

PROVIDER_REGISTRY: dict[str, type[LlmProvider]] = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
}


def build_provider(cfg: dict) -> LlmProvider:
    provider_cls = PROVIDER_REGISTRY[cfg["provider"]]
    api_key = os.getenv(cfg["api_key_env_var"])
    if not api_key:
        raise ValueError(f"{cfg['api_key_env_var']} is not set.")
    return provider_cls(model_name=cfg["name"], api_key=api_key)


__all__ = ["LlmProvider", "PROVIDER_REGISTRY", "build_provider"]
