from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models import MagicLink, RefreshToken, User, UserSettings


@pytest.fixture
async def db_session():
    async with AsyncSession(engine) as session:
        yield session


@pytest.fixture
async def test_user(db_session):
    """Create a test user and clean up after."""
    user = User(email="test@example.com", display_name="Test User")
    settings = UserSettings(user=user)  # noqa: F841
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user
    # Cleanup
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(email="create-test@example.com")
    settings = UserSettings(user=user)  # noqa: F841
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "create-test@example.com"
    assert user.billing_mode == "own_keys"
    assert user.display_name is None
    assert user.created_at is not None

    # Cleanup
    await db_session.delete(user)
    await db_session.commit()


@pytest.mark.asyncio
async def test_user_settings_created_with_user(test_user, db_session):
    await db_session.refresh(test_user, ["settings"])
    assert test_user.settings is not None
    assert test_user.settings.max_rounds is None


@pytest.mark.asyncio
async def test_user_email_unique(db_session):
    from sqlalchemy.exc import IntegrityError

    user1 = User(email="unique-test@example.com")
    settings1 = UserSettings(user=user1)  # noqa: F841
    db_session.add(user1)
    await db_session.commit()

    user2 = User(email="unique-test@example.com")
    settings2 = UserSettings(user=user2)  # noqa: F841
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # Cleanup
    await db_session.delete(user1)
    await db_session.commit()


@pytest.mark.asyncio
async def test_cascade_delete_user(db_session):
    user = User(email="cascade-test@example.com")
    settings = UserSettings(user=user)  # noqa: F841
    RefreshToken(
        user=user,
        token_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id

    await db_session.delete(user)
    await db_session.commit()

    # Verify cascade
    result = await db_session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    assert result.scalar_one_or_none() is None
    result = await db_session.execute(select(RefreshToken).where(RefreshToken.user_id == user_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_create_magic_link(db_session):
    link = MagicLink(
        email="magic@example.com",
        token_hash="b" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db_session.add(link)
    await db_session.commit()
    await db_session.refresh(link)

    assert link.id is not None
    assert link.used_at is None

    # Cleanup
    await db_session.delete(link)
    await db_session.commit()


@pytest.mark.asyncio
async def test_create_refresh_token(test_user, db_session):
    token = RefreshToken(
        user=test_user,
        token_hash="c" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)

    assert token.id is not None
    assert token.revoked_at is None
    await db_session.refresh(test_user)
    assert token.user_id == test_user.id

    # Cleanup
    await db_session.delete(token)
    await db_session.commit()
