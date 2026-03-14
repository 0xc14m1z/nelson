"""Event emission infrastructure (EVENT_SCHEMA §1, §5).

``EventEmitter`` is the runtime component that stamps events with
monotonic sequence numbers, unique IDs, and UTC timestamps. It also
supports async iteration for consumers that process the event stream.
"""

from collections.abc import AsyncIterator

from nelson.protocols.enums import EventType, Phase, Role
from nelson.protocols.events import ApplicationEvent, EventPayload
from nelson.utils.clock import utc_now_iso
from nelson.utils.ids import make_command_id


class EventEmitter:
    """Stamps and collects events for a single command execution.

    Sequence numbers start at 1 and increase monotonically (EVENT_SCHEMA §5).
    Each event gets a unique ``evt_``-prefixed ID derived from the command ID
    and its sequence position.

    This is a **batch-collect** emitter: events are accumulated in memory
    and can be iterated only after ``close()`` is called. This is sufficient
    for Phase 5 (event infrastructure). Phase 6+ will need a streaming
    variant (e.g. ``asyncio.Queue``-backed) for JSONL and live TUI output.

    Args:
        command_id: The command ID to embed in every event envelope.
            Auto-generated if not provided.
        run_id: Optional run ID for events that belong to a consensus run.
    """

    def __init__(
        self,
        command_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._command_id = command_id or make_command_id()
        self._run_id = run_id
        self._sequence = 0
        self._events: list[ApplicationEvent] = []
        self._closed = False

    @property
    def command_id(self) -> str:
        """The command ID embedded in every event envelope."""
        return self._command_id

    @property
    def run_id(self) -> str | None:
        """The run ID embedded in every event envelope, if set."""
        return self._run_id

    def emit(
        self,
        *,
        event_type: EventType,
        phase: Phase,
        role: Role,
        payload: EventPayload,
        model: str | None = None,
        round_number: int | None = None,
    ) -> ApplicationEvent:
        """Create and record an event with the next sequence number.

        Returns the created event so callers can inspect it if needed.
        """
        self._sequence += 1
        event = ApplicationEvent(
            event_id=f"evt_{self._command_id}_{self._sequence}",
            command_id=self._command_id,
            run_id=self._run_id,
            sequence=self._sequence,
            timestamp=utc_now_iso(),
            type=event_type,
            phase=phase,
            round=round_number,
            role=role,
            model=model,
            payload=payload,
        )
        self._events.append(event)
        return event

    def close(self) -> None:
        """Mark the event stream as complete for async iteration."""
        self._closed = True

    async def __aiter__(self) -> AsyncIterator[ApplicationEvent]:
        """Yield all emitted events in order.

        The emitter must be closed before iteration will terminate.
        Raises ``RuntimeError`` if iterated before closing.
        """
        if not self._closed:
            raise RuntimeError("EventEmitter must be closed before async iteration")
        for event in self._events:
            yield event
