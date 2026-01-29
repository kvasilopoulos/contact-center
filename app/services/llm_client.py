"""LLM client for OpenAI API integration."""

from io import BytesIO
import json
from typing import Any

from openai import AsyncOpenAI, OpenAIError
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import Settings
from app.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from app.prompts import registry

logger = structlog.get_logger(__name__)

# Global circuit breaker for OpenAI API
_openai_circuit_breaker = CircuitBreaker(
    failure_threshold=5,  # Open after 5 consecutive failures
    recovery_timeout=30.0,  # Try again after 30 seconds
    half_open_max_calls=3,  # Allow 3 test calls when half-open
    success_threshold=2,  # Need 2 successes to fully close
)


class LLMClientError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMServiceUnavailable(LLMClientError):
    """Exception when LLM service is unavailable (circuit breaker open)."""

    def __init__(self, message: str, retry_after: float = 0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMClient:
    """Async client for OpenAI API interactions with circuit breaker."""

    def __init__(self, settings: Settings, circuit_breaker: CircuitBreaker | None = None) -> None:
        """Initialize the LLM client.

        Args:
            settings: Application settings containing API configuration.
            circuit_breaker: Optional circuit breaker instance. Uses global if not provided.
        """
        self.settings = settings
        self._client: AsyncOpenAI | None = None
        self._circuit_breaker = circuit_breaker or _openai_circuit_breaker

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create the OpenAI client instance."""
        if self._client is None:
            api_key = self.settings.openai_api_key.get_secret_value()
            if not api_key:
                raise LLMClientError("OpenAI API key not configured")
            self._client = AsyncOpenAI(
                api_key=api_key,
                timeout=self.settings.openai_timeout,
                max_retries=0,  # We handle retries ourselves
            )
        return self._client

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> dict[str, Any]:
        """Send a completion request to the LLM with circuit breaker protection.

        Args:
            system_prompt: The system prompt defining the task.
            user_prompt: The user message to process.
            temperature: Sampling temperature (0.0 for deterministic).
            max_tokens: Maximum tokens in the response.

        Returns:
            Parsed JSON response from the LLM.

        Raises:
            LLMClientError: If the request fails or response is invalid.
            LLMServiceUnavailable: If circuit breaker is open.
        """
        try:
            result: dict[str, Any]
            async with self._circuit_breaker:
                result = await self._do_complete(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            return result
        except CircuitBreakerOpen as e:
            logger.warning(
                "Circuit breaker open - LLM service unavailable",
                retry_after=e.retry_after,
                circuit_state=self._circuit_breaker.state.value,
            )
            raise LLMServiceUnavailable(
                "LLM service temporarily unavailable. Please try again later.",
                retry_after=e.retry_after,
            ) from e

    @retry(
        retry=retry_if_exception_type(OpenAIError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _do_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Internal method to perform the actual LLM call with retries."""
        try:
            logger.debug(
                "Sending LLM request",
                model=self.settings.openai_model,
                user_prompt_length=len(user_prompt),
            )

            response = await self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise LLMClientError("Empty response from LLM")

            logger.debug(
                "LLM response received",
                model=self.settings.openai_model,
                usage=response.usage.model_dump() if response.usage else None,
            )

            result: dict[str, Any] = json.loads(content)
            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON", error=str(e))
            raise LLMClientError(f"Invalid JSON response from LLM: {e}") from e
        except OpenAIError as e:
            logger.error("OpenAI API error", error=str(e))
            raise LLMClientError(f"OpenAI API error: {e}") from e

    async def complete_with_template(
        self,
        template_id: str,
        variables: dict[str, Any],
        version: str | None = None,
        experiment_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Send a completion request using a prompt template.

        Args:
            template_id: ID of the prompt template to use
            variables: Variables to substitute in the template
            version: Optional specific version to use. If None, uses active version.
            experiment_id: Optional experiment ID for A/B testing

        Returns:
            Tuple of (LLM response, metadata) where metadata contains:
                - prompt_id: The prompt ID used
                - version: The prompt version used
                - variant: The variant name (for experiments) or "active"
                - experiment_id: The experiment ID (if applicable)

        Raises:
            LLMClientError: If the request fails or response is invalid
            LLMServiceUnavailable: If circuit breaker is open
            KeyError: If the template is not found
            ValueError: If template rendering fails
        """
        # Get template from registry (handles experiments if specified)
        if experiment_id:
            template, metadata = registry.get_for_experiment(template_id, experiment_id)
        elif version:
            template = registry.get(template_id, version)
            metadata = {
                "prompt_id": template_id,
                "version": version,
                "variant": "specified",
            }
        else:
            template = registry.get_active(template_id)
            metadata = {
                "prompt_id": template_id,
                "version": template.version,
                "variant": "active",
            }

        # Render user prompt with variables
        try:
            user_prompt = template.render_user_prompt(variables)
        except ValueError as e:
            logger.error(
                "Failed to render prompt template",
                template_id=template_id,
                version=metadata["version"],
                error=str(e),
            )
            raise

        # Log prompt usage
        logger.info(
            "Using prompt template",
            prompt_id=metadata["prompt_id"],
            version=metadata["version"],
            variant=metadata.get("variant"),
            experiment_id=metadata.get("experiment_id"),
        )

        # Use LLM config from template
        llm_response = await self.complete(
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
            temperature=template.llm_config.temperature,
            max_tokens=template.llm_config.max_tokens,
        )

        return llm_response, metadata

    @property
    def circuit_breaker_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return self._circuit_breaker.get_stats()

    async def health_check(self) -> bool:
        """Check if the LLM service is available.

        Returns:
            True if the service is healthy, False otherwise.
        """
        try:
            await self.client.models.retrieve(self.settings.openai_model)
            return True
        except Exception as e:
            logger.warning("LLM health check failed", error=str(e))
            return False

    async def close(self) -> None:
        """Close the client connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
