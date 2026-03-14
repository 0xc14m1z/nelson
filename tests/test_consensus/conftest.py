"""Shared fixtures for consensus tests.

Provides a FakeProvider configured for the happy-path consensus flow
and a helper to run the orchestrator and collect results.
"""

import json

import pytest

from nelson.core.events import EventEmitter
from nelson.protocols.domain import UsageSnapshot
from nelson.protocols.enums import ReleaseGateMode
from nelson.protocols.events import ApplicationEvent
from nelson.protocols.results import RunResult
from nelson.providers.base import ProviderResponse
from nelson.providers.fake import FakeProvider
from nelson.utils.ids import make_command_id, make_run_id

# ── Canned response builders ─────────────────────────────────────────


def framing_response() -> ProviderResponse:
    """Moderator task framing response."""
    data: dict[str, object] = {
        "task_type": "analytical",
        "sensitivity": "low",
        "objective": "Provide a clear explanation of the topic",
        "quality_criteria": ["accuracy", "clarity", "completeness"],
        "aspects_to_cover": ["definition", "key concepts", "examples"],
        "ambiguities": [],
        "assumptions": ["The user wants a general overview"],
    }
    return ProviderResponse(
        content=json.dumps(data),
        parsed=data,
        usage=UsageSnapshot(prompt_tokens=200, completion_tokens=80, total_tokens=280),
    )


def contribution_response(label: str = "A") -> ProviderResponse:
    """Participant contribution response."""
    data: dict[str, object] = {
        "answer_markdown": f"Participant {label}'s detailed answer about the topic.",
        "assumptions": ["General audience assumed"],
        "limitations": ["Limited to common knowledge"],
        "framing_feedback": {
            "status": "accept",
            "notes": [],
            "proposed_aspects": [],
        },
    }
    return ProviderResponse(
        content=json.dumps(data),
        parsed=data,
        usage=UsageSnapshot(prompt_tokens=300, completion_tokens=150, total_tokens=450),
    )


def synthesis_response() -> ProviderResponse:
    """Moderator candidate synthesis response."""
    data: dict[str, object] = {
        "candidate_markdown": (
            "A comprehensive synthesized answer combining the best of both contributions."
        ),
        "summary": "Combined key points from both participants",
        "relevant_excerpt_labels": ["response_a", "response_b"],
        "framing_update": None,
    }
    return ProviderResponse(
        content=json.dumps(data),
        parsed=data,
        usage=UsageSnapshot(prompt_tokens=500, completion_tokens=200, total_tokens=700),
    )


def review_approve_response() -> ProviderResponse:
    """Participant review response with approval."""
    data: dict[str, object] = {
        "decision": "approve",
        "summary": "The candidate answer is accurate and complete",
        "required_changes": [],
        "optional_improvements": [],
        "blocking_issues": [],
    }
    return ProviderResponse(
        content=json.dumps(data),
        parsed=data,
        usage=UsageSnapshot(prompt_tokens=400, completion_tokens=60, total_tokens=460),
    )


def release_gate_response() -> ProviderResponse:
    """Moderator release gate response with pass."""
    data: dict[str, object] = {
        "decision": "pass",
        "summary": "The answer is ready for delivery",
        "minor_fixes_applied": [],
        "blocking_issues": [],
        "final_answer_markdown": (
            "The final, polished answer about the topic with all key points covered."
        ),
    }
    return ProviderResponse(
        content=json.dumps(data),
        parsed=data,
        usage=UsageSnapshot(prompt_tokens=600, completion_tokens=100, total_tokens=700),
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
