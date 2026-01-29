"""Application data models and schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# Type aliases
ChannelType = Literal["chat", "voice", "mail"]
CategoryType = Literal["informational", "service_action", "safety_compliance"]


# ============================================================================
# Request Models
# ============================================================================


class ClassificationRequest(BaseModel):
    """Request model for message classification."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The customer message to classify",
        examples=["What is your refund policy for prescription products?"],
    )
    channel: ChannelType = Field(
        default="chat",
        description="The communication channel the message originated from",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata about the message context",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "What is your refund policy for prescription products?",
                    "channel": "chat",
                    "metadata": {"customer_id": "C123"},
                },
                {
                    "message": "I need to open a ticket because my order never arrived.",
                    "channel": "mail",
                    "metadata": {"order_id": "ORD-456"},
                },
                {
                    "message": "I experienced a severe headache after taking the medication.",
                    "channel": "voice",
                    "metadata": {"product_id": "MED-789"},
                },
            ]
        }
    }


# ============================================================================
# Response Models
# ============================================================================


class NextStepInfo(BaseModel):
    """Information about the recommended next step."""

    action: str = Field(
        ...,
        description="The recommended action to take",
    )
    description: str = Field(
        ...,
        description="Detailed description of the next step",
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="medium",
        description="Priority level of the action",
    )
    requires_human_review: bool = Field(
        default=False,
        description="Whether this requires human agent review",
    )
    external_system: str | None = Field(
        default=None,
        description="External system to integrate with, if any",
    )


class ClassificationResponse(BaseModel):
    """Response model for message classification."""

    request_id: str = Field(
        ...,
        description="Unique identifier for this request",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the classification",
    )
    category: CategoryType = Field(
        ...,
        description="The classified category of the message",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the classification (0.0 to 1.0)",
    )
    decision_path: str = Field(
        ...,
        description="Explanation of the classification reasoning",
    )
    next_step: NextStepInfo = Field(
        ...,
        description="Recommended next step based on the classification",
    )
    processing_time_ms: float = Field(
        ...,
        description="Time taken to process the request in milliseconds",
    )
    prompt_version: str = Field(
        default="",
        description="Version of the prompt template used for classification",
    )
    prompt_variant: str = Field(
        default="",
        description="Variant of the prompt (for A/B testing)",
    )
    model: str = Field(
        default="",
        description="LLM model used for classification",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request_id": "req_abc123",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "category": "informational",
                    "confidence": 0.95,
                    "decision_path": "Message asks about refund policy - classified as informational inquiry",
                    "next_step": {
                        "action": "provide_information",
                        "description": "Provide refund policy details from knowledge base",
                        "priority": "medium",
                        "requires_human_review": False,
                        "external_system": None,
                    },
                    "processing_time_ms": 245.5,
                    "prompt_version": "1.0.0",
                    "prompt_variant": "active",
                    "model": "gpt-4.1",
                }
            ]
        }
    }


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


__all__ = [
    "CategoryType",
    "ChannelType",
    "ClassificationRequest",
    "ClassificationResponse",
    "ErrorResponse",
    "HealthResponse",
    "NextStepInfo",
]
