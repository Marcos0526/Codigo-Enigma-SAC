"""
Enigma SAC API - Semantic Data Discovery & Interactive Dashboards
Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time
import uuid

from services.api.config import settings
from services.api.routes import search, datasets, summarization, visualization, health
from services.api.middleware import RequestIDMiddleware, LoggingMiddleware

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("application_starting", version=settings.APP_VERSION)
    # Initialize database connections, embedding service, etc.
    yield
    logger.info("application_shutting_down")


app = FastAPI(
    title="Enigma SAC API",
    description="Semantic Data Discovery & Interactive Dashboards for NASA PSI Combustion Science",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
    openapi_url="/openapi.json" if settings.APP_ENV == "development" else None,
    lifespan=lifespan,
)

# Middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "requestId": request_id,
                "timestamp": time.time(),
            }
        },
    )

# Routes
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(search.router, prefix="/api/v1", tags=["Search"])
app.include_router(datasets.router, prefix="/api/v1", tags=["Datasets"])
app.include_router(summarization.router, prefix="/api/v1", tags=["Summarization"])
app.include_router(visualization.router, prefix="/api/v1", tags=["Visualization"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Enigma SAC API",
        "version": settings.APP_VERSION,
        "description": "Semantic Data Discovery & Interactive Dashboards for NASA PSI Combustion Science",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "services.api.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "development",
    )