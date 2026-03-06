import uuid
from dataclasses import dataclass

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.keys.service import get_decrypted_key
from app.models import LLMModel, Provider


class NoKeyAvailableError(Exception):
    def __init__(self, model_slug: str):
        self.model_slug = model_slug
        super().__init__(f"No API key available for model '{model_slug}'")


@dataclass
class ResolvedModel:
    api_key: str
    base_url: str
    model_slug: str
    provider_slug: str
    via_openrouter: bool


async def resolve_model(
    user_id: uuid.UUID,
    llm_model: LLMModel,
    db: AsyncSession,
) -> ResolvedModel:
    """Resolve which API key and base URL to use for a given model.

    Resolution order:
    1. User's own key for the model's provider
    2. User's OpenRouter key (with slug translation)
    3. Raise NoKeyAvailableError
    """
    # Ensure provider is loaded (check without triggering lazy load)
    if "provider" not in inspect(llm_model).dict:
        query = select(LLMModel).options(joinedload(LLMModel.provider))
        result = await db.execute(query.where(LLMModel.id == llm_model.id))
        llm_model = result.scalar_one()

    provider = llm_model.provider

    # Step 1: Try user's own key for this provider
    direct_key = await get_decrypted_key(user_id, provider.id, db)
    if direct_key:
        return ResolvedModel(
            api_key=direct_key,
            base_url=provider.base_url,
            model_slug=llm_model.slug,
            provider_slug=provider.slug,
            via_openrouter=False,
        )

    # Step 2: Try OpenRouter fallback (skip if model is already OpenRouter-native)
    if provider.slug != "openrouter":
        or_provider = await db.execute(select(Provider).where(Provider.slug == "openrouter"))
        openrouter = or_provider.scalar_one_or_none()
        if openrouter:
            or_key = await get_decrypted_key(user_id, openrouter.id, db)
            if or_key:
                # Map provider slugs to OpenRouter prefixes where they differ
                or_slug_map = {"xai": "x-ai"}
                or_prefix = or_slug_map.get(provider.slug, provider.slug)
                return ResolvedModel(
                    api_key=or_key,
                    base_url=openrouter.base_url,
                    model_slug=f"{or_prefix}/{llm_model.slug}",
                    provider_slug="openrouter",
                    via_openrouter=True,
                )

    # Step 3: No key available
    raise NoKeyAvailableError(llm_model.slug)
