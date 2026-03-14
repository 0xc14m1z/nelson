"""Event envelope, typed payloads, and discriminated union."""

from pydantic import BaseModel, Field, model_validator

from nelson.protocols.domain import ErrorObject, UsageSnapshot
from nelson.protocols.enums import (
    Adapter,
    CandidateSource,
    EventType,
    FinishReason,
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
    """Payload for a command_received event."""

    command_type: str = Field(description="Type of command that was received.")
    adapter: Adapter = Field(description="Interface that originated the command.")


class CommandCompletedPayload(BaseModel):
    """Payload for a command_completed event."""

    command_type: str = Field(description="Type of command that completed.")
    status: str = Field(description="Terminal status of the command.")


class CommandFailedPayload(BaseModel):
    """Payload for a command_failed event."""

    command_type: str = Field(description="Type of command that failed.")
    error: ErrorObject = Field(description="Structured error details.")


class AuthKeySavedPayload(BaseModel):
    """Payload for an auth_key_saved event."""

    storage_path: str = Field(description="Filesystem path where the key was saved.")


class AuthStatusReportedPayload(BaseModel):
    """Payload for an auth_status_reported event."""

    saved_key_present: bool = Field(description="Whether a saved key exists on disk.")
    env_key_present: bool = Field(description="Whether an env var key is set.")
    effective_source: str = Field(description="Which key source is active: saved, env, or none.")
    verification: str = Field(
        description="Key verification result: valid, invalid, or not_checked."
    )


class AuthKeyClearedPayload(BaseModel):
    """Payload for an auth_key_cleared event."""

    saved_key_removed: bool = Field(description="Whether a saved key was actually removed.")


class RunStartedPayload(BaseModel):
    """Payload for a run_started event."""

    input_source: str = Field(description="How the prompt was provided.")
    max_rounds: int = Field(description="Maximum consensus rounds configured.")
    release_gate_mode: ReleaseGateMode = Field(description="Release gate mode for this run.")
    participants: list[str] = Field(description="OpenRouter model IDs of participants.")
    moderator: str = Field(description="OpenRouter model ID of the moderator.")


class RunCompletedPayload(BaseModel):
    """Payload for a run_completed event."""

    status: str = Field(description="Terminal run status.")
    rounds_completed: int = Field(description="Number of consensus rounds completed.")
    consensus_status: str = Field(description="Final consensus outcome.")
    framing_version: int = Field(description="Task framing version at completion.")
    final_answer_chars: int = Field(description="Character count of the final answer.")
    duration_ms: int = Field(description="Total run duration in milliseconds.")


class RunFailedPayload(BaseModel):
    """Payload for a run_failed event."""

    status: str = Field(description="Terminal run status (always 'failed').")
    framing_version: int | None = Field(
        description="Task framing version at failure, if framing was reached."
    )
    error: ErrorObject = Field(description="Structured error details.")


class ProgressUpdatedPayload(BaseModel):
    """Payload for a progress_updated event."""

    phase_name: str = Field(description="Name of the current pipeline phase.")
    phase_index: int = Field(description="Zero-based index of the current phase.")
    phase_count_estimate: int = Field(description="Estimated total number of phases.")
    round: int | None = Field(default=None, description="Current consensus round, if applicable.")
    max_rounds: int = Field(description="Maximum consensus rounds configured.")
    completed_units: int = Field(description="Work units completed in the current stage.")
    total_units: int = Field(description="Total work units in the current stage.")
    stage_progress: float = Field(description="Progress within the current stage (0.0-1.0).")
    overall_progress_estimate: float = Field(
        description="Estimated overall run progress (0.0-1.0)."
    )
    is_estimate: bool = Field(description="Whether the progress values are estimates.")
    message: str = Field(description="Human-readable progress message.")


class ConsensusPendingPayload(BaseModel):
    """Payload for a consensus_pending event."""

    candidate_id: str = Field(description="ID of the candidate under review.")
    reviewer_count: int = Field(description="Number of reviewers.")
    blocking_review_count: int = Field(description="Reviews with blocking issues.")
    minor_revise_count: int = Field(description="Reviews requesting minor revisions.")
    major_revise_count: int = Field(description="Reviews requesting major revisions.")
    reject_count: int = Field(description="Reviews that rejected the candidate.")
    summary: str = Field(description="Human-readable consensus status summary.")


class ConsensusReachedPayload(BaseModel):
    """Payload for a consensus_reached event."""

    candidate_id: str = Field(description="ID of the approved candidate.")
    reviewer_count: int = Field(description="Number of reviewers.")
    approve_count: int = Field(description="Reviews that approved the candidate.")
    minor_revise_count: int = Field(description="Reviews requesting minor revisions.")
    major_revise_count: int = Field(description="Reviews requesting major revisions.")
    reject_count: int = Field(description="Reviews that rejected the candidate.")
    summary: str = Field(description="Human-readable consensus summary.")


class ConsensusPartialPayload(BaseModel):
    """Payload for a consensus_partial event (max rounds exhausted)."""

    candidate_id: str = Field(description="ID of the best available candidate.")
    reason: str = Field(description="Why full consensus was not reached.")
    unresolved_issues: list[str] = Field(description="Issues that remained unresolved.")


class TaskFramingStartedPayload(BaseModel):
    """Payload for a task_framing_started event."""

    invocation_id: str = Field(description="ID of the model invocation.")
    schema_name: str = Field(description="Name of the structured output schema requested.")
    streaming: bool = Field(description="Whether the invocation uses streaming.")


class TaskFramingCompletedPayload(BaseModel):
    """Payload for a task_framing_completed event."""

    invocation_id: str = Field(description="ID of the model invocation.")
    task_type: TaskType = Field(description="Category assigned to the task.")
    sensitivity: Sensitivity = Field(description="Content sensitivity level.")
    objective: str = Field(description="Concise statement of the task objective.")
    quality_criteria: list[str] = Field(description="Criteria for evaluating candidates.")
    aspects_to_cover: list[str] = Field(description="Topics the answer must address.")
    ambiguities: list[str] = Field(default=[], description="Ambiguities identified in the prompt.")
    assumptions: list[str] = Field(
        default=[], description="Assumptions made to resolve ambiguities."
    )
    framing_version: int = Field(description="Version number of this framing.")


class TaskFramingUpdatedPayload(BaseModel):
    """Payload for a task_framing_updated event (mid-run reframing)."""

    task_type: TaskType = Field(description="Updated task category.")
    sensitivity: Sensitivity = Field(description="Updated sensitivity level.")
    objective: str = Field(description="Updated task objective.")
    quality_criteria: list[str] = Field(description="Updated evaluation criteria.")
    aspects_to_cover: list[str] = Field(description="Updated topics to address.")
    ambiguities: list[str] = Field(default=[], description="Ambiguities identified in the prompt.")
    assumptions: list[str] = Field(
        default=[], description="Assumptions made to resolve ambiguities."
    )
    framing_version: int = Field(description="New framing version number.")
    previous_framing_version: int = Field(description="Framing version this update replaces.")
    effective_from_round: int = Field(description="Round from which the new framing takes effect.")
    invalidated_candidate_id: str = Field(
        description="Candidate ID invalidated by this framing update."
    )
    update_reason: str = Field(description="Why the framing was updated.")


class ModelStartedPayload(BaseModel):
    """Payload for a model_started event."""

    invocation_id: str = Field(description="Unique invocation identifier.")
    purpose: InvocationPurpose = Field(description="Why this model invocation was made.")
    framing_version: int | None = Field(
        default=None, description="Task framing version, if applicable."
    )
    schema_name: str = Field(description="Structured output schema requested.")
    streaming: bool = Field(description="Whether the invocation uses streaming.")
    retry_index: int = Field(default=0, description="Zero-based retry attempt index.")
    repair_of_invocation_id: str | None = Field(
        default=None, description="ID of the invocation this repair attempt is fixing."
    )


class ModelDeltaPayload(BaseModel):
    """Payload for a model_delta event (streaming chunk)."""

    invocation_id: str = Field(description="ID of the invocation producing this chunk.")
    delta_index: int = Field(description="Zero-based index of this chunk in the stream.")
    text: str = Field(description="Text content of this streaming chunk.")
    is_structured_output: bool = Field(
        description="Whether the chunk is part of structured output."
    )


class ModelCompletedPayload(BaseModel):
    """Payload for a model_completed event."""

    invocation_id: str = Field(description="ID of the completed invocation.")
    purpose: InvocationPurpose = Field(description="Why this model invocation was made.")
    framing_version: int | None = Field(
        default=None, description="Task framing version, if applicable."
    )
    finish_reason: FinishReason = Field(description="Why the model stopped generating tokens.")
    output_format: OutputFormat = Field(description="Whether output is text or structured.")
    parsed: dict[str, object] | None = Field(
        default=None, description="Parsed structured output, if applicable."
    )
    raw_text: str | None = Field(
        default=None, description="Raw text output, if output_format is text."
    )
    repair_of_invocation_id: str | None = Field(
        default=None, description="ID of the invocation this repair attempt fixed."
    )


class ModelFailedPayload(BaseModel):
    """Payload for a model_failed event."""

    invocation_id: str = Field(description="ID of the failed invocation.")
    purpose: InvocationPurpose = Field(description="Why this model invocation was made.")
    framing_version: int | None = Field(
        default=None, description="Task framing version, if applicable."
    )
    retry_index: int = Field(default=0, description="Zero-based retry attempt index.")
    error: ErrorObject = Field(description="Structured error details.")
    repair_of_invocation_id: str | None = Field(
        default=None, description="ID of the invocation this repair attempt was fixing."
    )


class ParticipantExcludedPayload(BaseModel):
    """Payload for a participant_excluded event."""

    reason_code: str = Field(description="Machine-readable exclusion reason.")
    reason_summary: str = Field(description="Human-readable explanation of the exclusion.")
    failed_invocation_id: str = Field(description="ID of the invocation that triggered exclusion.")
    remaining_active_participant_count: int = Field(
        description="Number of active participants after exclusion."
    )
    quorum_preserved: bool = Field(description="Whether enough participants remain for consensus.")


class RoundStartedPayload(BaseModel):
    """Payload for a round_started event."""

    round: int = Field(description="Round number (1-based).")
    candidate_id: str = Field(description="ID of the candidate entering this round.")
    framing_version: int = Field(description="Active task framing version.")
    target_participant_count: int = Field(description="Number of participants targeted.")


class RoundCompletedPayload(BaseModel):
    """Payload for a round_completed event."""

    round: int = Field(description="Round number (1-based).")
    candidate_id: str = Field(description="ID of the candidate reviewed in this round.")
    framing_version: int = Field(description="Active task framing version.")
    review_executed: bool = Field(description="Whether participant review occurred this round.")
    approve_count: int | None = Field(default=None, description="Number of approvals.")
    minor_revise_count: int | None = Field(
        default=None, description="Number of minor revision requests."
    )
    major_revise_count: int | None = Field(
        default=None, description="Number of major revision requests."
    )
    reject_count: int | None = Field(default=None, description="Number of rejections.")
    candidate_invalidated_by_framing_update: bool = Field(
        default=False,
        description="Whether the candidate was invalidated by a framing update this round.",
    )
    will_continue: bool = Field(description="Whether another round will follow.")


class CandidateCreatedPayload(BaseModel):
    """Payload for a candidate_created event."""

    candidate_id: str = Field(description="Unique candidate identifier.")
    framing_version: int = Field(description="Task framing version used for synthesis.")
    source: CandidateSource = Field(description="How the candidate was produced.")
    text: str = Field(description="Full text of the candidate answer.")
    summary: str = Field(description="Brief summary of the candidate.")
    excerpt_count: int = Field(description="Number of participant excerpts used in synthesis.")


class CandidateUpdatedPayload(BaseModel):
    """Payload for a candidate_updated event."""

    candidate_id: str = Field(description="ID of the new candidate version.")
    previous_candidate_id: str = Field(description="ID of the candidate this one replaces.")
    framing_version: int = Field(description="Task framing version used for revision.")
    source: CandidateSource = Field(description="How the updated candidate was produced.")
    text: str = Field(description="Full text of the updated candidate answer.")
    summary: str = Field(description="Brief summary of what changed.")


class ReviewStartedPayload(BaseModel):
    """Payload for a review_started event."""

    candidate_id: str = Field(description="ID of the candidate being reviewed.")
    framing_version: int = Field(description="Active task framing version.")
    target_participant_count: int = Field(description="Number of reviewers targeted.")


class ReviewCompletedPayload(BaseModel):
    """Payload for a review_completed event."""

    candidate_id: str = Field(description="ID of the candidate that was reviewed.")
    framing_version: int = Field(description="Active task framing version.")
    reviewer_count: int = Field(description="Number of reviewers that participated.")
    approve_count: int = Field(description="Number of approvals.")
    minor_revise_count: int = Field(description="Number of minor revision requests.")
    major_revise_count: int = Field(description="Number of major revision requests.")
    reject_count: int = Field(description="Number of rejections.")
    blocking_issue_summaries: list[str] = Field(
        default=[], description="Summaries of blocking issues raised."
    )
    minor_improvement_summaries: list[str] = Field(
        default=[], description="Summaries of suggested minor improvements."
    )


class ReleaseGateStartedPayload(BaseModel):
    """Payload for a release_gate_started event."""

    invocation_id: str = Field(description="ID of the release gate invocation.")
    mode: ReleaseGateMode = Field(description="Release gate mode.")
    candidate_id: str = Field(description="ID of the candidate being evaluated.")
    framing_version: int = Field(description="Active task framing version.")


class ReleaseGateCompletedPayload(BaseModel):
    """Payload for a release_gate_completed event."""

    invocation_id: str = Field(description="ID of the release gate invocation.")
    candidate_id: str = Field(description="ID of the candidate that was evaluated.")
    framing_version: int = Field(description="Active task framing version.")
    executed: bool = Field(description="Whether the gate check was actually performed.")
    decision: ReleaseGateDecision = Field(description="Quality-gate verdict.")
    summary: str = Field(description="Explanation of the decision.")
    minor_fixes_applied: list[str] = Field(
        default=[], description="Minor fixes applied before release."
    )
    blocking_issues: list[str] = Field(default=[], description="Issues that blocked release.")


class UsageReportedPayload(BaseModel):
    """Payload for a usage_reported event."""

    scope: UsageScope = Field(description="Whether this covers one invocation or the full run.")
    invocation_id: str | None = Field(
        default=None, description="Invocation ID, if scope is 'invocation'."
    )
    usage: UsageSnapshot = Field(description="Token and cost totals.")


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
"""Union of all event payload types."""

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
"""Maps EventType string values to their corresponding payload class."""


class EventEnvelope(BaseModel):
    """Common envelope fields for all events — use ApplicationEvent for validated instances."""

    event_id: str = Field(description="Unique event identifier.")
    command_id: str = Field(description="ID of the command that triggered this event.")
    run_id: str | None = Field(default=None, description="Run ID, if this event belongs to a run.")
    sequence: int = Field(description="Monotonically increasing sequence number within a command.")
    timestamp: str = Field(description="ISO 8601 timestamp of when the event was emitted.")
    type: EventType = Field(description="Event type discriminator.")
    phase: Phase = Field(description="Pipeline phase in which this event occurred.")
    round: int | None = Field(default=None, description="Consensus round number, if applicable.")
    role: Role = Field(description="Actor role that produced this event.")
    model: str | None = Field(
        default=None, description="OpenRouter model ID, if the event involves a specific model."
    )


class ApplicationEvent(EventEnvelope):
    """Full event with typed, discriminated payload.

    The ``_resolve_payload`` validator uses the envelope's ``type`` field
    to look up the correct payload class from ``PAYLOAD_MAP`` and validates
    the raw payload dict into the typed model before Pydantic processes
    the rest of the envelope.
    """

    payload: EventPayload = Field(description="Typed event payload, resolved from the type field.")

    @model_validator(mode="before")
    @classmethod
    def _resolve_payload(cls, data: dict[str, object]) -> dict[str, object]:
        """Resolve the payload dict to the correct typed model based on the event type."""
        event_type = str(data.get("type", ""))
        payload_raw = data.get("payload")
        if isinstance(payload_raw, dict):
            payload_cls = PAYLOAD_MAP.get(event_type)
            if payload_cls is not None:
                data = {**data, "payload": payload_cls.model_validate(payload_raw)}
        return data
