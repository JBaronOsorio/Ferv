"""
prompt_builder.py
-----------------
PromptBuilder — loads versioned prompt templates and injects context variables.
Templates live at ferv_project/prompts/<template_name>.txt.
Never edit a versioned template in place; create _v2 and route new calls to it.
"""

import logging
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)

PROMPTS_DIR = settings.BASE_DIR / "prompts"


class PromptBuilder:
    def build(self, template_name: str, **context) -> tuple[str, str]:
        """
        Load the named template and inject context variables.

        Returns (filled_prompt, template_name) where template_name is the
        version key used for logging.
        """
        template_path = PROMPTS_DIR / f"{template_name}.txt"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {template_path}"
            )
        template = template_path.read_text(encoding="utf-8")
        filled = template.format_map(context)
        log.debug("Built prompt from template '%s' (%d chars)", template_name, len(filled))
        return filled, template_name
