"""Credential resolution — CLI override > env var > saved key.

Resolution order is defined in CLI_SPEC §4:
1. --openrouter-api-key (CLI flag)
2. OPENROUTER_API_KEY (environment variable)
3. ~/.nelson/openrouter_api_key (saved key file)
"""

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

    Tries each source in priority order and returns the first one found.
    Raises ``MissingCredentialError`` if no key is available from any source.
    """
    # 1. Explicit CLI override takes highest priority
    if cli_key is not None:
        return cli_key

    # 2. Environment variable is second
    env_key = os.environ.get(ENV_VAR)
    if env_key is not None:
        return env_key

    # 3. Saved key file is the fallback
    saved_key = read_key(config_dir=config_dir)
    if saved_key is not None:
        return saved_key

    raise MissingCredentialError(
        "No OpenRouter API key found. "
        "Set one with `nelson auth set --api-key <KEY>`, "
        "the OPENROUTER_API_KEY environment variable, "
        "or --openrouter-api-key."
    )
