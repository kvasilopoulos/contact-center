"""Request models for the API."""

from typing import Any, Literal

from pydantic import BaseModel, Field

ChannelType = Literal["chat", "voice", "mail"]


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
