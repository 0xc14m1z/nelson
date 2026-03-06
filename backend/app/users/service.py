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
        "summarizer_model_id": settings.summarizer_model_id if settings else None,
    }


async def update_settings(
    user_id: uuid.UUID,
    max_rounds: int | None,
    default_model_ids: list[uuid.UUID],
    db: AsyncSession,
    summarizer_model_id: uuid.UUID | None = None,
) -> dict:
    # Validate model IDs exist and are active
    all_model_ids = list(default_model_ids)
    if summarizer_model_id:
        all_model_ids.append(summarizer_model_id)
    if all_model_ids:
        result = await db.execute(
            select(LLMModel.id).where(
                LLMModel.id.in_(all_model_ids),
                LLMModel.is_active.is_(True),
            )
        )
        valid_ids = {row[0] for row in result.all()}
        invalid_default = set(default_model_ids) - valid_ids
        if invalid_default:
            raise ValueError(f"Invalid or inactive model IDs: {invalid_default}")
        if summarizer_model_id and summarizer_model_id not in valid_ids:
            raise ValueError(f"Invalid or inactive model IDs: {{{summarizer_model_id!r}}}")

    # Upsert user_settings
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    if settings:
        settings.max_rounds = max_rounds
        settings.summarizer_model_id = summarizer_model_id
    else:
        settings = UserSettings(
            user_id=user_id,
            max_rounds=max_rounds,
            summarizer_model_id=summarizer_model_id,
        )
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
        "summarizer_model_id": summarizer_model_id,
    }
