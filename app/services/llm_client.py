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
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

if TYPE_CHECKING:
    from app.config import Settings
from app.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from app.prompts import registry
from app.services.audio_utils import (
    AudioFormatError,
    convert_wav_to_pcm16_24khz,
    detect_audio_format,
    is_wav_file,
)

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

    def _build_response_format(
        self, response_format_config: str | dict[str, Any]
    ) -> dict[str, Any]:
        """Build response format configuration for OpenAI API.

        Args:
            response_format_config: Either "json_object" string or dict with schema definition

        Returns:
            Response format dict for OpenAI API
        """
        # If it's already a dict (structured schema), use it directly
        if isinstance(response_format_config, dict):
            return response_format_config

        # If it's "json_object", convert to structured output schema
        if response_format_config == "json_object":
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "classification_response",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["informational", "service_action", "safety_compliance"],
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                            "reasoning": {
                                "type": "string",
                            },
                        },
                        "required": ["category", "confidence", "reasoning"],
                        "additionalProperties": False,
                    },
                },
            }

        # Default: use structured output schema
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "classification_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["informational", "service_action", "safety_compliance"],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "reasoning": {
                            "type": "string",
                        },
                    },
                    "required": ["category", "confidence", "reasoning"],
                    "additionalProperties": False,
                },
            },
        }

    async def _do_complete_with_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Internal method to perform LLM call with specific model.

        This wraps _do_complete but allows specifying a different model.

        Args:
            model: Model name to use
            system_prompt: System prompt text
            user_prompt: User prompt text
            temperature: Temperature setting
            max_tokens: Maximum tokens to generate
            response_format: Optional response format. If None, uses structured output schema.
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
                    response_format=response_format,
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
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Internal method to perform the actual LLM call with retries.

        Args:
            model: Model name to use
            system_prompt: System prompt text
            user_prompt: User prompt text
            temperature: Temperature setting
            max_tokens: Maximum tokens to generate
            response_format: Optional response format. If None, uses structured output schema.
        """
        try:
            logger.debug(
                "Sending LLM request",
                model=model,
                user_prompt_length=len(user_prompt),
            )

            # Default to structured output schema if not provided
            if response_format is None:
                response_format = self._build_response_format("json_object")

            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
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

        # Build response format from template config
        response_format = self._build_response_format(template.llm_config.response_format)

        # Use LLM config from template with dynamic model
        llm_response = await self._do_complete_with_model(
            model=model_to_use,
            system_prompt=template.system_prompt,
            user_prompt=user_prompt,
            temperature=template.llm_config.temperature,
            max_tokens=template.llm_config.max_tokens,
            response_format=response_format,
        )

        # Add model to metadata
        metadata["model"] = model_to_use

        return llm_response, metadata

    async def classify_audio_realtime(
        self,
        audio: bytes,
        channel: str = "voice",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Classify audio using the Realtime API without explicit transcription.

        This method:
        - Creates a Realtime WebSocket session
        - Configures it with the classification system prompt
        - Sends the audio via conversation.item.create
        - Waits for a textual response containing JSON classification
        - Parses and returns the JSON object with prompt metadata

        Returns:
            Tuple of (classification_result, metadata) where metadata contains:
                - prompt_id: The prompt ID used
                - version: The prompt version used
                - model: The model used
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
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Internal helper to classify audio via Realtime WebSocket."""
        api_key = self.settings.openai_api_key.get_secret_value()
        if not api_key:
            raise LLMClientError("OpenAI API key not configured")

        # Get audio-specific classification prompt template for system instructions
        prompt_id = "classification_audio"
        try:
            template = registry.get_active("classification_audio")
        except KeyError:
            # Fallback to generic classification prompt if audio-specific one is not configured
            logger.warning(
                "Audio classification prompt 'classification_audio' not found, "
                "falling back to 'classification'",
            )
            template = registry.get_active("classification")
            prompt_id = "classification"

        # Build metadata
        metadata: dict[str, Any] = {
            "prompt_id": prompt_id,
            "version": template.version,
            "variant": "active",
        }

        # System instructions: use audio-specific classification system prompt,
        # and explicitly require JSON-only output (already enforced by prompt).
        instructions = template.system_prompt

        # Determine which model to use: template config > global default
        model_to_use = (
            template.llm_config.model
            if template.llm_config.model
            else self.settings.openai_realtime_model
        )

        # Add model to metadata
        metadata["model"] = model_to_use

        # Small text preamble to give the model context about the channel.
        input_text = (
            f"CHANNEL: {channel}\n\nCUSTOMER AUDIO FOLLOWS. "
            "Listen to the audio and classify it according to the instructions."
        )

        # Convert audio to required format: mono PCM16 at 24kHz
        # OpenAI Realtime API expects raw PCM data, not WAV with headers
        try:
            audio_format = detect_audio_format(audio)

            if audio_format == "wav":
                pcm_audio = convert_wav_to_pcm16_24khz(audio)
                logger.info(
                    "Converted WAV to PCM16 24kHz",
                    input_bytes=len(audio),
                    output_bytes=len(pcm_audio),
                )
            elif audio_format in ("webm", "ogg", "mp3", "flac"):
                # These formats require external tools (ffmpeg) to convert
                raise LLMClientError(
                    f"Unsupported audio format: {audio_format}. "
                    "Please upload audio in WAV format (mono, 16-bit PCM, preferably 24kHz). "
                    "Browser recordings typically use WebM/Opus which requires server-side "
                    "conversion tools not currently available."
                )
            elif audio_format == "unknown":
                # Could be raw PCM - try to use it directly but warn
                logger.warning(
                    "Unknown audio format, attempting to use as raw PCM16 at 24kHz",
                    input_bytes=len(audio),
                )
                pcm_audio = audio
            else:
                pcm_audio = audio
        except AudioFormatError as e:
            raise LLMClientError(f"Audio format conversion failed: {e}") from e

        # Base64-encode the raw PCM audio
        audio_b64 = base64.b64encode(pcm_audio).decode("ascii")

        url = f"wss://api.openai.com/v1/realtime?model={model_to_use}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        logger.debug(
            "Opening Realtime WebSocket for audio classification",
            model=model_to_use,
            audio_bytes=len(audio),
            prompt_id=template.id,
            prompt_version=template.version,
        )

        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                assert isinstance(ws, ClientConnection)

                try:
                    # 1) Configure session with instructions and audio format
                    # The Realtime API needs to know the expected audio input format
                    session_update = {
                        "type": "session.update",
                        "session": {
                            "instructions": instructions,
                            "modalities": ["text", "audio"],
                            "input_audio_format": "pcm16",
                            "output_audio_format": "pcm16",
                            "turn_detection": None,  # Disable VAD, we're sending complete audio
                        },
                    }
                    await ws.send(json.dumps(session_update))

                    # Wait for session.updated confirmation
                    while True:
                        raw = await ws.recv()
                        event = json.loads(raw)
                        if event.get("type") == "session.updated":
                            logger.debug("Realtime session configured successfully")
                            break
                        if event.get("type") == "error":
                            error_msg = event.get("error", {}).get("message", "Unknown error")
                            raise LLMClientError(f"Session configuration failed: {error_msg}")

                    # 2) Create a conversation item with both text context and audio
                    # Using conversation.item.create with input_audio for pre-recorded audio
                    conversation_item = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": input_text,
                                },
                                {
                                    "type": "input_audio",
                                    "audio": audio_b64,
                                },
                            ],
                        },
                    }
                    await ws.send(json.dumps(conversation_item))

                    # Wait for conversation.item.created confirmation
                    while True:
                        raw = await ws.recv()
                        event = json.loads(raw)
                        event_type = event.get("type")
                        if event_type == "conversation.item.created":
                            logger.debug("Conversation item created successfully")
                            break
                        if event_type == "error":
                            error_msg = event.get("error", {}).get("message", "Unknown error")
                            raise LLMClientError(f"Failed to create conversation item: {error_msg}")

                    # 3) Request a response from the model
                    response_create = {
                        "type": "response.create",
                        "response": {
                            "modalities": ["text"],  # We only want text output (JSON)
                        },
                    }
                    await ws.send(json.dumps(response_create))

                    # 6) Listen for a textual response containing JSON classification
                    result = await self._wait_for_realtime_json_response(ws)
                    return result, metadata
                except Exception as send_error:
                    logger.error(
                        "Error during Realtime WebSocket communication",
                        error=str(send_error),
                        error_type=type(send_error).__name__,
                        exc_info=True,
                    )
                    raise
                finally:
                    # Best-effort close
                    with contextlib.suppress(Exception):
                        await ws.close()
        except asyncio.TimeoutError as e:
            logger.error("Realtime classification timed out", error=str(e))
            raise LLMClientError("Realtime audio classification timed out") from e
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
            error_msg = f"WebSocket connection closed: code={e.code}, reason={e.reason or 'No reason provided'}"
            logger.error("Realtime WebSocket connection closed", code=e.code, reason=e.reason)
            raise LLMClientError(error_msg) from e
        except Exception as e:
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(
                "Realtime WebSocket error",
                error=error_msg,
                error_type=type(e).__name__,
                error_repr=repr(e),
                exc_info=True,
            )
            raise LLMClientError(f"Realtime audio classification failed: {error_msg}") from e

    async def _wait_for_realtime_json_response(
        self,
        ws: ClientConnection,
        timeout_seconds: float | None = 30.0,
    ) -> dict[str, Any]:
        """Wait for a Realtime response that contains JSON classification.

        This implementation looks for response events with text content and
        attempts to parse the last non-empty text chunk as JSON.
        """

        async def _inner() -> dict[str, Any]:
            accumulated_text: str = ""
            while True:
                try:
                    raw = await ws.recv()
                except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
                    error_msg = f"WebSocket closed during response: code={e.code}, reason={e.reason or 'No reason provided'}"
                    logger.error(
                        "WebSocket closed while waiting for response", code=e.code, reason=e.reason
                    )
                    raise LLMClientError(error_msg) from e
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    # Ignore non-JSON frames
                    continue

                event_type = event.get("type")

                # Log all events for debugging
                logger.debug("Realtime event received", event_type=event_type)

                # Collect text from response.text.delta events
                if event_type == "response.text.delta":
                    delta = event.get("delta", "")
                    if delta:
                        accumulated_text += delta

                # Also check for response.text.done which contains final text
                if event_type == "response.text.done":
                    text = event.get("text", "")
                    if text:
                        accumulated_text = text  # Use the complete text

                # When the response is done, try to parse JSON from accumulated text
                if event_type == "response.done":
                    response_data = event.get("response", {})
                    output_items = response_data.get("output", [])

                    # Try to extract text from output items
                    for item in output_items:
                        if item.get("type") == "message":
                            for content in item.get("content", []):
                                if content.get("type") == "text":
                                    text = content.get("text", "")
                                    if text:
                                        accumulated_text = text

                    if not accumulated_text:
                        raise LLMClientError("Realtime response contained no text output")

                    try:
                        return json.loads(accumulated_text)
                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to parse Realtime response text as JSON",
                            error=str(e),
                            text_preview=accumulated_text[:500],
                        )
                        raise LLMClientError(
                            f"Realtime response was not valid JSON: {accumulated_text[:200]}"
                        ) from e

                # If an error event arrives from the server, surface it
                if event_type == "error":
                    error_info = event.get("error", {})
                    message = error_info.get("message", "Unknown Realtime error")
                    code = error_info.get("code", "")
                    logger.error("Realtime API error", code=code, message=message)
                    raise LLMClientError(f"Realtime API error: {message}")

        if timeout_seconds is not None:
            return await asyncio.wait_for(_inner(), timeout=timeout_seconds)
        return await _inner()
