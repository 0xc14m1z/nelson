"""Credential resolution — CLI override > env var > saved key."""

import os
from pathlib import Path

from nelson.storage.auth import read_key

ENV_VAR = "OPENROUTER_API_KEY"


class MissingCredentialError(Exception):
    """No OpenRouter API key could be found from any source."""


def resolve_credential(
    cli_key: str | None = None,
    *,
    config_dir: Path | None = None,
) -> str:
    """Resolve the effective OpenRouter API key.

    Resolution order (first non-None wins):
    1. ``cli_key`` — explicit CLI override (``--openrouter-api-key``)
    2. ``OPENROUTER_API_KEY`` environment variable
    3. Saved key on disk (``~/.nelson/openrouter_api_key``)

    Raises ``MissingCredentialError`` if no key is available.
    """
    if cli_key is not None:
        return cli_key

    env_key = os.environ.get(ENV_VAR)
    if env_key is not None:
        return env_key

    saved_key = read_key(config_dir=config_dir)
    if saved_key is not None:
        return saved_key

    raise MissingCredentialError(
        "No OpenRouter API key found. "
        "Set one with `nelson auth set --api-key <KEY>`, "
        "the OPENROUTER_API_KEY environment variable, "
        "or --openrouter-api-key."
    )
