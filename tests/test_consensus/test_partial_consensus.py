"""Partial consensus tests (T-CONS-004, T-OUT-004).

Tests that persistent blocking reviews exhaust the round budget
and produce a partial result with residual disagreements.
"""

import pytest

from nelson.cli.render_human import render_human
from nelson.protocols.enums import (
    ConsensusStatus,
    EventType,
    RunStatus,
)
from nelson.providers.fake import FakeProvider

from .conftest import (
    contribution_response,
    framing_response,
    review_approve_response,
    review_major_revise_response,
    run_consensus_helper,
    synthesis_response,
)


@pytest.mark.asyncio
async def test_max_rounds_exhausted_returns_partial() -> None:
    """T-CONS-004: persistent major_revise with max_rounds=2 → status=partial.

    Both rounds have blocking reviews. The run exhausts its budget
    and returns partial with the best available candidate.
    """
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        # Round 1: synthesis + blocking reviews
        synthesis_response(),
        review_major_revise_response(),
        review_approve_response(),
        # Round 2: re-synthesis + still blocking
        synthesis_response(),
        review_major_revise_response(),
        review_approve_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=2)

    assert result.status == RunStatus.PARTIAL
    assert result.consensus.status == ConsensusStatus.PARTIAL
    assert result.consensus.rounds_completed == 2
    # Partial runs still produce a final answer (best available candidate)
    assert result.final_answer is not None

    # consensus_partial event should be emitted
    partial_events = [e for e in events if e.type == EventType.CONSENSUS_PARTIAL]
    assert len(partial_events) == 1


@pytest.mark.asyncio
async def test_residual_disagreements_populated() -> None:
    """T-CONS-004: residual_disagreements list is non-empty for partial consensus."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_response(),
        review_major_revise_response(),
        review_approve_response(),
        synthesis_response(),
        review_major_revise_response(),
        review_approve_response(),
    ])

    _events, result = await run_consensus_helper(provider, max_rounds=2)

    assert result.status == RunStatus.PARTIAL
    assert len(result.consensus.residual_disagreements) > 0


@pytest.mark.asyncio
async def test_human_output_shows_partial_consensus() -> None:
    """T-OUT-004: human output says 'partial' and shows disagreement info."""
    provider = FakeProvider(responses=[
        framing_response(),
        contribution_response("A"),
        contribution_response("B"),
        synthesis_response(),
        review_major_revise_response(),
        review_approve_response(),
        synthesis_response(),
        review_major_revise_response(),
        review_approve_response(),
    ])

    events, result = await run_consensus_helper(provider, max_rounds=2)

    stdout, _stderr = render_human(events, result)

    # Human output must mention partial consensus
    assert "partial" in stdout.lower() or "Partial" in stdout
    # Residual disagreements should be visible
    assert any(
        "disagreement" in stdout.lower() or issue in stdout
        for issue in result.consensus.residual_disagreements
    )
