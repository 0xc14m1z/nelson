"""RunResult validation tests.

Verifies that the RunResult produced by a happy-path consensus run
contains all required fields per RUN_RESULT_SCHEMA.md.
"""

from nelson.protocols.results import RunResult
from nelson.providers.fake import FakeProvider

from .conftest import run_happy_path


async def test_run_result_has_all_required_fields(
    happy_path_provider: FakeProvider,
) -> None:
    """All top-level fields from RUN_RESULT_SCHEMA.md must be present."""
    _events, result = await run_happy_path(happy_path_provider)
    # Top-level required fields per RUN_RESULT_SCHEMA §2
    assert result.run_id is not None
    assert result.status is not None
    assert result.input is not None
    assert result.models is not None
    assert result.consensus is not None
    assert result.release_gate is not None
    assert result.usage is not None
    assert result.timing is not None


async def test_run_result_validates_against_schema(
    happy_path_provider: FakeProvider,
) -> None:
    """Full RunResult must serialize and re-validate through Pydantic."""
    _events, result = await run_happy_path(happy_path_provider)
    # Round-trip through JSON to ensure all fields are serializable
    json_str = result.model_dump_json()
    revalidated = RunResult.model_validate_json(json_str)
    assert revalidated.status == result.status
    assert revalidated.run_id == result.run_id


async def test_run_result_timing_is_populated(
    happy_path_provider: FakeProvider,
) -> None:
    """Timing fields (started_at, completed_at, duration_ms) must be present."""
    _events, result = await run_happy_path(happy_path_provider)
    assert result.timing.started_at != ""
    assert result.timing.completed_at != ""
    assert result.timing.duration_ms >= 0


async def test_run_result_usage_is_populated(
    happy_path_provider: FakeProvider,
) -> None:
    """Usage must have per_invocation list and total snapshot."""
    _events, result = await run_happy_path(happy_path_provider)
    # per_invocation should have entries for each provider call
    assert len(result.usage.per_invocation) > 0
    # total should aggregate across all invocations
    assert result.usage.total is not None
    assert result.usage.total.total_tokens is not None
    assert result.usage.total.total_tokens > 0
