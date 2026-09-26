"""Health check route."""

from fastapi import APIRouter

from before_you_pay import __version__
from before_you_pay.api.schemas import HealthResponse
from before_you_pay.config import get_settings

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns current health status and version information.",
)
async def health_check() -> HealthResponse:
    """Return 200 OK with server health metadata."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=__version__,
    )
