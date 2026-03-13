"""CLI help smoke tests (T-CLI-001, T-CLI-002)."""

from typer.testing import CliRunner

from nelson.cli.app import app

runner = CliRunner()


def test_root_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "auth" in result.output
    assert "run" in result.output


def test_auth_help() -> None:
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0


def test_run_help() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--participant" in result.output
    assert "--moderator" in result.output
    assert "--json" in result.output
    assert "--jsonl" in result.output
