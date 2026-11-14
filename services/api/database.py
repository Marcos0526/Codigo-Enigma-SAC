"""
Database connection and session management
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
import structlog

from services.api.config import settings

logger = structlog.get_logger()

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


async def get_db_session() -> AsyncSession:
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
async def get_db_context():
    """Context manager for database sessions outside of FastAPI."""
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database connection and verify."""
    try:
        async with engine.begin() as conn:
            await conn.execute("SELECT 1")
        logger.info("database_connected", url=settings.DATABASE_URL.split("@")[1] if "@" in settings.DATABASE_URL else "hidden")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise


async def close_db():
    """Close database connections."""
    await engine.dispose()
    logger.info("database_disconnected")