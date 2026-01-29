"""LLM client for OpenAI API integration."""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI, OpenAIError
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
import websockets
from websockets.client import WebSocketClientProtocol

if TYPE_CHECKING:
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

    async def _do_complete_with_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Internal method to perform LLM call with specific model.

        This wraps _do_complete but allows specifying a different model.
        """
        try:
            result: dict[str, Any]
            async with self._circuit_breaker:
                result = await self._do_complete_internal(
                    model=model,
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
    async def _do_complete_internal(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """Internal method to perform the actual LLM call with retries."""
        try:
            logger.debug(
                "Sending LLM request",
                model=model,
                user_prompt_length=len(user_prompt),
            )

            response = await self.client.chat.completions.create(
                model=model,
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
                model=model,
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
        """Internal method to perform the actual LLM call with retries (legacy wrapper)."""
        return await self._do_complete_internal(
            model=self.settings.openai_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

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

        # Determine which model to use: variant override > template config > global default
        model_to_use = self.settings.openai_model
        if experiment_id and metadata.get("experiment_id"):
            # Check if variant has model override
            experiment = registry.get_experiment(experiment_id)
            if experiment:
                for variant in experiment.variants:
                    if variant.name == metadata.get("variant") and variant.model:
                        model_to_use = variant.model
                        break

        # Fall back to template model if specified and no variant override
        if model_to_use == self.settings.openai_model and template.llm_config.model:
            model_to_use = template.llm_config.model

        # Log prompt usage
        logger.info(
            "Using prompt template",
            prompt_id=metadata["prompt_id"],
            version=metadata["version"],
            variant=metadata.get("variant"),
            experiment_id=metadata.get("experiment_id"),
            model=model_to_use,
        )

        # Use LLM config from template with dynamic model
        llm_response = await self._do_complete_with_model(
            model=model_to_use,
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
            temperature=template.llm_config.temperature,
            max_tokens=template.llm_config.max_tokens,
        )

        # Add model to metadata
        metadata["model"] = model_to_use

        return llm_response, metadata

    async def classify_audio_realtime(
        self,
        audio: bytes,
        channel: str = "voice",
    ) -> dict[str, Any]:
        """Classify audio using the Realtime API without explicit transcription.

        This method:
        - Creates a Realtime WebSocket session
        - Configures it with the classification system prompt
        - Sends the audio via input_audio_buffer events
        - Waits for a textual response containing JSON classification
        - Parses and returns the JSON object

        The caller is responsible for mapping the JSON into domain models.
        """
        try:
            async with self._circuit_breaker:
                return await self._do_classify_audio_realtime(audio=audio, channel=channel)
        except CircuitBreakerOpen as e:
            logger.warning(
                "Circuit breaker open - Realtime service unavailable",
                retry_after=e.retry_after,
                circuit_state=self._circuit_breaker.state.value,
            )
            raise LLMServiceUnavailable(
                "Realtime service temporarily unavailable. Please try again later.",
                retry_after=e.retry_after,
            ) from e

    async def _do_classify_audio_realtime(
        self,
        audio: bytes,
        channel: str,
    ) -> dict[str, Any]:
        """Internal helper to classify audio via Realtime WebSocket."""
        api_key = self.settings.openai_api_key.get_secret_value()
        if not api_key:
            raise LLMClientError("OpenAI API key not configured")

        # Get classification prompt template for system instructions
        template = registry.get_active("classification")

        # System instructions: reuse existing classification system prompt,
        # and explicitly require JSON-only output (already enforced by prompt).
        instructions = template.system_prompt

        # Small text preamble to give the model context about the channel.
        input_text = (
            f"CHANNEL: {channel}\n\nCUSTOMER AUDIO FOLLOWS. "
            "Listen to the audio and classify it according to the instructions."
        )

        # Base64-encode the audio; assume client sends a WAV file.
        audio_b64 = base64.b64encode(audio).decode("ascii")

        url = f"wss://api.openai.com/v1/realtime?model={self.settings.openai_realtime_model}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        logger.debug(
            "Opening Realtime WebSocket for audio classification",
            model=self.settings.openai_realtime_model,
            audio_bytes=len(audio),
        )

        try:
            async with websockets.connect(url, extra_headers=headers) as ws:
                assert isinstance(ws, WebSocketClientProtocol)

                # 1) Configure session with instructions (system prompt)
                session_update = {
                    "type": "session.update",
                    "session": {
                        "instructions": instructions,
                    },
                }
                await ws.send(json.dumps(session_update))

                # 2) Send a small text message describing the channel
                input_text_event = {
                    "type": "input_text",
                    "text": input_text,
                }
                await ws.send(json.dumps(input_text_event))

                # 3) Append audio to input buffer
                append_event = {
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64,
                    "format": "wav",
                }
                await ws.send(json.dumps(append_event))

                # 4) Commit audio buffer so the model starts processing
                commit_event = {
                    "type": "input_audio_buffer.commit",
                }
                await ws.send(json.dumps(commit_event))

                # 5) Create a response (tell the model to respond)
                response_create = {
                    "type": "response.create",
                }
                await ws.send(json.dumps(response_create))

                # 6) Listen for a textual response containing JSON classification
                try:
                    return await self._wait_for_realtime_json_response(ws)
                finally:
                    # Best-effort close
                    with contextlib.suppress(Exception):
                        await ws.close()
        except asyncio.TimeoutError as e:
            logger.error("Realtime classification timed out", error=str(e))
            raise LLMClientError("Realtime audio classification timed out") from e
        except Exception as e:
            logger.error("Realtime WebSocket error", error=str(e))
            raise LLMClientError(f"Realtime audio classification failed: {e}") from e

    async def _wait_for_realtime_json_response(
        self,
        ws: WebSocketClientProtocol,
        timeout_seconds: float | None = 30.0,
    ) -> dict[str, Any]:
        """Wait for a Realtime response that contains JSON classification.

        This implementation looks for response events with text content and
        attempts to parse the last non-empty text chunk as JSON.
        """

        async def _inner() -> dict[str, Any]:
            last_text: str | None = None
            while True:
                raw = await ws.recv()
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    # Ignore non-JSON frames
                    continue

                event_type = event.get("type")

                # Collect any text deltas/content from response output
                if event_type in {"response.output_text.delta", "response.output_text.done"}:
                    delta = event.get("delta") or event.get("text")
                    if isinstance(delta, str) and delta:
                        last_text = (last_text or "") + delta

                # When the response is completed, try to parse JSON from accumulated text
                if event_type == "response.completed":
                    if not last_text:
                        raise LLMClientError("Realtime response contained no text output")
                    try:
                        return json.loads(last_text)
                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to parse Realtime response text as JSON",
                            error=str(e),
                            text_preview=last_text[:200],
                        )
                        raise LLMClientError("Realtime response was not valid JSON") from e

                # If an error event arrives from the server, surface it
                if event_type == "error":
                    message = event.get("error", {}).get("message", "Unknown Realtime error")
                    raise LLMClientError(f"Realtime API error: {message}")

        if timeout_seconds is not None:
            return await asyncio.wait_for(_inner(), timeout=timeout_seconds)
        return await _inner()

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
