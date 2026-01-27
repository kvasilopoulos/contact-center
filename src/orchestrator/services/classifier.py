"""AI Classifier service for message categorization."""

from dataclasses import dataclass
import time
from typing import Literal

import structlog

from orchestrator.config import Settings
from orchestrator.services.llm_client import LLMClient, LLMClientError

logger = structlog.get_logger(__name__)

CategoryType = Literal["informational", "service_action", "safety_compliance"]

CLASSIFICATION_SYSTEM_PROMPT = """You are a customer service classifier for a pharmacy/healthcare contact center.

Your task is to classify customer messages into exactly ONE of three categories.

CATEGORIES:

1. **informational** - Questions seeking information about:
   - Policies (refund, shipping, privacy, etc.)
   - Product details or availability
   - General inquiries and FAQs
   - Account information requests
   - Store hours, locations, contact info

2. **service_action** - Requests that require taking an action:
   - Opening support tickets
   - Tracking or modifying orders
   - Processing refunds or returns
   - Account changes (password reset, profile updates)
   - Scheduling appointments
   - Cancellations

3. **safety_compliance** - Health and safety concerns that require special handling:
   - Adverse reactions to medications
   - Side effects or allergic reactions
   - Medical emergencies
   - Product quality or contamination concerns
   - Drug interactions or safety questions
   - Any message mentioning physical symptoms after using a product

IMPORTANT RULES:
- safety_compliance takes priority if ANY health/safety concern is mentioned
- Be conservative: if unsure between categories, prefer lower confidence
- Consider the primary intent of the message

Respond ONLY with a JSON object in this exact format:
{
    "category": "<category_name>",
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation of why this category was chosen>"
}"""


@dataclass
class ClassificationResult:
    """Result of a message classification."""

    category: CategoryType
    confidence: float
    reasoning: str
    processing_time_ms: float


class ClassifierService:
    """Service for classifying customer messages using AI."""

    def __init__(self, settings: Settings, llm_client: LLMClient | None = None) -> None:
        """Initialize the classifier service.

        Args:
            settings: Application settings.
            llm_client: Optional LLM client instance. Created if not provided.
        """
        self.settings = settings
        self.llm_client = llm_client or LLMClient(settings)

    async def classify(
        self,
        message: str,
        channel: str = "chat",
    ) -> ClassificationResult:
        """Classify a customer message into a category.

        Args:
            message: The customer message to classify.
            channel: The communication channel (chat, voice, mail).

        Returns:
            ClassificationResult with category, confidence, and reasoning.

        Raises:
            ClassificationError: If classification fails.
        """
        start_time = time.perf_counter()

        # Build the user prompt with context
        user_prompt = f"CHANNEL: {channel}\n\nCUSTOMER MESSAGE:\n{message}"

        try:
            result = await self.llm_client.complete(
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.0,  # Deterministic for classification
                max_tokens=200,
            )

            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Validate and extract result
            category = result.get("category", "").lower()
            confidence = float(result.get("confidence", 0.0))
            reasoning = result.get("reasoning", "No reasoning provided")

            # Validate category
            valid_categories = {"informational", "service_action", "safety_compliance"}
            if category not in valid_categories:
                logger.warning(
                    "Invalid category returned by LLM",
                    category=category,
                    valid_categories=list(valid_categories),
                )
                # Default to service_action with low confidence for unknown categories
                category = "service_action"
                confidence = 0.3
                reasoning = (
                    f"Original category '{category}' was invalid, defaulting to service_action"
                )

            # Clamp confidence to valid range
            confidence = max(0.0, min(1.0, confidence))

            logger.info(
                "Message classified",
                category=category,
                confidence=confidence,
                channel=channel,
                processing_time_ms=round(processing_time_ms, 2),
            )

            return ClassificationResult(
                category=category,
                confidence=confidence,
                reasoning=reasoning,
                processing_time_ms=processing_time_ms,
            )

        except LLMClientError as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Classification failed",
                error=str(e),
                processing_time_ms=round(processing_time_ms, 2),
            )
            raise ClassificationError(f"Failed to classify message: {e}") from e

    def get_confidence_level(self, confidence: float) -> str:
        """Get a human-readable confidence level.

        Args:
            confidence: Confidence score between 0 and 1.

        Returns:
            String describing the confidence level.
        """
        if confidence >= 0.9:
            return "high"
        elif confidence >= 0.7:
            return "moderate"
        elif confidence >= 0.5:
            return "low"
        else:
            return "very_low"

    def requires_human_review(self, confidence: float) -> bool:
        """Determine if the classification requires human review.

        Args:
            confidence: Confidence score between 0 and 1.

        Returns:
            True if human review is recommended.
        """
        return confidence < self.settings.min_confidence_threshold


class ClassificationError(Exception):
    """Exception raised when classification fails."""

    pass
