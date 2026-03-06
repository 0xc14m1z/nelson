import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.keys.encryption import decrypt_api_key, encrypt_api_key
from app.keys.validation import validate_api_key
from app.models import ApiKey, Provider


class InvalidKeyError(Exception):
    def __init__(self, message: str = "Invalid API key"):
        self.message = message
        super().__init__(self.message)


async def store_key(
    user_id: uuid.UUID,
    provider_id: uuid.UUID,
    raw_key: str,
    db: AsyncSession,
    *,
    skip_validation: bool = False,
) -> ApiKey:
    """Encrypt and store (or update) an API key. Validates first unless skip_validation=True."""
    is_valid = True
    validated_at = None

    if not skip_validation:
        result = await db.execute(select(Provider).where(Provider.id == provider_id))
        provider = result.scalar_one_or_none()
        if provider is None:
            raise ValueError("Provider not found")

        is_valid, error = await validate_api_key(provider.slug, provider.base_url, raw_key)
        if not is_valid:
            raise InvalidKeyError(error or "Invalid API key")
        validated_at = datetime.now(UTC)

    encrypted = encrypt_api_key(raw_key)

    # Upsert: check for existing key for this user+provider
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_key = encrypted
        existing.is_valid = is_valid
        existing.validated_at = validated_at or existing.validated_at
        await db.flush()
        return existing

    key = ApiKey(
        user_id=user_id,
        provider_id=provider_id,
        encrypted_key=encrypted,
        is_valid=is_valid,
        validated_at=validated_at,
    )
    db.add(key)
    await db.flush()
    return key


async def list_keys(user_id: uuid.UUID, db: AsyncSession) -> list:
    """Return all keys for a user with masked display and provider info."""
    result = await db.execute(
        select(ApiKey)
        .options(joinedload(ApiKey.provider))
        .where(ApiKey.user_id == user_id)
        .order_by(ApiKey.created_at)
    )
    keys = result.scalars().all()

    return [
        type(
            "MaskedKey",
            (),
            {
                "id": key.id,
                "provider_id": key.provider_id,
                "provider_slug": key.provider.slug,
                "provider_display_name": key.provider.display_name,
                "masked_key": _mask_key(decrypt_api_key(key.encrypted_key)),
                "is_valid": key.is_valid,
                "validated_at": key.validated_at,
                "created_at": key.created_at,
            },
        )
        for key in keys
    ]


async def delete_key(user_id: uuid.UUID, provider_id: uuid.UUID, db: AsyncSession) -> bool:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        return False
    await db.delete(key)
    await db.flush()
    return True


async def get_decrypted_key(
    user_id: uuid.UUID, provider_id: uuid.UUID, db: AsyncSession
) -> str | None:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        return None
    return decrypt_api_key(key.encrypted_key)


async def validate_existing_key(
    user_id: uuid.UUID, provider_id: uuid.UUID, db: AsyncSession
) -> tuple[bool, str | None]:
    """Re-validate a stored key by calling the provider API."""
    result = await db.execute(
        select(ApiKey)
        .options(joinedload(ApiKey.provider))
        .where(ApiKey.user_id == user_id, ApiKey.provider_id == provider_id)
    )
    key = result.scalar_one_or_none()
    if key is None:
        return False, "No key stored for this provider"

    raw_key = decrypt_api_key(key.encrypted_key)
    is_valid, error = await validate_api_key(key.provider.slug, key.provider.base_url, raw_key)
    key.is_valid = is_valid
    key.validated_at = datetime.now(UTC)
    await db.flush()
    return is_valid, error


def _mask_key(raw_key: str) -> str:
    """Mask a key, showing only the last 4 characters."""
    if len(raw_key) <= 4:
        return "****"
    return f"****{raw_key[-4:]}"
