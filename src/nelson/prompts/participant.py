"""Participant prompt templates (PROMPT_SPEC §5, §7).

Builds chat messages for participant contributions and reviews.
"""

from nelson.prompts.labels import label_contributions
from nelson.protocols.domain import TaskFramingResult


def build_contribution_messages(
    *,
    user_prompt: str,
    framing: TaskFramingResult,
    participant_model: str,
) -> list[dict[str, str]]:
    """Build messages for a participant contribution invocation.

    Each participant generates a fresh answer proposal while also
    evaluating the moderator's framing (PROMPT_SPEC §5).
    """
    system = (
        "You are a participant in a multi-model consensus system. "
        "Your role is to provide a thorough, independent answer to the "
        "user's question and evaluate the task framing.\n\n"
        "Rules:\n"
        "- Answer the user's prompt directly\n"
        "- State assumptions and limitations explicitly\n"
        "- Inspect the task framing and flag issues if any\n"
        "- Suggest missing aspects only when relevant\n"
        "- Do not include markdown code fences around JSON\n\n"
        f"Task framing: {framing.model_dump_json()}\n\n"
        "Respond with a JSON object matching this schema:\n"
        '{"answer_markdown": "string", '
        '"assumptions": ["string"], '
        '"limitations": ["string"], '
        '"framing_feedback": {"status": "accept|minor_issue|major_issue", '
        '"notes": ["string"], "proposed_aspects": ["string"]}}'
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
    contributions: list[dict[str, object]],
    participant_model: str,
) -> list[dict[str, str]]:
    """Build messages for a participant review invocation.

    Participants review the moderator's candidate answer and determine
    whether it is ready (PROMPT_SPEC §7).
    """
    # Label contributions anonymously as response_a, response_b, etc.
    labeled = label_contributions(contributions)

    system = (
        "You are a participant reviewing a candidate answer. "
        "Judge the candidate against the user's prompt, not stylistic preference.\n\n"
        "Rules:\n"
        "- Use approve for answers ready to deliver\n"
        "- Use minor_revise only for non-blocking improvements\n"
        "- Use major_revise for substantive but recoverable problems\n"
        "- Use reject only when materially wrong or misaligned\n"
        "- Focus on changes that matter\n"
        "- Do not include markdown code fences around JSON\n\n"
        f"Task framing: {framing.model_dump_json()}\n"
        f"Synthesis summary: {synthesis_summary}\n\n"
        "Participant excerpts:\n" + "\n".join(labeled) + "\n\n"
        "Respond with a JSON object matching this schema:\n"
        '{"decision": "approve|minor_revise|major_revise|reject", '
        '"summary": "string", '
        '"required_changes": ["string"], '
        '"optional_improvements": ["string"], '
        '"blocking_issues": ["string"]}'
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Candidate answer:\n\n{candidate_markdown}"},
    ]
