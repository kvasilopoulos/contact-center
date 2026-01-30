"""Workflow router: dispatches to the appropriate workflow by category."""

from typing import Any

from app.workflows import InformationalWorkflow, SafetyComplianceWorkflow, ServiceActionWorkflow
from app.workflows.base import WorkflowResult


async def execute_workflow(
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
