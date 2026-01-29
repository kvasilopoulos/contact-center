"""AI Classifier service for message categorization."""

from dataclasses import dataclass
import time
from typing import Literal

import structlog

from app.config import Settings
from app.services.llm_client import LLMClient, LLMClientError

logger = structlog.get_logger(__name__)

CategoryType = Literal["informational", "service_action", "safety_compliance"]


@dataclass
class ClassificationResult:
    """Result of a message classification."""

    category: CategoryType
    confidence: float
    reasoning: str
    processing_time_ms: float
    prompt_version: str = ""
    prompt_variant: str = ""
    model: str = ""


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
        experiment_id: str | None = None,
    ) -> ClassificationResult:
        """Classify a customer message into a category.

        Args:
            message: The customer message to classify.
            channel: The communication channel (chat, voice, mail).
            experiment_id: Optional experiment ID for A/B testing.

        Returns:
            ClassificationResult with category, confidence, reasoning, and prompt metadata.

        Raises:
            ClassificationError: If classification fails.
        """
        start_time = time.perf_counter()

        try:
            # Use prompt template from registry
            result, prompt_metadata = await self.llm_client.complete_with_template(
                template_id="classification",
                variables={"channel": channel, "message": message},
                experiment_id=experiment_id,
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
                    prompt_version=prompt_metadata.get("version"),
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
                prompt_version=prompt_metadata.get("version"),
                prompt_variant=prompt_metadata.get("variant"),
                model=prompt_metadata.get("model"),
            )

            return ClassificationResult(
                category=category,
                confidence=confidence,
                reasoning=reasoning,
                processing_time_ms=processing_time_ms,
                prompt_version=prompt_metadata.get("version", ""),
                prompt_variant=prompt_metadata.get("variant", ""),
                model=prompt_metadata.get("model", ""),
            )

        except LLMClientError as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Classification failed",
                error=str(e),
                processing_time_ms=round(processing_time_ms, 2),
            )
            raise ClassificationError(f"Failed to classify message: {e}") from e

    async def classify_audio(
        self,
        audio: bytes,
        channel: str = "voice",
    ) -> ClassificationResult:
        """Classify a customer voice message using the Realtime audio pathway.

        Args:
            audio: Raw audio bytes (expected to be WAV-encoded).
            channel: The communication channel, defaults to \"voice\".

        Returns:
            ClassificationResult with category, confidence, reasoning, and metadata.

        Raises:
            ClassificationError: If classification fails.
        """
        start_time = time.perf_counter()

        try:
            # Call Realtime audio classification
            result = await self.llm_client.classify_audio_realtime(
                audio=audio,
                channel=channel,
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
                    "Invalid category returned by Realtime LLM",
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
                "Audio message classified",
                category=category,
                confidence=confidence,
                channel=channel,
                processing_time_ms=round(processing_time_ms, 2),
                model=self.settings.openai_realtime_model,
            )

            return ClassificationResult(
                category=category,
                confidence=confidence,
                reasoning=reasoning,
                processing_time_ms=processing_time_ms,
                prompt_version="",
                prompt_variant="",
                model=self.settings.openai_realtime_model,
            )

        except LLMClientError as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Realtime audio classification failed",
                error=str(e),
                processing_time_ms=round(processing_time_ms, 2),
            )
            raise ClassificationError(f"Failed to classify audio message: {e}") from e

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
