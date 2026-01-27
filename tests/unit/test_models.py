"""Tests for request and response models."""

from pydantic import ValidationError
import pytest

from orchestrator.models import (
    ClassificationRequest,
    ClassificationResponse,
    HealthResponse,
    NextStepInfo,
)


class TestClassificationRequest:
    """Tests for ClassificationRequest model."""

    def test_valid_request_minimal(self) -> None:
        """Test creating a request with minimal required fields."""
        request = ClassificationRequest(message="What is your refund policy?")
        assert request.message == "What is your refund policy?"
        assert request.channel == "chat"  # default
        assert request.metadata == {}  # default

    def test_valid_request_full(self) -> None:
        """Test creating a request with all fields."""
        request = ClassificationRequest(
            message="I need help with my order",
            channel="voice",
            metadata={"customer_id": "C123", "order_id": "ORD-456"},
        )
        assert request.message == "I need help with my order"
        assert request.channel == "voice"
        assert request.metadata["customer_id"] == "C123"

    def test_valid_channels(self) -> None:
        """Test all valid channel types."""
        for channel in ["chat", "voice", "mail"]:
            request = ClassificationRequest(message="Test", channel=channel)  # type: ignore[arg-type]
            assert request.channel == channel

    def test_invalid_channel(self) -> None:
        """Test that invalid channel raises error."""
        with pytest.raises(ValidationError):
            ClassificationRequest(message="Test", channel="invalid")  # type: ignore[arg-type]

    def test_empty_message_rejected(self) -> None:
        """Test that empty message is rejected."""
        with pytest.raises(ValidationError):
            ClassificationRequest(message="")

    def test_message_too_long_rejected(self) -> None:
        """Test that overly long message is rejected."""
        with pytest.raises(ValidationError):
            ClassificationRequest(message="x" * 5001)

    def test_message_at_max_length(self) -> None:
        """Test that message at max length is accepted."""
        request = ClassificationRequest(message="x" * 5000)
        assert len(request.message) == 5000


class TestClassificationResponse:
    """Tests for ClassificationResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid response."""
        response = ClassificationResponse(
            request_id="req_123",
            category="informational",
            confidence=0.95,
            decision_path="Customer asking about policy",
            next_step=NextStepInfo(
                action="provide_information",
                description="Provide policy details",
                priority="low",
            ),
            processing_time_ms=150.5,
        )
        assert response.request_id == "req_123"
        assert response.category == "informational"
        assert response.confidence == 0.95

    def test_valid_categories(self) -> None:
        """Test all valid category types."""
        for category in ["informational", "service_action", "safety_compliance"]:
            response = ClassificationResponse(
                request_id="req_123",
                category=category,  # type: ignore[arg-type]
                confidence=0.9,
                decision_path="Test",
                next_step=NextStepInfo(
                    action="test",
                    description="test",
                    priority="medium",
                ),
                processing_time_ms=100,
            )
            assert response.category == category

    def test_confidence_bounds(self) -> None:
        """Test confidence must be between 0 and 1."""
        # Valid bounds
        for conf in [0.0, 0.5, 1.0]:
            response = ClassificationResponse(
                request_id="req_123",
                category="informational",
                confidence=conf,
                decision_path="Test",
                next_step=NextStepInfo(
                    action="test",
                    description="test",
                    priority="medium",
                ),
                processing_time_ms=100,
            )
            assert response.confidence == conf

        # Invalid: below 0
        with pytest.raises(ValidationError):
            ClassificationResponse(
                request_id="req_123",
                category="informational",
                confidence=-0.1,
                decision_path="Test",
                next_step=NextStepInfo(
                    action="test",
                    description="test",
                    priority="medium",
                ),
                processing_time_ms=100,
            )

        # Invalid: above 1
        with pytest.raises(ValidationError):
            ClassificationResponse(
                request_id="req_123",
                category="informational",
                confidence=1.1,
                decision_path="Test",
                next_step=NextStepInfo(
                    action="test",
                    description="test",
                    priority="medium",
                ),
                processing_time_ms=100,
            )


class TestNextStepInfo:
    """Tests for NextStepInfo model."""

    def test_valid_next_step(self) -> None:
        """Test creating a valid next step."""
        next_step = NextStepInfo(
            action="create_ticket",
            description="Creating a support ticket",
            priority="high",
            requires_human_review=True,
            external_system="ticketing_system",
        )
        assert next_step.action == "create_ticket"
        assert next_step.priority == "high"
        assert next_step.requires_human_review is True
        assert next_step.external_system == "ticketing_system"

    def test_valid_priorities(self) -> None:
        """Test all valid priority levels."""
        for priority in ["low", "medium", "high", "urgent"]:
            next_step = NextStepInfo(
                action="test",
                description="test",
                priority=priority,  # type: ignore[arg-type]
            )
            assert next_step.priority == priority

    def test_defaults(self) -> None:
        """Test default values."""
        next_step = NextStepInfo(
            action="test",
            description="test",
            priority="medium",
        )
        assert next_step.requires_human_review is False
        assert next_step.external_system is None


class TestHealthResponse:
    """Tests for HealthResponse model."""

    def test_valid_health_response(self) -> None:
        """Test creating a valid health response."""
        response = HealthResponse(
            status="healthy",
            version="0.1.0",
            environment="development",
            checks={"api": True, "database": True},
        )
        assert response.status == "healthy"
        assert response.version == "0.1.0"
        assert response.checks["api"] is True

    def test_valid_statuses(self) -> None:
        """Test all valid status values."""
        for status in ["healthy", "degraded", "unhealthy"]:
            response = HealthResponse(
                status=status,  # type: ignore[arg-type]
                version="0.1.0",
                environment="development",
            )
            assert response.status == status
