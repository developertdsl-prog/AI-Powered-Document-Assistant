"""Health-check route."""

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.schemas.health import HealthResponse
from app.services.health import check_database

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service and database health check",
    responses={
        503: {
            "model": HealthResponse,
            "description": "The API is running but the database is unavailable.",
        }
    },
)
def health_check(response: Response) -> HealthResponse:
    """Report API status and verify database connectivity."""

    settings = get_settings()
    database_up = check_database()

    if not database_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="ok" if database_up else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database="up" if database_up else "down",
    )
