"""Application protocol dispatcher for auth commands."""

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
from nelson.protocols.enums import EventType, Phase, Role
from nelson.protocols.events import (
    ApplicationEvent,
    AuthKeyClearedPayload,
    AuthKeySavedPayload,
    AuthStatusReportedPayload,
    CommandCompletedPayload,
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
    """Build an ApplicationEvent with standard envelope fields."""
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
        """Generate the event stream for an auth command."""
        cmd = self._command
        seq = 1

        # command_received
        yield _make_event(
            cmd.command_id,
            seq,
            EventType.COMMAND_RECEIVED,
            Phase.COMMAND,
            CommandReceivedPayload(command_type=cmd.type, adapter=cmd.adapter),
        )
        seq += 1

        if isinstance(cmd, AuthSetCommand):
            event, self._result = self._handle_auth_set(cmd, seq)
            yield event
            seq += 1
        elif isinstance(cmd, AuthStatusCommand):
            event, self._result = self._handle_auth_status(cmd, seq)
            yield event
            seq += 1
        else:
            event, self._result = self._handle_auth_clear(cmd, seq)
            yield event
            seq += 1

        # command_completed
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
        """Handle AuthSetCommand — save key, return event and result."""
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
        """Handle AuthStatusCommand — check key sources and report."""
        saved_key = read_key(config_dir=self._config_dir)
        env_key = os.environ.get(ENV_VAR)

        saved_present = saved_key is not None
        env_present = env_key is not None

        if env_present:
            effective_source = "env"
        elif saved_present:
            effective_source = "saved"
        else:
            effective_source = "none"

        # Verification against OpenRouter is not performed here;
        # the CLI layer handles live verification when needed.
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
        """Handle AuthClearCommand — delete key file."""
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
