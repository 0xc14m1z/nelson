"""Terminal result models for commands."""

from pydantic import BaseModel, Field

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
    """Result of saving an OpenRouter API key."""

    saved: bool = Field(description="Whether the key was saved successfully.")
    storage_path: str = Field(description="Filesystem path where the key was saved.")


class AuthStatusResult(BaseModel):
    """Result of checking credential status."""

    saved_key_present: bool = Field(description="Whether a saved key exists on disk.")
    env_key_present: bool = Field(description="Whether an env var key is set.")
    effective_source: str = Field(description="Which key source is active: saved, env, or none.")
    verification: str = Field(
        description="Key verification result: valid, invalid, or not_checked."
    )
    key_label: str | None = Field(
        default=None, description="Masked label for the active key (e.g. 'sk-or-...xyz')."
    )
    remaining_limit: float | None = Field(
        default=None, description="Remaining credit limit, if available."
    )
    is_free_tier: bool | None = Field(
        default=None, description="Whether the key belongs to a free-tier account."
    )


class AuthClearResult(BaseModel):
    """Result of removing the saved API key."""

    saved_key_removed: bool = Field(description="Whether a saved key was actually removed.")


# ── RunResult sub-objects ───────────────────────────────────────────────


class RunInputInfo(BaseModel):
    """Describes how the user's prompt was provided."""

    source: str = Field(description="Input source: prompt, prompt_file, or stdin.")
    prompt_chars: int = Field(description="Character count of the prompt text.")
    prompt_file: str | None = Field(
        default=None, description="Path to the prompt file, if source is prompt_file."
    )


class RunModelsInfo(BaseModel):
    """Models involved in the run."""

    participants: list[str] = Field(description="OpenRouter model IDs of participants.")
    moderator: str = Field(description="OpenRouter model ID of the moderator.")
    excluded_participants: list[ExcludedParticipant] = Field(
        default=[], description="Participants excluded during the run."
    )


class RunTaskFramingInfo(BaseModel):
    """Final task framing that governed the run."""

    task_type: TaskType = Field(description="Category assigned to the task.")
    sensitivity: Sensitivity = Field(description="Content sensitivity level.")
    objective: str = Field(description="Concise statement of the task objective.")
    quality_criteria: list[str] = Field(description="Criteria for evaluating candidates.")
    aspects_to_cover: list[str] = Field(description="Topics the answer must address.")
    ambiguities: list[str] = Field(default=[], description="Ambiguities identified in the prompt.")
    assumptions: list[str] = Field(
        default=[], description="Assumptions made to resolve ambiguities."
    )
    framing_version: int = Field(description="Final task framing version number.")


class RunConsensusInfo(BaseModel):
    """Summary of the consensus process outcome."""

    status: ConsensusStatus = Field(description="Final consensus status.")
    rounds_completed: int = Field(description="Number of consensus rounds completed.")
    max_rounds: int = Field(description="Maximum rounds that were configured.")
    minor_revisions_applied: list[str] = Field(
        default=[], description="Minor revisions applied during consensus."
    )
    blocking_issues_resolved: list[str] = Field(
        default=[], description="Blocking issues that were resolved."
    )
    residual_disagreements: list[str] = Field(
        default=[], description="Disagreements that remained unresolved."
    )


class RunReleaseGateInfo(BaseModel):
    """Release gate outcome."""

    mode: ReleaseGateMode = Field(description="Release gate mode that was configured.")
    executed: bool = Field(description="Whether the gate check was actually performed.")
    decision: ReleaseGateDecision = Field(description="Quality-gate verdict.")
    summary: str = Field(description="Explanation of the decision.")
    minor_fixes_applied: list[str] = Field(
        default=[], description="Minor fixes applied before release."
    )
    blocking_issues: list[str] = Field(default=[], description="Issues that blocked release.")


class RunInvocationUsage(BaseModel):
    """Token and cost breakdown for a single model invocation."""

    invocation_id: str = Field(description="Unique invocation identifier.")
    model: str = Field(description="OpenRouter model ID.")
    role: str = Field(description="Role of the invoker: participant or moderator.")
    purpose: str = Field(description="Why the invocation was made.")
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
        description="Whether this usage record is complete.",
    )


class RunUsageInfo(BaseModel):
    """Aggregated usage for an entire run."""

    per_invocation: list[RunInvocationUsage] = Field(
        default=[], description="Per-invocation usage breakdown."
    )
    total: UsageSnapshot = Field(description="Aggregated totals across all invocations.")


class RunTimingInfo(BaseModel):
    """Wall-clock timing for a run."""

    started_at: str = Field(description="ISO 8601 timestamp when the run started.")
    completed_at: str = Field(description="ISO 8601 timestamp when the run completed.")
    duration_ms: int = Field(description="Total run duration in milliseconds.")


class RunResultError(ErrorObject):
    """Error details for a failed run, including the phase where failure occurred."""

    phase: str = Field(description="Pipeline phase where the failure occurred.")


# ── RunResult ───────────────────────────────────────────────────────────


class RunResult(BaseModel):
    """Terminal result of a consensus run."""

    run_id: str | None = Field(description="Unique run identifier.")
    status: RunStatus = Field(description="Terminal run status.")
    error: RunResultError | None = Field(
        default=None, description="Error details, if the run failed."
    )
    input: RunInputInfo = Field(description="How the prompt was provided.")
    models: RunModelsInfo = Field(description="Models involved in the run.")
    task_framing: RunTaskFramingInfo | None = Field(
        description="Final task framing, if framing was reached."
    )
    consensus: RunConsensusInfo = Field(description="Consensus process outcome.")
    release_gate: RunReleaseGateInfo = Field(description="Release gate outcome.")
    final_answer: str | None = Field(
        description="The final deliverable answer, or None if the run failed."
    )
    usage: RunUsageInfo = Field(description="Token and cost usage.")
    timing: RunTimingInfo = Field(description="Wall-clock timing.")


CommandResult = RunResult | AuthSetResult | AuthStatusResult | AuthClearResult
"""Union of all terminal command result types."""
