import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.catalog.schemas import ModelResponse, ProviderResponse
from app.database import get_db
from app.models import LLMModel, Provider

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Provider).where(Provider.is_active.is_(True)).order_by(Provider.display_name)
    )
    return result.scalars().all()


@router.get("/models", response_model=list[ModelResponse])
async def list_models(
    provider_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(LLMModel)
        .options(joinedload(LLMModel.provider))
        .where(LLMModel.is_active.is_(True))
    )
    if provider_id:
        query = query.where(LLMModel.provider_id == provider_id)
    query = query.order_by(LLMModel.display_name)
    result = await db.execute(query)
    models = result.scalars().all()

    return [
        ModelResponse(
            id=m.id,
            provider_id=m.provider_id,
            provider_slug=m.provider.slug,
            slug=m.slug,
            display_name=m.display_name,
            model_type=m.model_type,
            input_price_per_mtok=m.input_price_per_mtok,
            output_price_per_mtok=m.output_price_per_mtok,
            is_active=m.is_active,
            context_window=m.context_window,
            tokens_per_second=m.tokens_per_second,
        )
        for m in models
    ]
