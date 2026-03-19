"""Prompt template loader.

Loads prompt templates from Markdown files and substitutes placeholders.
Templates live in ``prompts/templates/`` as ``.md`` files with
``$placeholder`` markers (using ``string.Template``).
"""

from enum import StrEnum
from pathlib import Path
from string import Template

# Templates are co-located with this module under templates/
_TEMPLATE_DIR = Path(__file__).parent / "templates"


class PromptName(StrEnum):
    """Identifies a prompt template by its consensus phase role."""

    TASK_FRAMING = "task_framing"
    CONTRIBUTION = "contribution"
    SYNTHESIS = "synthesis"
    REVIEW = "review"
    RELEASE_GATE = "release_gate"


# Cache loaded templates to avoid repeated filesystem reads within a run
_cache: dict[PromptName, Template] = {}


def _load_template(name: PromptName) -> Template:
    """Load and cache a prompt template from disk."""
    if name not in _cache:
        path = _TEMPLATE_DIR / f"{name.value}.md"
        _cache[name] = Template(path.read_text())
    return _cache[name]


def render_prompt(name: PromptName, **kwargs: object) -> str:
    """Load a prompt template and substitute placeholders.

    Args:
        name: Which prompt template to load.
        **kwargs: Placeholder values to substitute (e.g. ``max_rounds=10``).

    Returns:
        The fully rendered prompt string.

    Raises:
        KeyError: If a required placeholder is missing from kwargs.
        FileNotFoundError: If the template file does not exist.
    """
    template = _load_template(name)
    return template.substitute(kwargs)
