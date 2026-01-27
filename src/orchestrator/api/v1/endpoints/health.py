"""Health check endpoints."""

from fastapi import APIRouter, Depends

from orchestrator.config import Settings, get_settings
from orchestrator.models import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Basic liveness check - returns healthy if the service is running",
)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Basic health check endpoint for liveness probes."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.environment,
        checks={"api": True},
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness Check",
    description="Readiness check - verifies all dependencies are available",
)
async def readiness_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Readiness check endpoint that verifies dependencies.

    Checks:
    - API is running
    - OpenAI API key is configured
    """
    checks = {
        "api": True,
        "openai_configured": bool(settings.openai_api_key.get_secret_value()),
    }

    all_healthy = all(checks.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        checks=checks,
    )
