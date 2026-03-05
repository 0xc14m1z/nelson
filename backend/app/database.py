from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

def _ensure_asyncpg_scheme(url: str) -> str:
    """Ensure the database URL uses the asyncpg driver.

    DigitalOcean App Platform injects postgresql:// but SQLAlchemy async
    requires postgresql+asyncpg://.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(_ensure_asyncpg_scheme(settings.database_url), echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
