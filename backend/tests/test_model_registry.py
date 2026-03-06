import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.model_registry import NoKeyAvailableError, resolve_model
from app.database import engine
from app.keys.service import store_key
from app.models import LLMModel, Provider, User, UserSettings


async def _create_user(session: AsyncSession) -> User:
    user = User(email=f"registry-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.add(UserSettings(user=user))
    await session.flush()
    return user


async def _get_model(session: AsyncSession, slug: str) -> LLMModel:
    result = await session.execute(select(LLMModel).where(LLMModel.slug == slug))
    return result.scalar_one()


async def _get_provider(session: AsyncSession, slug: str) -> Provider:
    result = await session.execute(select(Provider).where(Provider.slug == slug))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_resolve_with_direct_key():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        provider = await _get_provider(session, "openai")
        model = await _get_model(session, "gpt-4o")

        await store_key(user.id, provider.id, "sk-direct-key", session, skip_validation=True)

        resolved = await resolve_model(user.id, model, session)
        assert resolved.api_key == "sk-direct-key"
        assert resolved.base_url == "https://api.openai.com/v1"
        assert resolved.model_slug == "gpt-4o"
        assert resolved.provider_slug == "openai"
        assert resolved.via_openrouter is False
        await session.rollback()


@pytest.mark.asyncio
async def test_resolve_falls_back_to_openrouter():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        model = await _get_model(session, "gpt-4o")

        await store_key(user.id, openrouter.id, "sk-or-key", session, skip_validation=True)

        resolved = await resolve_model(user.id, model, session)
        assert resolved.api_key == "sk-or-key"
        assert resolved.base_url == "https://openrouter.ai/api/v1"
        assert resolved.model_slug == "openai/gpt-4o"
        assert resolved.via_openrouter is True
        await session.rollback()


@pytest.mark.asyncio
async def test_direct_key_takes_priority_over_openrouter():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openai = await _get_provider(session, "openai")
        openrouter = await _get_provider(session, "openrouter")
        model = await _get_model(session, "gpt-4o")

        await store_key(user.id, openai.id, "sk-openai-direct", session, skip_validation=True)
        await store_key(user.id, openrouter.id, "sk-or-key", session, skip_validation=True)

        resolved = await resolve_model(user.id, model, session)
        assert resolved.via_openrouter is False
        assert resolved.api_key == "sk-openai-direct"
        await session.rollback()


@pytest.mark.asyncio
async def test_resolve_no_key_raises():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        model = await _get_model(session, "gpt-4o")

        with pytest.raises(NoKeyAvailableError):
            await resolve_model(user.id, model, session)
        await session.rollback()
