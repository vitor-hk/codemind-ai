import pytest_asyncio
from app.infrastructure.database.session import engine, init_database


@pytest_asyncio.fixture(autouse=True)
async def _manage_db_lifecycle():
    await engine.dispose()
    await init_database()
    yield
    await engine.dispose()
