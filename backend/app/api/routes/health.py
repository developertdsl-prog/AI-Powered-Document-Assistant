"""Health-check route."""

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health", summary="Service health check")
def health_check() -> dict[str, str]:
    """Report that the API process is running."""

    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
