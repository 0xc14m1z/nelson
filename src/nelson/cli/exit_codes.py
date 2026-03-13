"""Process exit codes defined in CLI_SPEC.md §3."""

from enum import IntEnum


class ExitCode(IntEnum):
    """Exit codes for the Nelson CLI.

    These must remain stable across releases — external tooling
    (shell scripts, CI pipelines) may depend on the numeric values.
    """

    SUCCESS = 0
    """Command succeeded."""

    INVALID_USAGE = 2
    """Invalid CLI usage or invalid user input."""

    CREDENTIAL_ERROR = 3
    """Missing credentials or credential storage error."""

    CREDENTIAL_VERIFICATION_FAILED = 4
    """Credential verification failed or provider returned auth failure."""

    PROVIDER_ERROR = 5
    """Provider transport/runtime failure prevented completion."""

    ORCHESTRATION_FAILURE = 6
    """Orchestration failure after startup (quorum loss, moderator failure)."""

    SERIALIZATION_ERROR = 7
    """Serialization or output rendering failure."""

    INTERRUPTED = 130
    """Interrupted by user (SIGINT)."""
