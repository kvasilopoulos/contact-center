"""Workflow router: dispatches to the appropriate workflow by category."""

from typing import Any

from app.workflows import InformationalWorkflow, SafetyComplianceWorkflow, ServiceActionWorkflow
from app.workflows.base import WorkflowResult

# Singleton workflow instances
_workflows = {
    "informational": InformationalWorkflow(),
    "service_action": ServiceActionWorkflow(),
    "safety_compliance": SafetyComplianceWorkflow(),
}


async def execute_workflow(
    category: str,
    message: str,
    confidence: float,
    metadata: dict[str, Any],
) -> WorkflowResult:
    """Execute the appropriate workflow based on category."""
    workflow = _workflows.get(category)
    if workflow is None:
        return WorkflowResult(
            action="escalate_to_agent",
            description="Unknown category - routing to human agent",
            priority="medium",
        )

    return await workflow.execute(message, confidence, metadata)
