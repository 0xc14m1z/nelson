"""Event stream ordering tests (T-PROTO-002, T-EVENT-005).

Verifies that the event stream from a happy-path consensus run follows
the ordering rules defined in EVENT_SCHEMA §5 and APPLICATION_PROTOCOL §10.
"""

from nelson.protocols.enums import EventType, InvocationPurpose
from nelson.protocols.events import (
    ApplicationEvent,
    ModelCompletedPayload,
    ModelStartedPayload,
)
from nelson.providers.fake import FakeProvider

from .conftest import run_happy_path


def _purpose_of(event: ApplicationEvent) -> InvocationPurpose | None:
    """Extract the invocation purpose from a model event, or None."""
    payload = event.payload
    if isinstance(payload, ModelStartedPayload | ModelCompletedPayload):
        return payload.purpose
    return None


async def test_event_stream_starts_with_command_received(
    happy_path_provider: FakeProvider,
) -> None:
    """First event type must be command_received."""
    events, _result = await run_happy_path(happy_path_provider)
    assert len(events) > 0
    assert events[0].type == EventType.COMMAND_RECEIVED


async def test_run_started_follows_command_received(
    happy_path_provider: FakeProvider,
) -> None:
    """run_started must come immediately after command_received."""
    events, _result = await run_happy_path(happy_path_provider)
    types = [e.type for e in events]
    cmd_idx = types.index(EventType.COMMAND_RECEIVED)
    run_idx = types.index(EventType.RUN_STARTED)
    assert run_idx == cmd_idx + 1


async def test_run_completed_before_command_completed(
    happy_path_provider: FakeProvider,
) -> None:
    """run_completed must appear before command_completed."""
    events, _result = await run_happy_path(happy_path_provider)
    types = [e.type for e in events]
    run_completed_idx = types.index(EventType.RUN_COMPLETED)
    cmd_completed_idx = types.index(EventType.COMMAND_COMPLETED)
    assert run_completed_idx < cmd_completed_idx


async def test_task_framing_events_before_contributions(
    happy_path_provider: FakeProvider,
) -> None:
    """task_framing_completed must appear before model_started for participants."""
    events, _result = await run_happy_path(happy_path_provider)
    types = [e.type for e in events]
    framing_completed_idx = types.index(EventType.TASK_FRAMING_COMPLETED)
    # Find the first model_started for a participant contribution
    for i, event in enumerate(events):
        if event.type == EventType.MODEL_STARTED:
            payload = event.payload
            if (
                isinstance(payload, ModelStartedPayload)
                and payload.purpose == InvocationPurpose.INITIAL_CONTRIBUTION
            ):
                assert i > framing_completed_idx, (
                    f"model_started for contribution at index {i} "
                    f"must come after task_framing_completed at index {framing_completed_idx}"
                )
                return
    # If we get here, no contribution model_started was found — that's a test failure
    raise AssertionError("No model_started event with purpose=initial_contribution found")


async def test_parallel_contributions_started_before_completed(
    happy_path_provider: FakeProvider,
) -> None:
    """All contribution MODEL_STARTED events must appear before any
    contribution MODEL_COMPLETED — validates the parallel gather pattern."""
    events, _result = await run_happy_path(happy_path_provider)
    contrib_started_indices: list[int] = []
    contrib_completed_indices: list[int] = []
    for i, event in enumerate(events):
        if _purpose_of(event) != InvocationPurpose.INITIAL_CONTRIBUTION:
            continue
        if isinstance(event.payload, ModelStartedPayload):
            contrib_started_indices.append(i)
        elif isinstance(event.payload, ModelCompletedPayload):
            contrib_completed_indices.append(i)
    assert len(contrib_started_indices) >= 2, "Expected at least 2 contribution starts"
    assert len(contrib_completed_indices) >= 2, "Expected at least 2 contribution completions"
    # Every MODEL_STARTED must come before every MODEL_COMPLETED
    assert max(contrib_started_indices) < min(contrib_completed_indices)


async def test_parallel_reviews_started_before_completed(
    happy_path_provider: FakeProvider,
) -> None:
    """All review MODEL_STARTED events must appear before any
    review MODEL_COMPLETED — validates the parallel gather pattern."""
    events, _result = await run_happy_path(happy_path_provider)
    review_started_indices: list[int] = []
    review_completed_indices: list[int] = []
    for i, event in enumerate(events):
        if _purpose_of(event) != InvocationPurpose.CANDIDATE_REVIEW:
            continue
        if isinstance(event.payload, ModelStartedPayload):
            review_started_indices.append(i)
        elif isinstance(event.payload, ModelCompletedPayload):
            review_completed_indices.append(i)
    assert len(review_started_indices) >= 2, "Expected at least 2 review starts"
    assert len(review_completed_indices) >= 2, "Expected at least 2 review completions"
    assert max(review_started_indices) < min(review_completed_indices)


async def test_no_model_delta_for_structured_internal_phases(
    happy_path_provider: FakeProvider,
) -> None:
    """Structured internal phases (framing, contribution, synthesis, review, gate)
    must not emit model_delta events — only streaming phases emit deltas.

    In the happy path with FakeProvider.invoke() (non-streaming), no deltas
    should appear at all.
    """
    events, _result = await run_happy_path(happy_path_provider)
    delta_events = [e for e in events if e.type == EventType.MODEL_DELTA]
    assert delta_events == [], f"Expected no model_delta events, got {len(delta_events)}"
