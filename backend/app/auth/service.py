import hashlib
import secrets
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import MagicLink, RefreshToken, User, UserSettings


class RateLimitExceeded(Exception):
    pass


class InvalidToken(Exception):
    pass


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _send_email_smtp(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.send_message(msg)


def _send_email_resend(to: str, subject: str, body: str) -> None:
    import resend

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": settings.email_from,
            "to": to,
            "subject": subject,
            "text": body,
        }
    )


def _send_email(to: str, subject: str, body: str) -> None:
    if settings.email_provider == "resend":
        _send_email_resend(to, subject, body)
    else:
        _send_email_smtp(to, subject, body)


async def request_magic_link(email: str, db: AsyncSession) -> None:
    # Rate limit: 3 per email per 15 minutes
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    result = await db.execute(
        select(func.count())
        .select_from(MagicLink)
        .where(MagicLink.email == email, MagicLink.created_at >= since)
    )
    count = result.scalar()
    if count >= 3:
        raise RateLimitExceeded("Too many magic link requests. Try again later.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    link = MagicLink(
        email=email,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(link)
    await db.commit()

    url = f"{settings.magic_link_base_url}?token={raw_token}&email={email}"
    _send_email(
        to=email,
        subject="Your Nelson login link",
        body=f"Click here to log in: {url}\n\nThis link expires in 15 minutes.",
    )


async def verify_magic_link(email: str, token: str, db: AsyncSession) -> AuthTokens:
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(MagicLink).where(
            MagicLink.email == email,
            MagicLink.token_hash == token_hash,
            MagicLink.expires_at > now,
            MagicLink.used_at.is_(None),
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise InvalidToken("Invalid or expired magic link.")

    link.used_at = now
    await db.flush()

    # Get or create user
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if user is None:
        user = User(email=email)
        user_settings = UserSettings(user=user)  # noqa: F841
        db.add(user)
        await db.flush()

    # Create tokens
    access_token = _create_access_token(str(user.id), user.email)

    raw_refresh = secrets.token_urlsafe(32)
    refresh_hash = _hash_token(raw_refresh)
    refresh = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh)
    await db.commit()

    return AuthTokens(access_token=access_token, refresh_token=raw_refresh)


async def refresh_access_token(raw_refresh_token: str, db: AsyncSession) -> AuthTokens:
    token_hash = _hash_token(raw_refresh_token)
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > now,
            RefreshToken.revoked_at.is_(None),
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise InvalidToken("Invalid or expired refresh token.")

    # Revoke old token
    token.revoked_at = now
    await db.flush()

    # Load user
    user_result = await db.execute(select(User).where(User.id == token.user_id))
    user = user_result.scalar_one()

    # Issue new tokens
    access_token = _create_access_token(str(user.id), user.email)

    new_raw_refresh = secrets.token_urlsafe(32)
    new_refresh = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(new_raw_refresh),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_refresh)
    await db.commit()

    return AuthTokens(access_token=access_token, refresh_token=new_raw_refresh)


async def _extract_token_from_mailpit(email: str) -> str:
    """Test helper: extract the raw token from the last Mailpit email to this address."""
    import re

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://{settings.smtp_host}:8025/api/v1/messages")
        messages = resp.json()["messages"]

        for msg in messages:
            if any(email in r["Address"] for r in msg["To"]):
                # Fetch full message body
                detail = await client.get(
                    f"http://{settings.smtp_host}:8025/api/v1/message/{msg['ID']}"
                )
                body = detail.json()["Text"]
                match = re.search(r"token=([^&\s]+)", body)
                if match:
                    return match.group(1)

    raise ValueError(f"No magic link email found for {email}")
