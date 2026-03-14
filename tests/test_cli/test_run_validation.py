"""CLI ``run`` validation tests (T-CLI-003 through T-CLI-007).

Verifies that invalid ``nelson run`` invocations are rejected with exit code 2.
"""

from pathlib import Path

from typer.testing import CliRunner

from nelson.cli.app import app
from nelson.cli.exit_codes import ExitCode

runner = CliRunner()

# ── Minimal valid args (used as base to test individual violations) ────


def _valid_args() -> list[str]:
    """Return a minimal valid ``run`` argument list.

    Every test removes or overrides one flag to produce the specific
    validation failure being tested.
    """
    return [
        "run",
        "--participant", "openai/gpt-4",
        "--participant", "anthropic/claude-3-opus",
        "--moderator", "openai/gpt-4",
        "--prompt", "What is the meaning of life?",
    ]


# ── Individual validation rules ──────────────────────────────────────


def test_fewer_than_two_participants_exits_2() -> None:
    """Fewer than two --participant flags must exit 2."""
    result = runner.invoke(app, [
        "run",
        "--participant", "openai/gpt-4",
        "--moderator", "openai/gpt-4",
        "--prompt", "test",
    ])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_missing_moderator_exits_2() -> None:
    """Omitting --moderator must exit 2.

    Typer may handle this as a missing required option, which exits 2.
    """
    result = runner.invoke(app, [
        "run",
        "--participant", "openai/gpt-4",
        "--participant", "anthropic/claude-3-opus",
        "--prompt", "test",
    ])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_no_prompt_source_exits_2() -> None:
    """No --prompt, --prompt-file, or --stdin must exit 2."""
    result = runner.invoke(app, [
        "run",
        "--participant", "openai/gpt-4",
        "--participant", "anthropic/claude-3-opus",
        "--moderator", "openai/gpt-4",
    ])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_multiple_prompt_sources_exits_2() -> None:
    """Providing both --prompt and --prompt-file must exit 2."""
    result = runner.invoke(app, [
        "run",
        "--participant", "openai/gpt-4",
        "--participant", "anthropic/claude-3-opus",
        "--moderator", "openai/gpt-4",
        "--prompt", "test",
        "--prompt-file", "/tmp/some-file.txt",
    ])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_json_and_jsonl_together_exits_2() -> None:
    """Providing both --json and --jsonl must exit 2."""
    result = runner.invoke(app, [*_valid_args(), "--json", "--jsonl"])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_duplicate_participants_exits_2() -> None:
    """Duplicate model IDs in --participant must exit 2."""
    result = runner.invoke(app, [
        "run",
        "--participant", "openai/gpt-4",
        "--participant", "openai/gpt-4",
        "--moderator", "anthropic/claude-3-opus",
        "--prompt", "test",
    ])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_max_rounds_non_positive_exits_2() -> None:
    """--max-rounds with value <= 0 must exit 2."""
    result = runner.invoke(app, [*_valid_args(), "--max-rounds", "0"])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_max_rounds_negative_exits_2() -> None:
    """--max-rounds with negative value must exit 2."""
    result = runner.invoke(app, [*_valid_args(), "--max-rounds", "-1"])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_nonexistent_prompt_file_exits_2(tmp_path: Path) -> None:
    """--prompt-file pointing to a nonexistent file must exit 2."""
    result = runner.invoke(app, [
        "run",
        "--participant", "openai/gpt-4",
        "--participant", "anthropic/claude-3-opus",
        "--moderator", "openai/gpt-4",
        "--prompt-file", str(tmp_path / "no-such-file.txt"),
    ])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_invalid_release_gate_exits_2() -> None:
    """--release-gate with an invalid value must exit 2.

    Typer validates the StrEnum type and rejects unknown values.
    """
    result = runner.invoke(app, [*_valid_args(), "--release-gate", "banana"])
    assert result.exit_code == ExitCode.INVALID_USAGE


def test_valid_args_do_not_exit_2() -> None:
    """Sanity check: valid args must not exit with INVALID_USAGE.

    The run command is a stub that exits 0, so valid args should pass validation.
    """
    result = runner.invoke(app, _valid_args())
    assert result.exit_code != ExitCode.INVALID_USAGE
