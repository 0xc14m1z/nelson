"""Human output mode tests (T-OUT-001).

Verifies that human mode shows the final answer on stdout, progress on
stderr, and consensus status.
"""

from nelson.cli.render_human import render_human
from nelson.providers.fake import FakeProvider
from tests.test_consensus.conftest import run_happy_path


async def test_human_mode_final_answer_on_stdout(
    happy_path_provider: FakeProvider,
) -> None:
    """stdout must contain the final answer text."""
    events, result = await run_happy_path(happy_path_provider)
    stdout, _stderr = render_human(events, result)
    assert result.final_answer is not None
    # The final answer should appear in stdout
    assert result.final_answer in stdout


async def test_human_mode_progress_on_stderr(
    happy_path_provider: FakeProvider,
) -> None:
    """stderr must contain progress text during the run."""
    events, result = await run_happy_path(happy_path_provider)
    _stdout, stderr = render_human(events, result)
    # stderr should have some progress information
    assert len(stderr) > 0, "stderr must contain progress text"


async def test_human_mode_consensus_status_shown(
    happy_path_provider: FakeProvider,
) -> None:
    """Output must indicate the consensus status."""
    events, result = await run_happy_path(happy_path_provider)
    stdout, stderr = render_human(events, result)
    combined = stdout + stderr
    # Should mention consensus status somewhere
    assert "consensus" in combined.lower() or "reached" in combined.lower()
