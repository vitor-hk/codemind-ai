from collections.abc import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings
from app.core.logging import get_logger
from app.infrastructure.database.base import Base
import app.infrastructure.database.models

logger = get_logger(__name__)
settings = get_settings()

engine = create_async_engine(settings.async_database_url, echo=False, pool_pre_ping=True, pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_database() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE repositories ADD COLUMN IF NOT EXISTS total_chunks INTEGER DEFAULT 0 NOT NULL;"))
    logger.info("database_initialized", host=settings.POSTGRES_HOST, db=settings.POSTGRES_DB)
