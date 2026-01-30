"""Classification endpoint."""

import json
import time
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
import structlog

from app.config import Settings, get_settings
from app.schemas import (
    ClassificationRequest,
    ClassificationResponse,
    FeedbackRequest,
    FeedbackResponse,
    NextStepInfo,
)
from app.services.classifier import ClassificationError, ClassifierService
from app.telemetry import record_classification
from app.workflows import InformationalWorkflow, SafetyComplianceWorkflow, ServiceActionWorkflow
from app.workflows.base import WorkflowResult

logger = structlog.get_logger(__name__)

# Optional: wrap handlers with @observe() so production telemetry (Confident AI) gets traces
try:
    from deepeval.tracing import observe as _observe

    _observe_decorator = _observe()
except Exception:

    def _observe_decorator(f):  # no-op when deepeval unavailable
        return f


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
        request_id=request_id,
        channel=payload.channel,
        message_length=len(payload.message),
    )

    try:
        # Classify the message
        result = await classifier.classify(
            message=payload.message,
            channel=payload.channel,
        )

        # Execute the appropriate workflow
        workflow_result = await _execute_workflow(
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
            request_id=request_id,
            error=str(e),
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
        request_id=request_id,
        filename=audio_file.filename,
        content_type=audio_file.content_type,
    )

    # Parse optional metadata JSON
    metadata_dict: dict[str, Any] = {}
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
        except json.JSONDecodeError as e:
            logger.warning(
                "Invalid metadata JSON for voice classification",
                request_id=request_id,
                error=str(e),
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
        workflow_result = await _execute_workflow(
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
            request_id=request_id,
            error=error_str,
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


async def _execute_workflow(
    category: str,
    message: str,
    confidence: float,
    metadata: dict[str, Any],
) -> WorkflowResult:
    """Execute the appropriate workflow based on category.

    Args:
        category: The classified category.
        message: The original message.
        confidence: Classification confidence score.
        metadata: Additional metadata.

    Returns:
        WorkflowResult with next step information.
    """
    workflows = {
        "informational": InformationalWorkflow(),
        "service_action": ServiceActionWorkflow(),
        "safety_compliance": SafetyComplianceWorkflow(),
    }

    workflow = workflows.get(category)
    if workflow is None:
        # Fallback for unknown categories
        return WorkflowResult(
            action="escalate_to_agent",
            description="Unknown category - routing to human agent",
            priority="medium",
            external_system=None,
        )

    return await workflow.execute(
        message=message,
        confidence=confidence,
        metadata=metadata,
    )


# In-memory feedback storage (replace with database in production)
_feedback_store: dict[str, dict[str, Any]] = {}


@router.post(
    "/classify/{request_id}/feedback",
    response_model=FeedbackResponse,
    summary="Submit Classification Feedback",
    description=(
        "Submit feedback on a classification result to help improve model quality. "
        "This feedback is used for continuous evaluation and model improvement."
    ),
    responses={
        200: {"description": "Feedback recorded successfully"},
        404: {"description": "Request ID not found"},
        422: {"description": "Validation error in request"},
    },
)
async def submit_feedback(
    request_id: str,
    feedback: FeedbackRequest,
) -> FeedbackResponse:
    """Submit feedback on a classification result.

    This endpoint allows users to indicate whether a classification was correct
    and optionally provide the expected category if it was incorrect.
    This data is used for:
    - Continuous evaluation metrics
    - Model quality monitoring
    - Identifying areas for prompt improvement
    """
    feedback_id = str(uuid.uuid4())

    # Store feedback (in production, this would go to a database)
    feedback_data = {
        "request_id": request_id,
        "feedback_id": feedback_id,
        "correct": feedback.correct,
        "expected_category": feedback.expected_category,
        "comment": feedback.comment,
        "timestamp": time.time(),
    }
    _feedback_store[request_id] = feedback_data

    # Log feedback for analysis
    logger.info(
        "Classification feedback received",
        request_id=request_id,
        feedback_id=feedback_id,
        correct=feedback.correct,
        expected_category=feedback.expected_category,
    )

    return FeedbackResponse(
        request_id=request_id,
        feedback_id=feedback_id,
        recorded=True,
        message="Feedback recorded successfully. Thank you for helping improve our service.",
    )


@router.get(
    "/classify/{request_id}/feedback",
    response_model=dict[str, Any],
    summary="Get Classification Feedback",
    description="Retrieve feedback submitted for a specific classification request.",
    responses={
        200: {"description": "Feedback retrieved successfully"},
        404: {"description": "No feedback found for this request"},
    },
)
async def get_feedback(request_id: str) -> dict[str, Any]:
    """Retrieve feedback for a classification request."""
    if request_id not in _feedback_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "feedback_not_found",
                "message": f"No feedback found for request {request_id}",
            },
        )
    return _feedback_store[request_id]
