"""Tests for the classifier service."""

from unittest.mock import MagicMock

import pytest

from app.schemas.llm_responses import ClassificationLLMResponse
from app.services.classification import ClassificationError, ClassificationResult, Classifier
from app.services.llm import LLMClientError, LLMParseError


class TestClassifier:
    """Tests for the Classifier."""

    @pytest.mark.asyncio
    async def test_classify_informational(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
        informational_message: str,
        mock_classification_response_informational: ClassificationLLMResponse,
    ) -> None:
        """Test classifying an informational message."""
        mock_llm_client.classify_text.return_value = (
            mock_classification_response_informational,
            {
                "prompt_id": "classification",
                "version": "1.0.0",
                "variant": "active",
                "model": "gpt-4.1",
            },
        )

        result = await classifier.classify(informational_message)

        assert isinstance(result, ClassificationResult)
        assert result.category == "informational"
        assert result.confidence == 0.95
        assert "refund policy" in result.reasoning.lower()
        assert result.prompt_version == "1.0.0"
        assert result.prompt_variant == "active"

    @pytest.mark.asyncio
    async def test_classify_service_action(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
        service_action_message: str,
        mock_classification_response_service_action: ClassificationLLMResponse,
    ) -> None:
        """Test classifying a service action message."""
        mock_llm_client.classify_text.return_value = (
            mock_classification_response_service_action,
            {
                "prompt_id": "classification",
                "version": "1.0.0",
                "variant": "active",
                "model": "gpt-4.1",
            },
        )

        result = await classifier.classify(service_action_message)

        assert result.category == "service_action"
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_classify_safety_compliance(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
        safety_compliance_message: str,
        mock_classification_response_safety: ClassificationLLMResponse,
    ) -> None:
        """Test classifying a safety compliance message."""
        mock_llm_client.classify_text.return_value = (
            mock_classification_response_safety,
            {
                "prompt_id": "classification",
                "version": "1.0.0",
                "variant": "active",
                "model": "gpt-4.1",
            },
        )

        result = await classifier.classify(safety_compliance_message)

        assert result.category == "safety_compliance"
        assert result.confidence == 0.98

    @pytest.mark.asyncio
    async def test_classify_with_channel(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
        mock_classification_response_informational: ClassificationLLMResponse,
    ) -> None:
        """Test classification includes channel in prompt."""
        mock_llm_client.classify_text.return_value = (
            mock_classification_response_informational,
            {
                "prompt_id": "classification",
                "version": "1.0.0",
                "variant": "active",
                "model": "gpt-4.1",
            },
        )

        await classifier.classify("Test message", channel="voice")

        # Verify the template was called with correct variables
        call_args = mock_llm_client.classify_text.call_args
        variables = call_args.kwargs.get("variables", {})
        assert variables.get("channel") == "voice"
        assert variables.get("message") == "Test message"

    @pytest.mark.asyncio
    async def test_classify_parse_error_defaults(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test that parse error defaults to service_action with low confidence."""
        mock_llm_client.classify_text.side_effect = LLMParseError(
            "Failed to parse LLM response"
        )

        result = await classifier.classify("Test message")

        # Should default to service_action with low confidence
        assert result.category == "service_action"
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_classify_confidence_preserved(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test that confidence from valid response is preserved."""
        metadata = {
            "prompt_id": "classification",
            "version": "1.0.0",
            "variant": "active",
            "model": "gpt-4",
        }

        # With Pydantic validation, confidence is already bounded by the model
        # Test boundary values
        mock_llm_client.classify_text.return_value = (
            ClassificationLLMResponse(
                category="informational",
                confidence=1.0,
                reasoning="Test high confidence",
            ),
            metadata,
        )
        result = await classifier.classify("Test")
        assert result.confidence == 1.0

        mock_llm_client.classify_text.return_value = (
            ClassificationLLMResponse(
                category="informational",
                confidence=0.0,
                reasoning="Test low confidence",
            ),
            metadata,
        )
        result = await classifier.classify("Test")
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_classify_llm_error_raises(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test that LLM errors are properly propagated."""
        mock_llm_client.classify_text.side_effect = LLMClientError("API error")

        with pytest.raises(ClassificationError) as exc_info:
            await classifier.classify("Test message")

        assert "Failed to classify message" in str(exc_info.value)

    def test_requires_human_review(
        self,
        classifier: Classifier,
    ) -> None:
        """Test human review threshold."""
        # Threshold is 0.5
        assert classifier.requires_human_review(0.4) is True
        assert classifier.requires_human_review(0.49) is True
        assert classifier.requires_human_review(0.5) is False
        assert classifier.requires_human_review(0.9) is False

    @pytest.mark.asyncio
    async def test_classify_processing_time_tracked(
        self,
        classifier: Classifier,
        mock_llm_client: MagicMock,
        mock_classification_response_informational: ClassificationLLMResponse,
    ) -> None:
        """Test that processing time is tracked."""
        mock_llm_client.classify_text.return_value = (
            mock_classification_response_informational,
            {
                "prompt_id": "classification",
                "version": "1.0.0",
                "variant": "active",
                "model": "gpt-4.1",
            },
        )

        result = await classifier.classify("Test message")

        assert result.processing_time_ms > 0
