"""Service action category workflow.

Handles messages requesting actions like ticket creation, order tracking, refunds, etc.
"""

import re
from typing import Any

import structlog

from orchestrator.workflows.base import BaseWorkflow, WorkflowResult

logger = structlog.get_logger(__name__)


class ServiceActionWorkflow(BaseWorkflow):
    """Workflow for handling service action requests.

    This workflow:
    1. Extracts the intent and relevant entities from the message
    2. Prepares the action template (ticket, order lookup, etc.)
    3. Returns next steps for the appropriate external system
    """

    @property
    def category(self) -> str:
        return "service_action"

    async def execute(
        self,
        message: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> WorkflowResult:
        """Execute the service action workflow.

        Args:
            message: The customer's service request.
            confidence: Classification confidence score.
            metadata: Additional context including order_id, customer_id, etc.

        Returns:
            WorkflowResult with action details and external system info.
        """
        logger.info(
            "Executing service action workflow",
            message_length=len(message),
            confidence=confidence,
            metadata_keys=list(metadata.keys()),
        )

        # Check if escalation is needed
        if self.requires_escalation(confidence):
            return WorkflowResult(
                action="escalate_to_agent",
                description=(
                    "Low confidence classification. Routing to support agent "
                    "to determine the appropriate action."
                ),
                priority="medium",
                external_system="agent_queue",
                data={"reason": "low_confidence", "original_category": "service_action"},
            )

        # Extract intent from the message
        intent = self._extract_intent(message)

        # Route to appropriate handler based on intent
        handlers = {
            "open_ticket": self._handle_ticket_creation,
            "track_order": self._handle_order_tracking,
            "request_refund": self._handle_refund_request,
            "cancel_order": self._handle_cancellation,
            "update_account": self._handle_account_update,
            "unknown": self._handle_unknown_action,
        }

        handler = handlers.get(intent, self._handle_unknown_action)
        return await handler(message, metadata)

    def _extract_intent(self, message: str) -> str:
        """Extract the action intent from the message.

        Args:
            message: The customer's message.

        Returns:
            Extracted intent string.
        """
        message_lower = message.lower()

        # Intent patterns - ordered by priority
        intent_patterns = [
            (r"\b(cancel|cancellation)\b", "cancel_order"),
            (r"\b(refund|money back|reimburse)\b", "request_refund"),
            (r"\b(track|tracking|where is|status of|order status)\b", "track_order"),
            (r"\b(ticket|support|help|issue|problem|complaint)\b", "open_ticket"),
            (
                r"\b(update|change|modify|reset).*(account|password|profile|address)\b",
                "update_account",
            ),
            (
                r"\b(account|password|profile|address).*(update|change|modify|reset)\b",
                "update_account",
            ),
        ]

        for pattern, intent in intent_patterns:
            if re.search(pattern, message_lower):
                logger.debug("Intent extracted", intent=intent)
                return intent

        return "unknown"

    async def _handle_ticket_creation(
        self, message: str, metadata: dict[str, Any]
    ) -> WorkflowResult:
        """Handle ticket creation requests."""
        # Extract any order or reference numbers
        order_ref = self._extract_order_reference(message) or metadata.get("order_id")

        return WorkflowResult(
            action="create_ticket",
            description=(
                "Creating a support ticket for your issue. "
                "A support representative will contact you within 24 hours."
            ),
            priority="medium",
            external_system="ticketing_system",
            data={
                "ticket_template": {
                    "subject": "Customer Support Request",
                    "description": message[:500],  # Truncate for ticket
                    "order_reference": order_ref,
                    "customer_id": metadata.get("customer_id"),
                    "priority": "normal",
                },
                "estimated_response_time": "24 hours",
            },
        )

    async def _handle_order_tracking(
        self, message: str, metadata: dict[str, Any]
    ) -> WorkflowResult:
        """Handle order tracking requests."""
        order_ref = self._extract_order_reference(message) or metadata.get("order_id")

        if order_ref:
            return WorkflowResult(
                action="track_order",
                description=(
                    f"Looking up order {order_ref}. You will receive tracking information shortly."
                ),
                priority="low",
                external_system="order_management",
                data={
                    "order_reference": order_ref,
                    "action": "get_tracking_info",
                },
            )

        return WorkflowResult(
            action="request_order_id",
            description=(
                "To track your order, please provide your order number. "
                "You can find it in your confirmation email."
            ),
            priority="low",
            external_system=None,
            data={"missing": "order_reference"},
        )

    async def _handle_refund_request(
        self, message: str, metadata: dict[str, Any]
    ) -> WorkflowResult:
        """Handle refund requests."""
        order_ref = self._extract_order_reference(message) or metadata.get("order_id")

        return WorkflowResult(
            action="initiate_refund",
            description=(
                "Your refund request has been received. "
                "Our team will review it within 2-3 business days. "
                "Refunds are processed to the original payment method."
            ),
            priority="medium",
            external_system="refund_system",
            data={
                "refund_request": {
                    "order_reference": order_ref,
                    "reason": message[:200],
                    "status": "pending_review",
                },
            },
        )

    async def _handle_cancellation(self, message: str, metadata: dict[str, Any]) -> WorkflowResult:
        """Handle order cancellation requests."""
        order_ref = self._extract_order_reference(message) or metadata.get("order_id")

        return WorkflowResult(
            action="cancel_order",
            description=(
                "Processing your cancellation request. "
                "If the order hasn't shipped, it will be cancelled immediately. "
                "Otherwise, you may need to initiate a return."
            ),
            priority="high",
            external_system="order_management",
            data={
                "cancellation_request": {
                    "order_reference": order_ref,
                    "status": "pending",
                },
            },
        )

    async def _handle_account_update(
        self, message: str, metadata: dict[str, Any]  # noqa: ARG002
    ) -> WorkflowResult:
        """Handle account update requests."""
        update_type = self._detect_update_type(message)

        return WorkflowResult(
            action="update_account",
            description=(
                f"To update your {update_type}, please verify your identity. "
                "We've sent a verification link to your registered email."
            ),
            priority="medium",
            external_system="identity_verification",
            data={
                "update_type": update_type,
                "requires_verification": True,
            },
        )

    async def _handle_unknown_action(
        self, message: str, metadata: dict[str, Any]  # noqa: ARG002
    ) -> WorkflowResult:
        """Handle unknown service action requests."""
        return WorkflowResult(
            action="route_to_support",
            description=(
                "We're connecting you with a support representative who can help with your request."
            ),
            priority="medium",
            external_system="agent_queue",
            data={
                "reason": "unrecognized_action",
                "original_message": message[:200],
            },
        )

    def _extract_order_reference(self, message: str) -> str | None:
        """Extract order reference number from message."""
        # Common order reference patterns
        patterns = [
            r"\b(ORD[-_]?\d{4,10})\b",  # ORD-12345
            r"\b(ORDER[-_#]?\d{4,10})\b",  # ORDER#12345
            r"#(\d{6,10})\b",  # #123456
            r"\b(\d{8,12})\b",  # Plain long numbers
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return None

    def _detect_update_type(self, message: str) -> str:
        """Detect what type of account update is requested."""
        message_lower = message.lower()

        if "password" in message_lower:
            return "password"
        elif "address" in message_lower:
            return "shipping address"
        elif "email" in message_lower:
            return "email address"
        elif "phone" in message_lower:
            return "phone number"
        elif "payment" in message_lower or "card" in message_lower:
            return "payment method"
        else:
            return "account information"
