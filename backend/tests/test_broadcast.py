"""Tests for the in-memory SSE broadcast infrastructure."""

import asyncio
from uuid import uuid4

import pytest

from app.consensus.broadcast import (
    Broadcast,
    StreamEvent,
    get_broadcast,
    register_broadcast,
    unregister_broadcast,
)


@pytest.fixture
def broadcast() -> Broadcast:
    return Broadcast()


# ── Single consumer receives events ─────────────────────────────────────


@pytest.mark.asyncio
async def test_single_consumer_receives_events(broadcast: Broadcast) -> None:
    consumer = broadcast.subscribe()
    event = StreamEvent(event="token", data={"model": "gpt-4", "delta": "hello"})
    broadcast.push(event)
    broadcast.close()

    received = [item async for item in consumer]
    assert received == [event]


# ── Multiple consumers receive the same events ──────────────────────────


@pytest.mark.asyncio
async def test_multiple_consumers_receive_same_events(broadcast: Broadcast) -> None:
    c1 = broadcast.subscribe()
    c2 = broadcast.subscribe()

    e1 = StreamEvent(event="token", data={"delta": "a"})
    e2 = StreamEvent(event="token", data={"delta": "b"})
    broadcast.push(e1)
    broadcast.push(e2)
    broadcast.close()

    r1 = [item async for item in c1]
    r2 = [item async for item in c2]
    assert r1 == [e1, e2]
    assert r2 == [e1, e2]


# ── Late subscriber gets catchup text ───────────────────────────────────


@pytest.mark.asyncio
async def test_late_subscriber_gets_catchup(broadcast: Broadcast) -> None:
    broadcast.accumulate_text("gpt-4", "Hello")
    broadcast.accumulate_text("gpt-4", " world")
    broadcast.accumulate_text("claude-3", "Hi")

    catchup = broadcast.get_catchup()
    assert catchup == {"gpt-4": "Hello world", "claude-3": "Hi"}


# ── Unsubscribe stops receiving ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_unsubscribe_stops_receiving(broadcast: Broadcast) -> None:
    consumer = broadcast.subscribe()

    e1 = StreamEvent(event="token", data={"delta": "a"})
    broadcast.push(e1)

    # Give the queue a moment to process
    await asyncio.sleep(0.01)

    broadcast.unsubscribe(consumer)

    e2 = StreamEvent(event="token", data={"delta": "b"})
    broadcast.push(e2)

    received = [item async for item in consumer]
    assert e1 in received
    assert e2 not in received


# ── clear_text removes a model's buffer ─────────────────────────────────


@pytest.mark.asyncio
async def test_clear_text(broadcast: Broadcast) -> None:
    broadcast.accumulate_text("gpt-4", "Hello")
    broadcast.clear_text("gpt-4")
    assert broadcast.get_catchup() == {}


# ── Registry: register / get / unregister ────────────────────────────────


@pytest.mark.asyncio
async def test_registry_register_and_get() -> None:
    session_id = uuid4()
    bc = Broadcast()
    register_broadcast(session_id, bc)
    try:
        assert get_broadcast(session_id) is bc
    finally:
        unregister_broadcast(session_id)


@pytest.mark.asyncio
async def test_registry_unregister() -> None:
    session_id = uuid4()
    bc = Broadcast()
    register_broadcast(session_id, bc)
    unregister_broadcast(session_id)
    assert get_broadcast(session_id) is None


# ── Registry returns None for unknown session ────────────────────────────


@pytest.mark.asyncio
async def test_registry_unknown_session() -> None:
    assert get_broadcast(uuid4()) is None
