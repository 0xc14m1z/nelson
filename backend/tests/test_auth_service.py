import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine
from app.models import MagicLink, RefreshToken, User


@pytest.fixture
async def db_session():
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_mailpit():
    """Clear Mailpit inbox before each test."""
    async with httpx.AsyncClient() as client:
        await client.delete(f"http://{settings.smtp_host}:8025/api/v1/messages")
    yield


@pytest.fixture(autouse=True)
async def clean_test_users(db_session):
    """Clean up test users after each test."""
    yield
    for email in [
        "auth-test@example.com",
        "rate-test@example.com",
        "verify-test@example.com",
        "refresh-test@example.com",
    ]:
        result = await db_session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            await db_session.delete(user)
    # Clean up magic links
    result = await db_session.execute(select(MagicLink))
    for link in result.scalars().all():
        await db_session.delete(link)
    await db_session.commit()


# --- request_magic_link tests ---


@pytest.mark.asyncio
async def test_request_magic_link_sends_email(db_session):
    from app.auth.service import request_magic_link

    await request_magic_link("auth-test@example.com", db_session)

    # Check Mailpit received the email
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://{settings.smtp_host}:8025/api/v1/messages")
        messages = resp.json()["messages"]
        assert len(messages) >= 1
        latest = messages[0]
        assert any("auth-test@example.com" in r["Address"] for r in latest["To"])


@pytest.mark.asyncio
async def test_request_magic_link_creates_db_row(db_session):
    from app.auth.service import request_magic_link

    await request_magic_link("auth-test@example.com", db_session)

    result = await db_session.execute(
        select(MagicLink).where(MagicLink.email == "auth-test@example.com")
    )
    link = result.scalar_one()
    assert link.token_hash is not None
    assert len(link.token_hash) == 64  # SHA-256 hex digest
    assert link.used_at is None
    assert link.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_request_magic_link_rate_limit(db_session):
    from app.auth.service import RateLimitExceeded, request_magic_link

    for _ in range(3):
        await request_magic_link("rate-test@example.com", db_session)

    with pytest.raises(RateLimitExceeded):
        await request_magic_link("rate-test@example.com", db_session)


# --- verify_magic_link tests ---


@pytest.mark.asyncio
async def test_verify_creates_user_on_first_login(db_session):
    from app.auth.service import _extract_token_from_mailpit, request_magic_link, verify_magic_link

    await request_magic_link("verify-test@example.com", db_session)
    raw_token = await _extract_token_from_mailpit("verify-test@example.com")

    result = await verify_magic_link("verify-test@example.com", raw_token, db_session)

    assert result.access_token is not None
    assert result.refresh_token is not None

    # User was auto-created
    user_result = await db_session.execute(
        select(User).where(User.email == "verify-test@example.com")
    )
    user = user_result.scalar_one()
    assert user.billing_mode == "own_keys"


@pytest.mark.asyncio
async def test_verify_marks_link_used(db_session):
    from app.auth.service import _extract_token_from_mailpit, request_magic_link, verify_magic_link

    await request_magic_link("verify-test@example.com", db_session)
    raw_token = await _extract_token_from_mailpit("verify-test@example.com")

    await verify_magic_link("verify-test@example.com", raw_token, db_session)

    result = await db_session.execute(
        select(MagicLink).where(MagicLink.email == "verify-test@example.com")
    )
    link = result.scalar_one()
    assert link.used_at is not None


@pytest.mark.asyncio
async def test_verify_rejects_used_token(db_session):
    from app.auth.service import (
        InvalidToken,
        _extract_token_from_mailpit,
        request_magic_link,
        verify_magic_link,
    )

    await request_magic_link("verify-test@example.com", db_session)
    raw_token = await _extract_token_from_mailpit("verify-test@example.com")

    await verify_magic_link("verify-test@example.com", raw_token, db_session)
    with pytest.raises(InvalidToken):
        await verify_magic_link("verify-test@example.com", raw_token, db_session)


@pytest.mark.asyncio
async def test_verify_rejects_expired_token(db_session):
    from app.auth.service import InvalidToken, verify_magic_link

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    link = MagicLink(
        email="verify-test@example.com",
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(link)
    await db_session.commit()

    with pytest.raises(InvalidToken):
        await verify_magic_link("verify-test@example.com", raw_token, db_session)


# --- refresh tests ---


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(db_session):
    from app.auth.service import (
        _extract_token_from_mailpit,
        refresh_access_token,
        request_magic_link,
        verify_magic_link,
    )

    await request_magic_link("refresh-test@example.com", db_session)
    raw_token = await _extract_token_from_mailpit("refresh-test@example.com")
    auth = await verify_magic_link("refresh-test@example.com", raw_token, db_session)

    new_auth = await refresh_access_token(auth.refresh_token, db_session)
    assert new_auth.access_token is not None
    # Access tokens may be identical if generated in the same second (same sub, email, exp, iat)
    # The important check is that a new refresh token was issued
    assert new_auth.refresh_token is not None
    assert new_auth.refresh_token != auth.refresh_token


@pytest.mark.asyncio
async def test_refresh_revokes_old_token(db_session):
    from app.auth.service import (
        InvalidToken,
        _extract_token_from_mailpit,
        refresh_access_token,
        request_magic_link,
        verify_magic_link,
    )

    await request_magic_link("refresh-test@example.com", db_session)
    raw_token = await _extract_token_from_mailpit("refresh-test@example.com")
    auth = await verify_magic_link("refresh-test@example.com", raw_token, db_session)
    old_refresh = auth.refresh_token

    await refresh_access_token(old_refresh, db_session)

    # Old token is now revoked
    with pytest.raises(InvalidToken):
        await refresh_access_token(old_refresh, db_session)
