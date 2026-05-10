"""
llm_client.py
-------------
LlmClient  — sends prompts to the configured LLM, parses JSON responses,
             and validates them against a pydantic schema.

Provider-specific wiring lives in `recommendation.llm_providers`. This module
owns only post-processing (fence stripping, JSON parsing, schema validation)
and the response schemas used by the recommendation and edge-building flows.
"""

import json
import logging

from django.conf import settings
from pydantic import BaseModel, ValidationError

from recommendation.llm_providers import LlmProvider, build_provider

log = logging.getLogger(__name__)


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
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


class LlmClient:
    """
    Provider-agnostic LLM client. Depends only on the `LlmProvider` abstraction.
    Reads provider config from settings.RECOMMENDATION_CONFIGS[config_key] when
    no explicit provider is injected.
    Raises ValueError on parse or validation failure — no retries, no fallbacks.
    """

    def __init__(self, config_key: str = "default", provider: LlmProvider | None = None):
        if provider is None:
            cfg = settings.RECOMMENDATION_CONFIGS[config_key]["language_model"]
            provider = build_provider(cfg)
        self._provider = provider
        
    @property
    def model_name(self) -> str:
        return self._provider.model_name

    def send(self, prompt: str, schema: type[BaseModel]) -> tuple[dict, str]:
        """
        Send prompt to the LLM, strip fences, parse JSON, validate against schema.

        Returns (validated_dict, raw_response_text).
        Raises ValueError on any parse or validation failure with raw response attached.
        """
        raw = self._provider.generate(prompt)
        try:
            cleaned = _strip_fences(raw)
            parsed = json.loads(cleaned)
            log.debug("LLM response: %s", parsed)
            validated = schema.model_validate(parsed)
            log.debug("LLM response validated against %s", schema.__name__)
            return validated.model_dump(), raw
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(
                f"LLM response failed validation ({schema.__name__}): {e}\n"
                f"Raw response:\n{raw}"
            ) from e
