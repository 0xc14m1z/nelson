import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic_ai.models.test import TestModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.consensus_agent import critic_agent, responder_agent, summarizer_agent
from app.consensus.service import ConsensusOrchestrator, cleanup_orphaned_sessions
from app.database import engine
from app.models import LLMCall, LLMModel, Provider, Session, User


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def db_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


async def _create_test_data(db_session: AsyncSession):
    """Create a user, provider, two models, and a session for testing."""
    tag = _uid()
    user = User(email=f"orch-{tag}@example.com")
    db_session.add(user)
    await db_session.flush()

    provider = Provider(
        slug=f"test-prov-{tag}", display_name="Test Provider", base_url="https://test.com"
    )
    db_session.add(provider)
    await db_session.flush()

    m1 = LLMModel(provider_id=provider.id, slug=f"model-a-{tag}", display_name="Model A")
    m2 = LLMModel(provider_id=provider.id, slug=f"model-b-{tag}", display_name="Model B")
    db_session.add_all([m1, m2])
    await db_session.flush()

    return user, provider, m1, m2


@pytest.mark.asyncio
async def test_orchestrator_convergence(db_session):
    """TestModel returns structured types by default, which sets has_disagreements=False,
    so convergence should happen after round 2."""
    user, provider, m1, m2 = await _create_test_data(db_session)

    session = Session(user_id=user.id, enquiry="What is the meaning of life?")
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    orchestrator = ConsensusOrchestrator(session.id, user.id)

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    await db_session.refresh(session)
    assert session.status == "consensus_reached"
    assert session.completed_at is not None

    # Verify llm_calls were recorded
    result = await db_session.execute(
        select(LLMCall).where(LLMCall.session_id == session.id)
    )
    calls = result.scalars().all()
    assert len(calls) >= 4  # 2 responder + 2 critic (minimum)

    # Verify round numbers
    responder_calls = [c for c in calls if c.role == "responder"]
    critic_calls = [c for c in calls if c.role == "critic"]
    assert all(c.round_number == 1 for c in responder_calls)
    assert all(c.round_number >= 2 for c in critic_calls)

    # Cleanup
    for call in calls:
        await db_session.delete(call)
    await db_session.delete(session)
    await db_session.delete(m1)
    await db_session.delete(m2)
    await db_session.delete(provider)
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_orchestrator_max_rounds(db_session):
    """Use a critic TestModel that always disagrees, forcing max_rounds to be hit."""
    user, provider, m1, m2 = await _create_test_data(db_session)

    session = Session(
        user_id=user.id, enquiry="Controversial topic", max_rounds=3
    )
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    orchestrator = ConsensusOrchestrator(session.id, user.id)

    # Critic always returns has_disagreements=True so consensus is never reached
    disagreeing_critic = TestModel(
        custom_output_args={
            "has_disagreements": True,
            "disagreements": ["still disagree"],
            "revised_response": "my revised answer",
        }
    )

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=disagreeing_critic),
        summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    await db_session.refresh(session)
    assert session.status == "max_rounds_reached"
    assert session.completed_at is not None
    assert session.current_round == 3

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


@pytest.mark.asyncio
async def test_orchestrator_records_totals(db_session):
    user, provider, m1, m2 = await _create_test_data(db_session)

    session = Session(user_id=user.id, enquiry="What is 2+2?")
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    orchestrator = ConsensusOrchestrator(session.id, user.id)

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    await db_session.refresh(session)
    assert session.total_duration_ms > 0

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


@pytest.mark.asyncio
async def test_cleanup_orphaned_sessions(db_session):
    tag = _uid()
    user = User(email=f"orch-cleanup-{tag}@example.com")
    db_session.add(user)
    await db_session.flush()

    session = Session(
        user_id=user.id,
        enquiry="Stuck session",
        status="responding",
        last_heartbeat_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    await cleanup_orphaned_sessions()

    await db_session.refresh(session)
    assert session.status == "failed"
    assert session.completed_at is not None

    # Cleanup
    await db_session.delete(session)
    await db_session.delete(user)
    await db_session.commit()
