"""Tests that structured data (confidence, key_points, has_disagreements, disagreements)
gets persisted to the DB when LLM calls are saved during consensus orchestration."""

import uuid

import pytest
from pydantic_ai.models.test import TestModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.consensus_agent import (
    critic_agent,
    disagreement_agent,
    final_summarizer_agent,
    responder_agent,
    scorer_agent,
)
from app.consensus.service import ConsensusOrchestrator
from app.database import engine
from app.models import LLMCall, LLMModel, Provider, Session, User


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
async def db_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


async def _create_test_data(db_session: AsyncSession):
    tag = _uid()
    user = User(email=f"struct-{tag}@example.com")
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


async def _cleanup(db_session, session, m1, m2, provider, user):
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
async def test_responder_persists_confidence_and_key_points(db_session):
    """Responder LLMCall records should have confidence and key_points populated."""
    user, provider, m1, m2 = await _create_test_data(db_session)

    session = Session(user_id=user.id, enquiry="What is quantum computing?")
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    orchestrator = ConsensusOrchestrator(session.id, user.id)

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        scorer_agent.override(model=TestModel()),
        disagreement_agent.override(model=TestModel()),
        final_summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    # Query responder calls
    result = await db_session.execute(
        select(LLMCall).where(
            LLMCall.session_id == session.id,
            LLMCall.role == "responder",
        )
    )
    responder_calls = result.scalars().all()
    assert len(responder_calls) == 2

    for call in responder_calls:
        assert call.confidence is not None, "confidence should be persisted"
        assert call.key_points is not None, "key_points should be persisted"
        assert isinstance(call.confidence, float)
        assert isinstance(call.key_points, list)

    await _cleanup(db_session, session, m1, m2, provider, user)


@pytest.mark.asyncio
async def test_critic_persists_has_disagreements_and_disagreements(db_session):
    """Critic LLMCall records should have has_disagreements and disagreements populated."""
    user, provider, m1, m2 = await _create_test_data(db_session)

    session = Session(user_id=user.id, enquiry="What is the best programming language?")
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    orchestrator = ConsensusOrchestrator(session.id, user.id)

    # Use a disagreement checker that always disagrees so we have clear values to check
    disagreeing_checker = TestModel(
        custom_output_args={
            "has_disagreements": True,
            "disagreements": ["point A is wrong", "point B needs revision"],
        }
    )

    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        scorer_agent.override(model=TestModel()),
        disagreement_agent.override(model=disagreeing_checker),
        final_summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    # Query critic calls
    result = await db_session.execute(
        select(LLMCall).where(
            LLMCall.session_id == session.id,
            LLMCall.role == "critic",
        )
    )
    critic_calls = result.scalars().all()
    assert len(critic_calls) >= 2

    for call in critic_calls:
        assert call.has_disagreements is not None, "has_disagreements should be persisted"
        assert call.has_disagreements is True
        assert call.disagreements is not None, "disagreements should be persisted"
        assert isinstance(call.disagreements, list)
        assert len(call.disagreements) > 0

    await _cleanup(db_session, session, m1, m2, provider, user)


@pytest.mark.asyncio
async def test_critic_agreeing_persists_false_disagreements(db_session):
    """When critic agrees, has_disagreements=False and disagreements=[] should be persisted."""
    user, provider, m1, m2 = await _create_test_data(db_session)

    session = Session(user_id=user.id, enquiry="What is 2+2?")
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    orchestrator = ConsensusOrchestrator(session.id, user.id)

    # Default TestModel returns has_disagreements=False
    with (
        responder_agent.override(model=TestModel()),
        critic_agent.override(model=TestModel()),
        scorer_agent.override(model=TestModel()),
        disagreement_agent.override(model=TestModel()),
        final_summarizer_agent.override(model=TestModel()),
    ):
        await orchestrator.run()

    await db_session.refresh(session)
    assert session.status == "consensus_reached"

    # Query critic calls
    result = await db_session.execute(
        select(LLMCall).where(
            LLMCall.session_id == session.id,
            LLMCall.role == "critic",
        )
    )
    critic_calls = result.scalars().all()
    assert len(critic_calls) >= 2

    for call in critic_calls:
        assert call.has_disagreements is not None, "has_disagreements should be persisted"
        assert call.has_disagreements is False

    await _cleanup(db_session, session, m1, m2, provider, user)
