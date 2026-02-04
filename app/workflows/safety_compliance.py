"""Safety compliance workflow: handles health concerns and adverse reactions."""

from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import Any, ClassVar

from app.utils.pii_redaction import redact_pii
from app.workflows.base import BaseWorkflow, WorkflowResult

logger = logging.getLogger(__name__)


class SafetyComplianceWorkflow(BaseWorkflow):
    """Routes safety concerns to compliance review. Always requires human review."""

    @property
    def category(self) -> str:
        return "safety_compliance"

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
        self, message: str, confidence: float, metadata: dict[str, Any]
    ) -> WorkflowResult:
        logger.warning(
            "Safety compliance workflow triggered",
            extra={
                "message_hash": self._hash_message(message),
                "confidence": confidence,
            },
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
        redacted_summary = redact_pii(message[:200])

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
        """Return 'urgent', 'high', or 'standard' based on message patterns."""
        message_lower = message.lower()

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
        self, message: str, severity: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Create audit trail record for compliance tracking."""
        record_id = f"COMP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._hash_message(message)[:8]}"

        return {
            "id": record_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        """Log compliance record to audit system."""
        logger.info(
            "Compliance record created",
            extra={
                "record_id": record["id"],
                "severity": record["severity"],
                "requires_fda_report": record["requires_fda_report"],
            },
        )

    def _hash_message(self, message: str) -> str:
        """Create a hash of the message for audit purposes."""
        return hashlib.sha256(message.encode()).hexdigest()

    def requires_escalation(self, confidence: float) -> bool:  # noqa: ARG002
        """Safety compliance always requires human review."""
        return True
