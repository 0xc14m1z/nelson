import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models import LLMCall, LLMModel, Provider, Session, User


@pytest.fixture
async def db_session():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_create_session_with_models(db_session):
    tag = _uid()
    user = User(email=f"session-create-{tag}@example.com")
    db_session.add(user)
    await db_session.flush()

    provider = Provider(slug=f"prov-create-{tag}", display_name="Test", base_url="https://test.com")
    db_session.add(provider)
    await db_session.flush()

    m1 = LLMModel(provider_id=provider.id, slug=f"model-a-{tag}", display_name="Model A")
    m2 = LLMModel(provider_id=provider.id, slug=f"model-b-{tag}", display_name="Model B")
    db_session.add_all([m1, m2])
    await db_session.flush()

    session = Session(user_id=user.id, enquiry="Test question", max_rounds=5)
    session.models = [m1, m2]
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session, attribute_names=["models"])

    assert session.status == "pending"
    assert session.current_round == 0
    assert len(session.models) == 2

    # Cleanup
    await db_session.delete(session)
    await db_session.delete(m1)
    await db_session.delete(m2)
    await db_session.delete(provider)
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_insert_llm_call(db_session):
    tag = _uid()
    user = User(email=f"session-call-{tag}@example.com")
    db_session.add(user)
    await db_session.flush()

    provider = Provider(slug=f"prov-call-{tag}", display_name="Test", base_url="https://test.com")
    db_session.add(provider)
    await db_session.flush()

    model = LLMModel(provider_id=provider.id, slug=f"model-a-{tag}", display_name="Model A")
    db_session.add(model)
    await db_session.flush()

    session = Session(user_id=user.id, enquiry="Test question")
    db_session.add(session)
    await db_session.flush()

    call = LLMCall(
        session_id=session.id,
        llm_model_id=model.id,
        round_number=1,
        role="responder",
        prompt="Answer this",
        response="Here is my answer",
        input_tokens=100,
        output_tokens=50,
        cost=0.001,
        duration_ms=500,
    )
    db_session.add(call)
    await db_session.commit()
    await db_session.refresh(call)

    assert call.role == "responder"
    assert call.input_tokens == 100

    # Cleanup
    await db_session.delete(call)
    await db_session.delete(session)
    await db_session.delete(model)
    await db_session.delete(provider)
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_cascade_delete_session(db_session):
    tag = _uid()
    user = User(email=f"session-cascade-{tag}@example.com")
    db_session.add(user)
    await db_session.flush()

    provider = Provider(
        slug=f"prov-cascade-{tag}", display_name="Test", base_url="https://test.com"
    )
    db_session.add(provider)
    await db_session.flush()

    model = LLMModel(provider_id=provider.id, slug=f"model-a-{tag}", display_name="Model A")
    db_session.add(model)
    await db_session.flush()

    session = Session(user_id=user.id, enquiry="Test question")
    session.models = [model]
    db_session.add(session)
    await db_session.flush()

    call = LLMCall(
        session_id=session.id,
        llm_model_id=model.id,
        round_number=1,
        role="responder",
    )
    db_session.add(call)
    await db_session.commit()

    session_id = session.id
    await db_session.delete(session)
    await db_session.commit()

    result = await db_session.execute(select(LLMCall).where(LLMCall.session_id == session_id))
    assert result.scalars().all() == []

    # Cleanup
    await db_session.delete(model)
    await db_session.delete(provider)
    await db_session.delete(user)
    await db_session.commit()
