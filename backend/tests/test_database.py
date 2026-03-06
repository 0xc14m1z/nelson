import pytest
from sqlalchemy import func, inspect, select

from app.database import engine
from app.models import LLMModel, Provider


@pytest.fixture
async def db_session():
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as session:
        yield session


@pytest.mark.asyncio
async def test_providers_seeded(db_session):
    result = await db_session.execute(select(func.count()).select_from(Provider))
    assert result.scalar() == 5


@pytest.mark.asyncio
async def test_provider_slugs(db_session):
    result = await db_session.execute(select(Provider.slug).order_by(Provider.slug))
    slugs = [r[0] for r in result.all()]
    assert slugs == ["anthropic", "google", "mistral", "openai", "openrouter"]


@pytest.mark.asyncio
async def test_llm_models_seeded(db_session):
    result = await db_session.execute(select(func.count()).select_from(LLMModel))
    assert result.scalar() >= 13


@pytest.mark.asyncio
async def test_llm_models_have_providers(db_session):
    result = await db_session.execute(select(LLMModel))
    models = result.scalars().all()
    for model in models:
        assert model.provider_id is not None


@pytest.mark.asyncio
async def test_provider_relationship(db_session):
    result = await db_session.execute(select(Provider).where(Provider.slug == "openai"))
    openai = result.scalar_one()
    await db_session.refresh(openai, ["models"])
    model_slugs = sorted([m.slug for m in openai.models])
    assert "gpt-5" in model_slugs
    assert "gpt-5-mini" in model_slugs


@pytest.mark.asyncio
async def test_tables_exist(db_session):
    conn = await db_session.connection()

    def check_tables(sync_conn):
        inspector = inspect(sync_conn)
        tables = inspector.get_table_names()
        assert "providers" in tables
        assert "llm_models" in tables

    await conn.run_sync(check_tables)
