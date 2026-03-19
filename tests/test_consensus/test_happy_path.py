"""Happy-path consensus tests (T-CONS-001).

Verifies that a fully successful consensus run with fake provider
produces correct results, valid domain artifacts, and expected status.
"""

from nelson.protocols.domain import (
    TaskFramingResult,
)
from nelson.protocols.enums import (
    ConsensusStatus,
    ReleaseGateDecision,
    ReleaseGateMode,
    RunStatus,
)
from nelson.providers.fake import FakeProvider

from .conftest import run_happy_path


async def test_happy_path_success(happy_path_provider: FakeProvider) -> None:
    """Full happy-path run: status=success, final_answer present, 1 round."""
    _events, result = await run_happy_path(happy_path_provider)
    assert result.status == RunStatus.SUCCESS
    assert result.final_answer is not None
    assert result.consensus.rounds_completed == 1


async def test_task_framing_produces_valid_result(happy_path_provider: FakeProvider) -> None:
    """Task framing must return a valid TaskFramingResult."""
    _events, result = await run_happy_path(happy_path_provider)
    assert result.task_framing is not None
    # Validate it matches the TaskFramingResult schema
    framing = TaskFramingResult.model_validate(result.task_framing.model_dump())
    assert framing.task_type is not None
    assert framing.objective != ""
    assert len(framing.quality_criteria) > 0


async def test_participants_produce_valid_contributions(
    happy_path_provider: FakeProvider,
) -> None:
    """Each participant must return a valid ParticipantContribution.

    We verify this indirectly via the run result — the orchestrator must
    have successfully parsed contributions to reach synthesis.
    """
    _events, result = await run_happy_path(happy_path_provider)
    # If contributions were invalid, synthesis would not have been reached
    assert result.status == RunStatus.SUCCESS
    assert result.consensus.status == ConsensusStatus.REACHED


async def test_moderator_produces_valid_synthesis(
    happy_path_provider: FakeProvider,
) -> None:
    """Moderator must return a valid CandidateSynthesisResult.

    We verify this indirectly — if synthesis failed, no reviews would occur
    and consensus would not be reached.
    """
    _events, result = await run_happy_path(happy_path_provider)
    assert result.status == RunStatus.SUCCESS
    assert result.final_answer is not None
    assert len(result.final_answer) > 0


async def test_participants_produce_valid_reviews(
    happy_path_provider: FakeProvider,
) -> None:
    """All reviews must have decision=approve for consensus to be reached."""
    _events, result = await run_happy_path(happy_path_provider)
    assert result.consensus.status == ConsensusStatus.REACHED
    # No blocking issues should remain
    assert result.consensus.residual_disagreements == []


async def test_release_gate_executes_in_auto_mode(
    happy_path_provider: FakeProvider,
) -> None:
    """Release gate must execute in auto mode and produce pass or pass_with_minor_fixes."""
    _events, result = await run_happy_path(happy_path_provider)
    assert result.release_gate.mode == ReleaseGateMode.AUTO
    assert result.release_gate.executed is True
    assert result.release_gate.decision in (
        ReleaseGateDecision.PASS,
        ReleaseGateDecision.PASS_WITH_MINOR_FIXES,
    )
