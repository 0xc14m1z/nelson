import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.keys.schemas import ApiKeyResponse, StoreKeyRequest, ValidateKeyResponse
from app.keys.service import (
    InvalidKeyError,
    delete_key,
    list_keys,
    store_key,
    validate_existing_key,
)
from app.models import User

router = APIRouter(prefix="/api/keys", tags=["keys"])


def _masked_key_to_response(k: object) -> ApiKeyResponse:
    """Convert a MaskedKey (dynamic type from service) to an ApiKeyResponse."""
    return ApiKeyResponse(
        id=k.id,
        provider_id=k.provider_id,
        provider_slug=k.provider_slug,
        provider_display_name=k.provider_display_name,
        masked_key=k.masked_key,
        is_valid=k.is_valid,
        validated_at=k.validated_at,
        created_at=k.created_at,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def get_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    keys = await list_keys(current_user.id, db)
    return [_masked_key_to_response(k) for k in keys]


@router.post("", response_model=ApiKeyResponse, status_code=201)
async def create_key(
    body: StoreKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip_validation: bool = Query(False),
):
    try:
        await store_key(
            current_user.id, body.provider_id, body.api_key, db, skip_validation=skip_validation
        )
        await db.commit()
        # Re-fetch with provider loaded for response
        keys = await list_keys(current_user.id, db)
        matched = next(k for k in keys if k.provider_id == body.provider_id)
        return _masked_key_to_response(matched)
    except InvalidKeyError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{provider_id}", status_code=204)
async def remove_key(
    provider_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_key(current_user.id, provider_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="No key found for this provider")
    await db.commit()


@router.post("/{provider_id}/validate", response_model=ValidateKeyResponse)
async def validate_key(
    provider_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_valid, error = await validate_existing_key(current_user.id, provider_id, db)
    await db.commit()
    return ValidateKeyResponse(is_valid=is_valid, error=error)
