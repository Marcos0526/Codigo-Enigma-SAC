"""Health check routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
import httpx
import structlog

from services.search.src.embedding.http_client import embed_text
from services.api.src.config import settings
from services.api.src.database import get_db_session

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Comprehensive health check for all services."""
    if settings.DATA_SOURCE == "local":
        try:
            from services.api.src.routes.local_data import get_catalog

            catalog = get_catalog()
            services = {
                "local_data": {
                    "status": "healthy",
                    "path": settings.PSI_DATA_DIR,
                    "investigations": catalog.investigation_count,
                    "files": len(catalog),
                },
                "rag": {
                    "status": "lazy",
                    "model": settings.NASA_RAG_EMBEDDING_MODEL,
                    "retriever": "FAISS",
                },
            }
            return {"status": "healthy", "version": settings.APP_VERSION, "services": services}
        except Exception as e:
            return {
                "status": "unhealthy",
                "version": settings.APP_VERSION,
                "services": {"local_data": {"status": "unhealthy", "details": {"error": str(e)}}},
            }

    services = {}
    overall_status = "healthy"

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        services["database"] = {"status": "healthy"}
    except Exception as e:
        services["database"] = {"status": "unhealthy", "details": {"error": str(e)}}
        overall_status = "unhealthy"

    # Check Redis
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        services["redis"] = {"status": "healthy"}
    except Exception as e:
        services["redis"] = {"status": "unhealthy", "details": {"error": str(e)}}
        overall_status = "degraded" if overall_status == "healthy" else "unhealthy"

    # Check embedding service
    try:
        if settings.EMBEDDING_PROVIDER.lower() == "nvidia":
            await embed_text("health check", settings, input_type="query")
            services["embedding"] = {"status": "healthy", "provider": "nvidia", "model": settings.EMBEDDING_MODEL}
        else:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.EMBEDDING_API_URL.replace('/embed', '')}/health")
                if response.status_code == 200:
                    services["embedding"] = {"status": "healthy"}
                else:
                    services["embedding"] = {"status": "degraded", "details": {"status_code": response.status_code}}
                    overall_status = "degraded" if overall_status == "healthy" else overall_status
    except Exception as e:
        services["embedding"] = {"status": "unhealthy", "details": {"error": str(e)}}
        overall_status = "degraded" if overall_status == "healthy" else "unhealthy"

    return {
        "status": overall_status,
        "version": settings.APP_VERSION,
        "services": services,
    }


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Kubernetes readiness probe - checks if service can handle requests."""
    if settings.DATA_SOURCE == "local":
        from pathlib import Path

        return {
            "status": "ready" if Path(settings.PSI_DATA_DIR).is_dir() else "not ready",
            "source": settings.PSI_DATA_DIR,
        }
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return {"status": "not ready"}


@router.get("/health/live")
async def liveness_check() -> dict:
    """Kubernetes liveness probe - checks if service is alive."""
    return {"status": "alive"}