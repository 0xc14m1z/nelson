"""Framing update tests (T-CONS-005).

Tests that material framing changes from the moderator's synthesis
invalidate the current candidate, emit task_framing_updated, and
trigger fresh contributions under the new framing version.
"""

import pytest

from nelson.protocols.enums import (
    EventType,
    InvocationPurpose,
    RunStatus,
)
from nelson.protocols.events import (
    ModelStartedPayload,
    RoundCompletedPayload,
    TaskFramingUpdatedPayload,
)
from nelson.providers.fake import FakeProvider

from .conftest import (
    contribution_response,
    framing_response,
    release_gate_response,
    review_approve_response,
    run_consensus_helper,
    synthesis_response,
    synthesis_with_framing_update,
)


@pytest.mark.asyncio
async def test_material_framing_update_emits_event() -> None:
    """T-CONS-005: moderator synthesis with framing_update → task_framing_updated event."""
    provider = FakeProvider(responses=[
        framing_response(),
        # Round 1: contributions
        contribution_response("A"),
        contribution_response("B"),
        # Round 1: synthesis triggers framing update — candidate invalidated
        synthesis_with_framing_update(),
        # Round 2: fresh contributions under new framing
        contribution_response("A-reframed"),
        contribution_response("B-reframed"),
        # Round 2: synthesis (no framing update this time)
        synthesis_response(),
        # Round 2: reviews — all approve
        review_approve_response(),
        review_approve_response(),
        # Release gate
        release_gate_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=10)

    assert result.status == RunStatus.SUCCESS

    # task_framing_updated must have been emitted
    framing_updated_events = [
        e for e in events if e.type == EventType.TASK_FRAMING_UPDATED
    ]
    assert len(framing_updated_events) == 1

    # Verify the payload has the correct framing version transition
    payload = framing_updated_events[0].payload
    assert isinstance(payload, TaskFramingUpdatedPayload)
    assert payload.framing_version == 2
    assert payload.previous_framing_version == 1


@pytest.mark.asyncio
async def test_invalidated_candidate_no_review_events() -> None:
    """T-CONS-005: invalidated candidate receives no review_* or consensus_* events.

    When framing is updated, the round's candidate is invalidated.
    No review_started, review_completed, or consensus_* events should
    be emitted for that candidate.
    """
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        # Framing update invalidates the round 1 candidate
        synthesis_with_framing_update(),
        # Round 2: fresh contributions, synthesis, reviews, release gate
        contribution_response("A-reframed"),
        contribution_response("B-reframed"),
        synthesis_response(),
        review_approve_response(),
        review_approve_response(),
        release_gate_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=10)

    assert result.status == RunStatus.SUCCESS

    # Find the invalidated candidate ID from the task_framing_updated event
    framing_updated = next(
        e for e in events if e.type == EventType.TASK_FRAMING_UPDATED
    )
    assert isinstance(framing_updated.payload, TaskFramingUpdatedPayload)
    invalidated_cand_id = framing_updated.payload.invalidated_candidate_id

    # No review_started or review_completed for the invalidated candidate
    review_events_for_invalidated = [
        e for e in events
        if e.type in (EventType.REVIEW_STARTED, EventType.REVIEW_COMPLETED)
        and hasattr(e.payload, "candidate_id")
        and e.payload.candidate_id == invalidated_cand_id  # type: ignore[union-attr]
    ]
    assert len(review_events_for_invalidated) == 0

    # No consensus_reached or consensus_pending for the invalidated candidate
    consensus_events_for_invalidated = [
        e for e in events
        if e.type in (EventType.CONSENSUS_REACHED, EventType.CONSENSUS_PENDING)
        and hasattr(e.payload, "candidate_id")
        and e.payload.candidate_id == invalidated_cand_id  # type: ignore[union-attr]
    ]
    assert len(consensus_events_for_invalidated) == 0


@pytest.mark.asyncio
async def test_reframed_contribution_used_after_update() -> None:
    """T-CONS-005: after framing update, contributions use reframed_contribution purpose."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_with_framing_update(),
        # Round 2: reframed contributions
        contribution_response("A-reframed"),
        contribution_response("B-reframed"),
        synthesis_response(),
        review_approve_response(),
        review_approve_response(),
        release_gate_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=10)

    assert result.status == RunStatus.SUCCESS

    # After the framing update, model_started events for contributions should
    # use REFRAMED_CONTRIBUTION purpose
    model_started_events = [
        e for e in events
        if e.type == EventType.MODEL_STARTED
        and isinstance(e.payload, ModelStartedPayload)
        and e.payload.purpose == InvocationPurpose.REFRAMED_CONTRIBUTION
    ]
    # Should be 2 reframed contributions (one per participant)
    assert len(model_started_events) == 2


@pytest.mark.asyncio
async def test_framing_version_increments() -> None:
    """T-CONS-005: framing_version goes from 1 to 2 after an update."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_with_framing_update(),
        contribution_response("A-reframed"),
        contribution_response("B-reframed"),
        synthesis_response(),
        review_approve_response(),
        review_approve_response(),
        release_gate_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=10)

    # The final run result should reflect framing_version=2
    assert result.task_framing is not None
    assert result.task_framing.framing_version == 2

    # Verify model_started events in round 2 carry framing_version=2
    reframed_starts = [
        e for e in events
        if e.type == EventType.MODEL_STARTED
        and isinstance(e.payload, ModelStartedPayload)
        and e.payload.purpose == InvocationPurpose.REFRAMED_CONTRIBUTION
    ]
    for e in reframed_starts:
        assert isinstance(e.payload, ModelStartedPayload)
        assert e.payload.framing_version == 2


@pytest.mark.asyncio
async def test_invalidated_round_counts_toward_budget() -> None:
    """T-CONS-005: the invalidated round still counts toward rounds_completed."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        # Round 1: framing update invalidates candidate
        synthesis_with_framing_update(),
        # Round 2: fresh contributions + synthesis + reviews
        contribution_response("A-reframed"),
        contribution_response("B-reframed"),
        synthesis_response(),
        review_approve_response(),
        review_approve_response(),
        release_gate_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=10)

    # Round 1 (invalidated) + Round 2 (consensus reached) = 2 rounds
    assert result.consensus.rounds_completed == 2

    # Verify round_completed events: round 1 should show candidate_invalidated_by_framing_update
    round_completed_events = [
        e for e in events if e.type == EventType.ROUND_COMPLETED
    ]
    assert len(round_completed_events) == 2

    r1 = round_completed_events[0].payload
    assert isinstance(r1, RoundCompletedPayload)
    assert r1.round == 1
    assert r1.candidate_invalidated_by_framing_update is True
    # review_executed should be False for invalidated rounds
    assert r1.review_executed is False
