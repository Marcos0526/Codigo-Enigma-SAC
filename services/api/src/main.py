"""
Enigma SAC API - FastAPI application.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.api.src.config import settings
from services.api.src.database import init_db, close_db, get_db_session
from services.api.src.middleware.request_id import RequestIDMiddleware
from services.api.src.middleware.logging import LoggingMiddleware
from services.api.src.middleware.rate_limit import RateLimitMiddleware
from services.api.src.routes import search, datasets, summarization, visualization, health, chat
from sqlalchemy.ext.asyncio import AsyncSession

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
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    logger.info(
        "application_starting",
        version=settings.APP_VERSION,
        data_source=settings.DATA_SOURCE,
    )
    if settings.DATA_SOURCE != "local":
        await init_db()
    yield
    logger.info("application_shutting_down")
    if settings.DATA_SOURCE != "local":
        await close_db()


app = FastAPI(
    title="Enigma SAC API",
    description="Semantic Data Discovery & Interactive Dashboards for NASA PSI Combustion Science",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
    openapi_url="/openapi.json" if settings.APP_ENV == "development" else None,
    lifespan=lifespan,
)

# Middleware (order matters - outer to inner)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_RPM)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
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
            }
        },
    )

# Routes. Local mode never reads or generates synthetic datasets.
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
if settings.DATA_SOURCE == "local":
    from services.api.src.routes import local_data

    app.include_router(local_data.router, prefix="/api/v1", tags=["Local NASA PSI + RAG"])
else:
    app.include_router(search.router, prefix="/api/v1", tags=["Search"])
    app.include_router(datasets.router, prefix="/api/v1", tags=["Datasets"])
    app.include_router(summarization.router, prefix="/api/v1", tags=["Summarization"])
    app.include_router(visualization.router, prefix="/api/v1", tags=["Visualization"])
    app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])

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


# CLI entry point
import asyncio
import click
import uvicorn


@click.group()
@click.option("--database-url", envvar="DATABASE_URL", required=True, help="PostgreSQL database URL")
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", default=8000, help="Port to bind")
@click.option("--reload/--no-reload", default=False, help="Enable auto-reload")
@click.pass_context
def cli(ctx, database_url: str, host: str, port: int, reload: bool):
    """Enigma SAC API - Semantic Data Discovery & Interactive Dashboards."""
    ctx.ensure_object(dict)
    ctx.obj["database_url"] = database_url
    ctx.obj["host"] = host
    ctx.obj["port"] = port
    ctx.obj["reload"] = reload


@cli.command()
@click.pass_context
def run(ctx):
    """Run the API server."""
    uvicorn.run(
        "services.api.src.main:app",
        host=ctx.obj["host"],
        port=ctx.obj["port"],
        reload=ctx.obj["reload"],
    )


@cli.command()
@click.pass_context
def init_db_cmd(ctx):
    """Initialize database schema."""
    from services.api.src.database import init_db
    asyncio.run(init_db())
    click.echo("Database initialized")


if __name__ == "__main__":
    cli()