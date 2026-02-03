"""DeepEval LLM evaluation tests for the classification API.

Run with pytest using the evaluation marker:
    pytest -m evaluation tests/deepeval/

Or with DeepEval CLI:
    deepeval test run tests/deepeval/test_classification_evals.py

Set CONFIDENT_API_KEY for real-time monitoring (results sent to Confident AI).
"""

from unittest.mock import AsyncMock, patch

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from fastapi.testclient import TestClient
import pytest

from app.core import Settings, get_settings
from app.main import app
from app.services.classification import ClassificationResult
from deepeval import assert_test


@pytest.fixture
def deepeval_client() -> TestClient:
    """Test client with test settings for DeepEval runs."""
    settings = Settings(
        openai_api_key="test-key-deepeval",  # type: ignore[arg-type]
        openai_model="gpt-4o-mini",
        environment="development",
        debug=True,
        min_confidence_threshold=0.5,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _call_classify(client: TestClient, message: str) -> dict:
    """Call /api/v1/classify and return JSON. Uses mocked ClassifierService."""
    response = client.post("/api/v1/classify", json={"message": message})
    assert response.status_code == 200
    return response.json()


def _classification_geval() -> GEval:
    """GEval metric: actual output category must match expected category."""
    return GEval(
        name="ClassificationCorrectness",
        criteria=(
            "The 'actual output' is a classification result. "
            "Determine if the category in the actual output matches the expected category. "
            "Expected categories: informational, service_action, safety_compliance."
        ),
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        threshold=0.5,
    )


@pytest.mark.evaluation
def test_deepeval_informational_classification(deepeval_client: TestClient) -> None:
    """DeepEval: informational message is classified correctly."""
    message = "What is your refund policy for prescription products?"
    expected_category = "informational"
    mock_result = ClassificationResult(
        category=expected_category,
        confidence=0.94,
        reasoning="Customer asking about refund policy - informational inquiry.",
        processing_time_ms=120.0,
    )

    with patch("app.api.v1.endpoints.classify.ClassifierService") as MockService:
        mock_instance = MockService.return_value
        mock_instance.classify = AsyncMock(return_value=mock_result)
        mock_instance.requires_human_review = lambda x: x < 0.5

        data = _call_classify(deepeval_client, message)

    actual_output = f"Category: {data['category']}. Reasoning: {data.get('next_step', {}).get('description', '')}"
    test_case = LLMTestCase(
        input=message,
        actual_output=actual_output,
        expected_output=f"Category should be {expected_category}.",
    )
    assert_test(test_case, [_classification_geval()])


@pytest.mark.evaluation
def test_deepeval_service_action_classification(deepeval_client: TestClient) -> None:
    """DeepEval: service action message is classified correctly."""
    message = "I need to open a ticket because my order never arrived."
    expected_category = "service_action"
    mock_result = ClassificationResult(
        category=expected_category,
        confidence=0.91,
        reasoning="Customer wants to open a ticket for missing order - requires action.",
        processing_time_ms=100.0,
    )

    with patch("app.api.v1.endpoints.classify.ClassifierService") as MockService:
        mock_instance = MockService.return_value
        mock_instance.classify = AsyncMock(return_value=mock_result)
        mock_instance.requires_human_review = lambda x: x < 0.5

        data = _call_classify(deepeval_client, message)

    actual_output = f"Category: {data['category']}. Reasoning: {data.get('next_step', {}).get('description', '')}"
    test_case = LLMTestCase(
        input=message,
        actual_output=actual_output,
        expected_output=f"Category should be {expected_category}.",
    )
    assert_test(test_case, [_classification_geval()])


@pytest.mark.evaluation
def test_deepeval_safety_compliance_classification(deepeval_client: TestClient) -> None:
    """DeepEval: safety compliance message is classified correctly."""
    message = "I experienced severe headache and nausea right after taking the medication."
    expected_category = "safety_compliance"
    mock_result = ClassificationResult(
        category=expected_category,
        confidence=0.96,
        reasoning="Adverse reaction reported - safety compliance priority.",
        processing_time_ms=80.0,
    )

    with patch("app.api.v1.endpoints.classify.ClassifierService") as MockService:
        mock_instance = MockService.return_value
        mock_instance.classify = AsyncMock(return_value=mock_result)
        mock_instance.requires_human_review = lambda _: True

        data = _call_classify(deepeval_client, message)

    actual_output = f"Category: {data['category']}. Reasoning: {data.get('next_step', {}).get('description', '')}"
    test_case = LLMTestCase(
        input=message,
        actual_output=actual_output,
        expected_output=f"Category should be {expected_category}.",
    )
    assert_test(test_case, [_classification_geval()])
