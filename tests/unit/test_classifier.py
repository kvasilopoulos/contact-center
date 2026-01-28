"""Tests for the classifier service."""

from unittest.mock import MagicMock

import pytest

from app.services.classifier import ClassificationError, ClassificationResult, ClassifierService
from app.services.llm_client import LLMClientError


class TestClassifierService:
    """Tests for the ClassifierService."""

    @pytest.mark.asyncio
    async def test_classify_informational(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
        informational_message: str,
        mock_classification_response_informational: dict,
    ) -> None:
        """Test classifying an informational message."""
        mock_llm_client.complete.return_value = mock_classification_response_informational

        result = await classifier_service.classify(informational_message)

        assert isinstance(result, ClassificationResult)
        assert result.category == "informational"
        assert result.confidence == 0.95
        assert "refund policy" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_classify_service_action(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
        service_action_message: str,
        mock_classification_response_service_action: dict,
    ) -> None:
        """Test classifying a service action message."""
        mock_llm_client.complete.return_value = mock_classification_response_service_action

        result = await classifier_service.classify(service_action_message)

        assert result.category == "service_action"
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_classify_safety_compliance(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
        safety_compliance_message: str,
        mock_classification_response_safety: dict,
    ) -> None:
        """Test classifying a safety compliance message."""
        mock_llm_client.complete.return_value = mock_classification_response_safety

        result = await classifier_service.classify(safety_compliance_message)

        assert result.category == "safety_compliance"
        assert result.confidence == 0.98

    @pytest.mark.asyncio
    async def test_classify_with_channel(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
        mock_classification_response_informational: dict,
    ) -> None:
        """Test classification includes channel in prompt."""
        mock_llm_client.complete.return_value = mock_classification_response_informational

        await classifier_service.classify("Test message", channel="voice")

        # Verify channel was included in the prompt
        call_args = mock_llm_client.complete.call_args
        user_prompt = call_args.kwargs.get("user_prompt", call_args.args[1] if len(call_args.args) > 1 else "")
        assert "VOICE" in user_prompt.upper()

    @pytest.mark.asyncio
    async def test_classify_invalid_category_defaults(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test that invalid category from LLM defaults to service_action."""
        mock_llm_client.complete.return_value = {
            "category": "invalid_category",
            "confidence": 0.9,
            "reasoning": "Test",
        }

        result = await classifier_service.classify("Test message")

        # Should default to service_action with low confidence
        assert result.category == "service_action"
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_classify_confidence_clamped(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test that confidence is clamped to valid range."""
        # Test above 1.0
        mock_llm_client.complete.return_value = {
            "category": "informational",
            "confidence": 1.5,
            "reasoning": "Test",
        }
        result = await classifier_service.classify("Test")
        assert result.confidence == 1.0

        # Test below 0.0
        mock_llm_client.complete.return_value = {
            "category": "informational",
            "confidence": -0.5,
            "reasoning": "Test",
        }
        result = await classifier_service.classify("Test")
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_classify_llm_error_raises(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
    ) -> None:
        """Test that LLM errors are properly propagated."""
        mock_llm_client.complete.side_effect = LLMClientError("API error")

        with pytest.raises(ClassificationError) as exc_info:
            await classifier_service.classify("Test message")

        assert "Failed to classify message" in str(exc_info.value)

    def test_get_confidence_level(
        self,
        classifier_service: ClassifierService,
    ) -> None:
        """Test confidence level descriptions."""
        assert classifier_service.get_confidence_level(0.95) == "high"
        assert classifier_service.get_confidence_level(0.9) == "high"
        assert classifier_service.get_confidence_level(0.8) == "moderate"
        assert classifier_service.get_confidence_level(0.7) == "moderate"
        assert classifier_service.get_confidence_level(0.6) == "low"
        assert classifier_service.get_confidence_level(0.5) == "low"
        assert classifier_service.get_confidence_level(0.4) == "very_low"
        assert classifier_service.get_confidence_level(0.0) == "very_low"

    def test_requires_human_review(
        self,
        classifier_service: ClassifierService,
    ) -> None:
        """Test human review threshold."""
        # Threshold is 0.5
        assert classifier_service.requires_human_review(0.4) is True
        assert classifier_service.requires_human_review(0.49) is True
        assert classifier_service.requires_human_review(0.5) is False
        assert classifier_service.requires_human_review(0.9) is False

    @pytest.mark.asyncio
    async def test_classify_processing_time_tracked(
        self,
        classifier_service: ClassifierService,
        mock_llm_client: MagicMock,
        mock_classification_response_informational: dict,
    ) -> None:
        """Test that processing time is tracked."""
        mock_llm_client.complete.return_value = mock_classification_response_informational

        result = await classifier_service.classify("Test message")

        assert result.processing_time_ms > 0
