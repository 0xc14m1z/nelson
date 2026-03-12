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
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    currency: str = "USD"
    is_normalized: bool = True
    is_complete: bool = True


class ErrorObject(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, object] = Field(default_factory=dict)


class TaskFramingResult(BaseModel):
    task_type: TaskType
    sensitivity: Sensitivity
    objective: str
    quality_criteria: list[str]
    aspects_to_cover: list[str]
    ambiguities: list[str] = []
    assumptions: list[str] = []


class FramingFeedback(BaseModel):
    status: FramingFeedbackStatus
    notes: list[str] = []
    proposed_aspects: list[str] = []


class ParticipantContribution(BaseModel):
    answer_markdown: str
    assumptions: list[str] = []
    limitations: list[str] = []
    framing_feedback: FramingFeedback


class CandidateSynthesisResult(BaseModel):
    candidate_markdown: str
    summary: str
    relevant_excerpt_labels: list[str] = []
    framing_update: TaskFramingResult | None = None


class ReviewResult(BaseModel):
    decision: ReviewDecision
    summary: str
    required_changes: list[str] = []
    optional_improvements: list[str] = []
    blocking_issues: list[str] = []


class ReleaseGateResult(BaseModel):
    decision: ReleaseGateDecision
    summary: str
    minor_fixes_applied: list[str] = []
    blocking_issues: list[str] = []
    final_answer_markdown: str


class ExcludedParticipant(BaseModel):
    model: str
    round_excluded: int
    reason_code: str
    reason_summary: str
    failed_invocation_id: str
