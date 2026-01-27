"""Informational category workflow.

Handles messages seeking information about policies, products, FAQs, etc.
"""

import re
from typing import Any

import structlog

from orchestrator.workflows.base import BaseWorkflow, WorkflowResult

logger = structlog.get_logger(__name__)


# Mock FAQ/Knowledge Base for demonstration
FAQ_DATABASE = {
    "refund": {
        "question": "What is your refund policy?",
        "answer": (
            "We offer a 30-day refund policy for most products. "
            "Prescription medications cannot be returned once dispensed. "
            "Contact our support team to initiate a refund."
        ),
        "category": "policies",
    },
    "shipping": {
        "question": "What are your shipping options?",
        "answer": (
            "We offer standard shipping (5-7 business days), "
            "express shipping (2-3 business days), and overnight delivery. "
            "Free shipping on orders over $50."
        ),
        "category": "delivery",
    },
    "prescription": {
        "question": "How do I transfer a prescription?",
        "answer": (
            "To transfer a prescription, provide your current pharmacy's information "
            "and prescription details. We'll handle the transfer within 24-48 hours."
        ),
        "category": "prescriptions",
    },
    "hours": {
        "question": "What are your store hours?",
        "answer": (
            "Our online pharmacy is available 24/7. "
            "Customer support is available Monday-Friday 8am-8pm EST, "
            "Saturday 9am-5pm EST."
        ),
        "category": "general",
    },
    "privacy": {
        "question": "What is your privacy policy?",
        "answer": (
            "We take your privacy seriously. Your health information is protected "
            "under HIPAA. We never share your personal data with third parties "
            "without your consent."
        ),
        "category": "policies",
    },
}


class InformationalWorkflow(BaseWorkflow):
    """Workflow for handling informational inquiries.

    This workflow:
    1. Searches the FAQ/knowledge base for relevant information
    2. Returns matched information or suggests contact options
    3. Low confidence queries are flagged for human review
    """

    @property
    def category(self) -> str:
        return "informational"

    async def execute(
        self,
        message: str,
        confidence: float,
        metadata: dict[str, Any],  # noqa: ARG002
    ) -> WorkflowResult:
        """Execute the informational workflow.

        Args:
            message: The customer's question or inquiry.
            confidence: Classification confidence score.
            metadata: Additional context.

        Returns:
            WorkflowResult with information or escalation instructions.
        """
        logger.info(
            "Executing informational workflow",
            message_length=len(message),
            confidence=confidence,
        )

        # Check if escalation is needed due to low confidence
        if self.requires_escalation(confidence):
            return WorkflowResult(
                action="escalate_to_agent",
                description=(
                    "Low confidence classification. Routing to customer service "
                    "representative for personalized assistance."
                ),
                priority="medium",
                external_system="agent_queue",
                data={"reason": "low_confidence", "original_category": "informational"},
            )

        # Search FAQ database for relevant information
        faq_match = self._search_faq(message)

        if faq_match:
            return WorkflowResult(
                action="provide_information",
                description=f"Found relevant FAQ: {faq_match['answer']}",
                priority="low",
                external_system=None,
                data={
                    "faq_category": faq_match["category"],
                    "matched_question": faq_match["question"],
                    "source": "faq_database",
                },
            )

        # No FAQ match - suggest contact options
        return WorkflowResult(
            action="suggest_contact",
            description=(
                "We couldn't find an exact match for your question. "
                "Please contact our support team for personalized assistance, "
                "or browse our help center at help.example.com."
            ),
            priority="low",
            external_system=None,
            data={
                "suggestion": "contact_support",
                "help_center_url": "https://help.example.com",
            },
        )

    def _search_faq(self, message: str) -> dict[str, Any] | None:
        """Search the FAQ database for relevant information.

        Args:
            message: The customer's message to search for.

        Returns:
            Matching FAQ entry or None if no match found.
        """
        message_lower = message.lower()

        # Simple keyword matching for demonstration
        # In production, this would use semantic search or a proper search engine
        for keyword, faq_entry in FAQ_DATABASE.items():
            if keyword in message_lower:
                logger.debug("FAQ match found", keyword=keyword)
                return faq_entry

        # Check for common patterns
        patterns = [
            (r"\bpolicy\b", "refund"),
            (r"\bdeliver", "shipping"),
            (r"\bship", "shipping"),
            (r"\bhour", "hours"),
            (r"\bopen\b", "hours"),
            (r"\bprivate\b", "privacy"),
            (r"\btransfer\b", "prescription"),
        ]

        for pattern, faq_key in patterns:
            if re.search(pattern, message_lower):
                return FAQ_DATABASE.get(faq_key)

        return None
