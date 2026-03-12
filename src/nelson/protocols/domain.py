"""Domain models for internal workflow artifacts."""

from pydantic import BaseModel, Field

from nelson.protocols.enums import (
    FramingFeedbackStatus,
    ReleaseGateDecision,
    ReviewDecision,
    Sensitivity,
    TaskType,
)


class UsageSnapshot(BaseModel):
    """Token and cost totals for one or more model invocations."""

    prompt_tokens: int | None = Field(default=None, description="Number of input tokens sent.")
    completion_tokens: int | None = Field(
        default=None, description="Number of output tokens received."
    )
    total_tokens: int | None = Field(
        default=None, description="Sum of prompt and completion tokens."
    )
    cost_usd: float | None = Field(default=None, description="Estimated cost in USD, if available.")
    currency: str = Field(default="USD", description="Currency code for cost values.")
    is_normalized: bool = Field(
        default=True,
        description="Whether token counts have been normalized across providers.",
    )
    is_complete: bool = Field(
        default=True,
        description="Whether the snapshot covers all invocations (False if the run failed early).",
    )


class ErrorObject(BaseModel):
    """Structured error included in failure events and results."""

    code: str = Field(description="Machine-readable error code.")
    message: str = Field(description="Human-readable error description.")
    retryable: bool = Field(description="Whether the operation can be retried.")
    details: dict[str, object] = Field(
        default_factory=dict, description="Arbitrary additional context."
    )


class TaskFramingResult(BaseModel):
    """Moderator's structured analysis of the user's task."""

    task_type: TaskType = Field(description="Category assigned to the task.")
    sensitivity: Sensitivity = Field(description="Content sensitivity level.")
    objective: str = Field(description="Concise statement of what the answer must achieve.")
    quality_criteria: list[str] = Field(description="Criteria used to evaluate candidates.")
    aspects_to_cover: list[str] = Field(description="Specific topics the answer must address.")
    ambiguities: list[str] = Field(default=[], description="Ambiguities identified in the prompt.")
    assumptions: list[str] = Field(
        default=[], description="Assumptions made to resolve ambiguities."
    )


class FramingFeedback(BaseModel):
    """Participant's inline assessment of the task framing."""

    status: FramingFeedbackStatus = Field(
        description="Whether the participant accepts the framing."
    )
    notes: list[str] = Field(default=[], description="Explanatory notes on the assessment.")
    proposed_aspects: list[str] = Field(
        default=[], description="Additional aspects the participant suggests covering."
    )


class ParticipantContribution(BaseModel):
    """A participant's initial answer and framing feedback."""

    answer_markdown: str = Field(description="The participant's proposed answer in Markdown.")
    assumptions: list[str] = Field(default=[], description="Assumptions the participant made.")
    limitations: list[str] = Field(default=[], description="Known limitations of the answer.")
    framing_feedback: FramingFeedback = Field(
        description="Participant's assessment of the task framing."
    )


class CandidateSynthesisResult(BaseModel):
    """Moderator's synthesized candidate answer from participant contributions."""

    candidate_markdown: str = Field(description="The synthesized candidate answer in Markdown.")
    summary: str = Field(description="Brief summary of what was synthesized.")
    relevant_excerpt_labels: list[str] = Field(
        default=[], description="Labels of participant excerpts used in synthesis."
    )
    framing_update: TaskFramingResult | None = Field(
        default=None,
        description="Updated task framing if the moderator identified a material issue.",
    )


class ReviewResult(BaseModel):
    """A participant's review of a candidate answer."""

    decision: ReviewDecision = Field(description="The participant's review verdict.")
    summary: str = Field(description="Brief explanation of the decision.")
    required_changes: list[str] = Field(
        default=[], description="Changes required before the candidate can be approved."
    )
    optional_improvements: list[str] = Field(
        default=[], description="Suggested improvements that are not blocking."
    )
    blocking_issues: list[str] = Field(default=[], description="Issues that prevent approval.")


class ReleaseGateResult(BaseModel):
    """Moderator's final quality-gate evaluation of the candidate answer."""

    decision: ReleaseGateDecision = Field(description="Quality-gate verdict.")
    summary: str = Field(description="Explanation of the decision.")
    minor_fixes_applied: list[str] = Field(
        default=[], description="Minor fixes applied before release."
    )
    blocking_issues: list[str] = Field(
        default=[], description="Issues that blocked release (if decision is fail)."
    )
    final_answer_markdown: str = Field(description="The final deliverable answer in Markdown.")


class ExcludedParticipant(BaseModel):
    """Record of a participant removed from the run."""

    model: str = Field(description="OpenRouter model ID of the excluded participant.")
    round_excluded: int = Field(description="Round number when exclusion occurred.")
    reason_code: str = Field(description="Machine-readable exclusion reason.")
    reason_summary: str = Field(description="Human-readable explanation of the exclusion.")
    failed_invocation_id: str = Field(description="ID of the invocation that triggered exclusion.")
