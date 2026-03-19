"""Multi-round consensus tests (T-CONS-002, T-CONS-003).

Tests that blocking reviews (major_revise, reject) trigger new rounds,
minor_revise does not block, and early stop works before max_rounds.
"""

import pytest

from nelson.protocols.enums import (
    ConsensusStatus,
    EventType,
    RunStatus,
)
from nelson.providers.fake import FakeProvider

from .conftest import (
    contribution_response,
    framing_response,
    release_gate_response,
    review_approve_response,
    review_major_revise_response,
    review_minor_revise_response,
    review_reject_response,
    run_consensus_helper,
    synthesis_response,
)


@pytest.mark.asyncio
async def test_major_revise_triggers_new_round() -> None:
    """T-CONS-002: major_revise in round 1 triggers round 2 with re-synthesis.

    Round 1: contributions → synthesis → reviews (one major_revise) → consensus_pending
    Round 2: re-synthesis with feedback → reviews (all approve) → consensus_reached
    """
    provider = FakeProvider(responses=[
        # Phase: task framing
        framing_response(),
        # Round 1: contributions
        contribution_response("A"),
        contribution_response("B"),
        # Round 1: synthesis
        synthesis_response(),
        # Round 1: reviews — one major_revise, one approve
        review_major_revise_response(),
        review_approve_response(),
        # Round 2: re-synthesis (moderator revises candidate based on review feedback)
        synthesis_response(),
        # Round 2: reviews — both approve
        review_approve_response(),
        review_approve_response(),
        # Release gate
        release_gate_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=10)

    assert result.status == RunStatus.SUCCESS
    assert result.consensus.rounds_completed == 2
    assert result.consensus.status == ConsensusStatus.REACHED

    # Verify consensus_pending was emitted in round 1 (blocking review)
    pending_events = [e for e in events if e.type == EventType.CONSENSUS_PENDING]
    assert len(pending_events) >= 1

    # Verify consensus_reached was emitted in round 2
    reached_events = [e for e in events if e.type == EventType.CONSENSUS_REACHED]
    assert len(reached_events) == 1


@pytest.mark.asyncio
async def test_reject_triggers_new_round() -> None:
    """T-CONS-002 variant: reject in round 1 also triggers a new round."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_response(),
        # Round 1 reviews: one reject, one approve
        review_reject_response(),
        review_approve_response(),
        # Round 2: re-synthesis + reviews
        synthesis_response(),
        review_approve_response(),
        review_approve_response(),
        release_gate_response(),
    ])

    _events, result = await run_consensus_helper(provider, max_rounds=10)

    assert result.status == RunStatus.SUCCESS
    assert result.consensus.rounds_completed == 2


@pytest.mark.asyncio
async def test_minor_revise_does_not_block_closure() -> None:
    """T-CONS-003: all minor_revise allows consensus to close in 1 round.

    minor_revise is non-blocking — consensus can reach 'reached' status
    without triggering another round.
    """
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_response(),
        # Both reviewers say minor_revise — non-blocking
        review_minor_revise_response(),
        review_minor_revise_response(),
        release_gate_response(),
    ])

    _events, result = await run_consensus_helper(provider, max_rounds=10)

    assert result.status == RunStatus.SUCCESS
    assert result.consensus.rounds_completed == 1
    assert result.consensus.status == ConsensusStatus.REACHED


@pytest.mark.asyncio
async def test_minor_revise_feedback_incorporated() -> None:
    """T-CONS-003: minor revision suggestions appear in the result metadata."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_response(),
        review_minor_revise_response(),
        review_minor_revise_response(),
        release_gate_response(),
    ])

    _events, result = await run_consensus_helper(provider, max_rounds=10)

    # minor_revisions_applied should contain the optional_improvements from reviews
    assert len(result.consensus.minor_revisions_applied) > 0
    assert "Clarify packaging recommendation" in result.consensus.minor_revisions_applied


@pytest.mark.asyncio
async def test_early_stop_before_max_rounds() -> None:
    """Consensus in round 2 with max_rounds=10 stops early at rounds_completed=2."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_response(),
        # Round 1: one major_revise
        review_major_revise_response(),
        review_approve_response(),
        # Round 2: all approve
        synthesis_response(),
        review_approve_response(),
        review_approve_response(),
        release_gate_response(),
    ])

    _events, result = await run_consensus_helper(provider, max_rounds=10)

    assert result.status == RunStatus.SUCCESS
    assert result.consensus.rounds_completed == 2
    # Early stop: didn't use all 10 rounds
    assert result.consensus.max_rounds == 10
