"""Base workflow interface and common types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

ESCALATION_THRESHOLD = 0.5


@dataclass
class WorkflowResult:
    """Result from a workflow execution."""

    action: str
    description: str
    priority: Literal["low", "medium", "high", "urgent"]
    external_system: str | None = None
    data: dict[str, Any] | None = None


class BaseWorkflow(ABC):
    """Base class for category-specific workflows."""

    @property
    @abstractmethod
    def category(self) -> str:
        """The category this workflow handles."""

    @abstractmethod
    async def execute(
        self, message: str, confidence: float, metadata: dict[str, Any]
    ) -> WorkflowResult:
        """Execute the workflow for a classified message."""

    def requires_escalation(self, confidence: float) -> bool:
        """Return True if confidence is below escalation threshold."""
        return confidence < ESCALATION_THRESHOLD
