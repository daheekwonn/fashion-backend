"""
db/session.py — Async SQLAlchemy engine + session factory
"""
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
    """Create all tables on startup (dev convenience)."""
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        except Exception as e:
            if "already exists" in str(e):
                logger.warning("Schema already exists (partial deploy), skipping: %s", e)
            else:
                raise


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
