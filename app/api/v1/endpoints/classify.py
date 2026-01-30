"""Classification endpoint."""

import json
import logging
import os
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.core import Settings, get_settings, record_classification
from app.schemas import ClassificationRequest, ClassificationResponse, NextStepInfo
from app.services.classifier import ClassificationError, ClassifierService
from app.services.workflow_router import execute_workflow

logger = logging.getLogger(__name__)

# Optional: wrap handlers with @observe() so production telemetry (Confident AI) gets traces
# Only activate when CONFIDENT_API_KEY is set (production mode)
_CONFIDENT_API_KEY = os.environ.get("CONFIDENT_API_KEY")


def _observe_decorator(f):
    """No-op decorator by default."""
    return f


if _CONFIDENT_API_KEY:
    try:
        from deepeval.tracing import observe as _observe

        _observe_decorator = _observe()
        logger.info("DeepEval telemetry enabled (CONFIDENT_API_KEY set)")
    except Exception as e:
        logger.warning(f"DeepEval tracing unavailable: {e}")


router = APIRouter(tags=["Classification"])


def get_classifier_service(
    settings: Settings = Depends(get_settings),
) -> ClassifierService:
    """Dependency to get the classifier service."""
    return ClassifierService(settings)


@router.post(
    "/classify",
    response_model=ClassificationResponse,
    summary="Classify Customer Message",
    description=(
        "Classify a customer message into one of three categories: "
        "informational, service_action, or safety_compliance. "
        "Returns the category, confidence score, decision path, and recommended next steps."
    ),
    responses={
        200: {"description": "Successfully classified the message"},
        422: {"description": "Validation error in request"},
        500: {"description": "Classification failed"},
        503: {"description": "LLM service unavailable"},
    },
)
@_observe_decorator
async def classify_message(
    request: Request,
    payload: ClassificationRequest,
    classifier: ClassifierService = Depends(get_classifier_service),
) -> ClassificationResponse:
    """Classify a customer message and return category with next steps.

    This endpoint:
    1. Accepts a customer message from any channel (chat, voice, mail)
    2. Uses AI to classify into: informational, service_action, or safety_compliance
    3. Executes the appropriate workflow for the category
    4. Returns classification result with recommended next steps
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.info(
        "Classification request received",
        extra={
            "request_id": request_id,
            "channel": payload.channel,
            "message_length": len(payload.message),
        },
    )

    try:
        # Classify the message
        result = await classifier.classify(
            message=payload.message,
            channel=payload.channel,
        )

        # Execute the appropriate workflow
        workflow_result = await execute_workflow(
            category=result.category,
            message=payload.message,
            confidence=result.confidence,
            metadata=payload.metadata,
        )

        # Build the response
        next_step = NextStepInfo(
            action=workflow_result.action,
            description=workflow_result.description,
            priority=workflow_result.priority,
            requires_human_review=classifier.requires_human_review(result.confidence),
            external_system=workflow_result.external_system,
        )

        response = ClassificationResponse(
            request_id=request_id,
            category=result.category,
            confidence=result.confidence,
            decision_path=result.reasoning,
            next_step=next_step,
            processing_time_ms=result.processing_time_ms,
            prompt_version=result.prompt_version,
            prompt_variant=result.prompt_variant,
            model=result.model,
        )

        # Record telemetry for DeepEval / Confident AI
        record_classification(
            input_message=payload.message,
            channel=payload.channel,
            response_json=response.model_dump_json(),
        )
        return response

    except ClassificationError as e:
        logger.error(
            "Classification failed",
            extra={"request_id": request_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "classification_failed",
                "message": "Unable to classify message. Please try again later.",
                "request_id": request_id,
            },
        ) from e


@router.post(
    "/classify/voice",
    response_model=ClassificationResponse,
    summary="Classify Customer Voice Message",
    description=(
        "Accept a voice recording, process it with the configured Realtime model, "
        "and classify the resulting message into informational, service_action, or safety_compliance. "
        "Returns the category, confidence score, decision path, and recommended next steps."
    ),
    responses={
        200: {"description": "Successfully classified the voice message"},
        400: {"description": "Invalid audio or metadata"},
        422: {"description": "Validation error in request"},
        500: {"description": "Classification failed"},
        503: {"description": "LLM service unavailable"},
    },
)
@_observe_decorator
async def classify_voice_message(
    request: Request,
    audio_file: UploadFile = File(
        ...,
        description="Audio file containing the customer's voice message (WAV recommended).",
    ),
    metadata: str | None = File(
        default=None,
        description="Optional JSON-encoded metadata about the message context.",
    ),
    classifier: ClassifierService = Depends(get_classifier_service),
) -> ClassificationResponse:
    """Classify a customer voice message by sending audio to the Realtime model."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    logger.info(
        "Voice classification request received",
        extra={
            "request_id": request_id,
            "uploaded_filename": audio_file.filename,
            "content_type": audio_file.content_type,
        },
    )

    # Parse optional metadata JSON
    metadata_dict: dict[str, Any] = {}
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError as e:
            logger.warning(
                "Invalid metadata JSON for voice classification",
                extra={"request_id": request_id, "error": str(e)},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_metadata",
                    "message": "Metadata must be valid JSON.",
                    "request_id": request_id,
                },
            ) from e

    try:
        # Read audio bytes
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "empty_audio",
                    "message": "Uploaded audio file is empty.",
                    "request_id": request_id,
                },
            )

        # Classify the audio (channel is always 'voice' here)
        result = await classifier.classify_audio(
            audio=audio_bytes,
            channel="voice",
        )

        # Execute the appropriate workflow
        workflow_result = await execute_workflow(
            category=result.category,
            message="voice_message",  # We do not expose transcription; message is placeholder
            confidence=result.confidence,
            metadata=metadata_dict,
        )

        # Build the response
        next_step = NextStepInfo(
            action=workflow_result.action,
            description=workflow_result.description,
            priority=workflow_result.priority,
            requires_human_review=classifier.requires_human_review(result.confidence),
            external_system=workflow_result.external_system,
        )

        response = ClassificationResponse(
            request_id=request_id,
            category=result.category,
            confidence=result.confidence,
            decision_path=result.reasoning,
            next_step=next_step,
            processing_time_ms=result.processing_time_ms,
            prompt_version=result.prompt_version,
            prompt_variant=result.prompt_variant,
            model=result.model,
        )
        record_classification(
            input_message="[voice]",
            channel="voice",
            response_json=response.model_dump_json(),
        )
        return response

    except ClassificationError as e:
        error_str = str(e)
        logger.error(
            "Voice classification failed",
            extra={"request_id": request_id, "error": error_str},
        )

        # Check if this is an unsupported format error (client error, not server error)
        if "Unsupported audio format" in error_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "unsupported_audio_format",
                    "message": error_str.split(": ", 1)[-1] if ": " in error_str else error_str,
                    "request_id": request_id,
                    "supported_formats": ["wav"],
                    "hint": "Convert audio to WAV format (mono, 16-bit PCM, 24kHz sample rate)",
                },
            ) from e

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "voice_classification_failed",
                "message": "Unable to process voice message. Please try again later.",
                "request_id": request_id,
            },
        ) from e
