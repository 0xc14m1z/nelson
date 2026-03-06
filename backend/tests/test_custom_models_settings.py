import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.keys.service import store_key
from app.models import Provider, User, UserSettings
from app.openrouter.service import add_custom_model
from app.users.service import get_settings, update_settings


async def _create_user(session: AsyncSession) -> User:
    user = User(email=f"settings-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    session.add(UserSettings(user=user))
    await session.flush()
    return user


async def _get_provider(session: AsyncSession, slug: str) -> Provider:
    result = await session.execute(select(Provider).where(Provider.slug == slug))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_custom_model_can_be_selected_as_default():
    async with AsyncSession(engine) as session:
        user = await _create_user(session)
        openrouter = await _get_provider(session, "openrouter")
        await store_key(
            user.id, openrouter.id, "sk-or-test", session, skip_validation=True
        )

        ucm = await add_custom_model(
            user_id=user.id,
            model_slug="test/custom-model-settings",
            display_name="Custom Test Model",
            db=session,
        )

        # The llm_model_id from the custom model should be usable as a default
        result = await update_settings(
            user_id=user.id,
            max_rounds=None,
            default_model_ids=[ucm.llm_model.id],
            db=session,
        )
        assert ucm.llm_model.id in result["default_model_ids"]

        settings = await get_settings(user.id, session)
        assert ucm.llm_model.id in settings["default_model_ids"]

        await session.rollback()
