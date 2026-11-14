"""Health Check and Diagnostic Endpoints."""

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import check_db_health

router = APIRouter(prefix="/health", tags=["Health"])


class HealthResponse(BaseModel):
    """Safe public health diagnostic schema."""
    status: str
    app_name: str
    version: str
    database: str


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health Probe",
    description="Returns high-level application and database connectivity status without exposing sensitive paths or credentials.",
)
def get_health() -> HealthResponse:
    """Perform health and connectivity checks."""
    settings = get_settings()
    db_result = check_db_health()

    is_db_ok = db_result.get("status") == "connected"
    overall_status = "healthy" if is_db_ok else "degraded"
    db_status = "connected" if is_db_ok else "disconnected"

    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        version=settings.API_VERSION,
        database=db_status,
    )
