import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    for email in ["router-test@example.com", "rate-router@example.com"]:
        result = await db_session.execute(select(User).where(User.email == email))
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
async def test_magic_link_endpoint(client):
    resp = await client.post("/api/auth/magic-link", json={"email": "router-test@example.com"})
    assert resp.status_code == 200
    assert "check your email" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_magic_link_invalid_email(client):
    resp = await client.post("/api/auth/magic-link", json={"email": "not-an-email"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_magic_link_rate_limit(client):
    for _ in range(3):
        await client.post("/api/auth/magic-link", json={"email": "rate-router@example.com"})

    resp = await client.post("/api/auth/magic-link", json={"email": "rate-router@example.com"})
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_verify_endpoint(client):
    from app.auth.service import _extract_token_from_mailpit

    await client.post("/api/auth/magic-link", json={"email": "router-test@example.com"})
    raw_token = await _extract_token_from_mailpit("router-test@example.com")

    resp = await client.post(
        "/api/auth/verify", json={"email": "router-test@example.com", "token": raw_token}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    # Check refresh token cookie
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_verify_invalid_token(client):
    resp = await client.post(
        "/api/auth/verify", json={"email": "router-test@example.com", "token": "bad-token"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_endpoint(client):
    from app.auth.service import _extract_token_from_mailpit

    await client.post("/api/auth/magic-link", json={"email": "router-test@example.com"})
    raw_token = await _extract_token_from_mailpit("router-test@example.com")

    verify_resp = await client.post(
        "/api/auth/verify", json={"email": "router-test@example.com", "token": raw_token}
    )
    # httpx captures cookies automatically
    cookies = verify_resp.cookies

    refresh_resp = await client.post("/api/auth/refresh", cookies=cookies)
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()
    assert "refresh_token" in refresh_resp.cookies


@pytest.mark.asyncio
async def test_refresh_without_cookie(client):
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_with_token(client):
    from app.auth.service import _extract_token_from_mailpit

    await client.post("/api/auth/magic-link", json={"email": "router-test@example.com"})
    raw_token = await _extract_token_from_mailpit("router-test@example.com")

    verify_resp = await client.post(
        "/api/auth/verify", json={"email": "router-test@example.com", "token": raw_token}
    )
    access_token = verify_resp.json()["access_token"]

    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "router-test@example.com"


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 401 or 403 for missing token
