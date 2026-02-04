"""Pytest configuration and shared fixtures."""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

from app.core import Settings, get_settings
from app.main import app
from app.prompts import get_registry, load_prompts
from app.prompts.template import LLMConfig, PromptMetadata, PromptParameter, PromptTemplate
from app.schemas.llm_responses import ClassificationLLMResponse
from app.services.classification import Classifier
from app.services.llm import LLMClient


@pytest.fixture(autouse=True)
def setup_test_prompts() -> None:
    """Setup test prompts before each test."""
    # Clear the registry
    registry = get_registry()
    registry._templates.clear()
    registry._active_versions.clear()
    registry._experiments.clear()

    # Try to load prompts from project root
    try:
        project_root = Path(__file__).parent.parent
        prompts_dir = project_root / "prompts"
        if prompts_dir.exists():
            load_prompts(prompts_dir)
    except Exception:
        # If loading fails, create a minimal test prompt
        test_prompt = PromptTemplate(
            id="classification",
            version="1.0.0",
            system_prompt="You are a test classifier.",
            user_prompt_template="Channel: {{channel}}\nMessage: {{message}}",
            parameters=[
                PromptParameter(name="channel", type="string", description="Channel"),
                PromptParameter(name="message", type="string", description="Message"),
            ],
            llm_config=LLMConfig(temperature=0.0, max_tokens=200, model="gpt-4.1"),
            metadata=PromptMetadata(description="Test prompt"),
        )
        registry.register(test_prompt)


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
    mock.classify_text = AsyncMock()  # Structured output method for text
    mock.classify_audio = AsyncMock()  # Audio classification method
    return mock


@pytest.fixture
def classifier(test_settings: Settings, mock_llm_client: MagicMock) -> Classifier:
    """Create a classifier with mock LLM client."""
    return Classifier(settings=test_settings, llm_client=mock_llm_client)


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
def mock_classification_response_informational() -> ClassificationLLMResponse:
    """Mock LLM response for informational category."""
    return ClassificationLLMResponse(
        category="informational",
        confidence=0.95,
        reasoning="Customer is asking about refund policy - this is an informational inquiry.",
    )


@pytest.fixture
def mock_classification_response_service_action() -> ClassificationLLMResponse:
    """Mock LLM response for service action category."""
    return ClassificationLLMResponse(
        category="service_action",
        confidence=0.92,
        reasoning="Customer wants to open a ticket for a missing order - requires action.",
    )


@pytest.fixture
def mock_classification_response_safety() -> ClassificationLLMResponse:
    """Mock LLM response for safety compliance category."""
    return ClassificationLLMResponse(
        category="safety_compliance",
        confidence=0.98,
        reasoning="Customer reports adverse reaction after taking medication - safety concern.",
    )
