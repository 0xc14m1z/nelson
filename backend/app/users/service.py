import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LLMModel, UserSettings
from app.models.user import user_default_models


async def get_settings(user_id: uuid.UUID, db: AsyncSession) -> dict:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()

    model_ids_result = await db.execute(
        select(user_default_models.c.llm_model_id).where(
            user_default_models.c.user_id == user_id
        )
    )
    model_ids = [row[0] for row in model_ids_result.all()]

    return {
        "max_rounds": settings.max_rounds if settings else None,
        "default_model_ids": model_ids,
    }


async def update_settings(
    user_id: uuid.UUID,
    max_rounds: int | None,
    default_model_ids: list[uuid.UUID],
    db: AsyncSession,
) -> dict:
    # Validate model IDs exist and are active
    if default_model_ids:
        result = await db.execute(
            select(LLMModel.id).where(
                LLMModel.id.in_(default_model_ids),
                LLMModel.is_active.is_(True),
            )
        )
        valid_ids = {row[0] for row in result.all()}
        invalid = set(default_model_ids) - valid_ids
        if invalid:
            raise ValueError(f"Invalid or inactive model IDs: {invalid}")

    # Upsert user_settings
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    if settings:
        settings.max_rounds = max_rounds
    else:
        settings = UserSettings(user_id=user_id, max_rounds=max_rounds)
        db.add(settings)
    await db.flush()

    # Sync default models: delete all, re-insert
    await db.execute(
        delete(user_default_models).where(user_default_models.c.user_id == user_id)
    )
    if default_model_ids:
        await db.execute(
            user_default_models.insert(),
            [{"user_id": user_id, "llm_model_id": mid} for mid in default_model_ids],
        )
    await db.flush()

    return {
        "max_rounds": max_rounds,
        "default_model_ids": default_model_ids,
    }
