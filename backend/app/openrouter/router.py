import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.openrouter.schemas import (
    AddCustomModelRequest,
    CustomModelResponse,
    OpenRouterModelResponse,
)
from app.openrouter.service import (
    add_custom_model,
    delete_custom_model,
    get_openrouter_key,
    list_custom_models,
    search_openrouter_models,
)

router = APIRouter(tags=["openrouter"])


@router.get("/api/openrouter/models", response_model=list[OpenRouterModelResponse])
async def get_openrouter_models(
    search: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    api_key = await get_openrouter_key(current_user.id, db)
    if api_key is None:
        raise HTTPException(status_code=400, detail="No OpenRouter API key configured")
    return await search_openrouter_models(api_key, search)


@router.get(
    "/api/users/me/custom-models",
    response_model=list[CustomModelResponse],
)
async def get_custom_models(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ucms = await list_custom_models(current_user.id, db)
    return [
        CustomModelResponse(
            id=ucm.id,
            slug=ucm.llm_model.slug,
            display_name=ucm.llm_model.display_name,
            model_type=ucm.llm_model.model_type,
            input_price_per_mtok=ucm.llm_model.input_price_per_mtok,
            output_price_per_mtok=ucm.llm_model.output_price_per_mtok,
            context_window=ucm.llm_model.context_window,
            tokens_per_second=ucm.llm_model.tokens_per_second,
        )
        for ucm in ucms
    ]


@router.post(
    "/api/users/me/custom-models",
    response_model=CustomModelResponse,
    status_code=201,
)
async def create_custom_model(
    body: AddCustomModelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        ucm = await add_custom_model(
            current_user.id,
            body.model_slug,
            body.display_name,
            db,
            model_type=body.model_type,
            input_price_per_mtok=body.input_price_per_mtok,
            output_price_per_mtok=body.output_price_per_mtok,
            context_window=body.context_window,
            tokens_per_second=body.tokens_per_second,
        )
        await db.commit()
        return CustomModelResponse(
            id=ucm.id,
            slug=ucm.llm_model.slug,
            display_name=ucm.llm_model.display_name,
            model_type=ucm.llm_model.model_type,
            input_price_per_mtok=ucm.llm_model.input_price_per_mtok,
            output_price_per_mtok=ucm.llm_model.output_price_per_mtok,
            context_window=ucm.llm_model.context_window,
            tokens_per_second=ucm.llm_model.tokens_per_second,
        )
    except ValueError as e:
        if "already added" in str(e):
            raise HTTPException(status_code=409, detail="Model already added")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/users/me/custom-models/{model_id}", status_code=204)
async def remove_custom_model(
    model_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_custom_model(current_user.id, model_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Custom model not found")
    await db.commit()
