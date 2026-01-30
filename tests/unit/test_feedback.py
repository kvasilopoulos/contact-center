"""Tests for the feedback endpoint."""

from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestFeedbackEndpoint:
    """Tests for classification feedback functionality."""

    def test_submit_positive_feedback(self, client: TestClient) -> None:
        """Test submitting positive feedback."""
        response = client.post(
            "/api/v1/classify/test-request-123/feedback",
            json={"correct": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "test-request-123"
        assert data["recorded"] is True
        assert "feedback_id" in data

    def test_submit_negative_feedback_with_expected_category(self, client: TestClient) -> None:
        """Test submitting negative feedback with expected category."""
        response = client.post(
            "/api/v1/classify/test-request-456/feedback",
            json={
                "correct": False,
                "expected_category": "safety_compliance",
                "comment": "Message mentioned health concerns",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "test-request-456"
        assert data["recorded"] is True

    def test_submit_negative_feedback_without_expected_category(self, client: TestClient) -> None:
        """Test submitting negative feedback without specifying expected category."""
        response = client.post(
            "/api/v1/classify/test-request-789/feedback",
            json={"correct": False},
        )
        assert response.status_code == 200

    def test_get_feedback_after_submission(self, client: TestClient) -> None:
        """Test retrieving feedback after submission."""
        # First submit feedback
        request_id = "test-get-feedback"
        client.post(
            f"/api/v1/classify/{request_id}/feedback",
            json={
                "correct": False,
                "expected_category": "informational",
                "comment": "This was a FAQ question",
            },
        )

        # Then retrieve it
        response = client.get(f"/api/v1/classify/{request_id}/feedback")
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == request_id
        assert data["correct"] is False
        assert data["expected_category"] == "informational"
        assert data["comment"] == "This was a FAQ question"

    def test_get_feedback_not_found(self, client: TestClient) -> None:
        """Test retrieving feedback for non-existent request."""
        response = client.get("/api/v1/classify/non-existent-id/feedback")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "feedback_not_found"

    def test_submit_feedback_invalid_category(self, client: TestClient) -> None:
        """Test submitting feedback with invalid expected category."""
        response = client.post(
            "/api/v1/classify/test-invalid/feedback",
            json={
                "correct": False,
                "expected_category": "invalid_category",
            },
        )
        # Should fail validation
        assert response.status_code == 422

    def test_feedback_comment_max_length(self, client: TestClient) -> None:
        """Test that comment respects max length."""
        long_comment = "x" * 1001  # Exceeds 1000 char limit
        response = client.post(
            "/api/v1/classify/test-long-comment/feedback",
            json={
                "correct": True,
                "comment": long_comment,
            },
        )
        # Should fail validation
        assert response.status_code == 422
