"""Health check response schema."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Overall health status of the service",
    )
    version: str = Field(
        ...,
        description="Application version",
    )
    environment: str = Field(
        ...,
        description="Current environment (development, staging, production)",
    )
    checks: dict[str, bool] = Field(
        default_factory=dict,
        description="Individual component health checks",
    )
