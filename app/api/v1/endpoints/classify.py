"""Classification endpoint."""

from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
import structlog

from app.config import Settings, get_settings
from app.schemas import ClassificationRequest, ClassificationResponse, NextStepInfo
from app.services.classifier import ClassificationError, ClassifierService
from app.workflows import InformationalWorkflow, SafetyComplianceWorkflow, ServiceActionWorkflow
from app.workflows.base import WorkflowResult

logger = structlog.get_logger(__name__)

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

        return ClassificationResponse(
            request_id=request_id,
            category=result.category,
            confidence=result.confidence,
            decision_path=result.reasoning,
            next_step=next_step,
            processing_time_ms=result.processing_time_ms,
            prompt_version=result.prompt_version,
            prompt_variant=result.prompt_variant,
        )

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
