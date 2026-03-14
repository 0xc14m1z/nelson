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
    """Moderator candidate synthesis response."""
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


async def run_happy_path(
    provider: FakeProvider,
    *,
    release_gate_mode: ReleaseGateMode = ReleaseGateMode.AUTO,
    max_rounds: int = 10,
) -> tuple[list[ApplicationEvent], RunResult]:
    """Run the orchestrator with the given provider and return events + result.

    This helper centralizes the orchestrator call so all consensus tests
    use the same setup.
    """
    from nelson.consensus.orchestrator import run_consensus

    emitter = EventEmitter(command_id=make_command_id(), run_id=make_run_id())
    result = await run_consensus(
        prompt_text="What is Python?",
        participants=["openai/gpt-4", "anthropic/claude-3-opus"],
        moderator="openai/gpt-4",
        max_rounds=max_rounds,
        release_gate_mode=release_gate_mode,
        provider=provider,
        emitter=emitter,
    )
    emitter.close()
    events: list[ApplicationEvent] = []
    async for event in emitter:
        events.append(event)
    return events, result
