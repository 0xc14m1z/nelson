# Streaming UX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the batch-response UX with token-by-token streaming in a columnar layout, so users see LLM text appear in real time.

**Architecture:** In-memory broadcast queue replaces DB polling for SSE. Orchestrator switches from `agent.run()` to `agent.run_stream()` with `stream_responses()` + `validate_response_output(allow_partial=True)` to extract text deltas from structured output types. Frontend switches from chat-style to columnar layout (one column per model).

**Tech Stack:** PydanticAI `run_stream()` / `stream_responses()`, `asyncio.Queue` broadcast, `sse-starlette`, React state machine for streaming columns, Mantine UI.

**Design doc:** `docs/plans/2026-03-06-streaming-ux-design.md`

---

### Task 1: Backend — Broadcast module

**Files:**
- Create: `backend/app/consensus/broadcast.py`
- Test: `backend/tests/test_broadcast.py`

This is the core infrastructure: an in-memory event broadcast that lets the orchestrator push events and multiple SSE consumers receive them. Also supports late-joining consumers getting a catchup of in-progress model text.

**Step 1: Write the failing tests**

```python
# backend/tests/test_broadcast.py
import asyncio

import pytest

from app.consensus.broadcast import Broadcast, StreamEvent


@pytest.mark.asyncio
async def test_single_consumer_receives_events():
    bc = Broadcast()
    consumer = bc.subscribe()
    await bc.push(StreamEvent(event="test", data={"msg": "hello"}))
    await bc.close()
    events = []
    async for event in consumer:
        events.append(event)
    assert len(events) == 1
    assert events[0].data["msg"] == "hello"


@pytest.mark.asyncio
async def test_multiple_consumers_receive_same_events():
    bc = Broadcast()
    c1 = bc.subscribe()
    c2 = bc.subscribe()
    await bc.push(StreamEvent(event="test", data={"x": 1}))
    await bc.close()
    events1 = [e async for e in c1]
    events2 = [e async for e in c2]
    assert len(events1) == 1
    assert len(events2) == 1


@pytest.mark.asyncio
async def test_late_subscriber_gets_catchup():
    bc = Broadcast()
    # Push a model_start and some token_deltas before subscribing
    bc.accumulate_text("model-1", "Hello ")
    bc.accumulate_text("model-1", "world")
    await bc.push(StreamEvent(event="token_delta", data={"llm_model_id": "model-1", "delta": "Hello "}))
    await bc.push(StreamEvent(event="token_delta", data={"llm_model_id": "model-1", "delta": "world"}))
    # Late subscriber
    consumer = bc.subscribe()
    catchup = bc.get_catchup()
    assert len(catchup) == 1
    assert catchup["model-1"] == "Hello world"
    await bc.close()
    # Consumer should get future events (none in this case)
    events = [e async for e in consumer]
    assert len(events) == 0


@pytest.mark.asyncio
async def test_unsubscribe_stops_receiving():
    bc = Broadcast()
    consumer = bc.subscribe()
    bc.unsubscribe(consumer)
    await bc.push(StreamEvent(event="test", data={}))
    await bc.close()
    events = [e async for e in consumer]
    assert len(events) == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_broadcast.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.consensus.broadcast'`

**Step 3: Implement the broadcast module**

```python
# backend/app/consensus/broadcast.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class StreamEvent:
    event: str
    data: dict[str, Any]


_SENTINEL = object()


class _Consumer:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[StreamEvent | object] = asyncio.Queue()

    async def put(self, event: StreamEvent) -> None:
        await self._queue.put(event)

    async def stop(self) -> None:
        await self._queue.put(_SENTINEL)

    def __aiter__(self) -> AsyncIterator[StreamEvent]:
        return self

    async def __anext__(self) -> StreamEvent:
        item = await self._queue.get()
        if item is _SENTINEL:
            raise StopAsyncIteration
        return item  # type: ignore[return-value]


class Broadcast:
    def __init__(self) -> None:
        self._consumers: list[_Consumer] = []
        self._text_buffers: dict[str, str] = {}
        self._closed = False

    def subscribe(self) -> _Consumer:
        consumer = _Consumer()
        if not self._closed:
            self._consumers.append(consumer)
        return consumer

    def unsubscribe(self, consumer: _Consumer) -> None:
        if consumer in self._consumers:
            self._consumers.remove(consumer)
            asyncio.ensure_future(consumer.stop())

    async def push(self, event: StreamEvent) -> None:
        for consumer in list(self._consumers):
            await consumer.put(event)

    def accumulate_text(self, model_id: str, delta: str) -> None:
        self._text_buffers[model_id] = self._text_buffers.get(model_id, "") + delta

    def get_catchup(self) -> dict[str, str]:
        return dict(self._text_buffers)

    def clear_text(self, model_id: str) -> None:
        self._text_buffers.pop(model_id, None)

    async def close(self) -> None:
        self._closed = True
        for consumer in self._consumers:
            await consumer.stop()
        self._consumers.clear()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_broadcast.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add backend/app/consensus/broadcast.py backend/tests/test_broadcast.py
git commit -m "feat: add in-memory broadcast for SSE streaming events"
```

---

### Task 2: Backend — Session-to-broadcast registry

**Files:**
- Modify: `backend/app/consensus/broadcast.py`
- Test: `backend/tests/test_broadcast.py` (add tests)

A module-level registry mapping session IDs to their live broadcasts. The orchestrator registers on start, the SSE endpoint looks up the broadcast.

**Step 1: Write the failing tests**

Append to `backend/tests/test_broadcast.py`:

```python
from uuid import uuid4

from app.consensus.broadcast import get_broadcast, register_broadcast, unregister_broadcast


@pytest.mark.asyncio
async def test_registry_register_and_get():
    sid = uuid4()
    bc = Broadcast()
    register_broadcast(sid, bc)
    assert get_broadcast(sid) is bc
    unregister_broadcast(sid)
    assert get_broadcast(sid) is None


@pytest.mark.asyncio
async def test_registry_returns_none_for_unknown():
    assert get_broadcast(uuid4()) is None
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_broadcast.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_broadcast'`

**Step 3: Implement the registry**

Append to `backend/app/consensus/broadcast.py`:

```python
from uuid import UUID

_registry: dict[UUID, Broadcast] = {}


def register_broadcast(session_id: UUID, broadcast: Broadcast) -> None:
    _registry[session_id] = broadcast


def unregister_broadcast(session_id: UUID) -> None:
    _registry.pop(session_id, None)


def get_broadcast(session_id: UUID) -> Broadcast | None:
    return _registry.get(session_id)
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_broadcast.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add backend/app/consensus/broadcast.py backend/tests/test_broadcast.py
git commit -m "feat: add session-to-broadcast registry"
```

---

### Task 3: Backend — Streaming orchestrator

**Files:**
- Modify: `backend/app/consensus/service.py`
- Test: `backend/tests/test_consensus_orchestrator.py` (update existing tests)

Switch from `agent.run()` to `agent.run_stream()` with `stream_responses()` + `validate_response_output(allow_partial=True)`. Push streaming events to the broadcast.

**Step 1: Update the orchestrator**

Rewrite `backend/app/consensus/service.py`. Key changes:
- Import and create a `Broadcast` per orchestrator
- Register/unregister in the broadcast registry
- `_call_responder` → use `agent.run_stream()` + `stream_responses()` + emit `model_start`, `token_delta`, `model_done` events
- `_call_critic` → same streaming approach, track `revised_response` field
- `_run_summarizer` → stays as `agent.run()` (not streamed), emit `round_summary` event
- Emit `phase_change` events between rounds
- Use `asyncio.timeout()` instead of `asyncio.wait_for()` since we need to wrap the entire streaming block

```python
# backend/app/consensus/service.py
import asyncio
import contextlib
import time
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.agent.model_registry import NoKeyAvailableError, resolve_model
from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt
from app.consensus.broadcast import (
    Broadcast,
    StreamEvent,
    register_broadcast,
    unregister_broadcast,
)
from app.database import async_session_factory
from app.models import LLMCall, LLMModel, Session, UserSettings

MAX_ROUNDS_HARD_CAP = 20
LLM_TIMEOUT_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 10
CONCURRENCY_LIMIT = 10


def _resolve_override(agent, resolved):
    """Build an override context manager for the agent using a resolved model.

    If resolved is None (e.g. no API key available), return a no-op context
    manager so the agent uses whatever model is already configured (e.g. a
    TestModel set by an outer override in tests).
    """
    if resolved is None:
        return contextlib.nullcontext()

    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    pai_model = OpenAIChatModel(
        model_name=resolved.model_slug,
        provider=OpenAIProvider(
            base_url=resolved.base_url, api_key=resolved.api_key
        ),
    )
    return agent.override(model=pai_model)


class ConsensusOrchestrator:
    def __init__(self, session_id: UUID, user_id: UUID):
        self.session_id = session_id
        self.user_id = user_id
        self.semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        self._active_models: list[LLMModel] = []
        self._heartbeat_task: asyncio.Task | None = None
        self.broadcast = Broadcast()

    async def run(self) -> None:
        register_broadcast(self.session_id, self.broadcast)
        try:
            await self._run_inner()
        finally:
            await self.broadcast.close()
            unregister_broadcast(self.session_id)

    async def _run_inner(self) -> None:
        async with async_session_factory() as db:
            session = await db.get(Session, self.session_id)
            if not session:
                return

            await db.refresh(session, attribute_names=["models"])
            self._active_models = list(session.models)
            max_rounds = session.max_rounds or MAX_ROUNDS_HARD_CAP

            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            start_time = time.monotonic()

            try:
                # Round 1: Initial responses
                session.status = "responding"
                session.current_round = 1
                await db.commit()

                round1_responses = await self._run_responder_round(db, session)
                if len(self._active_models) < 2:
                    await self._fail_session(db, session, start_time)
                    return

                # Emit phase_change after round 1
                await self.broadcast.push(StreamEvent(
                    event="phase_change",
                    data={
                        "from_phase": "responding",
                        "to_phase": "critiquing",
                        "round_number": 2,
                        "summary": {
                            "models_completed": len(round1_responses),
                            "models_failed": len(session.models) - len(self._active_models),
                        },
                        "model_details": [
                            {
                                "llm_model_id": str(r["llm_model_id"]),
                                "confidence": r.get("confidence"),
                                "key_points": r.get("key_points"),
                            }
                            for r in round1_responses
                        ],
                    },
                ))

                # Rounds 2+: Critique loop
                prior_summary: str | None = None
                latest_responses = round1_responses

                for round_num in range(2, max_rounds + 1):
                    session.status = "critiquing"
                    session.current_round = round_num
                    await db.commit()

                    # Summarize prior round
                    prior_summary = await self._run_summarizer(
                        db, session, latest_responses, round_num
                    )

                    # Run critic round
                    critique_results = await self._run_critic_round(
                        db, session, latest_responses, prior_summary, round_num
                    )

                    if len(self._active_models) < 2:
                        await self._fail_session(db, session, start_time)
                        return

                    # Check convergence
                    all_agree = all(
                        not cr["has_disagreements"] for cr in critique_results
                    )
                    latest_responses = [
                        {
                            "llm_model_id": cr["llm_model_id"],
                            "model_name": cr["model_name"],
                            "response": cr["response"],
                        }
                        for cr in critique_results
                    ]

                    if all_agree:
                        session.status = "consensus_reached"
                        break

                    # Emit phase_change for next round (if not last)
                    if round_num < max_rounds:
                        await self.broadcast.push(StreamEvent(
                            event="phase_change",
                            data={
                                "from_phase": "critiquing",
                                "to_phase": "critiquing",
                                "round_number": round_num + 1,
                                "summary": {
                                    "models_completed": len(critique_results),
                                    "models_failed": len(session.models) - len(self._active_models),
                                },
                                "model_details": [
                                    {
                                        "llm_model_id": str(cr["llm_model_id"]),
                                        "disagreements": cr.get("disagreements", []),
                                    }
                                    for cr in critique_results
                                ],
                            },
                        ))
                else:
                    session.status = "max_rounds_reached"

                elapsed = int((time.monotonic() - start_time) * 1000)
                session.total_duration_ms = elapsed
                session.completed_at = datetime.now(UTC)
                await self._update_session_totals(db, session)
                await db.commit()

                # Emit terminal event
                await self.broadcast.push(StreamEvent(
                    event=session.status,
                    data={
                        "status": session.status,
                        "current_round": session.current_round,
                        "total_input_tokens": session.total_input_tokens,
                        "total_output_tokens": session.total_output_tokens,
                        "total_cost": float(session.total_cost),
                        "total_duration_ms": session.total_duration_ms,
                    },
                ))

            except Exception:
                await self._fail_session(db, session, start_time)
            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()

    async def _try_resolve(self, model: LLMModel, db: AsyncSession):
        try:
            return await resolve_model(self.user_id, model, db)
        except NoKeyAvailableError:
            return None

    async def _run_responder_round(
        self, db: AsyncSession, session: Session
    ) -> list[dict]:
        prompt = build_responder_prompt(session.enquiry)
        tasks = [
            self._call_responder(db, session, model, prompt)
            for model in list(self._active_models)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses = []
        for model, result in zip(list(self._active_models), results):
            if isinstance(result, Exception):
                await self._record_error(db, session, model, 1, "responder", str(result))
                self._active_models.remove(model)
            else:
                responses.append(result)
        await db.commit()
        return responses

    async def _call_responder(
        self, db: AsyncSession, session: Session, model: LLMModel, prompt: str
    ) -> dict:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            model_id_str = str(model.id)
            model_name = (
                f"{model.provider.slug}/{model.slug}" if model.provider else model.slug
            )
            start = time.monotonic()

            # Emit model_start
            await self.broadcast.push(StreamEvent(
                event="model_start",
                data={
                    "llm_model_id": model_id_str,
                    "round_number": 1,
                    "role": "responder",
                },
            ))

            with _resolve_override(responder_agent, resolved):
                try:
                    async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                        async with responder_agent.run_stream(prompt) as result:
                            prev_text = ""
                            async for response, last in result.stream_responses(debounce_by=0.01):
                                try:
                                    partial = await result.validate_response_output(
                                        response, allow_partial=not last
                                    )
                                    current_text = partial.response
                                    if len(current_text) > len(prev_text):
                                        delta = current_text[len(prev_text):]
                                        self.broadcast.accumulate_text(model_id_str, delta)
                                        await self.broadcast.push(StreamEvent(
                                            event="token_delta",
                                            data={
                                                "llm_model_id": model_id_str,
                                                "round_number": 1,
                                                "delta": delta,
                                            },
                                        ))
                                        prev_text = current_text
                                except ValidationError:
                                    continue

                            output = result.output
                            usage = result.usage()
                except TimeoutError:
                    raise TimeoutError(f"Timed out after {LLM_TIMEOUT_SECONDS}s")

            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.broadcast.clear_text(model_id_str)

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=1,
                role="responder",
                prompt=prompt,
                response=output.response,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)

            # Emit model_done
            await self.broadcast.push(StreamEvent(
                event="model_done",
                data={
                    "llm_model_id": model_id_str,
                    "round_number": 1,
                    "role": "responder",
                    "structured": {
                        "confidence": output.confidence,
                        "key_points": output.key_points,
                    },
                    "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0,
                    "cost": 0,
                    "duration_ms": elapsed_ms,
                },
            ))

            return {
                "llm_model_id": model.id,
                "model_name": model_name,
                "response": output.response,
                "confidence": output.confidence,
                "key_points": output.key_points,
            }

    async def _run_critic_round(
        self,
        db: AsyncSession,
        session: Session,
        latest_responses: list[dict],
        prior_summary: str | None,
        round_number: int,
    ) -> list[dict]:
        tasks = [
            self._call_critic(
                db, session, model, latest_responses, prior_summary, round_number
            )
            for model in list(self._active_models)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        critique_results = []
        for model, result in zip(list(self._active_models), results):
            if isinstance(result, Exception):
                await self._record_error(
                    db, session, model, round_number, "critic", str(result)
                )
                self._active_models.remove(model)
                # Emit model_error
                await self.broadcast.push(StreamEvent(
                    event="model_error",
                    data={
                        "llm_model_id": str(model.id),
                        "round_number": round_number,
                        "error": str(result),
                    },
                ))
            else:
                critique_results.append(result)
        await db.commit()
        return critique_results

    async def _call_critic(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        latest_responses: list[dict],
        prior_summary: str | None,
        round_number: int,
    ) -> dict:
        async with self.semaphore:
            resolved = await self._try_resolve(model, db)
            prompt = build_critic_prompt(session.enquiry, prior_summary, latest_responses)
            model_id_str = str(model.id)
            model_name = (
                f"{model.provider.slug}/{model.slug}" if model.provider else model.slug
            )
            start = time.monotonic()

            # Emit model_start
            await self.broadcast.push(StreamEvent(
                event="model_start",
                data={
                    "llm_model_id": model_id_str,
                    "round_number": round_number,
                    "role": "critic",
                },
            ))

            with _resolve_override(critic_agent, resolved):
                try:
                    async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
                        async with critic_agent.run_stream(prompt) as result:
                            prev_text = ""
                            async for response, last in result.stream_responses(debounce_by=0.01):
                                try:
                                    partial = await result.validate_response_output(
                                        response, allow_partial=not last
                                    )
                                    current_text = partial.revised_response
                                    if len(current_text) > len(prev_text):
                                        delta = current_text[len(prev_text):]
                                        self.broadcast.accumulate_text(model_id_str, delta)
                                        await self.broadcast.push(StreamEvent(
                                            event="token_delta",
                                            data={
                                                "llm_model_id": model_id_str,
                                                "round_number": round_number,
                                                "delta": delta,
                                            },
                                        ))
                                        prev_text = current_text
                                except ValidationError:
                                    continue

                            output = result.output
                            usage = result.usage()
                except TimeoutError:
                    raise TimeoutError(f"Timed out after {LLM_TIMEOUT_SECONDS}s")

            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.broadcast.clear_text(model_id_str)

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=round_number,
                role="critic",
                prompt=prompt,
                response=output.revised_response,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)

            # Emit model_done
            await self.broadcast.push(StreamEvent(
                event="model_done",
                data={
                    "llm_model_id": model_id_str,
                    "round_number": round_number,
                    "role": "critic",
                    "structured": {
                        "has_disagreements": output.has_disagreements,
                        "disagreements": output.disagreements,
                    },
                    "input_tokens": usage.input_tokens or 0,
                    "output_tokens": usage.output_tokens or 0,
                    "cost": 0,
                    "duration_ms": elapsed_ms,
                },
            ))

            return {
                "llm_model_id": model.id,
                "model_name": model_name,
                "response": output.revised_response,
                "has_disagreements": output.has_disagreements,
                "disagreements": output.disagreements,
            }

    async def _run_summarizer(
        self,
        db: AsyncSession,
        session: Session,
        responses: list[dict],
        round_number: int,
    ) -> str:
        settings = await db.execute(
            select(UserSettings).where(UserSettings.user_id == session.user_id)
        )
        user_settings = settings.scalar_one_or_none()

        summarizer_model_id = (
            user_settings.summarizer_model_id if user_settings else None
        )

        if summarizer_model_id:
            summarizer_llm = await db.get(LLMModel, summarizer_model_id)
        else:
            result = await db.execute(
                select(LLMModel).where(LLMModel.slug == "gpt-4o-mini")
            )
            summarizer_llm = result.scalar_one_or_none()

        if not summarizer_llm:
            fallback = "\n".join(
                f"{r['model_name']}: {r['response'][:200]}" for r in responses
            )
            return fallback

        prompt = build_summarizer_prompt(responses)
        start = time.monotonic()

        try:
            resolved = await self._try_resolve(summarizer_llm, db)

            with _resolve_override(summarizer_agent, resolved):
                result = await asyncio.wait_for(
                    summarizer_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            usage = result.usage()

            call = LLMCall(
                session_id=session.id,
                llm_model_id=summarizer_llm.id,
                round_number=round_number,
                role="summarizer",
                prompt=prompt,
                response=result.output.summary,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)
            await db.commit()

            # Emit round_summary
            await self.broadcast.push(StreamEvent(
                event="round_summary",
                data={
                    "round_number": round_number,
                    "agreements": result.output.agreements,
                    "disagreements": result.output.disagreements,
                    "shifts": result.output.shifts,
                },
            ))

            return result.output.summary

        except Exception:
            return "\n".join(
                f"{r['model_name']}: {r['response'][:200]}" for r in responses
            )

    async def _record_error(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        round_number: int,
        role: str,
        error: str,
    ) -> None:
        call = LLMCall(
            session_id=session.id,
            llm_model_id=model.id,
            round_number=round_number,
            role=role,
            error=error,
        )
        db.add(call)

    async def _fail_session(
        self, db: AsyncSession, session: Session, start_time: float
    ) -> None:
        session.status = "failed"
        session.total_duration_ms = int((time.monotonic() - start_time) * 1000)
        session.completed_at = datetime.now(UTC)
        await self._update_session_totals(db, session)
        await db.commit()

        await self.broadcast.push(StreamEvent(
            event="failed",
            data={
                "status": "failed",
                "current_round": session.current_round,
                "total_input_tokens": session.total_input_tokens,
                "total_output_tokens": session.total_output_tokens,
                "total_cost": float(session.total_cost),
                "total_duration_ms": session.total_duration_ms,
            },
        ))

    async def _update_session_totals(
        self, db: AsyncSession, session: Session
    ) -> None:
        result = await db.execute(
            select(LLMCall).where(LLMCall.session_id == session.id)
        )
        calls = result.scalars().all()
        session.total_input_tokens = sum(c.input_tokens for c in calls)
        session.total_output_tokens = sum(c.output_tokens for c in calls)
        session.total_cost = sum(float(c.cost) for c in calls)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                async with async_session_factory() as db:
                    session = await db.get(Session, self.session_id)
                    if session:
                        session.last_heartbeat_at = datetime.now(UTC)
                        await db.commit()
            except Exception:
                pass


async def cleanup_orphaned_sessions() -> None:
    """Mark stuck sessions as failed. Call on app startup."""
    from datetime import timedelta

    async with async_session_factory() as db:
        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        result = await db.execute(
            select(Session).where(
                Session.status.in_(["pending", "responding", "critiquing"]),
                Session.last_heartbeat_at < cutoff,
            )
        )
        for session in result.scalars().all():
            session.status = "failed"
            session.completed_at = datetime.now(UTC)
        await db.commit()
```

**Step 2: Run existing orchestrator tests**

Run: `cd backend && uv run pytest tests/test_consensus_orchestrator.py -v`
Expected: All 4 tests PASS (the API is backward-compatible — `TestModel` supports both `run()` and `run_stream()`)

**Important note about `TestModel` and `stream_responses()`:** PydanticAI's `TestModel` supports `run_stream()`. It produces a single response chunk. `stream_responses()` will yield one `(response, True)` tuple. `validate_response_output(response, allow_partial=False)` will return the full structured output. So existing tests should pass without changes.

If `stream_responses()` is not supported by `TestModel`, fall back: add a `_use_streaming` flag to the orchestrator that defaults to `True` but can be set to `False` for tests. Only do this if tests fail.

**Step 3: Add streaming-specific orchestrator tests**

Append to `backend/tests/test_consensus_orchestrator.py`:

```python
from app.consensus.broadcast import StreamEvent, get_broadcast


@pytest.mark.asyncio
async def test_orchestrator_emits_streaming_events(db_session):
    """Verify the orchestrator pushes model_start, model_done, phase_change events."""
    user, provider, m1, m2 = await _create_test_data(db_session)

    session = Session(user_id=user.id, enquiry="What is 2+2?")
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    orchestrator = ConsensusOrchestrator(session.id, user.id)
    consumer = orchestrator.broadcast.subscribe()

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    events: list[StreamEvent] = [e async for e in consumer]
    event_types = [e.event for e in events]

    # Should have model_start events for each model in round 1
    model_starts = [e for e in events if e.event == "model_start"]
    assert len(model_starts) >= 2

    # Should have model_done events
    model_dones = [e for e in events if e.event == "model_done"]
    assert len(model_dones) >= 2

    # Should have phase_change
    assert "phase_change" in event_types

    # Should have terminal event
    assert "consensus_reached" in event_types

    # Cleanup
    result = await db_session.execute(
        select(LLMCall).where(LLMCall.session_id == session.id)
    )
    for call in result.scalars().all():
        await db_session.delete(call)
    await db_session.delete(session)
    await db_session.delete(m1)
    await db_session.delete(m2)
    await db_session.delete(provider)
    await db_session.delete(user)
    await db_session.commit()
```

**Step 4: Run all orchestrator tests**

Run: `cd backend && uv run pytest tests/test_consensus_orchestrator.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add backend/app/consensus/service.py backend/tests/test_consensus_orchestrator.py
git commit -m "feat: switch orchestrator to streaming with broadcast events"
```

---

### Task 4: Backend — Push-based SSE endpoint

**Files:**
- Modify: `backend/app/consensus/router.py`
- Test: `backend/tests/test_session_endpoints.py` (update existing tests)

Replace the DB-polling `_session_event_generator` with a push-based approach using the broadcast.

**Step 1: Rewrite the SSE generator**

Replace `_session_event_generator` in `backend/app/consensus/router.py`:

```python
import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sse_starlette import EventSourceResponse
from starlette.requests import Request

from app.auth.dependencies import get_current_user
from app.consensus.broadcast import get_broadcast
from app.consensus.schemas import (
    CreateSessionRequest,
    LLMCallResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from app.consensus.service import ConsensusOrchestrator
from app.database import async_session_factory, get_db
from app.models import LLMCall, LLMModel, Session, User
from app.models.session import session_models

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_background_tasks: set[asyncio.Task] = set()

TERMINAL_STATUSES = ("consensus_reached", "max_rounds_reached", "failed")


# _session_to_response, create_session, list_sessions — UNCHANGED (keep as-is)


async def _session_event_generator(request: Request, session_id: UUID, user_id: UUID):
    """Replay completed calls from DB, then stream live events from broadcast."""
    async with async_session_factory() as db:
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            return

        # Step 1: Replay completed llm_calls from DB
        result = await db.execute(
            select(LLMCall)
            .where(LLMCall.session_id == session_id)
            .options(joinedload(LLMCall.llm_model).joinedload(LLMModel.provider))
            .order_by(LLMCall.round_number, LLMCall.created_at)
        )
        calls = result.scalars().unique().all()

        for call in calls:
            if await request.is_disconnected():
                return
            yield {
                "event": "model_done",
                "data": json.dumps({
                    "llm_model_id": str(call.llm_model_id),
                    "round_number": call.round_number,
                    "role": call.role,
                    "response": call.response,
                    "error": call.error,
                    "structured": {},
                    "input_tokens": call.input_tokens,
                    "output_tokens": call.output_tokens,
                    "cost": float(call.cost) if call.cost else 0,
                    "duration_ms": call.duration_ms,
                }),
            }

        # Step 2: If session is terminal, send terminal event and close
        await db.refresh(session)
        if session.status in TERMINAL_STATUSES:
            yield {
                "event": session.status,
                "data": json.dumps({
                    "status": session.status,
                    "current_round": session.current_round,
                    "total_input_tokens": session.total_input_tokens,
                    "total_output_tokens": session.total_output_tokens,
                    "total_cost": float(session.total_cost),
                    "total_duration_ms": session.total_duration_ms,
                }),
            }
            return

    # Step 3: Attach to live broadcast
    broadcast = get_broadcast(session_id)
    if not broadcast:
        return

    # Send catchup for in-progress models
    catchup = broadcast.get_catchup()
    for model_id, text_so_far in catchup.items():
        yield {
            "event": "model_catchup",
            "data": json.dumps({
                "llm_model_id": model_id,
                "text_so_far": text_so_far,
            }),
        }

    consumer = broadcast.subscribe()
    keepalive_seconds = 15
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(
                    consumer.__anext__(), timeout=keepalive_seconds
                )
                yield {
                    "event": event.event,
                    "data": json.dumps(event.data),
                }
                # Stop after terminal events
                if event.event in TERMINAL_STATUSES:
                    break
            except TimeoutError:
                yield {"comment": "keepalive"}
            except StopAsyncIteration:
                break
    finally:
        broadcast.unsubscribe(consumer)
```

**Step 2: Run existing endpoint tests**

Run: `cd backend && uv run pytest tests/test_session_endpoints.py -v`
Expected: All PASS (create, list, detail, delete endpoints unchanged)

**Step 3: Commit**

```bash
git add backend/app/consensus/router.py
git commit -m "feat: replace DB-polling SSE with push-based broadcast streaming"
```

---

### Task 5: Frontend — Update types for streaming events

**Files:**
- Modify: `frontend/src/types/session.ts`

**Step 1: Update types**

```typescript
// frontend/src/types/session.ts
export interface SessionSummary {
  id: string;
  enquiry: string;
  status: string;
  max_rounds: number | null;
  current_round: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  total_duration_ms: number;
  created_at: string;
  completed_at: string | null;
  model_ids: string[];
}

// Model info from session detail API
export interface SessionModel {
  id: string;
  slug: string;
  display_name: string;
  provider_slug: string;
}

// Streaming events
export interface ModelStartEvent {
  llm_model_id: string;
  round_number: number;
  role: "responder" | "critic";
}

export interface TokenDeltaEvent {
  llm_model_id: string;
  round_number: number;
  delta: string;
}

export interface ModelDoneEvent {
  llm_model_id: string;
  round_number: number;
  role: "responder" | "critic" | "summarizer";
  response?: string;
  error?: string | null;
  structured: Record<string, unknown>;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  duration_ms: number;
}

export interface ModelErrorEvent {
  llm_model_id: string;
  round_number: number;
  error: string;
}

export interface ModelCatchupEvent {
  llm_model_id: string;
  text_so_far: string;
}

export interface PhaseChangeEvent {
  from_phase: string;
  to_phase: string;
  round_number: number;
  summary: {
    models_completed: number;
    models_failed: number;
  };
  model_details: Array<{
    llm_model_id: string;
    confidence?: number;
    key_points?: string[];
    disagreements?: string[];
  }>;
}

export interface RoundSummaryEvent {
  round_number: number;
  agreements: string[];
  disagreements: string[];
  shifts: string[];
}

export interface TerminalEvent {
  status: string;
  current_round: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  total_duration_ms: number;
}

export type SessionStatus =
  | "pending"
  | "responding"
  | "critiquing"
  | "consensus_reached"
  | "max_rounds_reached"
  | "failed";

// Keep for backward compat with session detail API
export interface LLMCallEvent {
  id: string;
  llm_model_id: string;
  model_slug: string;
  provider_slug: string;
  round_number: number;
  role: "responder" | "critic" | "summarizer";
  response: string;
  error: string | null;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  duration_ms: number;
}

export const MODEL_COLORS = [
  "blue",
  "green",
  "orange",
  "grape",
  "cyan",
  "pink",
  "teal",
  "indigo",
] as const;
```

**Step 2: Commit**

```bash
git add frontend/src/types/session.ts
git commit -m "feat: add streaming event types for token-by-token SSE"
```

---

### Task 6: Frontend — Rewrite useConsensusStream hook

**Files:**
- Modify: `frontend/src/hooks/useConsensusStream.ts`

The hook now manages per-model streaming state (accumulated text, status) plus phase changes and round summaries.

**Step 1: Rewrite the hook**

```typescript
// frontend/src/hooks/useConsensusStream.ts
import { useCallback, useEffect, useRef, useState } from "react";
import { SSE } from "sse.js";
import { getAccessToken } from "@/lib/api";
import type {
  ModelDoneEvent,
  ModelErrorEvent,
  ModelStartEvent,
  ModelCatchupEvent,
  PhaseChangeEvent,
  RoundSummaryEvent,
  SessionStatus,
  TerminalEvent,
  TokenDeltaEvent,
} from "@/types/session";

export interface ModelStreamState {
  llm_model_id: string;
  round_number: number;
  role: "responder" | "critic";
  text: string;
  isStreaming: boolean;
  isDone: boolean;
  error: string | null;
  structured: Record<string, unknown> | null;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  duration_ms: number;
}

export interface PhaseInfo {
  round_number: number;
  phase: string;
  summary: PhaseChangeEvent["summary"];
  model_details: PhaseChangeEvent["model_details"];
  roundSummary: RoundSummaryEvent | null;
  collapsed: boolean;
}

interface ConsensusStreamState {
  models: Map<string, ModelStreamState>;
  phases: PhaseInfo[];
  currentRound: number;
  status: SessionStatus;
  terminalEvent: TerminalEvent | null;
  isConnected: boolean;
  error: string | null;
}

interface UseConsensusStreamOptions {
  sessionId: string;
  enabled?: boolean;
}

export function useConsensusStream({ sessionId, enabled = true }: UseConsensusStreamOptions) {
  const [state, setState] = useState<ConsensusStreamState>({
    models: new Map(),
    phases: [],
    currentRound: 0,
    status: "pending",
    terminalEvent: null,
    isConnected: false,
    error: null,
  });
  const sourceRef = useRef<SSE | null>(null);

  const connect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    const token = getAccessToken();
    const source = new SSE(`/api/sessions/${sessionId}/stream`, {
      headers: { Authorization: `Bearer ${token}` },
      start: false,
    });

    source.addEventListener("model_start", (e: MessageEvent) => {
      const data: ModelStartEvent = JSON.parse(e.data);
      setState((prev) => {
        const models = new Map(prev.models);
        const key = `${data.llm_model_id}-${data.round_number}`;
        models.set(key, {
          llm_model_id: data.llm_model_id,
          round_number: data.round_number,
          role: data.role,
          text: "",
          isStreaming: true,
          isDone: false,
          error: null,
          structured: null,
          input_tokens: 0,
          output_tokens: 0,
          cost: 0,
          duration_ms: 0,
        });
        return {
          ...prev,
          models,
          currentRound: data.round_number,
          status: data.role === "responder" ? "responding" : "critiquing",
        };
      });
    });

    source.addEventListener("token_delta", (e: MessageEvent) => {
      const data: TokenDeltaEvent = JSON.parse(e.data);
      setState((prev) => {
        const models = new Map(prev.models);
        const key = `${data.llm_model_id}-${data.round_number}`;
        const model = models.get(key);
        if (model) {
          models.set(key, { ...model, text: model.text + data.delta });
        }
        return { ...prev, models };
      });
    });

    source.addEventListener("model_done", (e: MessageEvent) => {
      const data: ModelDoneEvent = JSON.parse(e.data);
      setState((prev) => {
        const models = new Map(prev.models);
        const key = `${data.llm_model_id}-${data.round_number}`;
        const existing = models.get(key);
        models.set(key, {
          llm_model_id: data.llm_model_id,
          round_number: data.round_number,
          role: data.role as "responder" | "critic",
          text: existing?.text || data.response || "",
          isStreaming: false,
          isDone: true,
          error: data.error || null,
          structured: data.structured,
          input_tokens: data.input_tokens,
          output_tokens: data.output_tokens,
          cost: data.cost,
          duration_ms: data.duration_ms,
        });
        return { ...prev, models };
      });
    });

    source.addEventListener("model_error", (e: MessageEvent) => {
      const data: ModelErrorEvent = JSON.parse(e.data);
      setState((prev) => {
        const models = new Map(prev.models);
        const key = `${data.llm_model_id}-${data.round_number}`;
        const existing = models.get(key);
        if (existing) {
          models.set(key, {
            ...existing,
            isStreaming: false,
            isDone: true,
            error: data.error,
          });
        }
        return { ...prev, models };
      });
    });

    source.addEventListener("model_catchup", (e: MessageEvent) => {
      const data: ModelCatchupEvent = JSON.parse(e.data);
      setState((prev) => {
        const models = new Map(prev.models);
        // Find the active entry for this model
        for (const [key, model] of models) {
          if (model.llm_model_id === data.llm_model_id && model.isStreaming) {
            models.set(key, { ...model, text: data.text_so_far });
            break;
          }
        }
        return { ...prev, models };
      });
    });

    source.addEventListener("phase_change", (e: MessageEvent) => {
      const data: PhaseChangeEvent = JSON.parse(e.data);
      setState((prev) => {
        // Collapse previous phases
        const phases = prev.phases.map((p) => ({ ...p, collapsed: true }));
        phases.push({
          round_number: data.round_number,
          phase: data.to_phase,
          summary: data.summary,
          model_details: data.model_details,
          roundSummary: null,
          collapsed: false,
        });
        return { ...prev, phases };
      });
    });

    source.addEventListener("round_summary", (e: MessageEvent) => {
      const data: RoundSummaryEvent = JSON.parse(e.data);
      setState((prev) => {
        const phases = prev.phases.map((p) =>
          p.round_number === data.round_number ? { ...p, roundSummary: data } : p
        );
        return { ...prev, phases };
      });
    });

    const handleTerminal = (eventType: string) => (e: MessageEvent) => {
      const data: TerminalEvent = JSON.parse(e.data);
      setState((prev) => ({
        ...prev,
        status: eventType as SessionStatus,
        terminalEvent: data,
        isConnected: false,
      }));
      source.close();
    };

    source.addEventListener("consensus_reached", handleTerminal("consensus_reached"));
    source.addEventListener("max_rounds_reached", handleTerminal("max_rounds_reached"));
    source.addEventListener("failed", handleTerminal("failed"));

    source.addEventListener("open", () => {
      setState((prev) => ({ ...prev, isConnected: true, error: null }));
    });

    source.addEventListener("error", () => {
      setState((prev) => ({ ...prev, isConnected: false, error: "Connection lost" }));
    });

    sourceRef.current = source;
    source.stream();
  }, [sessionId]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return () => {
      sourceRef.current?.close();
    };
  }, [enabled, connect]);

  return state;
}
```

**Step 2: Commit**

```bash
git add frontend/src/hooks/useConsensusStream.ts
git commit -m "feat: rewrite useConsensusStream for token-by-token streaming"
```

---

### Task 7: Frontend — Streaming column components

**Files:**
- Create: `frontend/src/components/consensus/StreamingColumn.tsx`
- Create: `frontend/src/components/consensus/PhaseDivider.tsx`
- Delete or keep: `frontend/src/components/consensus/ChatMessage.tsx` (no longer used by session page, but keep if used elsewhere)

**Step 1: Create StreamingColumn component**

```tsx
// frontend/src/components/consensus/StreamingColumn.tsx
"use client";

import { Alert, Badge, Box, Group, Loader, ScrollArea, Text } from "@mantine/core";
import { IconAlertTriangle, IconCheck } from "@tabler/icons-react";
import { useEffect, useRef } from "react";
import type { ModelStreamState } from "@/hooks/useConsensusStream";

interface StreamingColumnProps {
  model: ModelStreamState;
  displayName: string;
  allModelsDone: boolean;
}

export function StreamingColumn({ model, displayName, allModelsDone }: StreamingColumnProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [model.text]);

  return (
    <Box
      miw={350}
      style={{
        flex: "1 1 0",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--mantine-color-dark-4)",
        opacity: model.error ? 0.5 : 1,
      }}
    >
      {/* Column header */}
      <Group gap="xs" px="md" py="sm" style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
        <Text fw={600} size="sm" style={{ flex: 1 }}>
          {displayName}
        </Text>
        {model.isStreaming && <Loader size={14} />}
        {model.isDone && !model.error && (
          <Badge size="sm" color="green" variant="light" leftSection={<IconCheck size={12} />}>
            Done
          </Badge>
        )}
        {model.error && (
          <Badge size="sm" color="red" variant="light" leftSection={<IconAlertTriangle size={12} />}>
            Error
          </Badge>
        )}
      </Group>

      {/* Streaming text area */}
      <ScrollArea flex={1} px="md" py="sm" viewportRef={scrollRef}>
        <Text
          size="sm"
          style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
        >
          {model.text}
          {model.isStreaming && (
            <Text
              component="span"
              style={{
                animation: "blink 1s step-end infinite",
              }}
            >
              |
            </Text>
          )}
        </Text>

        {/* Error alert */}
        {model.error && (
          <Alert color="red" mt="sm" title="Error">
            {model.error}
          </Alert>
        )}

        {/* Waiting message */}
        {model.isDone && !model.error && !allModelsDone && (
          <Text size="xs" c="dimmed" mt="md" ta="center" fs="italic">
            Waiting for other models to finish...
          </Text>
        )}
      </ScrollArea>
    </Box>
  );
}
```

**Step 2: Create PhaseDivider component**

```tsx
// frontend/src/components/consensus/PhaseDivider.tsx
"use client";

import { ActionIcon, Badge, Box, Collapse, Group, List, Paper, Text } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import type { PhaseInfo } from "@/hooks/useConsensusStream";

interface PhaseDividerProps {
  phase: PhaseInfo;
  modelNames: Map<string, string>;
  onToggle: () => void;
}

export function PhaseDivider({ phase, modelNames, onToggle }: PhaseDividerProps) {
  const label = phase.round_number === 1
    ? "Initial Responses"
    : `Round ${phase.round_number} — Critique`;

  return (
    <Paper bg="dark.8" px="md" py="sm" radius={0}>
      <Group gap="xs" style={{ cursor: "pointer" }} onClick={onToggle}>
        <ActionIcon variant="subtle" size="sm">
          {phase.collapsed ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
        </ActionIcon>
        <Text fw={600} size="sm">{label}</Text>
        <Badge size="xs" variant="light">
          {phase.summary.models_completed} completed
          {phase.summary.models_failed > 0 && `, ${phase.summary.models_failed} failed`}
        </Badge>
      </Group>

      <Collapse in={!phase.collapsed}>
        <Box mt="sm">
          {/* Per-model structured data */}
          {phase.model_details.map((detail) => (
            <Box key={detail.llm_model_id} mb="xs">
              <Text size="xs" c="dimmed" fw={600}>
                {modelNames.get(detail.llm_model_id) || detail.llm_model_id}
              </Text>
              {detail.confidence !== undefined && (
                <Text size="xs" c="dimmed">
                  Confidence: {(detail.confidence * 100).toFixed(0)}%
                </Text>
              )}
              {detail.key_points && detail.key_points.length > 0 && (
                <List size="xs" c="dimmed">
                  {detail.key_points.map((kp, i) => (
                    <List.Item key={i}>{kp}</List.Item>
                  ))}
                </List>
              )}
              {detail.disagreements && detail.disagreements.length > 0 && (
                <List size="xs" c="yellow.5">
                  {detail.disagreements.map((d, i) => (
                    <List.Item key={i}>{d}</List.Item>
                  ))}
                </List>
              )}
            </Box>
          ))}

          {/* Round summary */}
          {phase.roundSummary && (
            <Box mt="xs" pt="xs" style={{ borderTop: "1px solid var(--mantine-color-dark-5)" }}>
              <Text size="xs" c="dimmed" fw={600}>Round Summary</Text>
              {phase.roundSummary.agreements.length > 0 && (
                <>
                  <Text size="xs" c="green.5">Agreements:</Text>
                  <List size="xs" c="dimmed">
                    {phase.roundSummary.agreements.map((a, i) => <List.Item key={i}>{a}</List.Item>)}
                  </List>
                </>
              )}
              {phase.roundSummary.disagreements.length > 0 && (
                <>
                  <Text size="xs" c="yellow.5">Disagreements:</Text>
                  <List size="xs" c="dimmed">
                    {phase.roundSummary.disagreements.map((d, i) => <List.Item key={i}>{d}</List.Item>)}
                  </List>
                </>
              )}
            </Box>
          )}
        </Box>
      </Collapse>
    </Paper>
  );
}
```

**Step 3: Add blink animation to global styles**

Add to `frontend/src/app/global.css` (or equivalent):

```css
@keyframes blink {
  50% { opacity: 0; }
}
```

**Step 4: Commit**

```bash
git add frontend/src/components/consensus/StreamingColumn.tsx \
       frontend/src/components/consensus/PhaseDivider.tsx \
       frontend/src/app/global.css
git commit -m "feat: add StreamingColumn and PhaseDivider components"
```

---

### Task 8: Frontend — Rewrite session detail page

**Files:**
- Modify: `frontend/src/app/(protected)/sessions/[id]/page.tsx`

Replace the chat-style layout with the columnar streaming layout. Also fix the bug where completed sessions show no data (use session detail API to populate).

**Step 1: Rewrite the page**

```tsx
// frontend/src/app/(protected)/sessions/[id]/page.tsx
"use client";

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { Box, Loader, Paper, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { ConsensusBanner } from "@/components/consensus/ConsensusBanner";
import { PhaseDivider } from "@/components/consensus/PhaseDivider";
import { StreamingColumn } from "@/components/consensus/StreamingColumn";
import { useConsensusStream } from "@/hooks/useConsensusStream";
import type { LLMCallEvent, SessionStatus, TerminalEvent } from "@/types/session";

interface SessionDetail {
  id: string;
  enquiry: string;
  status: string;
  max_rounds: number | null;
  current_round: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost: number;
  total_duration_ms: number;
  created_at: string;
  completed_at: string | null;
  model_ids: string[];
  llm_calls: LLMCallEvent[];
}

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();

  // Fetch session detail (includes llm_calls for completed sessions)
  const { data: session } = useQuery<SessionDetail>({
    queryKey: ["session-detail", id],
    queryFn: async () => {
      const res = await apiFetch(`/api/sessions/${id}`);
      return res.json();
    },
  });

  const isTerminal = ["consensus_reached", "max_rounds_reached", "failed"].includes(
    session?.status || ""
  );

  // Stream events for live sessions
  const stream = useConsensusStream({ sessionId: id, enabled: !isTerminal });

  // Build model name map from available models query
  const { data: allModels } = useQuery<Array<{ id: string; slug: string; display_name: string; provider: { slug: string } }>>({
    queryKey: ["models"],
    queryFn: async () => {
      const res = await apiFetch("/api/models");
      return res.json();
    },
  });

  const modelNames = useMemo(() => {
    const map = new Map<string, string>();
    if (allModels) {
      for (const m of allModels) {
        map.set(m.id, `${m.provider.slug}/${m.slug}`);
      }
    }
    return map;
  }, [allModels]);

  // Phase toggle
  const [phaseCollapseOverrides, setPhaseCollapseOverrides] = useState<Map<number, boolean>>(new Map());

  const togglePhase = useCallback((roundNumber: number) => {
    setPhaseCollapseOverrides((prev) => {
      const next = new Map(prev);
      const phase = stream.phases.find((p) => p.round_number === roundNumber);
      const currentCollapsed = prev.has(roundNumber) ? prev.get(roundNumber) : phase?.collapsed;
      next.set(roundNumber, !currentCollapsed);
      return next;
    });
  }, [stream.phases]);

  // For completed sessions, build static view from session.llm_calls
  if (isTerminal && session) {
    return <CompletedSessionView session={session} modelNames={modelNames} />;
  }

  // Get current round's models
  const currentRoundModels = useMemo(() => {
    const models: Array<{ key: string; model: (typeof stream.models extends Map<string, infer V> ? V : never) }> = [];
    for (const [key, model] of stream.models) {
      if (model.round_number === stream.currentRound) {
        models.push({ key, model });
      }
    }
    return models;
  }, [stream.models, stream.currentRound]);

  const allCurrentDone = currentRoundModels.length > 0 && currentRoundModels.every(({ model }) => model.isDone);

  return (
    <Stack gap={0} h="100%">
      {/* Enquiry header */}
      {session && (
        <Paper p="md" radius={0} bg="dark.8" style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
          <Text size="xs" c="dimmed" fw={600}>Your enquiry</Text>
          <Text size="sm">{session.enquiry}</Text>
        </Paper>
      )}

      {/* Phase dividers (completed rounds) */}
      {stream.phases.map((phase) => {
        const effectiveCollapsed = phaseCollapseOverrides.has(phase.round_number)
          ? phaseCollapseOverrides.get(phase.round_number)!
          : phase.collapsed;
        return (
          <PhaseDivider
            key={phase.round_number}
            phase={{ ...phase, collapsed: effectiveCollapsed }}
            modelNames={modelNames}
            onToggle={() => togglePhase(phase.round_number)}
          />
        );
      })}

      {/* Current round: streaming columns */}
      {currentRoundModels.length > 0 && (
        <Box style={{ display: "flex", flex: 1, overflowX: "auto" }}>
          {currentRoundModels.map(({ key, model }) => (
            <StreamingColumn
              key={key}
              model={model}
              displayName={modelNames.get(model.llm_model_id) || model.llm_model_id}
              allModelsDone={allCurrentDone}
            />
          ))}
        </Box>
      )}

      {/* Loading indicator */}
      {stream.isConnected && currentRoundModels.length === 0 && (
        <Box ta="center" py="xl">
          <Loader size="sm" />
          <Text size="xs" c="dimmed" mt={4}>Starting consensus...</Text>
        </Box>
      )}

      {/* Terminal banner */}
      {stream.terminalEvent && (
        <ConsensusBanner
          type={stream.status as "consensus_reached" | "max_rounds_reached" | "failed"}
          event={stream.terminalEvent}
        />
      )}
    </Stack>
  );
}

/**
 * Static view for completed sessions — renders all rounds from DB data.
 */
function CompletedSessionView({
  session,
  modelNames,
}: {
  session: SessionDetail;
  modelNames: Map<string, string>;
}) {
  const [collapsedRounds, setCollapsedRounds] = useState<Set<number>>(new Set());

  // Group calls by round
  const rounds = useMemo(() => {
    const grouped = new Map<number, LLMCallEvent[]>();
    for (const call of session.llm_calls) {
      const existing = grouped.get(call.round_number) || [];
      existing.push(call);
      grouped.set(call.round_number, existing);
    }
    return grouped;
  }, [session.llm_calls]);

  const toggleRound = (round: number) => {
    setCollapsedRounds((prev) => {
      const next = new Set(prev);
      if (next.has(round)) {
        next.delete(round);
      } else {
        next.add(round);
      }
      return next;
    });
  };

  const terminalEvent: TerminalEvent = {
    status: session.status,
    current_round: session.current_round,
    total_input_tokens: session.total_input_tokens,
    total_output_tokens: session.total_output_tokens,
    total_cost: session.total_cost,
    total_duration_ms: session.total_duration_ms,
  };

  return (
    <Stack gap={0} h="100%">
      <Paper p="md" radius={0} bg="dark.8" style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
        <Text size="xs" c="dimmed" fw={600}>Your enquiry</Text>
        <Text size="sm">{session.enquiry}</Text>
      </Paper>

      {[...rounds.entries()].map(([roundNum, calls]) => {
        const nonSummarizer = calls.filter((c) => c.role !== "summarizer");
        const isCollapsed = collapsedRounds.has(roundNum);

        return (
          <Box key={roundNum}>
            {/* Round header */}
            <Paper
              bg="dark.8"
              px="md"
              py="sm"
              radius={0}
              style={{ cursor: "pointer", borderBottom: "1px solid var(--mantine-color-dark-5)" }}
              onClick={() => toggleRound(roundNum)}
            >
              <Text fw={600} size="sm">
                {roundNum === 1 ? "Round 1 — Initial Responses" : `Round ${roundNum} — Critique`}
              </Text>
            </Paper>

            {/* Columns for this round */}
            {!isCollapsed && (
              <Box style={{ display: "flex", overflowX: "auto", minHeight: 200 }}>
                {nonSummarizer.map((call) => (
                  <Box
                    key={call.id}
                    miw={350}
                    style={{
                      flex: "1 1 0",
                      borderRight: "1px solid var(--mantine-color-dark-4)",
                      opacity: call.error ? 0.5 : 1,
                    }}
                    px="md"
                    py="sm"
                  >
                    <Text fw={600} size="sm" mb="xs">
                      {modelNames.get(call.llm_model_id) || `${call.provider_slug}/${call.model_slug}`}
                    </Text>
                    <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                      {call.response}
                    </Text>
                    {call.error && (
                      <Text size="sm" c="red" mt="sm">{call.error}</Text>
                    )}
                  </Box>
                ))}
              </Box>
            )}
          </Box>
        );
      })}

      <ConsensusBanner
        type={session.status as "consensus_reached" | "max_rounds_reached" | "failed"}
        event={terminalEvent}
      />
    </Stack>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/app/(protected)/sessions/[id]/page.tsx
git commit -m "feat: rewrite session page with columnar streaming layout"
```

---

### Task 9: Frontend tests

**Files:**
- Create: `frontend/src/hooks/__tests__/useConsensusStream.test.ts`
- Create: `frontend/src/components/consensus/__tests__/StreamingColumn.test.tsx`

**Step 1: Write hook tests**

```typescript
// frontend/src/hooks/__tests__/useConsensusStream.test.ts
import { describe, it, expect, vi } from "vitest";

// This tests the state logic conceptually — full hook tests require SSE mocking
// which is complex. Focus on the component-level tests instead.

describe("useConsensusStream types", () => {
  it("ModelStreamState has required fields", async () => {
    // Type-level check — if this compiles, types are correct
    const state: import("@/hooks/useConsensusStream").ModelStreamState = {
      llm_model_id: "test",
      round_number: 1,
      role: "responder",
      text: "",
      isStreaming: true,
      isDone: false,
      error: null,
      structured: null,
      input_tokens: 0,
      output_tokens: 0,
      cost: 0,
      duration_ms: 0,
    };
    expect(state.isStreaming).toBe(true);
  });
});
```

**Step 2: Write StreamingColumn tests**

```tsx
// frontend/src/components/consensus/__tests__/StreamingColumn.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import React from "react";

// Mock Mantine with lightweight components
vi.mock("@mantine/core", () => {
  const R = require("react");
  const wrap = () => (props: Record<string, unknown>) => R.createElement("div", null, props.children);
  return {
    Alert: (props: Record<string, unknown>) => R.createElement("div", { role: "alert" }, props.children),
    Badge: (props: Record<string, unknown>) => R.createElement("span", null, props.children),
    Box: (props: Record<string, unknown>) => R.createElement("div", { style: props.style }, props.children),
    Group: wrap(),
    Loader: () => R.createElement("span", null, "loading..."),
    ScrollArea: Object.assign(
      (props: Record<string, unknown>) => R.createElement("div", null, props.children),
      { Autosize: wrap() }
    ),
    Text: (props: Record<string, unknown>) => R.createElement("span", null, props.children),
  };
});

vi.mock("@tabler/icons-react", () => {
  const R = require("react");
  const icon = () => () => R.createElement("span");
  return { IconAlertTriangle: icon(), IconCheck: icon() };
});

import { StreamingColumn } from "../StreamingColumn";
import type { ModelStreamState } from "@/hooks/useConsensusStream";

const baseModel: ModelStreamState = {
  llm_model_id: "model-1",
  round_number: 1,
  role: "responder",
  text: "",
  isStreaming: false,
  isDone: false,
  error: null,
  structured: null,
  input_tokens: 0,
  output_tokens: 0,
  cost: 0,
  duration_ms: 0,
};

describe("StreamingColumn", () => {
  it("renders model name", () => {
    render(<StreamingColumn model={baseModel} displayName="openai/gpt-4o" allModelsDone={false} />);
    expect(screen.getByText("openai/gpt-4o")).toBeInTheDocument();
  });

  it("shows streaming text with cursor", () => {
    const model = { ...baseModel, text: "Hello world", isStreaming: true };
    render(<StreamingColumn model={model} displayName="test" allModelsDone={false} />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
    expect(screen.getByText("|")).toBeInTheDocument();
  });

  it("shows Done badge when complete", () => {
    const model = { ...baseModel, text: "Complete response", isDone: true };
    render(<StreamingColumn model={model} displayName="test" allModelsDone={true} />);
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("shows waiting message when done but others still streaming", () => {
    const model = { ...baseModel, text: "Done", isDone: true };
    render(<StreamingColumn model={model} displayName="test" allModelsDone={false} />);
    expect(screen.getByText("Waiting for other models to finish...")).toBeInTheDocument();
  });

  it("shows error alert with reduced opacity", () => {
    const model = { ...baseModel, text: "Partial", isDone: true, error: "timeout after 60s" };
    render(<StreamingColumn model={model} displayName="test" allModelsDone={false} />);
    expect(screen.getByText("timeout after 60s")).toBeInTheDocument();
  });
});
```

**Step 3: Run frontend tests**

Run: `cd frontend && bun run test`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add frontend/src/hooks/__tests__/useConsensusStream.test.ts \
       frontend/src/components/consensus/__tests__/StreamingColumn.test.tsx
git commit -m "test: add streaming column and hook tests"
```

---

### Task 10: Backend — Run full test suite and fix any issues

**Step 1: Run all backend tests**

Run: `cd backend && uv run pytest -v`
Expected: All tests PASS. If any fail due to the streaming changes, fix them.

**Common issues to watch for:**
- `TestModel` might not support `stream_responses()` — if so, the orchestrator needs a fallback. Check PydanticAI docs for `TestModel` streaming support.
- The `_call_responder` return type changed from `dict[str, str]` to `dict` (now includes `llm_model_id`, `confidence`, `key_points`). Ensure all references handle this.
- `_run_responder_round` error handling loop references `list(self._active_models)` — ensure the zip iteration doesn't break with the new return type.

**Step 2: Run all frontend tests**

Run: `cd frontend && bun run test`
Expected: All tests PASS. The new session page test may need updating since the component structure changed.

**Step 3: Run linting**

Run: `cd backend && uv run ruff check . && cd ../frontend && bun run lint`
Expected: No errors

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test and lint issues from streaming refactor"
```

---

### Task 11: Integration smoke test

**Step 1: Start the full stack**

Run: `make up` (or `docker compose up`)

**Step 2: Manual verification**

1. Log in via magic link
2. Go to Settings, ensure API keys are configured
3. Create a new session with 2+ models
4. Verify:
   - Columns appear immediately for each model
   - Text streams in token-by-token with blinking cursor
   - "Done" badge appears when each model finishes
   - "Waiting for other models..." shows on early finishers
   - Phase divider appears between rounds
   - Consensus banner shows at the end
5. Refresh the page — verify the completed session shows all rounds in columnar layout
6. Navigate away and come back — same verification

**Step 3: Final commit and update PLAN.md progress**

```bash
# Update PLAN.md progress table
git add PLAN.md
git commit -m "docs: mark streaming UX milestone as done"
```

---

## Notes for the implementing engineer

### PydanticAI streaming with structured output

The key pattern for streaming structured output is:

```python
async with agent.run_stream(prompt) as result:
    prev_text = ""
    async for response, last in result.stream_responses(debounce_by=0.01):
        try:
            partial = await result.validate_response_output(
                response, allow_partial=not last
            )
            # Track the text field (response or revised_response)
            current_text = partial.response
            if len(current_text) > len(prev_text):
                delta = current_text[len(prev_text):]
                # push delta
                prev_text = current_text
        except ValidationError:
            continue
    # After loop: result.output has full structured output
    # result.usage() has token counts
```

`allow_partial=True` tells Pydantic to accept incomplete objects (missing required fields). This is necessary because during streaming, only part of the JSON has been generated.

### TestModel and streaming

PydanticAI's `TestModel` supports `run_stream()`. It produces a single response chunk. `stream_responses()` will yield one `(response, True)` tuple. If this doesn't work, add a `_use_streaming: bool` parameter to the orchestrator class defaulting to `True`, and fall back to `agent.run()` when `False`. Set to `False` in tests.

### Frontend state management

The hook uses a `Map<string, ModelStreamState>` keyed by `{llm_model_id}-{round_number}`. This ensures each model in each round has its own state. When a new round starts, new entries are created — old ones remain for reference by the completed session view.

### Replay for completed sessions

The session detail page checks `isTerminal` first. If the session is already complete, it renders `CompletedSessionView` which uses data from `GET /api/sessions/{id}` (includes `llm_calls`). No streaming is needed. This fixes the existing bug where completed sessions show nothing.
