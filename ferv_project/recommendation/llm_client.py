"""
llm_client.py
-------------
LlmClient  — sends prompts to the configured LLM, parses JSON responses,
             and validates them against a pydantic schema.

Pydantic schemas for both pipelines live here so callers can import them
alongside LlmClient without a separate schemas module.
"""

import json
import logging
import os
from typing import Any, Protocol, cast

from django.conf import settings
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

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


# ── Response schemas ──────────────────────────────────────────────────────────

class RecommendationItem(BaseModel):
    place_id: str
    rationale: str


class RecommendationOutput(BaseModel):
    recommendations: list[RecommendationItem]


class EdgeItem(BaseModel):
    from_node_id: int
    to_node_id: int
    weight: float
    reason: str
    reason_type: str  # food|ambiance|activity|neighborhood|social|other


class EdgeBuildingOutput(BaseModel):
    edges: list[EdgeItem]


# ── LlmClient ─────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove markdown code fences that LLMs sometimes wrap around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop opening fence line and closing fence line
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


class LlmClient:
    """
    Provider-agnostic LLM client.
    Reads provider config from settings.RECOMMENDATION_CONFIGS[config_key].
    Raises ValueError on parse or validation failure — no retries, no fallbacks.
    """

    def __init__(self, config_key: str = "default"):
        cfg = settings.RECOMMENDATION_CONFIGS[config_key]["language_model"]
        self.model_name: str = cfg["name"]
        api_key = os.getenv(cfg["api_key_env_var"])
        self._genai_models: _GenAiModels | None = None
        self._openai_client = None

        if "gemini" in self.model_name.lower():
            from google import genai
            if not api_key:
                raise ValueError(f"{cfg['api_key_env_var']} is not set.")
            genai_client = genai.Client(api_key=api_key)
            self._genai_models = cast(_GenAiModels, genai_client.models)
            self._provider = "gemini"
        else:
            from openai import OpenAI
            if not api_key:
                raise ValueError(f"{cfg['api_key_env_var']} is not set.")
            self._openai_client = OpenAI(api_key=api_key)
            self._provider = "openai"

    def send(self, prompt: str, schema: type[BaseModel]) -> tuple[dict, str]:
        """
        Send prompt to the LLM, strip fences, parse JSON, validate against schema.

        Returns (validated_dict, raw_response_text).
        Raises ValueError on any parse or validation failure with raw response attached.
        """
        raw = ""
        try:
            if self._provider == "gemini":
                if self._genai_models is None:
                    raise ValueError("Gemini client is not configured.")
                response = self._genai_models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )
                raw = response.text
                if raw is None:
                    raise ValueError("Gemini response text is empty.")
            else:
                if self._openai_client is None:
                    raise ValueError("OpenAI client is not configured.")
                response = self._openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                raw = response.choices[0].message.content
                if raw is None:
                    raise ValueError("OpenAI response text is empty.")

            cleaned = _strip_fences(raw)
            parsed = json.loads(cleaned)
            print("LLM response: %s", parsed)
            validated = schema.model_validate(parsed)
            log.debug("LLM response validated against %s", schema.__name__)
            return validated.model_dump(), raw

        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(
                f"LLM response failed validation ({schema.__name__}): {e}\n"
                f"Raw response:\n{raw}"
            ) from e
