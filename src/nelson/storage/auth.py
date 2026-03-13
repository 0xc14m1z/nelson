"""OpenRouter API key storage — save, read, delete with permission enforcement."""

import os
from pathlib import Path

# CLI_SPEC §5.1: saved key lives at ~/.nelson/openrouter_api_key
KEY_FILENAME = "openrouter_api_key"


def _key_path(config_dir: Path | None = None) -> Path:
    """Return the full path to the key file.

    Defaults to ``~/.nelson/`` when no config_dir is given.
    Computed at call time (not import time) so that HOME overrides
    in tests are respected.
    """
    base = config_dir or (Path.home() / ".nelson")
    return base / KEY_FILENAME


def save_key(key: str, *, config_dir: Path | None = None) -> Path:
    """Save an OpenRouter API key to disk with restrictive permissions.

    Creates the config directory if it does not exist. The key file is
    written with owner-only read/write permissions (0o600) using a
    restrictive file descriptor to avoid a world-readable window.

    Returns the path to the saved key file.
    """
    path = _key_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Open with explicit 0o600 mode so the file is never world-readable,
    # even briefly. Using Path.write_text() + chmod() would leave a window
    # where the secret is exposed with default umask permissions.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, key.encode())
    finally:
        os.close(fd)
    return path


def read_key(*, config_dir: Path | None = None) -> str | None:
    """Read the saved OpenRouter API key, or None if no key file exists.

    Uses try/except instead of exists() to avoid a TOCTOU race where
    the file could be deleted between the check and the read.
    """
    path = _key_path(config_dir)
    try:
        return path.read_text()
    except FileNotFoundError:
        return None


def delete_key(*, config_dir: Path | None = None) -> bool:
    """Delete the saved OpenRouter API key file.

    Returns True if the file was removed, False if it did not exist.
    Uses try/except instead of exists() to avoid a TOCTOU race.
    """
    path = _key_path(config_dir)
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
