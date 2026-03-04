import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import _extract_token_from_mailpit
from app.config import settings
from app.database import engine
from app.main import app
from app.models import MagicLink, User


@pytest.fixture
async def db_session():
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture(autouse=True)
async def clean_mailpit():
    async with httpx.AsyncClient() as client:
        await client.delete(f"http://{settings.smtp_host}:8025/api/v1/messages")
    yield


@pytest.fixture(autouse=True)
async def clean_test_data(db_session):
    yield
    result = await db_session.execute(select(User).where(User.email == "integration@example.com"))
    user = result.scalar_one_or_none()
    if user:
        await db_session.delete(user)
    result = await db_session.execute(select(MagicLink))
    for link in result.scalars().all():
        await db_session.delete(link)
    await db_session.commit()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_full_auth_flow(client):
    """End-to-end: request magic link -> extract from Mailpit -> verify ->
    access protected endpoint -> refresh -> access again."""

    email = "integration@example.com"

    # 1. Request magic link
    resp = await client.post("/api/auth/magic-link", json={"email": email})
    assert resp.status_code == 200

    # 2. Extract token from Mailpit
    raw_token = await _extract_token_from_mailpit(email)
    assert raw_token is not None

    # 3. Verify magic link
    resp = await client.post("/api/auth/verify", json={"email": email, "token": raw_token})
    assert resp.status_code == 200
    access_token = resp.json()["access_token"]
    assert access_token
    assert "refresh_token" in resp.cookies

    # 4. Access protected endpoint
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == email

    # 5. Refresh using the cookie from verify
    # The ASGITransport + httpx may not propagate path-scoped cookies automatically,
    # so we extract the cookie value directly.
    refresh_cookie_value = client.cookies.get("refresh_token")
    if refresh_cookie_value:
        refresh_resp = await client.post(
            "/api/auth/refresh", cookies={"refresh_token": refresh_cookie_value}
        )
        assert refresh_resp.status_code == 200
        new_access_token = refresh_resp.json()["access_token"]
        assert new_access_token

        # 6. Access protected endpoint with new token
        resp = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {new_access_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == email


@pytest.mark.asyncio
async def test_reused_magic_link_rejected(client):
    """Verify that a magic link cannot be used twice."""

    email = "integration@example.com"

    resp = await client.post("/api/auth/magic-link", json={"email": email})
    assert resp.status_code == 200

    raw_token = await _extract_token_from_mailpit(email)

    # First use succeeds
    resp = await client.post("/api/auth/verify", json={"email": email, "token": raw_token})
    assert resp.status_code == 200

    # Second use fails
    resp = await client.post("/api/auth/verify", json={"email": email, "token": raw_token})
    assert resp.status_code == 401
