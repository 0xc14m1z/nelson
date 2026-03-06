"""In-memory event broadcast for SSE streaming.

Allows the consensus orchestrator to push events that multiple SSE
consumers (one per browser tab) receive in real time.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

# Sentinel used to signal a consumer to stop iterating.
_STOP = object()


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """A single event to be sent over SSE."""

    event: str
    data: dict[str, Any]


class _Consumer:
    """Async iterator that reads events from a queue.

    Created by :meth:`Broadcast.subscribe`; iterate with ``async for``.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[StreamEvent | object] = asyncio.Queue()

    def put_nowait(self, item: StreamEvent | object) -> None:
        self._queue.put_nowait(item)

    def stop(self) -> None:
        """Enqueue the stop sentinel so the iterator terminates."""
        self._queue.put_nowait(_STOP)

    def __aiter__(self) -> _Consumer:
        return self

    async def __anext__(self) -> StreamEvent:
        item = await self._queue.get()
        if item is _STOP:
            raise StopAsyncIteration
        return item  # type: ignore[return-value]


class Broadcast:
    """Fan-out event broadcaster for a single consensus session."""

    def __init__(self) -> None:
        self._consumers: list[_Consumer] = []
        self._text_buffers: dict[str, str] = {}
        self._closed = False
        self._subscriber_event = asyncio.Event()

    # ── consumer management ──────────────────────────────────────────

    def subscribe(self) -> _Consumer:
        """Create and register a new consumer."""
        if self._closed:
            raise RuntimeError("Broadcast is closed")
        consumer = _Consumer()
        self._consumers.append(consumer)
        self._subscriber_event.set()
        return consumer

    async def wait_for_subscriber(self, timeout: float = 5.0) -> bool:
        """Wait until at least one consumer subscribes, or timeout."""
        if self._consumers:
            return True
        try:
            await asyncio.wait_for(self._subscriber_event.wait(), timeout)
            return True
        except TimeoutError:
            return False

    def unsubscribe(self, consumer: _Consumer) -> None:
        """Remove a consumer and signal it to stop."""
        try:
            self._consumers.remove(consumer)
        except ValueError:
            pass
        consumer.stop()

    # ── event pushing ────────────────────────────────────────────────

    def push(self, event: StreamEvent) -> None:
        """Fan out *event* to every registered consumer."""
        for consumer in self._consumers:
            consumer.put_nowait(event)

    # ── text accumulation (late-joiner catchup) ──────────────────────

    def accumulate_text(self, model_id: str, delta: str) -> None:
        """Append *delta* to the per-model text buffer."""
        self._text_buffers[model_id] = self._text_buffers.get(model_id, "") + delta

    def get_catchup(self) -> dict[str, str]:
        """Return a snapshot of all accumulated text buffers."""
        return dict(self._text_buffers)

    def clear_text(self, model_id: str) -> None:
        """Remove a model's text buffer."""
        self._text_buffers.pop(model_id, None)

    # ── lifecycle ────────────────────────────────────────────────────

    def close(self) -> None:
        """Stop all consumers and mark the broadcast as closed."""
        self._closed = True
        for consumer in self._consumers:
            consumer.stop()
        self._consumers.clear()


# ── Session → Broadcast registry ─────────────────────────────────────────

_registry: dict[UUID, Broadcast] = {}


def register_broadcast(session_id: UUID, broadcast: Broadcast) -> None:
    """Associate a broadcast instance with a session."""
    _registry[session_id] = broadcast


def unregister_broadcast(session_id: UUID) -> None:
    """Remove the broadcast for a session."""
    _registry.pop(session_id, None)


def get_broadcast(session_id: UUID) -> Broadcast | None:
    """Look up the broadcast for a session, or ``None``."""
    return _registry.get(session_id)
