import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models import ApiKey, Provider, User


@pytest.mark.asyncio
async def test_api_key_create_and_read():
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Provider).where(Provider.slug == "openai"))
        provider = result.scalar_one()

        user = User(email="apikey-test@example.com")
        session.add(user)
        await session.flush()

        key = ApiKey(
            user_id=user.id,
            provider_id=provider.id,
            encrypted_key=b"fake-encrypted-data",
            is_valid=True,
        )
        session.add(key)
        await session.flush()

        result = await session.execute(select(ApiKey).where(ApiKey.id == key.id))
        saved = result.scalar_one()
        assert saved.encrypted_key == b"fake-encrypted-data"
        assert saved.is_valid is True
        assert saved.provider_id == provider.id
        await session.rollback()
