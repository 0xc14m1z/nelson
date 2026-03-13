"""Application protocol dispatcher for auth commands.

Implements the CommandExecution protocol (APPLICATION_PROTOCOL §3):
one typed command in → one ordered event stream out → one typed result out.

Event ordering follows APPLICATION_PROTOCOL §9-10:
  command_received → one auth domain event → command_completed
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from nelson.core.credentials import ENV_VAR
from nelson.protocols.commands import (
    AuthClearCommand,
    AuthSetCommand,
    AuthStatusCommand,
)
from nelson.protocols.domain import ErrorObject
from nelson.protocols.enums import EventType, Phase, Role
from nelson.protocols.events import (
    ApplicationEvent,
    AuthKeyClearedPayload,
    AuthKeySavedPayload,
    AuthStatusReportedPayload,
    CommandCompletedPayload,
    CommandFailedPayload,
    CommandReceivedPayload,
    EventPayload,
)
from nelson.protocols.results import (
    AuthClearResult,
    AuthSetResult,
    AuthStatusResult,
    CommandResult,
)
from nelson.storage.auth import delete_key, read_key, save_key

AuthCommand = AuthSetCommand | AuthStatusCommand | AuthClearCommand
"""Union of auth command types handled by this dispatcher."""


def _make_event(
    command_id: str,
    sequence: int,
    event_type: EventType,
    phase: Phase,
    payload: EventPayload,
) -> ApplicationEvent:
    """Build an ApplicationEvent with standard envelope fields.

    Auth events are always emitted by the system role (not a participant
    or moderator), so role is hardcoded to SYSTEM.
    """
    return ApplicationEvent(
        event_id=f"evt_{command_id}_{sequence}",
        command_id=command_id,
        sequence=sequence,
        timestamp=datetime.now(UTC).isoformat(),
        type=event_type,
        phase=phase,
        role=Role.SYSTEM,
        payload=payload,
    )


class AuthCommandExecution:
    """CommandExecution implementation for auth commands.

    Produces a stream of typed events and a terminal result for
    ``AuthSetCommand``, ``AuthStatusCommand``, and ``AuthClearCommand``.

    The result is populated as a side-effect of iterating the event stream.
    Callers must drain ``.events`` before calling ``.result()``.
    """

    def __init__(self, command: AuthCommand, *, config_dir: Path | None = None) -> None:
        self._command = command
        self._config_dir = config_dir
        self._result: CommandResult | None = None

    @property
    def events(self) -> AsyncIterator[ApplicationEvent]:
        """Async stream of events emitted during execution."""
        return self._execute()

    async def result(self) -> CommandResult | None:
        """Terminal result after event stream is drained."""
        return self._result

    async def _execute(self) -> AsyncIterator[ApplicationEvent]:
        """Generate the event stream for an auth command.

        On success the stream is exactly 3 events:
        1. command_received (APPLICATION_PROTOCOL §9 — always first)
        2. One domain event (auth_key_saved / auth_status_reported / auth_key_cleared)
        3. command_completed (APPLICATION_PROTOCOL §9 — always last)

        On failure the domain event is skipped and command_failed replaces
        command_completed, so the stream is exactly 2 events.
        """
        cmd = self._command
        seq = 1

        # Event 1: acknowledge receipt of the command
        yield _make_event(
            cmd.command_id,
            seq,
            EventType.COMMAND_RECEIVED,
            Phase.COMMAND,
            CommandReceivedPayload(command_type=cmd.type, adapter=cmd.adapter),
        )
        seq += 1

        # Event 2: execute the command and emit the domain event
        try:
            if isinstance(cmd, AuthSetCommand):
                event, self._result = self._handle_auth_set(cmd, seq)
            elif isinstance(cmd, AuthStatusCommand):
                event, self._result = self._handle_auth_status(cmd, seq)
            else:
                event, self._result = self._handle_auth_clear(cmd, seq)
            yield event
            seq += 1
        except OSError as exc:
            # Filesystem errors (permission denied, disk full, etc.)
            # produce a command_failed event instead of a domain event.
            yield _make_event(
                cmd.command_id,
                seq,
                EventType.COMMAND_FAILED,
                Phase.AUTH,
                CommandFailedPayload(
                    command_type=cmd.type,
                    error=ErrorObject(
                        code="credential_storage_error",
                        message=str(exc),
                        retryable=False,
                    ),
                ),
            )
            # No result — caller sees None from result()
            return

        # Event 3: mark the command as completed
        yield _make_event(
            cmd.command_id,
            seq,
            EventType.COMMAND_COMPLETED,
            Phase.COMMAND,
            CommandCompletedPayload(command_type=cmd.type, status="success"),
        )

    def _handle_auth_set(
        self, cmd: AuthSetCommand, seq: int
    ) -> tuple[ApplicationEvent, AuthSetResult]:
        """Handle AuthSetCommand — save key to disk."""
        path = save_key(cmd.api_key, config_dir=self._config_dir)
        event = _make_event(
            cmd.command_id,
            seq,
            EventType.AUTH_KEY_SAVED,
            Phase.AUTH,
            AuthKeySavedPayload(storage_path=str(path)),
        )
        result = AuthSetResult(saved=True, storage_path=str(path))
        return event, result

    def _handle_auth_status(
        self, cmd: AuthStatusCommand, seq: int
    ) -> tuple[ApplicationEvent, AuthStatusResult]:
        """Handle AuthStatusCommand — check which key sources are available.

        Determines effective_source using the same priority as
        credentials.resolve_credential (CLI_SPEC §4):
        env var wins over saved key.
        """
        saved_key = read_key(config_dir=self._config_dir)
        env_key = os.environ.get(ENV_VAR)

        saved_present = saved_key is not None
        env_present = env_key is not None

        # Determine which source would be used if a run were started now
        if env_present:
            effective_source = "env"
        elif saved_present:
            effective_source = "saved"
        else:
            effective_source = "none"

        # Verification against OpenRouter (GET /api/v1/key) is not performed
        # in the dispatcher — it will be added at the CLI layer when live
        # verification is implemented. For now, report "not_checked".
        verification = "not_checked"

        result = AuthStatusResult(
            saved_key_present=saved_present,
            env_key_present=env_present,
            effective_source=effective_source,
            verification=verification,
        )

        event = _make_event(
            cmd.command_id,
            seq,
            EventType.AUTH_STATUS_REPORTED,
            Phase.AUTH,
            AuthStatusReportedPayload(
                saved_key_present=saved_present,
                env_key_present=env_present,
                effective_source=effective_source,
                verification=verification,
            ),
        )
        return event, result

    def _handle_auth_clear(
        self, cmd: AuthClearCommand, seq: int
    ) -> tuple[ApplicationEvent, AuthClearResult]:
        """Handle AuthClearCommand — delete the saved key file."""
        removed = delete_key(config_dir=self._config_dir)
        event = _make_event(
            cmd.command_id,
            seq,
            EventType.AUTH_KEY_CLEARED,
            Phase.AUTH,
            AuthKeyClearedPayload(saved_key_removed=removed),
        )
        result = AuthClearResult(saved_key_removed=removed)
        return event, result


def dispatch(
    command: AuthCommand,
    *,
    config_dir: Path | None = None,
) -> AuthCommandExecution:
    """Dispatch a typed application command and return its execution.

    The returned ``AuthCommandExecution`` implements the ``CommandExecution``
    protocol: iterate ``.events`` for the event stream, then call
    ``.result()`` for the terminal result.
    """
    return AuthCommandExecution(command, config_dir=config_dir)
