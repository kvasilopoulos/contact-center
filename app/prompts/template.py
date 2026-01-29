"""Prompt template dataclass and rendering logic."""

from dataclasses import dataclass, field
from typing import Any

from jinja2 import Template, TemplateSyntaxError
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PromptParameter:
    """Definition of a required parameter for prompt rendering."""

    name: str
    type: str
    description: str = ""


@dataclass
class PromptMetadata:
    """Metadata about a prompt version."""

    author: str = ""
    created: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    changes: str = ""


@dataclass
class LLMConfig:
    """LLM configuration for a prompt."""

    temperature: float = 0.0
    max_tokens: int = 500
    response_format: str = "json_object"
    model: str = ""  # Empty string means use global default from settings


@dataclass
class PromptTemplate:
    """A versioned prompt template loaded from YAML.

    Attributes:
        id: Unique identifier for the prompt (e.g., "classification")
        version: Semantic version string (e.g., "1.0.0")
        system_prompt: The system prompt text
        user_prompt_template: Jinja2 template for user prompt
        parameters: List of required parameters for rendering
        llm_config: LLM configuration settings
        metadata: Metadata about this prompt version
    """

    id: str
    version: str
    system_prompt: str
    user_prompt_template: str
    parameters: list[PromptParameter] = field(default_factory=list)
    llm_config: LLMConfig = field(default_factory=LLMConfig)
    metadata: PromptMetadata = field(default_factory=PromptMetadata)

    def __post_init__(self) -> None:
        """Validate and compile templates after initialization."""
        try:
            # Compile Jinja2 template to catch syntax errors early
            Template(self.user_prompt_template)
        except TemplateSyntaxError as e:
            logger.error(
                "Invalid Jinja2 template in user_prompt_template",
                prompt_id=self.id,
                version=self.version,
                error=str(e),
            )
            raise ValueError(f"Invalid template syntax in {self.id} v{self.version}: {e}") from e

    def render_user_prompt(self, variables: dict[str, Any]) -> str:
        """Render the user prompt template with provided variables.

        Args:
            variables: Dictionary of variables to substitute in template

        Returns:
            Rendered user prompt string

        Raises:
            ValueError: If required parameters are missing or rendering fails
        """
        # Validate required parameters
        missing_params = []
        for param in self.parameters:
            if param.name not in variables:
                missing_params.append(param.name)

        if missing_params:
            raise ValueError(
                f"Missing required parameters for {self.id} v{self.version}: {missing_params}"
            )

        try:
            template = Template(self.user_prompt_template)
            return template.render(**variables)
        except Exception as e:
            logger.error(
                "Failed to render user prompt template",
                prompt_id=self.id,
                version=self.version,
                error=str(e),
                variables=list(variables.keys()),
            )
            raise ValueError(f"Failed to render template for {self.id} v{self.version}: {e}") from e

    def get_full_key(self) -> str:
        """Get the full key for this prompt (id + version).

        Returns:
            String in format "id:version"
        """
        return f"{self.id}:{self.version}"

    def __repr__(self) -> str:
        """String representation of the prompt template."""
        return f"PromptTemplate(id='{self.id}', version='{self.version}')"
