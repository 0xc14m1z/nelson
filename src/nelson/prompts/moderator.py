"""Moderator prompt templates (PROMPT_SPEC §4, §6, §8).

Builds chat messages for the moderator's three roles:
task framing, candidate synthesis, and release gate.
Prompt text lives in external Markdown templates; this module
handles placeholder injection and message formatting.
"""

from nelson.prompts.labels import label_contributions
from nelson.prompts.loader import PromptName, render_prompt
from nelson.protocols.domain import TaskFramingResult


def build_framing_messages(
    *,
    user_prompt: str,
    max_rounds: int,
    release_gate_mode: str,
) -> list[dict[str, str]]:
    """Build messages for the moderator task framing invocation."""
    system = render_prompt(
        PromptName.TASK_FRAMING,
        max_rounds=max_rounds,
        release_gate_mode=release_gate_mode,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def build_synthesis_messages(
    *,
    user_prompt: str,
    framing: TaskFramingResult,
    contributions: list[dict[str, object]],
    round_number: int,
) -> list[dict[str, str]]:
    """Build messages for the moderator candidate synthesis invocation."""
    labeled = label_contributions(contributions)
    system = render_prompt(
        PromptName.SYNTHESIS,
        task_framing_json=framing.model_dump_json(),
        round_number=round_number,
        labeled_contributions="\n".join(labeled),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def build_release_gate_messages(
    *,
    user_prompt: str,
    framing: TaskFramingResult,
    candidate_markdown: str,
    consensus_summary: str,
    release_gate_mode: str,
) -> list[dict[str, str]]:
    """Build messages for the moderator release gate invocation."""
    system = render_prompt(
        PromptName.RELEASE_GATE,
        task_framing_json=framing.model_dump_json(),
        consensus_summary=consensus_summary,
        release_gate_mode=release_gate_mode,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Candidate answer:\n\n{candidate_markdown}"},
    ]
