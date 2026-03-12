"""Terminal result models for commands."""

from pydantic import BaseModel

from nelson.protocols.domain import ErrorObject, ExcludedParticipant, UsageSnapshot
from nelson.protocols.enums import (
    ConsensusStatus,
    ReleaseGateDecision,
    ReleaseGateMode,
    RunStatus,
    Sensitivity,
    TaskType,
)

# ── Auth results ────────────────────────────────────────────────────────


class AuthSetResult(BaseModel):
    saved: bool
    storage_path: str


class AuthStatusResult(BaseModel):
    saved_key_present: bool
    env_key_present: bool
    effective_source: str
    verification: str
    key_label: str | None = None
    remaining_limit: float | None = None
    is_free_tier: bool | None = None


class AuthClearResult(BaseModel):
    saved_key_removed: bool


# ── RunResult sub-objects ───────────────────────────────────────────────


class RunInputInfo(BaseModel):
    source: str
    prompt_chars: int
    prompt_file: str | None = None


class RunModelsInfo(BaseModel):
    participants: list[str]
    moderator: str
    excluded_participants: list[ExcludedParticipant] = []


class RunTaskFramingInfo(BaseModel):
    task_type: TaskType
    sensitivity: Sensitivity
    objective: str
    quality_criteria: list[str]
    aspects_to_cover: list[str]
    ambiguities: list[str] = []
    assumptions: list[str] = []
    framing_version: int


class RunConsensusInfo(BaseModel):
    status: ConsensusStatus
    rounds_completed: int
    max_rounds: int
    minor_revisions_applied: list[str] = []
    blocking_issues_resolved: list[str] = []
    residual_disagreements: list[str] = []


class RunReleaseGateInfo(BaseModel):
    mode: ReleaseGateMode
    executed: bool
    decision: ReleaseGateDecision
    summary: str
    minor_fixes_applied: list[str] = []
    blocking_issues: list[str] = []


class RunInvocationUsage(BaseModel):
    invocation_id: str
    model: str
    role: str
    purpose: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    currency: str = "USD"
    is_normalized: bool = True
    is_complete: bool = True


class RunUsageInfo(BaseModel):
    per_invocation: list[RunInvocationUsage] = []
    total: UsageSnapshot


class RunTimingInfo(BaseModel):
    started_at: str
    completed_at: str
    duration_ms: int


class RunResultError(ErrorObject):
    phase: str


# ── RunResult ───────────────────────────────────────────────────────────


class RunResult(BaseModel):
    run_id: str | None
    status: RunStatus
    error: RunResultError | None = None
    input: RunInputInfo
    models: RunModelsInfo
    task_framing: RunTaskFramingInfo | None
    consensus: RunConsensusInfo
    release_gate: RunReleaseGateInfo
    final_answer: str | None
    usage: RunUsageInfo
    timing: RunTimingInfo


CommandResult = RunResult | AuthSetResult | AuthStatusResult | AuthClearResult
