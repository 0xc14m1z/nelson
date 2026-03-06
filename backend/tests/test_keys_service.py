import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.keys.encryption import decrypt_api_key
from app.keys.service import delete_key, get_decrypted_key, list_keys, store_key
from app.models import ApiKey, Provider, User, UserSettings


async def _create_test_user(session: AsyncSession) -> User:
    user = User(email=f"test-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.add(UserSettings(user=user))
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_store_key_encrypts_and_saves():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        key_record = await store_key(
            user_id=user.id,
            provider_id=provider.id,
            raw_key="sk-test-12345",
            db=session,
            skip_validation=True,
        )

        assert key_record.is_valid is True
        assert key_record.provider_id == provider.id
        decrypted = decrypt_api_key(key_record.encrypted_key)
        assert decrypted == "sk-test-12345"
        await session.rollback()


@pytest.mark.asyncio
async def test_store_key_upserts_on_duplicate():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-first", session, skip_validation=True)
        await store_key(user.id, provider.id, "sk-second", session, skip_validation=True)

        keys = await session.execute(
            select(ApiKey).where(ApiKey.user_id == user.id, ApiKey.provider_id == provider.id)
        )
        all_keys = keys.scalars().all()
        assert len(all_keys) == 1
        assert decrypt_api_key(all_keys[0].encrypted_key) == "sk-second"
        await session.rollback()


@pytest.mark.asyncio
async def test_list_keys_returns_masked():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-test-secret-key", session, skip_validation=True)
        keys = await list_keys(user.id, session)

        assert len(keys) == 1
        assert keys[0].masked_key == "****-key"
        assert keys[0].provider_slug == "openai"


@pytest.mark.asyncio
async def test_delete_key():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-to-delete", session, skip_validation=True)
        deleted = await delete_key(user.id, provider.id, session)
        assert deleted is True

        keys = await list_keys(user.id, session)
        assert len(keys) == 0
        await session.rollback()


@pytest.mark.asyncio
async def test_get_decrypted_key():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        await store_key(user.id, provider.id, "sk-my-secret", session, skip_validation=True)
        decrypted = await get_decrypted_key(user.id, provider.id, session)
        assert decrypted == "sk-my-secret"
        await session.rollback()


@pytest.mark.asyncio
async def test_get_decrypted_key_not_found():
    async with AsyncSession(engine) as session:
        user = await _create_test_user(session)
        decrypted = await get_decrypted_key(user.id, uuid.uuid4(), session)
        assert decrypted is None
        await session.rollback()
