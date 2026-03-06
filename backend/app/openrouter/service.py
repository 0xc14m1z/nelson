import uuid
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.keys.service import get_decrypted_key
from app.models import LLMModel, Provider, UserCustomModel
from app.models.user import user_default_models
from app.openrouter.schemas import OpenRouterModelResponse

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


async def get_openrouter_key(user_id: uuid.UUID, db: AsyncSession) -> str | None:
    """Get the decrypted OpenRouter API key for a user."""
    result = await db.execute(select(Provider).where(Provider.slug == "openrouter"))
    provider = result.scalar_one_or_none()
    if provider is None:
        return None
    return await get_decrypted_key(user_id, provider.id, db)


_CODE_HINTS = {"coder", "codestral", "code"}
_DIFFUSION_HINTS = {"diffusion", "mercury"}


def _classify_model_type(
    slug: str,
    name: str,
    supported_params: list[str] | None,
) -> str | None:
    """Classify a model using OpenRouter's supported_parameters.

    Logic:
    - 'reasoning' in params + no 'temperature' → pure reasoning model
    - 'reasoning' in params + 'temperature' → hybrid (can toggle reasoning)
    - code/diffusion hints in slug/name override the above
    - everything else with params → chat
    """
    lower_slug = slug.lower()
    lower_name = name.lower()
    combined = f"{lower_slug} {lower_name}"

    # Check for diffusion models first (name-based)
    if any(h in combined for h in _DIFFUSION_HINTS):
        return "diffusion"

    # Check for code models (name-based)
    if any(h in combined for h in _CODE_HINTS):
        return "code"

    if not supported_params:
        return None

    has_reasoning = "reasoning" in supported_params
    has_temperature = "temperature" in supported_params

    if has_reasoning and not has_temperature:
        return "reasoning"
    if has_reasoning and has_temperature:
        return "hybrid"

    return "chat"


async def search_openrouter_models(
    api_key: str,
    search: str | None = None,
) -> list[OpenRouterModelResponse]:
    """Fetch models from OpenRouter API and map to our schema."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            OPENROUTER_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()

    data = resp.json().get("data", [])
    models: list[OpenRouterModelResponse] = []

    for m in data:
        model_id = m.get("id", "")
        name = m.get("name", model_id)

        # Filter by search term if provided
        if search:
            term = search.lower()
            if term not in model_id.lower() and term not in name.lower():
                continue

        pricing = m.get("pricing", {})
        prompt_price = pricing.get("prompt")
        completion_price = pricing.get("completion")

        input_price = Decimal(str(prompt_price)) * 1_000_000 if prompt_price is not None else None
        output_price = (
            Decimal(str(completion_price)) * 1_000_000 if completion_price is not None else None
        )

        context_length = m.get("context_length")
        supported_params = m.get("supported_parameters", [])
        model_type = _classify_model_type(model_id, name, supported_params)

        models.append(
            OpenRouterModelResponse(
                slug=model_id,
                display_name=name,
                model_type=model_type,
                input_price_per_mtok=input_price,
                output_price_per_mtok=output_price,
                context_window=context_length,
                tokens_per_second=None,
            )
        )

    return models


async def add_custom_model(
    user_id: uuid.UUID,
    model_slug: str,
    display_name: str,
    db: AsyncSession,
    *,
    model_type: str | None = None,
    input_price_per_mtok: Decimal | None = None,
    output_price_per_mtok: Decimal | None = None,
    context_window: int | None = None,
    tokens_per_second: float | None = None,
) -> UserCustomModel:
    """Upsert an LLMModel row for this OpenRouter model, then link it to the user."""
    # Find the OpenRouter provider
    result = await db.execute(select(Provider).where(Provider.slug == "openrouter"))
    provider = result.scalar_one_or_none()
    if provider is None:
        raise ValueError("OpenRouter provider not found")

    # Upsert the LLMModel
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.provider_id == provider.id,
            LLMModel.slug == model_slug,
        )
    )
    llm_model = result.scalar_one_or_none()

    if llm_model is None:
        llm_model = LLMModel(
            provider_id=provider.id,
            slug=model_slug,
            display_name=display_name,
            model_type=model_type,
            input_price_per_mtok=input_price_per_mtok or Decimal("0"),
            output_price_per_mtok=output_price_per_mtok or Decimal("0"),
            context_window=context_window or 128000,
            tokens_per_second=tokens_per_second,
        )
        db.add(llm_model)
        await db.flush()
    else:
        # Update fields if model already exists
        llm_model.display_name = display_name
        if model_type is not None:
            llm_model.model_type = model_type
        if input_price_per_mtok is not None:
            llm_model.input_price_per_mtok = input_price_per_mtok
        if output_price_per_mtok is not None:
            llm_model.output_price_per_mtok = output_price_per_mtok
        if context_window is not None:
            llm_model.context_window = context_window
        if tokens_per_second is not None:
            llm_model.tokens_per_second = tokens_per_second
        await db.flush()

    # Check if user already has this custom model
    result = await db.execute(
        select(UserCustomModel).where(
            UserCustomModel.user_id == user_id,
            UserCustomModel.llm_model_id == llm_model.id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise ValueError("Model already added")

    ucm = UserCustomModel(user_id=user_id, llm_model_id=llm_model.id)
    db.add(ucm)
    await db.flush()

    # Eagerly load the llm_model relationship
    result = await db.execute(
        select(UserCustomModel)
        .options(joinedload(UserCustomModel.llm_model))
        .where(UserCustomModel.id == ucm.id)
    )
    return result.scalar_one()


async def list_custom_models(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[UserCustomModel]:
    """List all custom models for a user with their LLMModel details."""
    result = await db.execute(
        select(UserCustomModel)
        .options(joinedload(UserCustomModel.llm_model))
        .where(UserCustomModel.user_id == user_id)
        .order_by(UserCustomModel.created_at)
    )
    return list(result.scalars().all())


async def delete_custom_model(
    user_id: uuid.UUID,
    model_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """Delete a user's custom model link. Also removes any user_default_models reference."""
    result = await db.execute(
        select(UserCustomModel).where(
            UserCustomModel.id == model_id,
            UserCustomModel.user_id == user_id,
        )
    )
    ucm = result.scalar_one_or_none()
    if ucm is None:
        return False

    # Remove from user_default_models if referenced
    await db.execute(
        user_default_models.delete().where(
            user_default_models.c.user_id == user_id,
            user_default_models.c.llm_model_id == ucm.llm_model_id,
        )
    )

    await db.delete(ucm)
    await db.flush()
    return True
