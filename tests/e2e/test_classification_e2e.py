"""End-to-end tests for the classification flow.

These tests can optionally use real LLM calls when OPENAI_API_KEY is set
and E2E_REAL_LLM=true environment variable is present.
"""

import os
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.services.classification import ClassificationResult

# Skip real LLM tests unless explicitly enabled
USE_REAL_LLM = os.getenv("E2E_REAL_LLM", "false").lower() == "true"


@pytest.fixture
def e2e_client() -> TestClient:
    """Create a test client for E2E tests."""
    return TestClient(app)


class TestClassificationE2E:
    """End-to-end tests for the full classification flow."""

    @pytest.mark.skipif(not USE_REAL_LLM, reason="Real LLM tests disabled")
    def test_real_informational_classification(self, e2e_client: TestClient) -> None:
        """Test real classification of informational message."""
        response = e2e_client.post(
            "/api/v1/classify",
            json={"message": "What is your refund policy for prescription products?"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "informational"
        assert data["confidence"] >= 0.7

    @pytest.mark.skipif(not USE_REAL_LLM, reason="Real LLM tests disabled")
    def test_real_service_action_classification(self, e2e_client: TestClient) -> None:
        """Test real classification of service action message."""
        response = e2e_client.post(
            "/api/v1/classify",
            json={"message": "I need to open a ticket because my order never arrived."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "service_action"
        assert data["confidence"] >= 0.7

    @pytest.mark.skipif(not USE_REAL_LLM, reason="Real LLM tests disabled")
    def test_real_safety_compliance_classification(self, e2e_client: TestClient) -> None:
        """Test real classification of safety compliance message."""
        response = e2e_client.post(
            "/api/v1/classify",
            json={
                "message": "I experienced a severe headache and nausea right after taking the medication."
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "safety_compliance"
        assert data["confidence"] >= 0.7

    def test_full_flow_with_mock(self, e2e_client: TestClient) -> None:
        """Test full classification flow with mocked LLM."""
        mock_result = ClassificationResult(
            category="informational",
            confidence=0.95,
            reasoning="Customer asking about policy",
            processing_time_ms=100.0,
        )

        with patch("app.api.v1.endpoints.classify.Classifier") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_result)
            mock_instance.requires_human_review = lambda x: x < 0.5

            response = e2e_client.post(
                "/api/v1/classify",
                json={
                    "message": "What is your return policy?",
                    "channel": "chat",
                    "metadata": {"customer_id": "C123"},
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Verify full response structure
        assert "request_id" in data
        assert "timestamp" in data
        assert data["category"] == "informational"
        assert data["confidence"] == 0.95
        assert "decision_path" in data
        assert "next_step" in data
        assert "processing_time_ms" in data

        # Verify next_step structure
        next_step = data["next_step"]
        assert "action" in next_step
        assert "description" in next_step
        assert "priority" in next_step
        assert "requires_human_review" in next_step

    def test_workflow_integration_informational(self, e2e_client: TestClient) -> None:
        """Test that informational workflow is properly integrated."""
        mock_result = ClassificationResult(
            category="informational",
            confidence=0.9,
            reasoning="FAQ question about refunds",
            processing_time_ms=150.0,
        )

        with patch("app.api.v1.endpoints.classify.Classifier") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_result)
            mock_instance.requires_human_review = lambda x: x < 0.5

            response = e2e_client.post(
                "/api/v1/classify",
                json={"message": "What is your refund policy?"},
            )

        assert response.status_code == 200
        data = response.json()
        # Should match FAQ and return info
        assert data["next_step"]["action"] == "provide_information"
        assert "refund" in data["next_step"]["description"].lower()

    def test_workflow_integration_service_action(self, e2e_client: TestClient) -> None:
        """Test that service action workflow is properly integrated."""
        mock_result = ClassificationResult(
            category="service_action",
            confidence=0.92,
            reasoning="Customer wants to open a ticket",
            processing_time_ms=120.0,
        )

        with patch("app.api.v1.endpoints.classify.Classifier") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_result)
            mock_instance.requires_human_review = lambda x: x < 0.5

            response = e2e_client.post(
                "/api/v1/classify",
                json={"message": "I need to open a support ticket"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["next_step"]["action"] == "create_ticket"
        assert data["next_step"]["external_system"] == "ticketing_system"

    def test_workflow_integration_safety_compliance(self, e2e_client: TestClient) -> None:
        """Test that safety compliance workflow is properly integrated."""
        mock_result = ClassificationResult(
            category="safety_compliance",
            confidence=0.98,
            reasoning="Adverse reaction reported",
            processing_time_ms=80.0,
        )

        with patch("app.api.v1.endpoints.classify.Classifier") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_result)
            mock_instance.requires_human_review = lambda _: True  # Always for safety

            response = e2e_client.post(
                "/api/v1/classify",
                json={"message": "I experienced nausea and dizziness after taking the medication"},
            )

        assert response.status_code == 200
        data = response.json()
        # Should be routed to pharmacist
        assert data["next_step"]["priority"] == "high"
        assert data["next_step"]["requires_human_review"] is True

    def test_request_id_propagation(self, e2e_client: TestClient) -> None:
        """Test that request ID is properly propagated through the system."""
        custom_request_id = "test-request-id-12345"

        mock_result = ClassificationResult(
            category="informational",
            confidence=0.9,
            reasoning="Test",
            processing_time_ms=100.0,
        )

        with patch("app.api.v1.endpoints.classify.Classifier") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_result)
            mock_instance.requires_human_review = lambda _: False

            response = e2e_client.post(
                "/api/v1/classify",
                json={"message": "Test"},
                headers={"X-Request-ID": custom_request_id},
            )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == custom_request_id
        assert response.json()["request_id"] == custom_request_id

    def test_multi_channel_support(self, e2e_client: TestClient) -> None:
        """Test that different channels are properly handled."""
        channels = ["chat", "voice", "mail"]

        mock_result = ClassificationResult(
            category="informational",
            confidence=0.9,
            reasoning="Test",
            processing_time_ms=100.0,
        )

        for channel in channels:
            with patch("app.api.v1.endpoints.classify.Classifier") as MockService:
                mock_instance = MockService.return_value
                mock_instance.classify = AsyncMock(return_value=mock_result)
                mock_instance.requires_human_review = lambda _: False

                response = e2e_client.post(
                    "/api/v1/classify",
                    json={"message": "Test message", "channel": channel},
                )

            assert response.status_code == 200, f"Failed for channel: {channel}"
