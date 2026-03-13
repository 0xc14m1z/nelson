"""Auth protocol tests — dispatcher event stream (T-PROTO-003 adapted)."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from nelson.core.dispatcher import AuthCommandExecution, dispatch
from nelson.protocols.commands import AuthClearCommand, AuthSetCommand, AuthStatusCommand
from nelson.protocols.enums import ErrorCode
from nelson.protocols.events import ApplicationEvent
from nelson.protocols.results import AuthClearResult, AuthSetResult, AuthStatusResult


async def _collect_events(execution: AuthCommandExecution) -> list[ApplicationEvent]:
    """Drain all events from a CommandExecution."""
    events: list[ApplicationEvent] = []
    async for event in execution.events:
        events.append(event)
    return events


async def test_auth_set_emits_correct_events(tmp_home: Path) -> None:
    """AuthSetCommand event stream: command_received, auth_key_saved, command_completed."""
    cmd = AuthSetCommand(command_id="cmd_test_set", api_key="sk-test")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types == ["command_received", "auth_key_saved", "command_completed"]
    assert isinstance(result, AuthSetResult)


async def test_auth_status_emits_correct_events(tmp_home: Path) -> None:
    """AuthStatusCommand: command_received, auth_status_reported, command_completed."""
    cmd = AuthStatusCommand(command_id="cmd_test_status")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types == ["command_received", "auth_status_reported", "command_completed"]
    assert isinstance(result, AuthStatusResult)


async def test_auth_clear_emits_correct_events(tmp_home: Path) -> None:
    """AuthClearCommand event stream: command_received, auth_key_cleared, command_completed."""
    cmd = AuthClearCommand(command_id="cmd_test_clear")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types == ["command_received", "auth_key_cleared", "command_completed"]
    assert isinstance(result, AuthClearResult)


async def test_auth_set_resolves_typed_result(tmp_home: Path) -> None:
    """AuthSetCommand terminal result is a typed AuthSetResult."""
    cmd = AuthSetCommand(command_id="cmd_test_result", api_key="sk-test")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")
    async for _ in execution.events:
        pass
    result = await execution.result()

    assert isinstance(result, AuthSetResult)
    assert result.saved is True
    assert "openrouter_api_key" in result.storage_path


# ── Failure path tests ───────────────────────────────────────────────────


async def test_auth_set_emits_command_failed_on_unwritable_dir(tmp_home: Path) -> None:
    """AuthSetCommand emits command_failed when the config dir is not writable."""
    config_dir = tmp_home / ".nelson"
    config_dir.mkdir()
    # Remove write permission so save_key raises an OSError
    os.chmod(config_dir, 0o444)

    cmd = AuthSetCommand(command_id="cmd_test_fail_set", api_key="sk-test")
    execution = dispatch(cmd, config_dir=config_dir)
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types == ["command_received", "command_failed"]
    # No result is produced on failure
    assert result is None

    # The command_failed event carries a structured error
    failed_event = events[1]
    assert failed_event.payload.error.code == ErrorCode.CREDENTIAL_STORAGE_ERROR
    assert failed_event.payload.error.retryable is False

    # Restore permissions so tmp_path cleanup succeeds
    os.chmod(config_dir, 0o755)


async def test_auth_clear_emits_command_failed_on_unwritable_dir(tmp_home: Path) -> None:
    """AuthClearCommand emits command_failed when the key file can't be deleted."""
    config_dir = tmp_home / ".nelson"
    config_dir.mkdir()
    key_file = config_dir / "openrouter_api_key"
    key_file.write_text("sk-to-delete")
    # Remove write permission on the directory (needed to unlink files)
    os.chmod(config_dir, 0o444)

    cmd = AuthClearCommand(command_id="cmd_test_fail_clear")
    execution = dispatch(cmd, config_dir=config_dir)
    events = await _collect_events(execution)
    result = await execution.result()

    event_types = [e.type for e in events]
    assert event_types == ["command_received", "command_failed"]
    assert result is None

    failed_event = events[1]
    assert failed_event.payload.error.code == ErrorCode.CREDENTIAL_STORAGE_ERROR

    # Restore permissions so tmp_path cleanup succeeds
    os.chmod(config_dir, 0o755)


# ── Validation tests ────────────────────────────────────────────────────


def test_auth_set_rejects_empty_api_key() -> None:
    """AuthSetCommand rejects empty string as api_key."""
    with pytest.raises(ValidationError, match="API key must not be empty"):
        AuthSetCommand(api_key="")


def test_auth_set_rejects_whitespace_only_api_key() -> None:
    """AuthSetCommand rejects whitespace-only string as api_key."""
    with pytest.raises(ValidationError, match="API key must not be empty"):
        AuthSetCommand(api_key="   ")


# ── Event stream identity tests ─────────────────────────────────────────


async def test_events_property_returns_same_iterator(tmp_home: Path) -> None:
    """Accessing .events multiple times returns the same iterator, not a new execution."""
    cmd = AuthSetCommand(command_id="cmd_test_identity", api_key="sk-test")
    execution = dispatch(cmd, config_dir=tmp_home / ".nelson")

    # Both accesses must return the exact same iterator object
    first = execution.events
    second = execution.events
    assert first is second
