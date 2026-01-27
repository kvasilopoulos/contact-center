"""Safety compliance category workflow.

Handles messages involving health/safety concerns, adverse reactions, and medical issues.
These require special handling for regulatory compliance.
"""

from datetime import datetime
import hashlib
import re
from typing import Any, ClassVar

import structlog

from orchestrator.workflows.base import BaseWorkflow, WorkflowResult

logger = structlog.get_logger(__name__)


class SafetyComplianceWorkflow(BaseWorkflow):
    """Workflow for handling safety and compliance-related messages.

    This workflow:
    1. Flags the message as urgent for compliance review
    2. Creates an audit trail entry
    3. Redacts PII for logging purposes
    4. Routes to appropriate escalation queue

    IMPORTANT: Safety compliance messages are always treated as high priority
    and require human review regardless of confidence score.
    """

    @property
    def category(self) -> str:
        return "safety_compliance"

    # Patterns indicating severity levels
    URGENT_PATTERNS: ClassVar[list[str]] = [
        r"\b(emergency|ER|hospital|ambulance|911)\b",
        r"\b(can't breathe|difficulty breathing|chest pain)\b",
        r"\b(unconscious|passed out|fainted)\b",
        r"\b(severe allergic|anaphylaxis|swelling.*throat)\b",
        r"\b(overdose|too many|too much)\b",
    ]

    HIGH_PRIORITY_PATTERNS: ClassVar[list[str]] = [
        r"\b(adverse|reaction|side effect)\b",
        r"\b(nausea|vomiting|dizziness|headache)\b",
        r"\b(rash|hives|itching)\b",
        r"\b(medication|drug|medicine).*(problem|issue|concern)\b",
    ]

    async def execute(
        self,
        message: str,
        confidence: float,
        metadata: dict[str, Any],
    ) -> WorkflowResult:
        """Execute the safety compliance workflow.

        Args:
            message: The customer's message with safety/health concerns.
            confidence: Classification confidence score.
            metadata: Additional context.

        Returns:
            WorkflowResult with compliance handling instructions.
        """
        logger.warning(
            "Safety compliance workflow triggered",
            message_hash=self._hash_message(message),
            confidence=confidence,
        )

        # Determine severity
        severity = self._assess_severity(message)

        # Create compliance record (audit trail)
        compliance_record = self._create_compliance_record(
            message=message,
            severity=severity,
            metadata=metadata,
        )

        # Log to compliance system (stub - in production, this would be a real system)
        await self._log_to_compliance_system(compliance_record)

        # Redact PII for response
        redacted_summary = self._redact_pii(message[:200])

        if severity == "urgent":
            return WorkflowResult(
                action="urgent_escalation",
                description=(
                    "URGENT: Your message indicates a potential medical emergency. "
                    "If you are experiencing a medical emergency, please call 911 immediately. "
                    "A pharmacist will contact you within 15 minutes for follow-up."
                ),
                priority="urgent",
                external_system="urgent_escalation_queue",
                data={
                    "compliance_record_id": compliance_record["id"],
                    "severity": severity,
                    "requires_pharmacist_review": True,
                    "sla_minutes": 15,
                    "redacted_summary": redacted_summary,
                },
            )

        elif severity == "high":
            return WorkflowResult(
                action="pharmacist_review",
                description=(
                    "We take adverse reactions very seriously. "
                    "Your report has been flagged for pharmacist review. "
                    "A healthcare professional will contact you within 2 hours."
                ),
                priority="high",
                external_system="pharmacist_queue",
                data={
                    "compliance_record_id": compliance_record["id"],
                    "severity": severity,
                    "requires_pharmacist_review": True,
                    "sla_minutes": 120,
                    "redacted_summary": redacted_summary,
                },
            )

        else:
            return WorkflowResult(
                action="compliance_review",
                description=(
                    "Thank you for reporting this. Your concern has been logged "
                    "and will be reviewed by our compliance team within 24 hours. "
                    "If symptoms worsen, please seek medical attention."
                ),
                priority="high",
                external_system="compliance_review_queue",
                data={
                    "compliance_record_id": compliance_record["id"],
                    "severity": severity,
                    "requires_pharmacist_review": False,
                    "sla_hours": 24,
                    "redacted_summary": redacted_summary,
                },
            )

    def _assess_severity(self, message: str) -> str:
        """Assess the severity of the safety concern.

        Args:
            message: The customer's message.

        Returns:
            Severity level: 'urgent', 'high', or 'standard'.
        """
        message_lower = message.lower()

        # Check for urgent patterns
        for pattern in self.URGENT_PATTERNS:
            if re.search(pattern, message_lower):
                logger.warning("Urgent safety concern detected")
                return "urgent"

        # Check for high priority patterns
        for pattern in self.HIGH_PRIORITY_PATTERNS:
            if re.search(pattern, message_lower):
                return "high"

        return "standard"

    def _create_compliance_record(
        self,
        message: str,
        severity: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a compliance/audit record.

        Args:
            message: The original message.
            severity: Assessed severity level.
            metadata: Additional context.

        Returns:
            Compliance record dictionary.
        """
        record_id = (
            f"COMP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self._hash_message(message)[:8]}"
        )

        return {
            "id": record_id,
            "timestamp": datetime.utcnow().isoformat(),
            "category": "safety_compliance",
            "severity": severity,
            "message_hash": self._hash_message(message),
            "message_length": len(message),
            "channel": metadata.get("channel", "unknown"),
            "customer_id": metadata.get("customer_id"),
            "product_id": metadata.get("product_id"),
            "requires_fda_report": severity in ("urgent", "high"),
            "status": "pending_review",
        }

    async def _log_to_compliance_system(self, record: dict[str, Any]) -> None:
        """Log the compliance record to the compliance system.

        In production, this would integrate with a real compliance/audit system.

        Args:
            record: The compliance record to log.
        """
        # Stub implementation - in production, this would:
        # 1. Write to a secure, immutable audit log
        # 2. Potentially notify compliance officers
        # 3. Create FDA adverse event report if required
        logger.info(
            "Compliance record created",
            record_id=record["id"],
            severity=record["severity"],
            requires_fda_report=record["requires_fda_report"],
        )

    def _hash_message(self, message: str) -> str:
        """Create a hash of the message for audit purposes.

        Args:
            message: The message to hash.

        Returns:
            SHA-256 hash of the message.
        """
        return hashlib.sha256(message.encode()).hexdigest()

    def _redact_pii(self, text: str) -> str:
        """Redact personally identifiable information from text.

        Args:
            text: Text potentially containing PII.

        Returns:
            Text with PII redacted.
        """
        # Email addresses
        text = re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b", "[EMAIL REDACTED]", text)

        # Phone numbers (various formats)
        text = re.sub(
            r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "[PHONE REDACTED]",
            text,
        )

        # SSN
        text = re.sub(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", "[SSN REDACTED]", text)

        # Credit card numbers (basic pattern)
        text = re.sub(r"\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b", "[CARD REDACTED]", text)

        # Names after common prefixes (basic)
        text = re.sub(
            r"\b(Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b",
            r"\1 [NAME REDACTED]",
            text,
        )

        return text

    def requires_escalation(self, confidence: float) -> bool:  # noqa: ARG002
        """Safety compliance always requires human review.

        Args:
            confidence: Classification confidence score.

        Returns:
            Always True for safety compliance.
        """
        return True  # Safety compliance always needs human review
