"""Enums shared across all protocol models."""

from enum import StrEnum


class Phase(StrEnum):
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
    SYSTEM = "system"
    PARTICIPANT = "participant"
    MODERATOR = "moderator"


class EventType(StrEnum):
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
    TASK_FRAMING = "task_framing"
    INITIAL_CONTRIBUTION = "initial_contribution"
    REFRAMED_CONTRIBUTION = "reframed_contribution"
    CANDIDATE_SYNTHESIS = "candidate_synthesis"
    CANDIDATE_REVIEW = "candidate_review"
    RELEASE_GATE = "release_gate"
    REPAIR = "repair"


class CommandType(StrEnum):
    AUTH_SET = "auth_set"
    AUTH_STATUS = "auth_status"
    AUTH_CLEAR = "auth_clear"
    RUN = "run"


class InputSource(StrEnum):
    PROMPT = "prompt"
    PROMPT_FILE = "prompt_file"
    STDIN = "stdin"


class TaskType(StrEnum):
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
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FramingFeedbackStatus(StrEnum):
    ACCEPT = "accept"
    MINOR_ISSUE = "minor_issue"
    MAJOR_ISSUE = "major_issue"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    MINOR_REVISE = "minor_revise"
    MAJOR_REVISE = "major_revise"
    REJECT = "reject"


class RunStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ConsensusStatus(StrEnum):
    REACHED = "reached"
    PARTIAL = "partial"
    FAILED = "failed"


class ReleaseGateMode(StrEnum):
    OFF = "off"
    AUTO = "auto"
    ON = "on"


class ReleaseGateDecision(StrEnum):
    SKIPPED = "skipped"
    PASS = "pass"
    PASS_WITH_MINOR_FIXES = "pass_with_minor_fixes"
    FAIL = "fail"


class CandidateSource(StrEnum):
    INITIAL_SYNTHESIS = "initial_synthesis"
    MAJOR_REVISE_CYCLE = "major_revise_cycle"
    MINOR_REVISE_INCORPORATION = "minor_revise_incorporation"
    RELEASE_GATE_FIX = "release_gate_fix"


class OutputFormat(StrEnum):
    TEXT = "text"
    STRUCTURED = "structured"


class UsageScope(StrEnum):
    INVOCATION = "invocation"
    RUN_TOTAL = "run_total"
