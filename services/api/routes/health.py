"""
Health check routes
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
import httpx
import structlog
from typing import Dict, Any

from services.api.config import settings
from services.api.database import get_db_session

router = APIRouter()
logger = structlog.get_logger()


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Comprehensive health check for all services."""
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
) -> Dict[str, Any]:
    """Kubernetes readiness probe - checks if service can handle requests."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return {"status": "not ready"}


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Kubernetes liveness probe - checks if service is alive."""
    return {"status": "alive"}