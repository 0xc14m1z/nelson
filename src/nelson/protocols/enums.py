"""Enums shared across all protocol models."""

from enum import StrEnum


class Phase(StrEnum):
    """Pipeline phase in which an event occurs."""

    COMMAND = "command"
    AUTH = "auth"
    STARTUP = "startup"
    TASK_FRAMING = "task_framing"
    PARTICIPANT_GENERATION = "participant_generation"
    CANDIDATE_SYNTHESIS = "candidate_synthesis"
    PARTICIPANT_REVIEW = "participant_review"
    RELEASE_GATE = "release_gate"
    FINALIZATION = "finalization"
    ERROR = "error"


class Role(StrEnum):
    """Actor role that produced an event."""

    SYSTEM = "system"
    PARTICIPANT = "participant"
    MODERATOR = "moderator"


class EventType(StrEnum):
    """Discriminator for all application event types."""

    COMMAND_RECEIVED = "command_received"
    COMMAND_COMPLETED = "command_completed"
    COMMAND_FAILED = "command_failed"
    AUTH_KEY_SAVED = "auth_key_saved"
    AUTH_STATUS_REPORTED = "auth_status_reported"
    AUTH_KEY_CLEARED = "auth_key_cleared"
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    PROGRESS_UPDATED = "progress_updated"
    CONSENSUS_PENDING = "consensus_pending"
    CONSENSUS_REACHED = "consensus_reached"
    CONSENSUS_PARTIAL = "consensus_partial"
    TASK_FRAMING_STARTED = "task_framing_started"
    TASK_FRAMING_COMPLETED = "task_framing_completed"
    TASK_FRAMING_UPDATED = "task_framing_updated"
    MODEL_STARTED = "model_started"
    MODEL_DELTA = "model_delta"
    MODEL_COMPLETED = "model_completed"
    MODEL_FAILED = "model_failed"
    PARTICIPANT_EXCLUDED = "participant_excluded"
    ROUND_STARTED = "round_started"
    ROUND_COMPLETED = "round_completed"
    CANDIDATE_CREATED = "candidate_created"
    CANDIDATE_UPDATED = "candidate_updated"
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    RELEASE_GATE_STARTED = "release_gate_started"
    RELEASE_GATE_COMPLETED = "release_gate_completed"
    USAGE_REPORTED = "usage_reported"


class InvocationPurpose(StrEnum):
    """Why a model invocation was made."""

    TASK_FRAMING = "task_framing"
    INITIAL_CONTRIBUTION = "initial_contribution"
    REFRAMED_CONTRIBUTION = "reframed_contribution"
    CANDIDATE_SYNTHESIS = "candidate_synthesis"
    CANDIDATE_REVIEW = "candidate_review"
    RELEASE_GATE = "release_gate"
    REPAIR = "repair"


class CommandType(StrEnum):
    """Application command discriminator."""

    AUTH_SET = "auth_set"
    AUTH_STATUS = "auth_status"
    AUTH_CLEAR = "auth_clear"
    RUN = "run"


class InputSource(StrEnum):
    """How the user's prompt was provided."""

    PROMPT = "prompt"
    PROMPT_FILE = "prompt_file"
    STDIN = "stdin"


class TaskType(StrEnum):
    """Category assigned to the user's task by the moderator."""

    FACTUAL = "factual"
    COMPARATIVE = "comparative"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    ADVICE = "advice"
    PLANNING = "planning"
    CLASSIFICATION = "classification"
    TRANSFORMATION = "transformation"
    OTHER = "other"


class Sensitivity(StrEnum):
    """Content sensitivity level determined by the moderator."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FramingFeedbackStatus(StrEnum):
    """Participant's assessment of the task framing."""

    ACCEPT = "accept"
    MINOR_ISSUE = "minor_issue"
    MAJOR_ISSUE = "major_issue"


class ReviewDecision(StrEnum):
    """Participant's verdict on a candidate answer."""

    APPROVE = "approve"
    MINOR_REVISE = "minor_revise"
    MAJOR_REVISE = "major_revise"
    REJECT = "reject"


class RunStatus(StrEnum):
    """Terminal status of a consensus run."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ConsensusStatus(StrEnum):
    """Outcome of the consensus process."""

    REACHED = "reached"
    PARTIAL = "partial"
    FAILED = "failed"


class ReleaseGateMode(StrEnum):
    """Controls whether the moderator performs a final quality check."""

    OFF = "off"
    AUTO = "auto"
    ON = "on"


class ReleaseGateDecision(StrEnum):
    """Moderator's final quality-gate verdict."""

    SKIPPED = "skipped"
    PASS = "pass"
    PASS_WITH_MINOR_FIXES = "pass_with_minor_fixes"
    FAIL = "fail"


class CandidateSource(StrEnum):
    """How a candidate answer was produced."""

    INITIAL_SYNTHESIS = "initial_synthesis"
    MAJOR_REVISE_CYCLE = "major_revise_cycle"
    MINOR_REVISE_INCORPORATION = "minor_revise_incorporation"
    RELEASE_GATE_FIX = "release_gate_fix"


class OutputFormat(StrEnum):
    """Format of a model invocation's output."""

    TEXT = "text"
    STRUCTURED = "structured"


class ErrorCode(StrEnum):
    """Machine-readable error codes for ErrorObject (CLI_SPEC §10)."""

    CREDENTIAL_STORAGE_ERROR = "credential_storage_error"
    PROVIDER_AUTH_ERROR = "provider_auth_error"
    PROVIDER_TRANSPORT_ERROR = "provider_transport_error"
    PROVIDER_TIMEOUT = "provider_timeout"
    PARTICIPANT_FAILED = "participant_failed"
    PARTICIPANT_QUORUM_LOST = "participant_quorum_lost"
    FRAMING_UPDATE_BUDGET_EXHAUSTED = "framing_update_budget_exhausted"
    MODERATOR_FAILED = "moderator_failed"
    STRUCTURED_OUTPUT_INVALID = "structured_output_invalid"
    STRUCTURED_OUTPUT_REPAIR_FAILED = "structured_output_repair_failed"
    SERIALIZATION_FAILED = "serialization_failed"
    INTERRUPTED = "interrupted"


class FinishReason(StrEnum):
    """Why a model invocation stopped generating tokens."""

    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    TOOL_CALLS = "tool_calls"
    ERROR = "error"


class Adapter(StrEnum):
    """Interface that originated a command."""

    CLI = "cli"


class UsageScope(StrEnum):
    """Granularity of a usage report."""

    INVOCATION = "invocation"
    RUN_TOTAL = "run_total"
