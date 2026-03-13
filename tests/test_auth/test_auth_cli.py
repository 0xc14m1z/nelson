"""Auth CLI integration tests (T-AUTH-001 through T-AUTH-005)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from nelson.cli.app import app

runner = CliRunner()


def test_auth_set_creates_key_file(tmp_home: Path) -> None:
    """T-AUTH-001: `auth set --api-key` saves the key file and exits 0."""
    result = runner.invoke(app, ["auth", "set", "--api-key", "sk-test"])
    assert result.exit_code == 0, result.output
    key_file = tmp_home / ".nelson" / "openrouter_api_key"
    assert key_file.exists()
    assert key_file.read_text() == "sk-test"


def test_auth_set_missing_key_exits_2() -> None:
    """Missing --api-key argument should exit with code 2."""
    result = runner.invoke(app, ["auth", "set"])
    assert result.exit_code == 2


def test_auth_status_no_key_exits_3(tmp_home: Path) -> None:
    """T-AUTH-002: `auth status` with no key should exit 3."""
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 3


def test_auth_status_with_saved_key_reports_present(
    tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After saving a key, `auth status` reports presence and exits 0 or 4.

    Since we cannot verify against OpenRouter in tests, the effective key
    is present but verification may report not_checked or invalid.
    This test checks that the saved key is detected and reported.
    """
    runner.invoke(app, ["auth", "set", "--api-key", "sk-test-key"])
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code != 3, f"Expected non-3 exit code, got output: {result.output}"
    assert "present" in result.output.lower() or "saved" in result.output.lower()


def test_auth_clear_removes_key(tmp_home: Path) -> None:
    """T-AUTH-005: `auth clear` removes the saved key file."""
    runner.invoke(app, ["auth", "set", "--api-key", "sk-test-key"])
    result = runner.invoke(app, ["auth", "clear"])
    assert result.exit_code == 0
    key_file = tmp_home / ".nelson" / "openrouter_api_key"
    assert not key_file.exists()


def test_auth_clear_succeeds_when_no_key(tmp_home: Path) -> None:
    """Clearing when no key exists still exits 0."""
    result = runner.invoke(app, ["auth", "clear"])
    assert result.exit_code == 0


def test_full_key_never_printed(tmp_home: Path) -> None:
    """The full API key must never appear in stdout or stderr."""
    key = "sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890"
    runner.invoke(app, ["auth", "set", "--api-key", key])
    result = runner.invoke(app, ["auth", "status"])
    assert key not in result.output, "Full API key must never appear in output"
