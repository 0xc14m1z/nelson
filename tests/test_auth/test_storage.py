"""Key storage tests — save, read, delete, permissions."""

from pathlib import Path

from nelson.storage.auth import delete_key, read_key, save_key


def test_save_key_creates_directory_and_file(tmp_path: Path) -> None:
    """Saving a key creates the config directory and key file."""
    config_dir = tmp_path / ".nelson"
    save_key("sk-or-test-key", config_dir=config_dir)
    key_file = config_dir / "openrouter_api_key"
    assert key_file.exists()
    assert key_file.read_text() == "sk-or-test-key"


def test_save_key_sets_restrictive_permissions(tmp_path: Path) -> None:
    """Saved key file must have owner-only permissions (0o600)."""
    config_dir = tmp_path / ".nelson"
    save_key("sk-or-test-key", config_dir=config_dir)
    key_file = config_dir / "openrouter_api_key"
    mode = key_file.stat().st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


def test_save_key_overwrites_existing(tmp_path: Path) -> None:
    """Saving a key twice overwrites the first value."""
    config_dir = tmp_path / ".nelson"
    save_key("first-key", config_dir=config_dir)
    save_key("second-key", config_dir=config_dir)
    key_file = config_dir / "openrouter_api_key"
    assert key_file.read_text() == "second-key"


def test_read_key_returns_saved_value(tmp_path: Path) -> None:
    """Reading after saving returns the saved key."""
    config_dir = tmp_path / ".nelson"
    save_key("sk-or-test-key", config_dir=config_dir)
    assert read_key(config_dir=config_dir) == "sk-or-test-key"


def test_read_key_returns_none_when_absent(tmp_path: Path) -> None:
    """Reading when no key file exists returns None."""
    config_dir = tmp_path / ".nelson"
    assert read_key(config_dir=config_dir) is None


def test_delete_key_removes_file(tmp_path: Path) -> None:
    """Deleting a saved key removes the file."""
    config_dir = tmp_path / ".nelson"
    save_key("sk-or-test-key", config_dir=config_dir)
    result = delete_key(config_dir=config_dir)
    assert result is True
    assert not (config_dir / "openrouter_api_key").exists()


def test_delete_key_succeeds_when_absent(tmp_path: Path) -> None:
    """Deleting when no key file exists succeeds without error."""
    config_dir = tmp_path / ".nelson"
    result = delete_key(config_dir=config_dir)
    assert result is False
