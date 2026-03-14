"""Moderator prompt templates (PROMPT_SPEC §4, §6, §8).

Builds chat messages for the moderator's three roles:
task framing, candidate synthesis, and release gate.
"""

from nelson.prompts.labels import label_contributions
from nelson.protocols.domain import TaskFramingResult


def build_framing_messages(
    *,
    user_prompt: str,
    max_rounds: int,
    release_gate_mode: str,
) -> list[dict[str, str]]:
    """Build messages for the moderator task framing invocation.

    The moderator analyzes the user's prompt and creates a structured
    framing that guides all subsequent consensus phases (PROMPT_SPEC §4).
    """
    system = (
        "You are a moderator in a multi-model consensus system. "
        "Your role is to analyze the user's request and create a structured "
        "task framing. Do NOT answer the question — only analyze it.\n\n"
        "Rules:\n"
        "- Classify the task type\n"
        "- Estimate content sensitivity\n"
        "- Identify what a good answer must accomplish\n"
        "- Identify aspects to cover\n"
        "- Identify ambiguity or context dependence\n"
        "- Do not include markdown code fences around JSON\n"
        "- Do not include explanatory prose outside the requested schema\n\n"
        f"Runtime context: max_rounds={max_rounds}, "
        f"release_gate_mode={release_gate_mode}\n\n"
        "Respond with a JSON object matching this schema:\n"
        '{"task_type": "analytical|factual|comparative|creative|advice|'
        'planning|classification|transformation|other", '
        '"sensitivity": "low|medium|high", '
        '"objective": "string", '
        '"quality_criteria": ["string"], '
        '"aspects_to_cover": ["string"], '
        '"ambiguities": ["string"], '
        '"assumptions": ["string"]}'
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
    """Build messages for the moderator candidate synthesis invocation.

    The moderator combines participant contributions into a single
    candidate answer (PROMPT_SPEC §6).
    """
    # Label contributions as response_a, response_b, etc.
    labeled = label_contributions(contributions)

    system = (
        "You are a moderator synthesizing participant responses into a "
        "single candidate answer.\n\n"
        "Rules:\n"
        "- Combine complementary strengths\n"
        "- Remove redundancy\n"
        "- Resolve conflicts where possible\n"
        "- Preserve justified caveats\n"
        "- Update framing only when participant objections are substantial\n"
        "- Do not include markdown code fences around JSON\n\n"
        f"Task framing: {framing.model_dump_json()}\n\n"
        f"Round: {round_number}\n\n"
        "Participant contributions:\n" + "\n".join(labeled) + "\n\n"
        "Respond with a JSON object matching this schema:\n"
        '{"candidate_markdown": "string", '
        '"summary": "string", '
        '"relevant_excerpt_labels": ["string"], '
        '"framing_update": null}'
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
    """Build messages for the moderator release gate invocation.

    The release gate checks whether the candidate is ready to return
    to the user (PROMPT_SPEC §8).
    """
    system = (
        "You are a moderator performing a final quality check on a "
        "candidate answer before delivering it to the user.\n\n"
        "Check:\n"
        "- Direct answer quality\n"
        "- Coherence\n"
        "- Plausibility and factual caution\n"
        "- Whether important consensus points are represented\n"
        "- Whether uncertainty is calibrated correctly\n"
        "- Do not include markdown code fences around JSON\n\n"
        f"Task framing: {framing.model_dump_json()}\n"
        f"Consensus summary: {consensus_summary}\n"
        f"Release gate mode: {release_gate_mode}\n\n"
        "Respond with a JSON object matching this schema:\n"
        '{"decision": "pass|pass_with_minor_fixes|fail", '
        '"summary": "string", '
        '"minor_fixes_applied": ["string"], '
        '"blocking_issues": ["string"], '
        '"final_answer_markdown": "string"}'
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Candidate answer:\n\n{candidate_markdown}"},
    ]
