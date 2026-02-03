"""Pydantic models for LLM structured output responses.

These models are used with OpenAI's beta.chat.completions.parse() method
for automatic validation of LLM responses.
"""

from pydantic import BaseModel, Field

from app.schemas.common import CategoryType


class ClassificationLLMResponse(BaseModel):
    """LLM response model for message classification.

    This model is used with OpenAI structured outputs to ensure
    the LLM returns a valid classification response. The CategoryType
    Literal type automatically validates the category value.
    """

    category: CategoryType = Field(
        ...,
        description="The classified category of the message",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
    )
    reasoning: str = Field(
        ...,
        max_length=500,
        description="Brief justification for the classification",
    )
