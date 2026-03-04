from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    AuthResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    UserResponse,
    VerifyRequest,
)
from app.auth.service import (
    InvalidTokenError,
    RateLimitError,
    refresh_access_token,
    request_magic_link,
    verify_magic_link,
)
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/magic-link", response_model=MagicLinkResponse)
async def send_magic_link(body: MagicLinkRequest, db: AsyncSession = Depends(get_db)):
    try:
        await request_magic_link(body.email, db)
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    return MagicLinkResponse(message="Check your email for a login link.")


@router.post("/verify", response_model=AuthResponse)
async def verify(body: VerifyRequest, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        tokens = await verify_magic_link(body.email, body.token, db)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired magic link.")

    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=False,  # False for local dev; set True in production via config
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
        path="/api/auth/refresh",
    )
    return AuthResponse(access_token=tokens.access_token)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="No refresh token.")

    try:
        tokens = await refresh_access_token(refresh_token, db)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/api/auth/refresh",
    )
    return AuthResponse(access_token=tokens.access_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
