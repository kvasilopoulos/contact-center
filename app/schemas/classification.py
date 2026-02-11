"""Classification request and response schemas."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import CategoryType, ChannelType


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


class VoiceClassificationRequest(BaseModel):
    """Request model for voice message classification metadata."""

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata about the voice message context",
    )

    model_config = ConfigDict(
        title="Voice classification request (metadata only)",
        json_schema_extra={
            "examples": [
                {
                    "metadata": {
                        "customer_id": "C123",
                        "call_id": "CALL-789",
                    }
                }
            ]
        },
    )

    model_config = ConfigDict(
        title="Classification request (message + channel)",
        json_schema_extra={
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
        },
    )


class NextStepInfo(BaseModel):
    """Information about the recommended next step."""

    model_config = ConfigDict(title="Next step (action, priority, human review)")

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
        default_factory=lambda: datetime.now(timezone.utc),
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

    model_config = ConfigDict(
        title="Classification result (category, confidence, next step)",
        json_schema_extra={
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
        },
    )
