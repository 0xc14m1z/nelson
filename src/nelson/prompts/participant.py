"""Participant prompt templates (PROMPT_SPEC §5, §7).

Builds chat messages for participant contributions and reviews.
Prompt text lives in external Markdown templates; this module
handles placeholder injection and message formatting.
"""

from nelson.prompts.labels import label_contributions
from nelson.prompts.loader import PromptName, render_prompt
from nelson.protocols.domain import ParticipantContribution, TaskFramingResult


def build_contribution_messages(
    *,
    user_prompt: str,
    framing: TaskFramingResult,
    participant_model: str,
) -> list[dict[str, str]]:
    """Build messages for a participant contribution invocation."""
    system = render_prompt(
        PromptName.CONTRIBUTION,
        task_framing_json=framing.model_dump_json(),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def build_review_messages(
    *,
    user_prompt: str,
    framing: TaskFramingResult,
    candidate_markdown: str,
    synthesis_summary: str,
    contributions: list[ParticipantContribution],
    participant_model: str,
) -> list[dict[str, str]]:
    """Build messages for a participant review invocation."""
    labeled = label_contributions(contributions)
    system = render_prompt(
        PromptName.REVIEW,
        task_framing_json=framing.model_dump_json(),
        synthesis_summary=synthesis_summary,
        labeled_contributions="\n".join(labeled),
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Candidate answer:\n\n{candidate_markdown}"},
    ]
