"""Integration tests for API endpoints."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import pytest

from app.services.classification import ClassificationResult


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test the /health endpoint returns healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert data["checks"]["api"] is True

    def test_ready_endpoint_with_key(self, client: TestClient) -> None:
        """Test the /ready endpoint with API key configured."""
        response = client.get("/api/v1/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["checks"]["openai_configured"] is True

    def test_health_includes_request_id(self, client: TestClient) -> None:
        """Test that responses include X-Request-ID header."""
        response = client.get("/api/v1/health")

        assert "X-Request-ID" in response.headers
        assert "X-Process-Time-Ms" in response.headers


class TestClassifyEndpoint:
    """Tests for the /classify endpoint."""

    @pytest.fixture
    def mock_classifier(self) -> AsyncMock:
        """Create a mock classifier result."""
        return ClassificationResult(
            category="informational",
            confidence=0.95,
            reasoning="Customer asking about policy",
            processing_time_ms=100.0,
        )

    def test_classify_valid_request(
        self, client: TestClient, mock_classifier: ClassificationResult
    ) -> None:
        """Test classification with valid request."""
        with patch("app.api.v1.endpoints.classify.ClassifierService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_classifier)
            mock_instance.requires_human_review = lambda x: x < 0.5

            response = client.post(
                "/api/v1/classify",
                json={"message": "What is your refund policy?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "informational"
        assert data["confidence"] == 0.95
        assert "request_id" in data
        assert "next_step" in data
        assert "processing_time_ms" in data

    def test_classify_with_channel(
        self, client: TestClient, mock_classifier: ClassificationResult
    ) -> None:
        """Test classification with specified channel."""
        with patch("app.api.v1.endpoints.classify.ClassifierService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_classifier)
            mock_instance.requires_human_review = lambda x: x < 0.5

            response = client.post(
                "/api/v1/classify",
                json={
                    "message": "I need help",
                    "channel": "voice",
                    "metadata": {"customer_id": "C123"},
                },
            )

        assert response.status_code == 200

    def test_classify_empty_message_rejected(self, client: TestClient) -> None:
        """Test that empty message is rejected."""
        response = client.post(
            "/api/v1/classify",
            json={"message": ""},
        )

        assert response.status_code == 422
        data = response.json()
        assert "error" in data or "detail" in data

    def test_classify_message_too_long_rejected(self, client: TestClient) -> None:
        """Test that overly long message is rejected."""
        response = client.post(
            "/api/v1/classify",
            json={"message": "x" * 5001},
        )

        assert response.status_code == 422

    def test_classify_invalid_channel_rejected(self, client: TestClient) -> None:
        """Test that invalid channel is rejected."""
        response = client.post(
            "/api/v1/classify",
            json={"message": "Test", "channel": "invalid"},
        )

        assert response.status_code == 422

    def test_classify_missing_message_rejected(self, client: TestClient) -> None:
        """Test that missing message field is rejected."""
        response = client.post(
            "/api/v1/classify",
            json={},
        )

        assert response.status_code == 422

    def test_classify_response_structure(
        self, client: TestClient, mock_classifier: ClassificationResult
    ) -> None:
        """Test that response has all required fields."""
        with patch("app.api.v1.endpoints.classify.ClassifierService") as MockService:
            mock_instance = MockService.return_value
            mock_instance.classify = AsyncMock(return_value=mock_classifier)
            mock_instance.requires_human_review = lambda x: x < 0.5

            response = client.post(
                "/api/v1/classify",
                json={"message": "Test message"},
            )

        assert response.status_code == 200
        data = response.json()

        # Check all required fields
        required_fields = [
            "request_id",
            "timestamp",
            "category",
            "confidence",
            "decision_path",
            "next_step",
            "processing_time_ms",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        # Check next_step structure
        next_step = data["next_step"]
        next_step_fields = ["action", "description", "priority"]
        for field in next_step_fields:
            assert field in next_step, f"Missing next_step field: {field}"


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation endpoints."""

    def test_openapi_json_available(self, client: TestClient) -> None:
        """Test that OpenAPI JSON is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_docs_available(self, client: TestClient) -> None:
        """Test that Swagger UI is available at /swagger."""
        response = client.get("/swagger")
        assert response.status_code == 200

    def test_redoc_available(self, client: TestClient) -> None:
        """Test that ReDoc is available."""
        response = client.get("/redoc")
        assert response.status_code == 200
