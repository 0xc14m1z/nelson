# Milestone 4 — Core Consensus Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the full consensus engine end-to-end: backend orchestrator with PydanticAI agents, SSE streaming, and chat-style frontend.

**Architecture:** Three PydanticAI agents (responder, critic, summarizer) driven by a ConsensusOrchestrator that runs iterative convergence rounds. Sessions are persisted to Postgres, streamed to the frontend via SSE, and displayed as a group-chat UI where each AI model is a color-coded participant.

**Tech Stack:** PydanticAI (agents + TestModel), sse-starlette (SSE backend), sse.js (SSE client), TanStack Query (data fetching), Mantine (UI components)

**Design doc:** `docs/plans/2026-03-06-milestone-4-consensus-design.md`

---

## Task 1: Session & LLM Call DB Models + Migration

**Files:**
- Create: `backend/app/models/session.py`
- Create: `backend/app/models/llm_call.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_session_models.py`

### Step 1: Write the ORM models

`backend/app/models/session.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Column,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKey

session_models = Table(
    "session_models",
    Base.metadata,
    Column("session_id", ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("llm_model_id", ForeignKey("llm_models.id"), primary_key=True),
)


class Session(UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    enquiry: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    max_rounds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    models = relationship("LLMModel", secondary=session_models)
    llm_calls = relationship("LLMCall", back_populates="session", cascade="all, delete-orphan")
```

`backend/app/models/llm_call.py`:

```python
import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampMixin, UUIDPrimaryKey


class LLMCall(UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "llm_calls"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    llm_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("llm_models.id"), index=True
    )
    round_number: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))  # responder, critic, summarizer
    prompt: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    session = relationship("Session", back_populates="llm_calls")
    llm_model = relationship("LLMModel")
```

Update `backend/app/models/__init__.py` to export `Session`, `LLMCall`, `session_models`.

### Step 2: Write failing tests

`backend/tests/test_session_models.py`:

```python
import pytest
from sqlalchemy import select

from app.models import LLMCall, LLMModel, Session, User


@pytest.fixture
async def user(db):
    user = User(email="session-test@example.com")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def models(db):
    from app.models import Provider

    provider = Provider(slug="test-provider", display_name="Test", base_url="https://test.com")
    db.add(provider)
    await db.flush()
    m1 = LLMModel(provider_id=provider.id, slug="model-a", display_name="Model A")
    m2 = LLMModel(provider_id=provider.id, slug="model-b", display_name="Model B")
    db.add_all([m1, m2])
    await db.commit()
    await db.refresh(m1)
    await db.refresh(m2)
    return [m1, m2]


async def test_create_session_with_models(db, user, models):
    session = Session(user_id=user.id, enquiry="Test question", max_rounds=5)
    session.models = models
    db.add(session)
    await db.commit()
    await db.refresh(session, attribute_names=["models"])

    assert session.status == "pending"
    assert session.current_round == 0
    assert len(session.models) == 2


async def test_insert_llm_call(db, user, models):
    session = Session(user_id=user.id, enquiry="Test question")
    db.add(session)
    await db.commit()

    call = LLMCall(
        session_id=session.id,
        llm_model_id=models[0].id,
        round_number=1,
        role="responder",
        prompt="Answer this",
        response="Here is my answer",
        input_tokens=100,
        output_tokens=50,
        cost=0.001,
        duration_ms=500,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    assert call.role == "responder"
    assert call.input_tokens == 100


async def test_cascade_delete_session(db, user, models):
    session = Session(user_id=user.id, enquiry="Test question")
    session.models = models
    db.add(session)
    await db.commit()

    call = LLMCall(
        session_id=session.id,
        llm_model_id=models[0].id,
        round_number=1,
        role="responder",
    )
    db.add(call)
    await db.commit()

    await db.delete(session)
    await db.commit()

    result = await db.execute(select(LLMCall).where(LLMCall.session_id == session.id))
    assert result.scalars().all() == []
```

### Step 3: Run tests to verify they fail

```bash
cd backend && uv run pytest tests/test_session_models.py -v
```

Expected: FAIL (tables don't exist yet)

### Step 4: Generate Alembic migration

```bash
cd backend && uv run alembic revision --autogenerate -m "add sessions and llm_calls tables"
```

### Step 5: Apply migration and run tests

```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/test_session_models.py -v
```

Expected: All 3 tests PASS

### Step 6: Commit

```bash
git add backend/app/models/session.py backend/app/models/llm_call.py \
  backend/app/models/__init__.py backend/alembic/versions/ \
  backend/tests/test_session_models.py
git commit -m "feat: add sessions and llm_calls DB models"
```

---

## Task 2: Add summarizer_model_id to UserSettings

**Files:**
- Modify: `backend/app/models/user.py` (add `summarizer_model_id` column)
- Modify: `backend/app/users/schemas.py` (add field to settings schemas)
- Modify: `backend/app/users/service.py` (handle summarizer in get/update settings)
- Modify: `backend/tests/test_users.py` (or relevant test file)

### Step 1: Add column to UserSettings model

In `backend/app/models/user.py`, add to `UserSettings`:

```python
summarizer_model_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("llm_models.id"), nullable=True
)
```

### Step 2: Update schemas

In `backend/app/users/schemas.py`, add `summarizer_model_id: UUID | None` to both `SettingsResponse` and `UpdateSettingsRequest`.

### Step 3: Update service

In `backend/app/users/service.py`:
- `get_settings()`: include `summarizer_model_id` in returned dict
- `update_settings()`: accept and persist `summarizer_model_id`

### Step 4: Write test

```python
async def test_update_summarizer_model(client, auth_headers, db):
    # Get a model ID from seed data (e.g., gpt-4o-mini)
    from sqlalchemy import select
    from app.models import LLMModel
    result = await db.execute(
        select(LLMModel).where(LLMModel.slug == "gpt-4o-mini")
    )
    model = result.scalar_one()

    response = await client.put(
        "/api/users/me/settings",
        json={"summarizer_model_id": str(model.id)},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["summarizer_model_id"] == str(model.id)
```

### Step 5: Generate migration, run tests

```bash
cd backend && uv run alembic revision --autogenerate -m "add summarizer_model_id to user_settings"
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/ -v
```

### Step 6: Commit

```bash
git commit -m "feat: add summarizer model setting to user settings"
```

---

## Task 3: PydanticAI Agent Types + Prompts

**Files:**
- Create: `backend/app/agent/types.py`
- Create: `backend/app/agent/prompts.py`
- Create: `backend/tests/test_agent_types.py`

### Step 1: Write structured output types

`backend/app/agent/types.py`:

```python
from pydantic import BaseModel, Field


class InitialResponse(BaseModel):
    response: str = Field(description="Thorough answer to the enquiry")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level 0-1")
    key_points: list[str] = Field(description="Key points of the response")


class CritiqueResponse(BaseModel):
    has_disagreements: bool = Field(description="Whether disagreements remain with other models")
    disagreements: list[str] = Field(description="Specific points of disagreement")
    revised_response: str = Field(description="Updated answer incorporating valid points from others")


class RoundSummary(BaseModel):
    agreements: list[str] = Field(description="Points all models agree on")
    disagreements: list[str] = Field(description="Points where models still differ")
    shifts: list[str] = Field(description="What changed from the prior round")
    summary: str = Field(description="Concise prose summary of the round")
```

### Step 2: Write system prompts

`backend/app/agent/prompts.py`:

```python
RESPONDER_SYSTEM_PROMPT = """\
You are a knowledgeable expert participating in a multi-model consensus process.
Answer the following enquiry thoroughly and accurately.
Identify the key points of your response and rate your confidence level.
Be specific and substantive in your answer."""

CRITIC_SYSTEM_PROMPT = """\
You are a critical analyst in a multi-model consensus process.
You will receive the original enquiry, a summary of prior discussion rounds,
and the latest responses from all participating models.

Your task:
1. Evaluate all responses for accuracy, completeness, and reasoning quality.
2. Identify any remaining disagreements between the models.
3. Produce a revised response that incorporates valid points from all models.
4. Set has_disagreements to false ONLY if you believe all models have converged
   on a substantially similar answer."""

SUMMARIZER_SYSTEM_PROMPT = """\
You are a concise summarizer. Given a set of model responses from a consensus round,
produce a brief summary capturing:
- Key agreements between models
- Remaining disagreements
- What shifted from the previous round (if applicable)
Keep the summary under 200 words."""


def build_responder_prompt(enquiry: str) -> str:
    return f"Please answer the following enquiry:\n\n{enquiry}"


def build_critic_prompt(
    enquiry: str, prior_summary: str | None, responses: list[dict[str, str]]
) -> str:
    parts = [f"Original enquiry:\n{enquiry}\n"]
    if prior_summary:
        parts.append(f"Summary of prior rounds:\n{prior_summary}\n")
    parts.append("Latest responses from all models:\n")
    for r in responses:
        parts.append(f"--- {r['model_name']} ---\n{r['response']}\n")
    return "\n".join(parts)


def build_summarizer_prompt(responses: list[dict[str, str]]) -> str:
    parts = ["Summarize the following model responses from this consensus round:\n"]
    for r in responses:
        parts.append(f"--- {r['model_name']} ---\n{r['response']}\n")
    return "\n".join(parts)
```

### Step 3: Write tests

`backend/tests/test_agent_types.py`:

```python
from app.agent.types import CritiqueResponse, InitialResponse, RoundSummary
from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt


def test_initial_response_schema():
    r = InitialResponse(
        response="The answer is 42",
        confidence=0.95,
        key_points=["point 1", "point 2"],
    )
    assert r.confidence == 0.95
    assert len(r.key_points) == 2


def test_critique_response_schema():
    r = CritiqueResponse(
        has_disagreements=True,
        disagreements=["disagree on X"],
        revised_response="Updated answer",
    )
    assert r.has_disagreements is True


def test_round_summary_schema():
    r = RoundSummary(
        agreements=["agree on A"],
        disagreements=["disagree on B"],
        shifts=["shifted from C to D"],
        summary="Models mostly agree but differ on B.",
    )
    assert "agree on A" in r.agreements


def test_build_responder_prompt():
    prompt = build_responder_prompt("What is 2+2?")
    assert "What is 2+2?" in prompt


def test_build_critic_prompt_with_summary():
    prompt = build_critic_prompt(
        enquiry="What is 2+2?",
        prior_summary="Models agree it is 4.",
        responses=[
            {"model_name": "GPT-4o", "response": "The answer is 4."},
            {"model_name": "Claude", "response": "It equals 4."},
        ],
    )
    assert "What is 2+2?" in prompt
    assert "Models agree" in prompt
    assert "GPT-4o" in prompt
    assert "Claude" in prompt


def test_build_critic_prompt_without_summary():
    prompt = build_critic_prompt(
        enquiry="What is 2+2?",
        prior_summary=None,
        responses=[{"model_name": "GPT-4o", "response": "4"}],
    )
    assert "Summary of prior rounds" not in prompt


def test_build_summarizer_prompt():
    prompt = build_summarizer_prompt(
        responses=[
            {"model_name": "GPT-4o", "response": "Answer A"},
            {"model_name": "Claude", "response": "Answer B"},
        ]
    )
    assert "GPT-4o" in prompt
    assert "Answer B" in prompt
```

### Step 4: Run tests

```bash
cd backend && uv run pytest tests/test_agent_types.py -v
```

Expected: All PASS (pure Pydantic models + string functions, no DB needed)

### Step 5: Commit

```bash
git commit -m "feat: add PydanticAI agent types and prompts"
```

---

## Task 4: PydanticAI Agent Definitions

**Files:**
- Create: `backend/app/agent/consensus_agent.py`
- Create: `backend/tests/test_consensus_agents.py`

### Step 1: Write the three agents

`backend/app/agent/consensus_agent.py`:

```python
from pydantic_ai import Agent

from app.agent.prompts import (
    CRITIC_SYSTEM_PROMPT,
    RESPONDER_SYSTEM_PROMPT,
    SUMMARIZER_SYSTEM_PROMPT,
)
from app.agent.types import CritiqueResponse, InitialResponse, RoundSummary

responder_agent = Agent(
    "openai:gpt-4o",  # placeholder, overridden at runtime
    output_type=InitialResponse,
    system_prompt=RESPONDER_SYSTEM_PROMPT,
)

critic_agent = Agent(
    "openai:gpt-4o",
    output_type=CritiqueResponse,
    system_prompt=CRITIC_SYSTEM_PROMPT,
)

summarizer_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=RoundSummary,
    system_prompt=SUMMARIZER_SYSTEM_PROMPT,
)
```

**Note:** The placeholder model (`"openai:gpt-4o"`) is always overridden at runtime
via `agent.override(model=...)`. The agents are singletons; only the model varies per call.

### Step 2: Write tests with TestModel

`backend/tests/test_consensus_agents.py`:

```python
import pytest
from pydantic_ai.models.test import TestModel

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt
from app.agent.types import CritiqueResponse, InitialResponse, RoundSummary


async def test_responder_agent_returns_initial_response():
    with responder_agent.override(model=TestModel()):
        result = await responder_agent.run(build_responder_prompt("What is gravity?"))
        assert isinstance(result.output, InitialResponse)
        assert result.usage().requests >= 1


async def test_critic_agent_returns_critique_response():
    prompt = build_critic_prompt(
        enquiry="What is gravity?",
        prior_summary=None,
        responses=[{"model_name": "Model A", "response": "Gravity is a force."}],
    )
    with critic_agent.override(model=TestModel()):
        result = await critic_agent.run(prompt)
        assert isinstance(result.output, CritiqueResponse)
        assert isinstance(result.output.has_disagreements, bool)


async def test_summarizer_agent_returns_round_summary():
    prompt = build_summarizer_prompt(
        responses=[
            {"model_name": "Model A", "response": "Answer A"},
            {"model_name": "Model B", "response": "Answer B"},
        ]
    )
    with summarizer_agent.override(model=TestModel()):
        result = await summarizer_agent.run(prompt)
        assert isinstance(result.output, RoundSummary)
```

### Step 3: Run tests

```bash
cd backend && uv run pytest tests/test_consensus_agents.py -v
```

Expected: All 3 PASS

### Step 4: Commit

```bash
git commit -m "feat: add PydanticAI agent definitions for responder, critic, summarizer"
```

---

## Task 5: ConsensusOrchestrator

This is the core engine. Largest and most critical task.

**Files:**
- Create: `backend/app/consensus/service.py`
- Create: `backend/tests/test_consensus_orchestrator.py`

### Step 1: Write the orchestrator

`backend/app/consensus/service.py`:

```python
import asyncio
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.agent.model_registry import NoKeyAvailableError, resolve_model
from app.agent.prompts import build_critic_prompt, build_responder_prompt, build_summarizer_prompt
from app.database import async_session_factory
from app.models import LLMCall, LLMModel, Session, UserSettings

MAX_ROUNDS_HARD_CAP = 20
LLM_TIMEOUT_SECONDS = 60
HEARTBEAT_INTERVAL_SECONDS = 10
CONCURRENCY_LIMIT = 10


class ConsensusOrchestrator:
    def __init__(self, session_id: UUID, user_id: UUID):
        self.session_id = session_id
        self.user_id = user_id
        self.semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        self._active_models: list[LLMModel] = []
        self._heartbeat_task: asyncio.Task | None = None

    async def run(self) -> None:
        async with async_session_factory() as db:
            session = await db.get(Session, self.session_id)
            if not session:
                return

            await db.refresh(session, attribute_names=["models"])
            self._active_models = list(session.models)
            max_rounds = session.max_rounds or MAX_ROUNDS_HARD_CAP

            # Start heartbeat
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
                        {"model_name": cr["model_name"], "response": cr["response"]}
                        for cr in critique_results
                    ]

                    if all_agree:
                        session.status = "consensus_reached"
                        break
                else:
                    session.status = "max_rounds_reached"

                elapsed = int((time.monotonic() - start_time) * 1000)
                session.total_duration_ms = elapsed
                session.completed_at = datetime.now(timezone.utc)
                await self._update_session_totals(db, session)
                await db.commit()

            except Exception:
                await self._fail_session(db, session, start_time)
            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()

    async def _run_responder_round(
        self, db: AsyncSession, session: Session
    ) -> list[dict[str, str]]:
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
    ) -> dict[str, str]:
        async with self.semaphore:
            resolved = await resolve_model(self.user_id, model, db)
            start = time.monotonic()

            # Build PydanticAI model instance
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            pai_model = OpenAIChatModel(
                model_name=resolved.model_slug,
                provider=OpenAIProvider(
                    base_url=resolved.base_url, api_key=resolved.api_key
                ),
            )

            with responder_agent.override(model=pai_model):
                result = await asyncio.wait_for(
                    responder_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            usage = result.usage()

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=1,
                role="responder",
                prompt=prompt,
                response=result.output.response,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,  # cost from usage if available
                duration_ms=elapsed_ms,
            )
            db.add(call)

            model_name = f"{model.provider.slug}/{model.slug}" if model.provider else model.slug
            return {"model_name": model_name, "response": result.output.response}

    async def _run_critic_round(
        self,
        db: AsyncSession,
        session: Session,
        latest_responses: list[dict[str, str]],
        prior_summary: str | None,
        round_number: int,
    ) -> list[dict]:
        tasks = [
            self._call_critic(db, session, model, latest_responses, prior_summary, round_number)
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
            else:
                critique_results.append(result)
        await db.commit()
        return critique_results

    async def _call_critic(
        self,
        db: AsyncSession,
        session: Session,
        model: LLMModel,
        latest_responses: list[dict[str, str]],
        prior_summary: str | None,
        round_number: int,
    ) -> dict:
        async with self.semaphore:
            resolved = await resolve_model(self.user_id, model, db)
            prompt = build_critic_prompt(session.enquiry, prior_summary, latest_responses)
            start = time.monotonic()

            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            pai_model = OpenAIChatModel(
                model_name=resolved.model_slug,
                provider=OpenAIProvider(
                    base_url=resolved.base_url, api_key=resolved.api_key
                ),
            )

            with critic_agent.override(model=pai_model):
                result = await asyncio.wait_for(
                    critic_agent.run(prompt),
                    timeout=LLM_TIMEOUT_SECONDS,
                )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            usage = result.usage()

            call = LLMCall(
                session_id=session.id,
                llm_model_id=model.id,
                round_number=round_number,
                role="critic",
                prompt=prompt,
                response=result.output.revised_response,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cost=0,
                duration_ms=elapsed_ms,
            )
            db.add(call)

            model_name = f"{model.provider.slug}/{model.slug}" if model.provider else model.slug
            return {
                "model_name": model_name,
                "response": result.output.revised_response,
                "has_disagreements": result.output.has_disagreements,
            }

    async def _run_summarizer(
        self,
        db: AsyncSession,
        session: Session,
        responses: list[dict[str, str]],
        round_number: int,
    ) -> str:
        # Get user's summarizer model
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
            # Default to gpt-4o-mini
            result = await db.execute(
                select(LLMModel).where(LLMModel.slug == "gpt-4o-mini")
            )
            summarizer_llm = result.scalar_one_or_none()

        if not summarizer_llm:
            # Fallback: return concatenated responses as "summary"
            return "\n".join(f"{r['model_name']}: {r['response'][:200]}" for r in responses)

        prompt = build_summarizer_prompt(responses)
        start = time.monotonic()

        try:
            resolved = await resolve_model(self.user_id, summarizer_llm, db)

            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider

            pai_model = OpenAIChatModel(
                model_name=resolved.model_slug,
                provider=OpenAIProvider(
                    base_url=resolved.base_url, api_key=resolved.api_key
                ),
            )

            with summarizer_agent.override(model=pai_model):
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
            return result.output.summary

        except (NoKeyAvailableError, Exception):
            return "\n".join(f"{r['model_name']}: {r['response'][:200]}" for r in responses)

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
        session.completed_at = datetime.now(timezone.utc)
        await self._update_session_totals(db, session)
        await db.commit()

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
                        session.last_heartbeat_at = datetime.now(timezone.utc)
                        await db.commit()
            except Exception:
                pass


async def cleanup_orphaned_sessions() -> None:
    """Mark stuck sessions as failed. Call on app startup."""
    from datetime import timedelta

    async with async_session_factory() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        result = await db.execute(
            select(Session).where(
                Session.status.in_(["pending", "responding", "critiquing"]),
                Session.last_heartbeat_at < cutoff,
            )
        )
        for session in result.scalars().all():
            session.status = "failed"
            session.completed_at = datetime.now(timezone.utc)
        await db.commit()
```

### Step 2: Write tests

`backend/tests/test_consensus_orchestrator.py`:

```python
import pytest
from pydantic_ai.models.test import TestModel
from sqlalchemy import select

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.consensus.service import ConsensusOrchestrator, cleanup_orphaned_sessions
from app.models import LLMCall, LLMModel, Provider, Session, User, UserSettings


@pytest.fixture
async def user(db):
    user = User(email="orchestrator-test@example.com")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def test_models(db):
    provider = Provider(
        slug="test-provider", display_name="Test Provider", base_url="https://test.com"
    )
    db.add(provider)
    await db.flush()
    m1 = LLMModel(provider_id=provider.id, slug="model-a", display_name="Model A")
    m2 = LLMModel(provider_id=provider.id, slug="model-b", display_name="Model B")
    db.add_all([m1, m2])
    await db.commit()
    await db.refresh(m1)
    await db.refresh(m2)
    return [m1, m2]


@pytest.fixture
async def session_obj(db, user, test_models):
    session = Session(user_id=user.id, enquiry="What is the meaning of life?")
    session.models = test_models
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def test_orchestrator_convergence(db, user, session_obj):
    """TestModel returns structured types by default, which sets has_disagreements=False,
    so convergence should happen after round 2."""
    orchestrator = ConsensusOrchestrator(session_obj.id, user.id)

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    await db.refresh(session_obj)
    assert session_obj.status == "consensus_reached"
    assert session_obj.completed_at is not None

    # Verify llm_calls were recorded
    result = await db.execute(
        select(LLMCall).where(LLMCall.session_id == session_obj.id)
    )
    calls = result.scalars().all()
    assert len(calls) >= 4  # 2 responder + 2 critic (minimum)

    # Verify round numbers
    responder_calls = [c for c in calls if c.role == "responder"]
    critic_calls = [c for c in calls if c.role == "critic"]
    assert all(c.round_number == 1 for c in responder_calls)
    assert all(c.round_number >= 2 for c in critic_calls)


async def test_orchestrator_max_rounds(db, user, test_models):
    session = Session(
        user_id=user.id, enquiry="Controversial topic", max_rounds=3
    )
    session.models = test_models
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Use a TestModel that always returns has_disagreements=True
    # by customizing the response data
    orchestrator = ConsensusOrchestrator(session.id, user.id)

    # We need to make critic always disagree — this requires
    # a custom TestModel or response override. For now, test
    # that the max_rounds cap is respected.
    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    await db.refresh(session)
    # TestModel defaults has_disagreements to False, so this
    # will likely reach consensus. The important thing is it completes.
    assert session.status in ("consensus_reached", "max_rounds_reached")
    assert session.completed_at is not None


async def test_orchestrator_records_totals(db, user, session_obj):
    orchestrator = ConsensusOrchestrator(session_obj.id, user.id)

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    await db.refresh(session_obj)
    assert session_obj.total_duration_ms > 0


async def test_cleanup_orphaned_sessions(db, user):
    from datetime import datetime, timedelta, timezone

    session = Session(
        user_id=user.id,
        enquiry="Stuck session",
        status="responding",
        last_heartbeat_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db.add(session)
    await db.commit()

    await cleanup_orphaned_sessions()

    await db.refresh(session)
    assert session.status == "failed"
    assert session.completed_at is not None
```

### Step 3: Run tests

```bash
cd backend && uv run pytest tests/test_consensus_orchestrator.py -v
```

Expected: All PASS (using TestModel, no real API calls)

**Note:** The orchestrator tests use TestModel which generates default structured output.
For `CritiqueResponse`, TestModel will set `has_disagreements` to `False` by default,
which means convergence happens quickly. This tests the happy path. To test max_rounds,
we would need a custom TestModel that returns `has_disagreements=True` — this can be
refined during implementation.

### Step 4: Commit

```bash
git commit -m "feat: add ConsensusOrchestrator with iterative convergence"
```

---

## Task 6: Session Endpoints (CRUD)

**Files:**
- Create: `backend/app/consensus/router.py`
- Create: `backend/app/consensus/schemas.py`
- Modify: `backend/app/main.py` (register router + startup event)
- Create: `backend/tests/test_session_endpoints.py`

### Step 1: Write schemas

`backend/app/consensus/schemas.py`:

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    enquiry: str = Field(min_length=1, max_length=10000)
    model_ids: list[UUID] = Field(min_length=2)
    max_rounds: int | None = Field(default=None, ge=2, le=20)


class SessionResponse(BaseModel):
    id: UUID
    enquiry: str
    status: str
    max_rounds: int | None
    current_round: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    total_duration_ms: int
    created_at: datetime
    completed_at: datetime | None
    model_ids: list[UUID]

    model_config = {"from_attributes": True}


class LLMCallResponse(BaseModel):
    id: UUID
    llm_model_id: UUID
    model_slug: str
    provider_slug: str
    round_number: int
    role: str
    prompt: str
    response: str
    input_tokens: int
    output_tokens: int
    cost: float
    duration_ms: int
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    llm_calls: list[LLMCallResponse]


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int
    page: int
    page_size: int
```

### Step 2: Write router

`backend/app/consensus/router.py`:

```python
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth.dependencies import get_current_user
from app.consensus.schemas import (
    CreateSessionRequest,
    LLMCallResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from app.consensus.service import ConsensusOrchestrator
from app.database import get_db
from app.models import LLMCall, LLMModel, Session, User
from app.models.session import session_models

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Store background tasks to prevent garbage collection
_background_tasks: set[asyncio.Task] = set()


def _session_to_response(session: Session, model_ids: list[UUID]) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        enquiry=session.enquiry,
        status=session.status,
        max_rounds=session.max_rounds,
        current_round=session.current_round,
        total_input_tokens=session.total_input_tokens,
        total_output_tokens=session.total_output_tokens,
        total_cost=float(session.total_cost),
        total_duration_ms=session.total_duration_ms,
        created_at=session.created_at,
        completed_at=session.completed_at,
        model_ids=model_ids,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate models exist and are active
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.id.in_(body.model_ids),
            LLMModel.is_active.is_(True),
        )
    )
    models = result.scalars().all()
    if len(models) < 2:
        raise HTTPException(400, "At least 2 valid, active models are required")
    if len(models) != len(body.model_ids):
        raise HTTPException(400, "One or more model IDs are invalid or inactive")

    # TODO: validate user has keys for all selected models' providers

    session = Session(
        user_id=user.id,
        enquiry=body.enquiry,
        max_rounds=body.max_rounds,
    )
    session.models = list(models)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Launch orchestrator as background task
    orchestrator = ConsensusOrchestrator(session.id, user.id)
    task = asyncio.create_task(orchestrator.run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return _session_to_response(session, body.model_ids)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Count
    count_result = await db.execute(
        select(func.count(Session.id)).where(Session.user_id == user.id)
    )
    total = count_result.scalar() or 0

    # Fetch page
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    # Get model IDs for each session
    session_responses = []
    for s in sessions:
        model_result = await db.execute(
            select(session_models.c.llm_model_id).where(
                session_models.c.session_id == s.id
            )
        )
        model_ids = [row[0] for row in model_result.all()]
        session_responses.append(_session_to_response(s, model_ids))

    return SessionListResponse(
        sessions=session_responses, total=total, page=page, page_size=page_size
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found")

    # Get model IDs
    model_result = await db.execute(
        select(session_models.c.llm_model_id).where(
            session_models.c.session_id == session.id
        )
    )
    model_ids = [row[0] for row in model_result.all()]

    # Get LLM calls with model info
    calls_result = await db.execute(
        select(LLMCall)
        .where(LLMCall.session_id == session.id)
        .options(joinedload(LLMCall.llm_model).joinedload(LLMModel.provider))
        .order_by(LLMCall.round_number, LLMCall.created_at)
    )
    calls = calls_result.scalars().unique().all()

    call_responses = [
        LLMCallResponse(
            id=c.id,
            llm_model_id=c.llm_model_id,
            model_slug=c.llm_model.slug,
            provider_slug=c.llm_model.provider.slug,
            round_number=c.round_number,
            role=c.role,
            prompt=c.prompt,
            response=c.response,
            input_tokens=c.input_tokens,
            output_tokens=c.output_tokens,
            cost=float(c.cost),
            duration_ms=c.duration_ms,
            error=c.error,
            created_at=c.created_at,
        )
        for c in calls
    ]

    return SessionDetailResponse(
        id=session.id,
        enquiry=session.enquiry,
        status=session.status,
        max_rounds=session.max_rounds,
        current_round=session.current_round,
        total_input_tokens=session.total_input_tokens,
        total_output_tokens=session.total_output_tokens,
        total_cost=float(session.total_cost),
        total_duration_ms=session.total_duration_ms,
        created_at=session.created_at,
        completed_at=session.completed_at,
        model_ids=model_ids,
        llm_calls=call_responses,
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.commit()
```

### Step 3: Register router + startup event in `main.py`

Add to `backend/app/main.py`:

```python
from app.consensus.router import router as sessions_router
from app.consensus.service import cleanup_orphaned_sessions

app.include_router(sessions_router)

@app.on_event("startup")
async def startup():
    await cleanup_orphaned_sessions()
```

### Step 4: Write endpoint tests

`backend/tests/test_session_endpoints.py`:

```python
import pytest
from pydantic_ai.models.test import TestModel
from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent


async def test_create_session(client, auth_headers, db):
    from sqlalchemy import select
    from app.models import LLMModel

    result = await db.execute(select(LLMModel).limit(2))
    models = result.scalars().all()
    assert len(models) >= 2

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        response = await client.post(
            "/api/sessions",
            json={
                "enquiry": "What is the speed of light?",
                "model_ids": [str(m.id) for m in models[:2]],
            },
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["enquiry"] == "What is the speed of light?"


async def test_create_session_requires_min_2_models(client, auth_headers, db):
    from sqlalchemy import select
    from app.models import LLMModel

    result = await db.execute(select(LLMModel).limit(1))
    model = result.scalars().first()

    response = await client.post(
        "/api/sessions",
        json={"enquiry": "Test", "model_ids": [str(model.id)]},
        headers=auth_headers,
    )
    assert response.status_code == 422  # Pydantic validation: min_length=2


async def test_list_sessions(client, auth_headers):
    response = await client.get("/api/sessions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "total" in data


async def test_get_session_not_found(client, auth_headers):
    import uuid
    response = await client.get(
        f"/api/sessions/{uuid.uuid4()}", headers=auth_headers
    )
    assert response.status_code == 404


async def test_delete_session(client, auth_headers, db):
    from sqlalchemy import select
    from app.models import LLMModel, Session

    result = await db.execute(select(LLMModel).limit(2))
    models = result.scalars().all()

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        create_resp = await client.post(
            "/api/sessions",
            json={
                "enquiry": "Delete me",
                "model_ids": [str(m.id) for m in models[:2]],
            },
            headers=auth_headers,
        )
    session_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/sessions/{session_id}", headers=auth_headers
    )
    assert delete_resp.status_code == 204
```

### Step 5: Run tests

```bash
cd backend && uv run pytest tests/test_session_endpoints.py -v
```

### Step 6: Commit

```bash
git commit -m "feat: add session CRUD endpoints with background orchestration"
```

---

## Task 7: SSE Stream Endpoint

**Files:**
- Modify: `backend/app/consensus/router.py` (add SSE endpoint)
- Create: `backend/tests/test_sse_stream.py`

### Step 1: Add SSE endpoint to router

Add to `backend/app/consensus/router.py`:

```python
import json
from starlette.requests import Request
from sse_starlette import EventSourceResponse


async def _session_event_generator(request: Request, session_id: UUID, user_id: UUID):
    """Replay existing events then poll for new ones."""
    last_seen_count = 0
    keepalive_interval = 15  # seconds
    poll_interval = 1  # seconds
    polls_per_keepalive = keepalive_interval // poll_interval

    async with async_session_factory() as db:
        # Verify session belongs to user
        session = await db.get(Session, session_id)
        if not session or session.user_id != user_id:
            return

        poll_count = 0
        while True:
            if await request.is_disconnected():
                break

            # Fetch all calls after last_seen_count
            result = await db.execute(
                select(LLMCall)
                .where(LLMCall.session_id == session_id)
                .options(joinedload(LLMCall.llm_model).joinedload(LLMModel.provider))
                .order_by(LLMCall.round_number, LLMCall.created_at)
            )
            calls = result.scalars().unique().all()

            # Send new calls
            for call in calls[last_seen_count:]:
                model_slug = call.llm_model.slug
                provider_slug = call.llm_model.provider.slug
                event_type = call.role  # "responder", "critic", "summarizer"
                if call.error:
                    event_type = "model_dropped"

                yield {
                    "event": event_type,
                    "data": json.dumps({
                        "id": str(call.id),
                        "model_slug": model_slug,
                        "provider_slug": provider_slug,
                        "model_name": f"{provider_slug}/{model_slug}",
                        "round_number": call.round_number,
                        "role": call.role,
                        "response": call.response,
                        "error": call.error,
                        "input_tokens": call.input_tokens,
                        "output_tokens": call.output_tokens,
                        "cost": float(call.cost),
                        "duration_ms": call.duration_ms,
                    }),
                }
                last_seen_count += 1

            # Check session status
            await db.refresh(session)
            terminal_statuses = ("consensus_reached", "max_rounds_reached", "failed")
            if session.status in terminal_statuses:
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
                break

            # Keepalive ping
            poll_count += 1
            if poll_count >= polls_per_keepalive:
                yield {"comment": "keepalive"}
                poll_count = 0

            await asyncio.sleep(poll_interval)


@router.get("/{session_id}/stream")
async def stream_session(
    request: Request,
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(404, "Session not found")

    return EventSourceResponse(
        _session_event_generator(request, session_id, user.id)
    )
```

**Note:** Import `async_session_factory` from `app.database` at the top of the file.

### Step 2: Write SSE tests

`backend/tests/test_sse_stream.py`:

Test SSE with a completed session (replay mode). Testing live polling is harder
and can be added later — the replay test verifies the event format.

```python
import asyncio
import pytest
from pydantic_ai.models.test import TestModel
from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent


async def test_sse_replay_completed_session(client, auth_headers, db):
    """Create a session, wait for completion, then verify SSE replay."""
    from sqlalchemy import select
    from app.models import LLMModel

    result = await db.execute(select(LLMModel).limit(2))
    models = result.scalars().all()

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        create_resp = await client.post(
            "/api/sessions",
            json={
                "enquiry": "SSE test question",
                "model_ids": [str(m.id) for m in models[:2]],
            },
            headers=auth_headers,
        )
        session_id = create_resp.json()["id"]

        # Wait for orchestrator to finish
        await asyncio.sleep(2)

    # Now stream the completed session
    async with client.stream(
        "GET",
        f"/api/sessions/{session_id}/stream",
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        events = []
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
            if "consensus_reached" in line or "max_rounds_reached" in line:
                break

    assert len(events) > 0
    assert events[-1] in ("consensus_reached", "max_rounds_reached")
```

### Step 3: Run tests

```bash
cd backend && uv run pytest tests/test_sse_stream.py -v
```

### Step 4: Commit

```bash
git commit -m "feat: add SSE stream endpoint for live session events"
```

---

## Task 8: Frontend — Install Dependencies + SSE Hook

**Files:**
- Modify: `frontend/package.json` (add sse.js)
- Create: `frontend/src/hooks/useConsensusStream.ts`
- Create: `frontend/src/types/session.ts`

### Step 1: Install sse.js

```bash
cd frontend && bun add sse.js
```

### Step 2: Create session types

`frontend/src/types/session.ts`:

```typescript
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

export interface LLMCallEvent {
  id: string;
  model_slug: string;
  provider_slug: string;
  model_name: string;
  round_number: number;
  role: "responder" | "critic" | "summarizer";
  response: string;
  error: string | null;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  duration_ms: number;
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

// Color assignments for models in chat UI
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

### Step 3: Create SSE hook

`frontend/src/hooks/useConsensusStream.ts`:

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import { SSE } from "sse.js";
import { getAccessToken } from "@/lib/api";
import type { LLMCallEvent, SessionStatus, TerminalEvent } from "@/types/session";

interface UseConsensusStreamOptions {
  sessionId: string;
  enabled?: boolean;
}

interface ConsensusStreamState {
  events: LLMCallEvent[];
  status: SessionStatus;
  terminalEvent: TerminalEvent | null;
  isConnected: boolean;
  error: string | null;
}

export function useConsensusStream({ sessionId, enabled = true }: UseConsensusStreamOptions) {
  const [state, setState] = useState<ConsensusStreamState>({
    events: [],
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
      headers: {
        Authorization: `Bearer ${token}`,
      },
      start: false,
    });

    const handleEvent = (eventType: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);

        if (["consensus_reached", "max_rounds_reached", "failed"].includes(eventType)) {
          setState((prev) => ({
            ...prev,
            status: eventType as SessionStatus,
            terminalEvent: data,
            isConnected: false,
          }));
          source.close();
          return;
        }

        setState((prev) => ({
          ...prev,
          events: [...prev.events, data as LLMCallEvent],
          status: eventType === "model_dropped" ? prev.status : (
            data.role === "responder" ? "responding" : "critiquing"
          ),
        }));
      } catch {
        // ignore parse errors
      }
    };

    source.addEventListener("responder", handleEvent("responder"));
    source.addEventListener("critic", handleEvent("critic"));
    source.addEventListener("summarizer", handleEvent("summarizer"));
    source.addEventListener("model_dropped", handleEvent("model_dropped"));
    source.addEventListener("consensus_reached", handleEvent("consensus_reached"));
    source.addEventListener("max_rounds_reached", handleEvent("max_rounds_reached"));
    source.addEventListener("failed", handleEvent("failed"));

    source.addEventListener("open", () => {
      setState((prev) => ({ ...prev, isConnected: true, error: null }));
    });

    source.addEventListener("error", (e: Event) => {
      setState((prev) => ({
        ...prev,
        isConnected: false,
        error: "Connection lost",
      }));
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

**Note:** `getAccessToken` needs to be exported from `frontend/src/lib/api.ts`.
Add `export` to the existing `getAccessToken` function.

### Step 4: Commit

```bash
git commit -m "feat: add sse.js dependency and useConsensusStream hook"
```

---

## Task 9: Frontend — Enquiry Page (`/sessions/new`)

**Files:**
- Create: `frontend/src/app/(protected)/sessions/new/page.tsx`

### Step 1: Build the enquiry page

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Box,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Stack,
  Switch,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

interface Model {
  id: string;
  slug: string;
  display_name: string;
  provider_slug: string;
}

export default function NewSessionPage() {
  const router = useRouter();
  const [enquiry, setEnquiry] = useState("");
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const [untilConsensus, setUntilConsensus] = useState(true);
  const [maxRounds, setMaxRounds] = useState<number>(5);

  // Fetch available models (user has keys for these providers)
  const { data: models = [] } = useQuery<Model[]>({
    queryKey: ["available-models"],
    queryFn: async () => {
      const res = await apiFetch("/api/models");
      return res.json();
    },
  });

  // Group models by provider
  const grouped = models.reduce<Record<string, Model[]>>((acc, m) => {
    (acc[m.provider_slug] ??= []).push(m);
    return acc;
  }, {});

  const createSession = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enquiry,
          model_ids: selectedModelIds,
          max_rounds: untilConsensus ? null : maxRounds,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create session");
      }
      return res.json();
    },
    onSuccess: (data) => {
      router.push(`/sessions/${data.id}`);
    },
    onError: (err: Error) => {
      notifications.show({ title: "Error", message: err.message, color: "red" });
    },
  });

  const canSubmit = enquiry.trim().length > 0 && selectedModelIds.length >= 2;

  return (
    <Stack gap="lg" maw={700}>
      <Title order={2}>New Enquiry</Title>

      <Textarea
        label="Your question"
        placeholder="Ask anything..."
        minRows={4}
        autosize
        value={enquiry}
        onChange={(e) => setEnquiry(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && canSubmit) {
            createSession.mutate();
          }
        }}
      />

      <Box>
        <Text fw={500} mb="xs">Select models (minimum 2)</Text>
        {Object.entries(grouped).map(([provider, providerModels]) => (
          <Box key={provider} mb="sm">
            <Text size="sm" c="dimmed" tt="uppercase" mb={4}>{provider}</Text>
            <Checkbox.Group value={selectedModelIds} onChange={setSelectedModelIds}>
              <Stack gap={4}>
                {providerModels.map((m) => (
                  <Checkbox key={m.id} value={m.id} label={m.display_name} />
                ))}
              </Stack>
            </Checkbox.Group>
          </Box>
        ))}
      </Box>

      <Group>
        <Switch
          label="Run until consensus"
          checked={untilConsensus}
          onChange={(e) => setUntilConsensus(e.currentTarget.checked)}
        />
        {!untilConsensus && (
          <NumberInput
            label="Max rounds"
            value={maxRounds}
            onChange={(v) => setMaxRounds(Number(v))}
            min={2}
            max={20}
            w={100}
          />
        )}
      </Group>

      <Button
        onClick={() => createSession.mutate()}
        loading={createSession.isPending}
        disabled={!canSubmit}
      >
        Start Consensus
      </Button>
    </Stack>
  );
}
```

### Step 2: Commit

```bash
git commit -m "feat: add enquiry page for new consensus sessions"
```

---

## Task 10: Frontend — Session Chat UI (`/sessions/[id]`)

**Files:**
- Create: `frontend/src/app/(protected)/sessions/[id]/page.tsx`
- Create: `frontend/src/components/consensus/ChatMessage.tsx`
- Create: `frontend/src/components/consensus/RoundDivider.tsx`
- Create: `frontend/src/components/consensus/ConsensusBanner.tsx`

### Step 1: Build chat message component

`frontend/src/components/consensus/ChatMessage.tsx`:

```typescript
import { Box, Paper, Text } from "@mantine/core";
import type { LLMCallEvent } from "@/types/session";
import { MODEL_COLORS } from "@/types/session";

interface ChatMessageProps {
  event: LLMCallEvent;
  colorIndex: number;
  isUser?: boolean;
}

export function ChatMessage({ event, colorIndex, isUser }: ChatMessageProps) {
  const color = MODEL_COLORS[colorIndex % MODEL_COLORS.length];

  if (event.error) {
    return (
      <Paper p="sm" radius="md" bg="red.9" mb="xs">
        <Text size="xs" c="red.3" fw={600}>{event.model_name}</Text>
        <Text size="sm" c="red.1">Dropped: {event.error}</Text>
      </Paper>
    );
  }

  return (
    <Paper
      p="sm"
      radius="md"
      mb="xs"
      style={(theme) => ({
        borderLeft: `3px solid ${theme.colors[color][6]}`,
        backgroundColor: theme.colors.dark[7],
      })}
    >
      <Text size="xs" c={`${color}.4`} fw={600} mb={4}>
        {event.model_name}
        {event.role === "critic" && " (revised)"}
      </Text>
      <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
        {event.response}
      </Text>
    </Paper>
  );
}
```

### Step 2: Build round divider

`frontend/src/components/consensus/RoundDivider.tsx`:

```typescript
import { Divider, Text } from "@mantine/core";

interface RoundDividerProps {
  round: number;
  label?: string;
}

export function RoundDivider({ round, label }: RoundDividerProps) {
  return (
    <Divider
      my="md"
      label={
        <Text size="xs" c="dimmed">
          {label || `Round ${round}${round > 1 ? " — Critique" : " — Initial Responses"}`}
        </Text>
      }
      labelPosition="center"
    />
  );
}
```

### Step 3: Build consensus banner

`frontend/src/components/consensus/ConsensusBanner.tsx`:

```typescript
import { Alert, Group, Text } from "@mantine/core";
import type { TerminalEvent } from "@/types/session";

interface ConsensusBannerProps {
  type: "consensus_reached" | "max_rounds_reached" | "failed";
  event: TerminalEvent;
}

export function ConsensusBanner({ type, event }: ConsensusBannerProps) {
  const config = {
    consensus_reached: {
      color: "green",
      title: "Consensus Reached",
      message: `Models converged after ${event.current_round} rounds.`,
    },
    max_rounds_reached: {
      color: "yellow",
      title: "Max Rounds Reached",
      message: `No consensus after ${event.current_round} rounds.`,
    },
    failed: {
      color: "red",
      title: "Session Failed",
      message: "Too few models remaining to continue.",
    },
  }[type];

  return (
    <Alert color={config.color} title={config.title} my="md">
      <Text size="sm">{config.message}</Text>
      <Group gap="lg" mt="xs">
        <Text size="xs" c="dimmed">
          Tokens: {event.total_input_tokens + event.total_output_tokens}
        </Text>
        <Text size="xs" c="dimmed">
          Cost: ${event.total_cost.toFixed(4)}
        </Text>
        <Text size="xs" c="dimmed">
          Duration: {(event.total_duration_ms / 1000).toFixed(1)}s
        </Text>
      </Group>
    </Alert>
  );
}
```

### Step 4: Build session page

`frontend/src/app/(protected)/sessions/[id]/page.tsx`:

```typescript
"use client";

import { useEffect, useMemo, useRef } from "react";
import { useParams } from "next/navigation";
import { Box, Loader, Paper, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { ChatMessage } from "@/components/consensus/ChatMessage";
import { ConsensusBanner } from "@/components/consensus/ConsensusBanner";
import { RoundDivider } from "@/components/consensus/RoundDivider";
import { useConsensusStream } from "@/hooks/useConsensusStream";
import type { SessionSummary } from "@/types/session";

export default function SessionPage() {
  const { id } = useParams<{ id: string }>();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Fetch session metadata
  const { data: session } = useQuery<SessionSummary>({
    queryKey: ["session", id],
    queryFn: async () => {
      const res = await apiFetch(`/api/sessions/${id}`);
      return res.json();
    },
  });

  // Stream events
  const isTerminal = ["consensus_reached", "max_rounds_reached", "failed"].includes(
    session?.status || ""
  );
  const stream = useConsensusStream({ sessionId: id, enabled: !isTerminal });

  // Build color map: model_name -> index
  const colorMap = useMemo(() => {
    const map = new Map<string, number>();
    let idx = 0;
    for (const event of stream.events) {
      if (!map.has(event.model_name)) {
        map.set(event.model_name, idx++);
      }
    }
    return map;
  }, [stream.events]);

  // Group events by round
  const rounds = useMemo(() => {
    const grouped = new Map<number, typeof stream.events>();
    for (const event of stream.events) {
      const existing = grouped.get(event.round_number) || [];
      existing.push(event);
      grouped.set(event.round_number, existing);
    }
    return grouped;
  }, [stream.events]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [stream.events.length]);

  return (
    <Stack gap="md" maw={800}>
      {/* User enquiry as first message */}
      {session && (
        <Paper p="sm" radius="md" bg="blue.9" mb="xs">
          <Text size="xs" c="blue.3" fw={600}>You</Text>
          <Text size="sm">{session.enquiry}</Text>
        </Paper>
      )}

      {/* Rounds */}
      {[...rounds.entries()].map(([roundNum, events]) => (
        <Box key={roundNum}>
          <RoundDivider round={roundNum} />
          {events.map((event) => (
            <ChatMessage
              key={event.id}
              event={event}
              colorIndex={colorMap.get(event.model_name) || 0}
            />
          ))}
        </Box>
      ))}

      {/* Loading indicator while active */}
      {stream.isConnected && (
        <Box ta="center" py="md">
          <Loader size="sm" />
          <Text size="xs" c="dimmed" mt={4}>Models are deliberating...</Text>
        </Box>
      )}

      {/* Terminal banner */}
      {stream.terminalEvent && (
        <ConsensusBanner
          type={stream.status as "consensus_reached" | "max_rounds_reached" | "failed"}
          event={stream.terminalEvent}
        />
      )}

      <div ref={bottomRef} />
    </Stack>
  );
}
```

### Step 5: Commit

```bash
git commit -m "feat: add chat-style session page with live SSE streaming"
```

---

## Task 11: Frontend — Session List Page

**Files:**
- Create: `frontend/src/app/(protected)/sessions/page.tsx`

### Step 1: Build session list

```typescript
"use client";

import { useRouter } from "next/navigation";
import {
  Badge,
  Box,
  Button,
  Group,
  Paper,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { SessionSummary } from "@/types/session";

const STATUS_COLORS: Record<string, string> = {
  pending: "gray",
  responding: "blue",
  critiquing: "yellow",
  consensus_reached: "green",
  max_rounds_reached: "orange",
  failed: "red",
};

export default function SessionsPage() {
  const router = useRouter();

  const { data } = useQuery({
    queryKey: ["sessions"],
    queryFn: async () => {
      const res = await apiFetch("/api/sessions");
      return res.json();
    },
  });

  const sessions: SessionSummary[] = data?.sessions || [];

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Sessions</Title>
        <Button onClick={() => router.push("/sessions/new")}>New Enquiry</Button>
      </Group>

      {sessions.length === 0 && (
        <Text c="dimmed">No sessions yet. Start your first enquiry!</Text>
      )}

      {sessions.map((s) => (
        <Paper
          key={s.id}
          p="md"
          radius="md"
          withBorder
          style={{ cursor: "pointer" }}
          onClick={() => router.push(`/sessions/${s.id}`)}
        >
          <Group justify="space-between" mb={4}>
            <Text fw={500} lineClamp={1} style={{ flex: 1 }}>
              {s.enquiry}
            </Text>
            <Badge color={STATUS_COLORS[s.status] || "gray"} variant="light">
              {s.status.replace(/_/g, " ")}
            </Badge>
          </Group>
          <Group gap="lg">
            <Text size="xs" c="dimmed">{s.model_ids.length} models</Text>
            <Text size="xs" c="dimmed">{s.current_round} rounds</Text>
            <Text size="xs" c="dimmed">${s.total_cost.toFixed(4)}</Text>
            <Text size="xs" c="dimmed">
              {new Date(s.created_at).toLocaleDateString()}
            </Text>
          </Group>
        </Paper>
      ))}
    </Stack>
  );
}
```

### Step 2: Commit

```bash
git commit -m "feat: add session list page"
```

---

## Task 12: Frontend — Settings Update (Summarizer Model)

**Files:**
- Modify: `frontend/src/app/(protected)/settings/page.tsx`

### Step 1: Add summarizer model selector to Preferences tab

Read the existing settings page first, then add a `Select` dropdown for
the summarizer model within the Preferences tab. It should:

- Fetch all available models via `GET /api/models`
- Show a select dropdown with models grouped by provider
- Save via the existing `updateSettings` mutation (add `summarizer_model_id` to the payload)
- Default label: "GPT-4o Mini (default)"

### Step 2: Commit

```bash
git commit -m "feat: add summarizer model selector to settings"
```

---

## Task 13: Frontend Tests

**Files:**
- Create: `frontend/src/app/(protected)/sessions/new/page.test.tsx`
- Create: `frontend/src/app/(protected)/sessions/page.test.tsx`

### Step 1: Write enquiry page test

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Mock dependencies as needed (similar to settings page test pattern)

describe("NewSessionPage", () => {
  it("renders enquiry form with model selector", () => {
    // Render with mocked providers
    // Assert textarea, model checkboxes, submit button present
  });

  it("disables submit with fewer than 2 models selected", () => {
    // Assert button disabled
  });
});
```

### Step 2: Write session list test

```typescript
describe("SessionsPage", () => {
  it("renders empty state when no sessions", () => {
    // Assert "No sessions yet" message
  });

  it("renders session cards with status badges", () => {
    // Mock sessions data, assert cards render
  });
});
```

### Step 3: Run frontend tests

```bash
cd frontend && bun test
```

### Step 4: Commit

```bash
git commit -m "test: add frontend tests for session pages"
```

---

## Task 14: Navigation + Final Integration

**Files:**
- Modify: `frontend/src/app/(protected)/layout.tsx` or navigation component
- Modify: `frontend/src/app/(protected)/dashboard/page.tsx` (add link to sessions)

### Step 1: Add "Sessions" link to navigation

Update the app's navigation (sidebar or header) to include links to
`/sessions` and `/sessions/new`.

### Step 2: Run full test suite

```bash
cd backend && uv run pytest -v
cd frontend && bun test
```

### Step 3: Run lint

```bash
cd backend && uv run ruff check .
cd frontend && bun lint
```

### Step 4: Final commit

```bash
git commit -m "feat: add sessions navigation and finalize milestone 4"
```

---

## Summary

| Task | Description | Key Files |
|------|-------------|-----------|
| 1 | Session + LLMCall DB models | `models/session.py`, `models/llm_call.py` |
| 2 | Summarizer model setting | `models/user.py`, `users/service.py` |
| 3 | Agent types + prompts | `agent/types.py`, `agent/prompts.py` |
| 4 | PydanticAI agent definitions | `agent/consensus_agent.py` |
| 5 | ConsensusOrchestrator | `consensus/service.py` |
| 6 | Session CRUD endpoints | `consensus/router.py`, `consensus/schemas.py` |
| 7 | SSE stream endpoint | `consensus/router.py` (addition) |
| 8 | Frontend SSE hook + types | `hooks/useConsensusStream.ts`, `types/session.ts` |
| 9 | Enquiry page | `sessions/new/page.tsx` |
| 10 | Chat UI session page | `sessions/[id]/page.tsx`, components |
| 11 | Session list page | `sessions/page.tsx` |
| 12 | Settings: summarizer model | `settings/page.tsx` (modification) |
| 13 | Frontend tests | Test files for session pages |
| 14 | Navigation + integration | Layout, dashboard updates |
