"""Pytest configuration and shared fixtures."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

from orchestrator.config import Settings, get_settings
from orchestrator.main import app
from orchestrator.services.classifier import ClassifierService
from orchestrator.services.llm_client import LLMClient


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with mock API key."""
    return Settings(
        openai_api_key="test-api-key-12345",  # type: ignore[arg-type]
        openai_model="gpt-4o-mini",
        environment="development",
        debug=True,
        min_confidence_threshold=0.5,
    )


@pytest.fixture
def mock_llm_client(test_settings: Settings) -> MagicMock:  # noqa: ARG001
    """Create a mock LLM client."""
    mock = MagicMock(spec=LLMClient)
    mock.complete = AsyncMock()
    mock.health_check = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def classifier_service(test_settings: Settings, mock_llm_client: MagicMock) -> ClassifierService:
    """Create a classifier service with mock LLM client."""
    return ClassifierService(settings=test_settings, llm_client=mock_llm_client)


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app."""
    # Override settings dependency
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(
    test_settings: Settings,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client for the FastAPI app."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# Sample test data
@pytest.fixture
def informational_message() -> str:
    """Sample informational message."""
    return "What is your refund policy for prescription products?"


@pytest.fixture
def service_action_message() -> str:
    """Sample service action message."""
    return "I need to open a ticket because my order never arrived."


@pytest.fixture
def safety_compliance_message() -> str:
    """Sample safety compliance message."""
    return "I experienced a severe headache and nausea right after taking the medication."


@pytest.fixture
def mock_classification_response_informational() -> dict:
    """Mock LLM response for informational category."""
    return {
        "category": "informational",
        "confidence": 0.95,
        "reasoning": "Customer is asking about refund policy - this is an informational inquiry.",
    }


@pytest.fixture
def mock_classification_response_service_action() -> dict:
    """Mock LLM response for service action category."""
    return {
        "category": "service_action",
        "confidence": 0.92,
        "reasoning": "Customer wants to open a ticket for a missing order - requires action.",
    }


@pytest.fixture
def mock_classification_response_safety() -> dict:
    """Mock LLM response for safety compliance category."""
    return {
        "category": "safety_compliance",
        "confidence": 0.98,
        "reasoning": "Customer reports adverse reaction after taking medication - safety concern.",
    }
