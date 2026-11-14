"""RelayPoint Backend Application Entrypoint.

Configures FastAPI application, middleware, lifecycle events, and API routers.
"""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.repositories import router as repositories_router
from app.api.analysis import router as analysis_router
from app.core.config import get_settings
from app.core.database import init_db

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("relaypoint")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown initialization."""
    settings = get_settings()
    logger.info("Initializing RelayPoint (%s mode)...", settings.APP_ENV)
    try:
        # Idempotently ensure database schema and tables exist
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error("Failed to initialize database during startup: %s", exc)
        raise

    yield

    logger.info("RelayPoint service shutting down.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.API_VERSION,
        description="Automated Knowledge Handover Platform API",
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url="/redoc" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    # Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(health_router, prefix="/api")
    app.include_router(repositories_router, prefix="/api")
    app.include_router(analysis_router, prefix="/api")

    # Global Exception Handlers (Prevent internal trace and credential leakage)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled internal server error: %s", exc, exc_info=settings.APP_DEBUG)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error occurred. Please contact the administrator."},
        )

    return app


app = create_app()
