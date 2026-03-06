import asyncio
import os
import re
import subprocess
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

# ---------------------------------------------------------------------------
# Eagerly swap app.database to point at nelson_test BEFORE any test module
# imports `from app.database import engine`.  This runs at conftest load time
# (i.e. before collection), so every subsequent import sees the test engine.
# ---------------------------------------------------------------------------

TEST_DB_NAME = "nelson_test"
_base_url = settings.database_url.rsplit("/", 1)[0]
TEST_DATABASE_URL = f"{_base_url}/{TEST_DB_NAME}"


def _setup_test_db_sync() -> None:
    """Create the test database and run Alembic migrations (sync wrapper)."""

    async def _inner():
        admin_engine = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_NAME}'")
            )
            if not exists:
                await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        await admin_engine.dispose()

    asyncio.run(_inner())

    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=str(Path(__file__).resolve().parent.parent),
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True,
        capture_output=True,
    )


# Run DB setup immediately
_setup_test_db_sync()

# Swap engine and session factory BEFORE any test imports app.database.engine
import app.database as _db_mod

_original_engine = _db_mod.engine
_original_factory = _db_mod.async_session_factory

_db_mod.engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_db_mod.async_session_factory = async_sessionmaker(_db_mod.engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def _teardown_test_engine():
    """Dispose the test engine after all tests and restore originals."""
    yield
    await _db_mod.engine.dispose()
    _db_mod.engine = _original_engine
    _db_mod.async_session_factory = _original_factory


async def extract_token_from_mailpit(email: str) -> str:
    """Extract the raw magic-link token from the last Mailpit email to this address."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://{settings.smtp_host}:8025/api/v1/messages")
        messages = resp.json()["messages"]

        for msg in messages:
            if any(email in r["Address"] for r in msg["To"]):
                detail = await client.get(
                    f"http://{settings.smtp_host}:8025/api/v1/message/{msg['ID']}"
                )
                body = detail.json()["Text"]
                match = re.search(r"token=([^&\s]+)", body)
                if match:
                    return match.group(1)

    raise ValueError(f"No magic link email found for {email}")


@pytest.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
