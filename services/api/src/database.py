"""Database connection and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from services.api.src.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=5,
    pool_pre_ping=True,
    poolclass=NullPool if settings.APP_ENV == "test" else None,
    echo=settings.APP_ENV == "development",
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[asyncpg.Connection, None]:
    """Context manager for raw asyncpg connections (for pgvector operations)."""
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        yield conn
    finally:
        await conn.close()


from sqlalchemy import text

async def init_db() -> None:
    """Initialize database connection and verify."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("Database connected successfully")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
    print("Database connections closed")