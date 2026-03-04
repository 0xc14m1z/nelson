import re

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app


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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
