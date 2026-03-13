"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture()
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME to a temporary directory for auth tests.

    Sets HOME to ``tmp_path`` and removes ``OPENROUTER_API_KEY`` from
    the environment so auth commands use a fresh, isolated config dir.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return tmp_path
