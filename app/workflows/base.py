"""Base workflow interface and common types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class WorkflowResult:
    """Result from a workflow execution."""

    action: str
    description: str
    priority: Literal["low", "medium", "high", "urgent"]
    external_system: str | None = None
    data: dict[str, Any] | None = None


class BaseWorkflow(ABC):
    """Abstract base class for category-specific workflows.

    Each workflow handles the post-classification logic for its category,
    preparing the appropriate next steps and any required data.
    """

    @property
    @abstractmethod
    def category(self) -> str:
        """The category this workflow handles."""
        pass

    @abstractmethod
    async def execute(
        self,
        message: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> WorkflowResult:
        """Execute the workflow for a classified message.

        Args:
            message: The original customer message.
            confidence: Classification confidence score (0.0 to 1.0).
            metadata: Additional context and metadata.

        Returns:
            WorkflowResult with recommended action and next steps.
        """
        pass

    def requires_escalation(self, confidence: float) -> bool:
        """Determine if low confidence requires escalation.

        Args:
            confidence: Classification confidence score.

        Returns:
            True if the message should be escalated to a human agent.
        """
        return confidence < 0.5
