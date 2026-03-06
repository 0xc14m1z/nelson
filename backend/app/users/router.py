from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.users.schemas import (
    ProfileResponse,
    SettingsResponse,
    UpdateProfileRequest,
    UpdateSettingsRequest,
)
from app.users.service import get_settings, update_settings

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=ProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=ProfileResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.billing_mode is not None:
        current_user.billing_mode = body.billing_mode
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/me/settings", response_model=SettingsResponse)
async def get_user_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_settings(current_user.id, db)


@router.put("/me/settings", response_model=SettingsResponse)
async def update_user_settings(
    body: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await update_settings(current_user.id, body.max_rounds, body.default_model_ids, db)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
