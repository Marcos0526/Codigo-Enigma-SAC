"""Compatibility entry point for the canonical API in services.api.src.

Keep existing uvicorn and Docker commands on the same routes as development.
"""

from services.api.src.main import app


if __name__ == "__main__":
    import uvicorn
    from services.api.src.config import settings

    uvicorn.run(
        "services.api.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "development",
    )
