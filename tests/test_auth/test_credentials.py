"""Credential resolution order tests — CLI > env > saved."""

from pathlib import Path

import pytest

from nelson.core.credentials import resolve_credential
from nelson.storage.auth import save_key


def test_cli_override_takes_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI key overrides env var and saved key."""
    config_dir = tmp_path / ".nelson"
    save_key("saved-key", config_dir=config_dir)
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")

    result = resolve_credential(cli_key="cli-key", config_dir=config_dir)
    assert result == "cli-key"


def test_env_var_takes_precedence_over_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env var key takes precedence over saved key when no CLI key is given."""
    config_dir = tmp_path / ".nelson"
    save_key("saved-key", config_dir=config_dir)
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")

    result = resolve_credential(config_dir=config_dir)
    assert result == "env-key"


def test_saved_key_used_as_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Saved key is used when no CLI key or env var is set."""
    config_dir = tmp_path / ".nelson"
    save_key("saved-key", config_dir=config_dir)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = resolve_credential(config_dir=config_dir)
    assert result == "saved-key"


def test_no_key_available_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing all key sources raises an error."""
    config_dir = tmp_path / ".nelson"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    with pytest.raises(Exception, match=r"(?i)credential|key"):
        resolve_credential(config_dir=config_dir)
