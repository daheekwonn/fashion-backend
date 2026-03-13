"""
db/session.py — Async SQLAlchemy engine + session factory
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.config import get_settings
from app.models.database import Base
import logging

settings = get_settings()
logger = logging.getLogger("app.db")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.APP_ENV == "development"),
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Create all tables on startup. Each table gets its own connection so
    a failure on one (e.g. duplicate index) never poisons the others.

    For the looks table, pre-existing indexes are dropped first to avoid
    DuplicateTableError on ix_looks_show_id.
    """
    for table in Base.metadata.sorted_tables:
        try:
            # Drop conflicting indexes before creating the table so that
            # CREATE TABLE … checkfirst=True doesn't choke on a duplicate
            # index name (e.g. ix_looks_show_id) from a prior partial run.
            if table.name == "looks":
                async with engine.begin() as conn:
                    for idx in table.indexes:
                        await conn.execute(
                            text(f"DROP INDEX IF EXISTS {idx.name}")
                        )

            async with engine.begin() as conn:
                await conn.run_sync(table.create, checkfirst=True)
            logger.info(f"Table ready: {table.name}")
        except Exception as e:
            logger.warning(f"Skipping table {table.name}: {e}")


async def get_db():
    """FastAPI dependency — yields an async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
