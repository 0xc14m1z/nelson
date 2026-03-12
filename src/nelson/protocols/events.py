"""Event envelope, typed payloads, and discriminated union."""

from pydantic import BaseModel, model_validator

from nelson.protocols.domain import ErrorObject, UsageSnapshot
from nelson.protocols.enums import (
    Adapter,
    CandidateSource,
    EventType,
    InvocationPurpose,
    OutputFormat,
    Phase,
    ReleaseGateDecision,
    ReleaseGateMode,
    Role,
    Sensitivity,
    TaskType,
    UsageScope,
)

# ── Payload models ──────────────────────────────────────────────────────


class CommandReceivedPayload(BaseModel):
    command_type: str
    adapter: Adapter


class CommandCompletedPayload(BaseModel):
    command_type: str
    status: str


class CommandFailedPayload(BaseModel):
    command_type: str
    error: ErrorObject


class AuthKeySavedPayload(BaseModel):
    storage_path: str


class AuthStatusReportedPayload(BaseModel):
    saved_key_present: bool
    env_key_present: bool
    effective_source: str
    verification: str


class AuthKeyClearedPayload(BaseModel):
    saved_key_removed: bool


class RunStartedPayload(BaseModel):
    input_source: str
    max_rounds: int
    release_gate_mode: ReleaseGateMode
    participants: list[str]
    moderator: str


class RunCompletedPayload(BaseModel):
    status: str
    rounds_completed: int
    consensus_status: str
    framing_version: int
    final_answer_chars: int
    duration_ms: int


class RunFailedPayload(BaseModel):
    status: str
    framing_version: int | None
    error: ErrorObject


class ProgressUpdatedPayload(BaseModel):
    phase_name: str
    phase_index: int
    phase_count_estimate: int
    round: int | None = None
    max_rounds: int
    completed_units: int
    total_units: int
    stage_progress: float
    overall_progress_estimate: float
    is_estimate: bool
    message: str


class ConsensusPendingPayload(BaseModel):
    candidate_id: str
    reviewer_count: int
    blocking_review_count: int
    minor_revise_count: int
    major_revise_count: int
    reject_count: int
    summary: str


class ConsensusReachedPayload(BaseModel):
    candidate_id: str
    reviewer_count: int
    approve_count: int
    minor_revise_count: int
    major_revise_count: int
    reject_count: int
    summary: str


class ConsensusPartialPayload(BaseModel):
    candidate_id: str
    reason: str
    unresolved_issues: list[str]


class TaskFramingStartedPayload(BaseModel):
    invocation_id: str
    schema_name: str
    streaming: bool


class TaskFramingCompletedPayload(BaseModel):
    invocation_id: str
    task_type: TaskType
    sensitivity: Sensitivity
    objective: str
    quality_criteria: list[str]
    aspects_to_cover: list[str]
    ambiguities: list[str] = []
    assumptions: list[str] = []
    framing_version: int


class TaskFramingUpdatedPayload(BaseModel):
    task_type: TaskType
    sensitivity: Sensitivity
    objective: str
    quality_criteria: list[str]
    aspects_to_cover: list[str]
    ambiguities: list[str] = []
    assumptions: list[str] = []
    framing_version: int
    previous_framing_version: int
    effective_from_round: int
    invalidated_candidate_id: str
    update_reason: str


class ModelStartedPayload(BaseModel):
    invocation_id: str
    purpose: InvocationPurpose
    framing_version: int | None = None
    schema_name: str
    streaming: bool
    retry_index: int = 0
    repair_of_invocation_id: str | None = None


class ModelDeltaPayload(BaseModel):
    invocation_id: str
    delta_index: int
    text: str
    is_structured_output: bool


class ModelCompletedPayload(BaseModel):
    invocation_id: str
    purpose: InvocationPurpose
    framing_version: int | None = None
    finish_reason: str
    output_format: OutputFormat
    parsed: dict[str, object] | None = None
    raw_text: str | None = None
    repair_of_invocation_id: str | None = None


class ModelFailedPayload(BaseModel):
    invocation_id: str
    purpose: InvocationPurpose
    framing_version: int | None = None
    retry_index: int = 0
    error: ErrorObject
    repair_of_invocation_id: str | None = None


class ParticipantExcludedPayload(BaseModel):
    reason_code: str
    reason_summary: str
    failed_invocation_id: str
    remaining_active_participant_count: int
    quorum_preserved: bool


class RoundStartedPayload(BaseModel):
    round: int
    candidate_id: str
    framing_version: int
    target_participant_count: int


class RoundCompletedPayload(BaseModel):
    round: int
    candidate_id: str
    framing_version: int
    review_executed: bool
    approve_count: int | None = None
    minor_revise_count: int | None = None
    major_revise_count: int | None = None
    reject_count: int | None = None
    candidate_invalidated_by_framing_update: bool = False
    will_continue: bool


class CandidateCreatedPayload(BaseModel):
    candidate_id: str
    framing_version: int
    source: CandidateSource
    text: str
    summary: str
    excerpt_count: int


class CandidateUpdatedPayload(BaseModel):
    candidate_id: str
    previous_candidate_id: str
    framing_version: int
    source: CandidateSource
    text: str
    summary: str


class ReviewStartedPayload(BaseModel):
    candidate_id: str
    framing_version: int
    target_participant_count: int


class ReviewCompletedPayload(BaseModel):
    candidate_id: str
    framing_version: int
    reviewer_count: int
    approve_count: int
    minor_revise_count: int
    major_revise_count: int
    reject_count: int
    blocking_issue_summaries: list[str] = []
    minor_improvement_summaries: list[str] = []


class ReleaseGateStartedPayload(BaseModel):
    invocation_id: str
    mode: ReleaseGateMode
    candidate_id: str
    framing_version: int


class ReleaseGateCompletedPayload(BaseModel):
    invocation_id: str
    candidate_id: str
    framing_version: int
    executed: bool
    decision: ReleaseGateDecision
    summary: str
    minor_fixes_applied: list[str] = []
    blocking_issues: list[str] = []


class UsageReportedPayload(BaseModel):
    scope: UsageScope
    invocation_id: str | None = None
    usage: UsageSnapshot


# ── Type → Payload mapping ──────────────────────────────────────────────

EventPayload = (
    CommandReceivedPayload
    | CommandCompletedPayload
    | CommandFailedPayload
    | AuthKeySavedPayload
    | AuthStatusReportedPayload
    | AuthKeyClearedPayload
    | RunStartedPayload
    | RunCompletedPayload
    | RunFailedPayload
    | ProgressUpdatedPayload
    | ConsensusPendingPayload
    | ConsensusReachedPayload
    | ConsensusPartialPayload
    | TaskFramingStartedPayload
    | TaskFramingCompletedPayload
    | TaskFramingUpdatedPayload
    | ModelStartedPayload
    | ModelDeltaPayload
    | ModelCompletedPayload
    | ModelFailedPayload
    | ParticipantExcludedPayload
    | RoundStartedPayload
    | RoundCompletedPayload
    | CandidateCreatedPayload
    | CandidateUpdatedPayload
    | ReviewStartedPayload
    | ReviewCompletedPayload
    | ReleaseGateStartedPayload
    | ReleaseGateCompletedPayload
    | UsageReportedPayload
)

PAYLOAD_MAP: dict[str, type[BaseModel]] = {
    "command_received": CommandReceivedPayload,
    "command_completed": CommandCompletedPayload,
    "command_failed": CommandFailedPayload,
    "auth_key_saved": AuthKeySavedPayload,
    "auth_status_reported": AuthStatusReportedPayload,
    "auth_key_cleared": AuthKeyClearedPayload,
    "run_started": RunStartedPayload,
    "run_completed": RunCompletedPayload,
    "run_failed": RunFailedPayload,
    "progress_updated": ProgressUpdatedPayload,
    "consensus_pending": ConsensusPendingPayload,
    "consensus_reached": ConsensusReachedPayload,
    "consensus_partial": ConsensusPartialPayload,
    "task_framing_started": TaskFramingStartedPayload,
    "task_framing_completed": TaskFramingCompletedPayload,
    "task_framing_updated": TaskFramingUpdatedPayload,
    "model_started": ModelStartedPayload,
    "model_delta": ModelDeltaPayload,
    "model_completed": ModelCompletedPayload,
    "model_failed": ModelFailedPayload,
    "participant_excluded": ParticipantExcludedPayload,
    "round_started": RoundStartedPayload,
    "round_completed": RoundCompletedPayload,
    "candidate_created": CandidateCreatedPayload,
    "candidate_updated": CandidateUpdatedPayload,
    "review_started": ReviewStartedPayload,
    "review_completed": ReviewCompletedPayload,
    "release_gate_started": ReleaseGateStartedPayload,
    "release_gate_completed": ReleaseGateCompletedPayload,
    "usage_reported": UsageReportedPayload,
}


class EventEnvelope(BaseModel):
    """Common envelope for all events — use ApplicationEvent for validated instances."""

    event_id: str
    command_id: str
    run_id: str | None = None
    sequence: int
    timestamp: str
    type: EventType
    phase: Phase
    round: int | None = None
    role: Role
    model: str | None = None


class ApplicationEvent(EventEnvelope):
    """Full event with typed, discriminated payload."""

    payload: EventPayload

    @model_validator(mode="before")
    @classmethod
    def _resolve_payload(cls, data: dict[str, object]) -> dict[str, object]:
        event_type = str(data.get("type", ""))
        payload_raw = data.get("payload")
        if isinstance(payload_raw, dict):
            payload_cls = PAYLOAD_MAP.get(event_type)
            if payload_cls is not None:
                data = {**data, "payload": payload_cls.model_validate(payload_raw)}
        return data
