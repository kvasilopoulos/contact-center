"""Common types and error response schema."""

from typing import Any, Literal

from pydantic import BaseModel, Field

ChannelType = Literal["chat", "voice", "mail"]
CategoryType = Literal["informational", "service_action", "safety_compliance"]


class ErrorResponse(BaseModel):
    """Response model for API errors."""

    error: str = Field(
        ...,
        description="Error type",
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    request_id: str | None = Field(
        default=None,
        description="Request ID if available",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
    )
