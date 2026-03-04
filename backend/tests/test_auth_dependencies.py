from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import engine
from app.models import User, UserSettings


@pytest.fixture
async def db_session():
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture
async def test_user(db_session):
    user = User(email="dep-test@example.com")
    settings_obj = UserSettings(user=user)  # noqa: F841
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_decode_valid_token(test_user, db_session):
    from app.auth.dependencies import _decode_token

    token = jwt.encode(
        {
            "sub": str(test_user.id),
            "email": test_user.email,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    payload = _decode_token(token)
    assert payload["sub"] == str(test_user.id)


@pytest.mark.asyncio
async def test_decode_expired_token():
    from app.auth.dependencies import AuthenticationError, _decode_token

    token = jwt.encode(
        {
            "sub": "fake-id",
            "email": "x@x.com",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(AuthenticationError):
        _decode_token(token)


@pytest.mark.asyncio
async def test_decode_invalid_token():
    from app.auth.dependencies import AuthenticationError, _decode_token

    with pytest.raises(AuthenticationError):
        _decode_token("not.a.token")
