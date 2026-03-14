"""EventEmitter tests (T-EVENT-002).

Verifies monotonic sequence numbering, unique event IDs with correct prefix,
UTC ISO 8601 timestamps, and async iteration.
"""

import re
from datetime import datetime, timedelta

from nelson.core.events import EventEmitter
from nelson.protocols.enums import Adapter, EventType, Phase, Role
from nelson.protocols.events import ApplicationEvent, CommandReceivedPayload


def _payload() -> CommandReceivedPayload:
    """Minimal payload for testing — event type doesn't matter for emitter mechanics."""
    return CommandReceivedPayload(command_type="run", adapter=Adapter.CLI)


async def test_sequence_starts_at_one() -> None:
    """Emit one event, assert sequence == 1."""
    emitter = EventEmitter(command_id="cmd_test123456")
    event = emitter.emit(
        event_type=EventType.COMMAND_RECEIVED,
        phase=Phase.COMMAND,
        role=Role.SYSTEM,
        payload=_payload(),
    )
    assert event.sequence == 1


async def test_sequence_increases_monotonically() -> None:
    """Emit 5 events, assert sequence is 1,2,3,4,5."""
    emitter = EventEmitter(command_id="cmd_test123456")
    sequences: list[int] = []
    for _ in range(5):
        event = emitter.emit(
            event_type=EventType.COMMAND_RECEIVED,
            phase=Phase.COMMAND,
            role=Role.SYSTEM,
            payload=_payload(),
        )
        sequences.append(event.sequence)
    assert sequences == [1, 2, 3, 4, 5]


async def test_events_have_unique_ids() -> None:
    """Emit 10 events, assert all event_ids are distinct."""
    emitter = EventEmitter(command_id="cmd_test123456")
    ids: set[str] = set()
    for _ in range(10):
        event = emitter.emit(
            event_type=EventType.COMMAND_RECEIVED,
            phase=Phase.COMMAND,
            role=Role.SYSTEM,
            payload=_payload(),
        )
        ids.add(event.event_id)
    assert len(ids) == 10


async def test_event_ids_have_correct_prefix() -> None:
    """Assert event_id starts with ``evt_``."""
    emitter = EventEmitter(command_id="cmd_test123456")
    event = emitter.emit(
        event_type=EventType.COMMAND_RECEIVED,
        phase=Phase.COMMAND,
        role=Role.SYSTEM,
        payload=_payload(),
    )
    assert event.event_id.startswith("evt_")


async def test_timestamps_are_utc_iso8601() -> None:
    """Assert timestamp is valid UTC ISO 8601."""
    emitter = EventEmitter(command_id="cmd_test123456")
    event = emitter.emit(
        event_type=EventType.COMMAND_RECEIVED,
        phase=Phase.COMMAND,
        role=Role.SYSTEM,
        payload=_payload(),
    )
    # Must parse as ISO 8601
    parsed = datetime.fromisoformat(event.timestamp)
    # Must be UTC (tzinfo present and offset zero)
    offset = parsed.utcoffset()
    assert offset is not None
    assert offset == timedelta(0)
    # Must match ISO 8601 pattern with timezone
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", event.timestamp)


async def test_emitter_async_iteration() -> None:
    """Iterate over emitter, collect events, assert order."""
    emitter = EventEmitter(command_id="cmd_test123456")
    # Emit events first
    for _ in range(3):
        emitter.emit(
            event_type=EventType.COMMAND_RECEIVED,
            phase=Phase.COMMAND,
            role=Role.SYSTEM,
            payload=_payload(),
        )
    # Mark stream as complete so async iteration terminates
    emitter.close()
    collected: list[ApplicationEvent] = []
    async for event in emitter:
        collected.append(event)
    assert len(collected) == 3
    assert [e.sequence for e in collected] == [1, 2, 3]


async def test_emitter_preserves_envelope_fields() -> None:
    """Verify emitter correctly sets command_id, run_id, model, and round on events."""
    emitter = EventEmitter(command_id="cmd_abc", run_id="run_xyz")
    event = emitter.emit(
        event_type=EventType.COMMAND_RECEIVED,
        phase=Phase.COMMAND,
        role=Role.SYSTEM,
        payload=_payload(),
        model="openai/gpt-4",
        round_number=2,
    )
    assert event.command_id == "cmd_abc"
    assert event.run_id == "run_xyz"
    assert event.model == "openai/gpt-4"
    assert event.round == 2
