"""AI Classifier for message categorization."""

from dataclasses import dataclass
import logging
import time

from app.core import Settings
from app.schemas import CategoryType
from app.schemas.llm_responses import ClassificationLLMResponse
from app.services.llm import LLMClient, LLMClientError, LLMParseError, LLMRefusalError
from app.utils.pii_redaction import redact_pii

logger = logging.getLogger(__name__)


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


class Classifier:
    """Classifies customer messages using AI."""

    def __init__(self, settings: Settings, llm_client: LLMClient | None = None) -> None:
        self.settings = settings
        self.llm_client = llm_client or LLMClient(settings)

    async def classify(
        self,
        message: str,
        channel: str = "chat",
        experiment_id: str | None = None,
    ) -> ClassificationResult:
        """Classify a customer message into a category.

        Uses OpenAI structured outputs for automatic validation.
        The Pydantic model ensures category is one of the valid types.

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
            # Use structured output parsing - validation is automatic via Pydantic model
            result, prompt_metadata = await self.llm_client.classify_text(
                template_id="classification",
                variables={"channel": channel, "message": message},
                response_model=ClassificationLLMResponse,
                experiment_id=experiment_id,
            )

            processing_time_ms = (time.perf_counter() - start_time) * 1000

            # Confidence clamping (defensive - model should respect constraints)
            confidence = max(0.0, min(1.0, result.confidence))

            logger.info(
                "Message classified",
                extra={
                    "category": result.category,
                    "confidence": confidence,
                    "channel": channel,
                    "processing_time_ms": round(processing_time_ms, 2),
                    "prompt_version": prompt_metadata.get("version"),
                    "prompt_variant": prompt_metadata.get("variant"),
                    "model": prompt_metadata.get("model"),
                    "message_preview": redact_pii(message[:100])
                    if len(message) > 100
                    else redact_pii(message),
                },
            )

            return ClassificationResult(
                category=result.category,
                confidence=confidence,
                reasoning=result.reasoning,
                processing_time_ms=processing_time_ms,
                prompt_version=prompt_metadata.get("version", ""),
                prompt_variant=prompt_metadata.get("variant", ""),
                model=prompt_metadata.get("model", ""),
            )

        except (LLMParseError, LLMRefusalError) as e:
            # Structured output failed - return safe default
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "Structured output parsing failed, using fallback",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "processing_time_ms": round(processing_time_ms, 2),
                },
            )
            return ClassificationResult(
                category="service_action",
                confidence=0.3,
                reasoning=f"Classification failed: {e}. Defaulting to service_action.",
                processing_time_ms=processing_time_ms,
            )

        except LLMClientError as e:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Classification failed",
                extra={
                    "error": str(e),
                    "processing_time_ms": round(processing_time_ms, 2),
                },
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
            # Call audio classification via Realtime API
            result, prompt_metadata = await self.llm_client.classify_audio(
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
                    extra={
                        "category": category,
                        "valid_categories": list(valid_categories),
                        "prompt_id": prompt_metadata.get("prompt_id"),
                        "prompt_version": prompt_metadata.get("version"),
                    },
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
                extra={
                    "category": category,
                    "confidence": confidence,
                    "channel": channel,
                    "processing_time_ms": round(processing_time_ms, 2),
                    "prompt_id": prompt_metadata.get("prompt_id"),
                    "prompt_version": prompt_metadata.get("version"),
                    "model": prompt_metadata.get("model"),
                },
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
                "Realtime audio classification failed",
                extra={
                    "error": str(e),
                    "processing_time_ms": round(processing_time_ms, 2),
                },
            )
            raise ClassificationError(f"Failed to classify audio message: {e}") from e

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
