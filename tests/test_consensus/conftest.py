"""Shared fixtures for consensus tests.

Provides a FakeProvider configured for the happy-path consensus flow
and a helper to run the orchestrator and collect results.
"""

import pytest
from pydantic import BaseModel

from nelson.core.events import EventEmitter
from nelson.protocols.domain import (
    CandidateSynthesisResult,
    FramingFeedback,
    ParticipantContribution,
    ReleaseGateResult,
    ReviewResult,
    TaskFramingResult,
    UsageSnapshot,
)
from nelson.protocols.enums import (
    Adapter,
    FramingFeedbackStatus,
    ReleaseGateDecision,
    ReleaseGateMode,
    ReviewDecision,
    Sensitivity,
    TaskType,
)
from nelson.protocols.events import ApplicationEvent
from nelson.protocols.results import RunResult
from nelson.providers.base import ProviderResponse
from nelson.providers.fake import FakeProvider
from nelson.utils.ids import make_command_id, make_run_id

# ── Helpers ───────────────────────────────────────────────────────────

# Default participants used across all consensus test helpers
DEFAULT_PARTICIPANTS = ["openai/gpt-4", "anthropic/claude-3-opus"]
DEFAULT_MODERATOR = "openai/gpt-4"


def _model_to_response(
    model: BaseModel,
    *,
    usage: UsageSnapshot,
) -> ProviderResponse:
    """Convert a Pydantic domain model to a ProviderResponse.

    Simulates what a real provider returns: the JSON string as content
    and the parsed dict as structured output.
    """
    return ProviderResponse(
        content=model.model_dump_json(),
        parsed=model.model_dump(),  # type: ignore[arg-type]  # dict invariance
        usage=usage,
    )


# ── Default usage snapshot ───────────────────────────────────────────

_DEFAULT_USAGE = UsageSnapshot(
    prompt_tokens=100, completion_tokens=50, total_tokens=150,
)


# ── Canned response builders ─────────────────────────────────────────


def framing_response() -> ProviderResponse:
    """Moderator task framing response."""
    return _model_to_response(
        TaskFramingResult(
            task_type=TaskType.ANALYTICAL,
            sensitivity=Sensitivity.LOW,
            objective="Provide a clear explanation of the topic",
            quality_criteria=["accuracy", "clarity", "completeness"],
            aspects_to_cover=["definition", "key concepts", "examples"],
            assumptions=["The user wants a general overview"],
        ),
        usage=UsageSnapshot(
            prompt_tokens=200, completion_tokens=80, total_tokens=280,
        ),
    )


def contribution_response(label: str = "A") -> ProviderResponse:
    """Participant contribution response."""
    return _model_to_response(
        ParticipantContribution(
            answer_markdown=f"Participant {label}'s detailed answer about the topic.",
            assumptions=["General audience assumed"],
            limitations=["Limited to common knowledge"],
            framing_feedback=FramingFeedback(
                status=FramingFeedbackStatus.ACCEPT,
            ),
        ),
        usage=UsageSnapshot(
            prompt_tokens=300, completion_tokens=150, total_tokens=450,
        ),
    )


def synthesis_response() -> ProviderResponse:
    """Moderator candidate synthesis response (no framing update)."""
    return _model_to_response(
        CandidateSynthesisResult(
            candidate_markdown=(
                "A comprehensive synthesized answer combining "
                "the best of both contributions."
            ),
            summary="Combined key points from both participants",
            relevant_excerpt_labels=["response_a", "response_b"],
        ),
        usage=UsageSnapshot(
            prompt_tokens=500, completion_tokens=200, total_tokens=700,
        ),
    )


def synthesis_with_framing_update() -> ProviderResponse:
    """Moderator synthesis that triggers a material framing update (PROMPT_SPEC §6.3).

    The framing_update field is non-null, which signals to the orchestrator
    that the current candidate is invalidated and a new contribution round
    must begin under the updated framing.
    """
    return _model_to_response(
        CandidateSynthesisResult(
            candidate_markdown="This candidate is invalidated by framing update.",
            summary="Framing update required: deployment caveats missing",
            relevant_excerpt_labels=["response_a"],
            framing_update=TaskFramingResult(
                task_type=TaskType.ANALYTICAL,
                sensitivity=Sensitivity.MEDIUM,
                objective="Provide a clear explanation including deployment caveats",
                quality_criteria=["accuracy", "clarity", "completeness"],
                aspects_to_cover=["definition", "key concepts", "examples", "deployment caveats"],
                assumptions=["The user wants practical guidance"],
            ),
        ),
        usage=_DEFAULT_USAGE,
    )


def review_major_revise_response() -> ProviderResponse:
    """Participant review requesting major revision (blocking)."""
    return _model_to_response(
        ReviewResult(
            decision=ReviewDecision.MAJOR_REVISE,
            summary="The candidate has a significant factual error",
            required_changes=["Correct the claim about deployment defaults"],
            blocking_issues=["Unsupported technical claim about deployment"],
        ),
        usage=_DEFAULT_USAGE,
    )


def review_reject_response() -> ProviderResponse:
    """Participant review that rejects the candidate (blocking)."""
    return _model_to_response(
        ReviewResult(
            decision=ReviewDecision.REJECT,
            summary="The candidate is fundamentally wrong",
            required_changes=["Rewrite the entire answer"],
            blocking_issues=["Core premise is incorrect"],
        ),
        usage=_DEFAULT_USAGE,
    )


def review_minor_revise_response() -> ProviderResponse:
    """Participant review requesting minor revision (non-blocking)."""
    return _model_to_response(
        ReviewResult(
            decision=ReviewDecision.MINOR_REVISE,
            summary="Could use some polish",
            optional_improvements=["Clarify packaging recommendation"],
        ),
        usage=_DEFAULT_USAGE,
    )


def review_approve_response() -> ProviderResponse:
    """Participant review response with approval."""
    return _model_to_response(
        ReviewResult(
            decision=ReviewDecision.APPROVE,
            summary="The candidate answer is accurate and complete",
        ),
        usage=UsageSnapshot(
            prompt_tokens=400, completion_tokens=60, total_tokens=460,
        ),
    )


def release_gate_response() -> ProviderResponse:
    """Moderator release gate response with pass."""
    return _model_to_response(
        ReleaseGateResult(
            decision=ReleaseGateDecision.PASS,
            summary="The answer is ready for delivery",
            final_answer_markdown=(
                "The final, polished answer about the topic "
                "with all key points covered."
            ),
        ),
        usage=UsageSnapshot(
            prompt_tokens=600, completion_tokens=100, total_tokens=700,
        ),
    )


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def happy_path_provider() -> FakeProvider:
    """FakeProvider configured for a 2-participant happy-path consensus run.

    Call order: framing, contribution x2, synthesis, review x2, release gate.
    """
    return FakeProvider(
        responses=[
            framing_response(),
            contribution_response("A"),
            contribution_response("B"),
            synthesis_response(),
            review_approve_response(),
            review_approve_response(),
            release_gate_response(),
        ]
    )


async def run_consensus_helper(
    provider: FakeProvider,
    *,
    release_gate_mode: ReleaseGateMode = ReleaseGateMode.AUTO,
    max_rounds: int = 10,
    participants: list[str] | None = None,
    moderator: str | None = None,
) -> tuple[list[ApplicationEvent], RunResult]:
    """Run the orchestrator with the given provider and return events + result.

    This helper centralizes the orchestrator call so all consensus tests
    use the same setup. Supports overriding participants and moderator
    for tests that need different configurations.
    """
    from nelson.consensus.orchestrator import run_consensus

    emitter = EventEmitter(command_id=make_command_id(), run_id=make_run_id())
    result = await run_consensus(
        prompt_text="What is Python?",
        participants=participants or DEFAULT_PARTICIPANTS,
        moderator=moderator or DEFAULT_MODERATOR,
        max_rounds=max_rounds,
        release_gate_mode=release_gate_mode,
        adapter=Adapter.CLI,
        provider=provider,
        emitter=emitter,
    )
    emitter.close()
    events: list[ApplicationEvent] = []
    async for event in emitter:
        events.append(event)
    return events, result


# Backward-compat alias for existing happy-path tests
async def run_happy_path(
    provider: FakeProvider,
    *,
    release_gate_mode: ReleaseGateMode = ReleaseGateMode.AUTO,
    max_rounds: int = 10,
) -> tuple[list[ApplicationEvent], RunResult]:
    """Run the orchestrator for happy-path tests (convenience wrapper)."""
    return await run_consensus_helper(
        provider,
        release_gate_mode=release_gate_mode,
        max_rounds=max_rounds,
    )
