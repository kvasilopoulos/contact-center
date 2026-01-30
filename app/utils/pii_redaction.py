"""PII (Personally Identifiable Information) detection and redaction utilities.

This module provides functionality to detect and redact sensitive information
from text to ensure compliance with data protection regulations.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import ClassVar

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected and redacted."""

    SSN = "ssn"
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    MEDICAL_RECORD = "medical_record"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"


@dataclass
class PIIMatch:
    """Represents a detected PII match."""

    pii_type: PIIType
    original: str
    start: int
    end: int
    redacted: str


@dataclass
class PIIRedactor:
    """Detects and redacts PII from text.

    This class uses regex patterns to identify common PII types and replaces
    them with redaction placeholders while preserving text structure.

    Example:
        >>> redactor = PIIRedactor()
        >>> text = "Contact me at john@example.com or 555-123-4567"
        >>> redacted, matches = redactor.redact(text)
        >>> print(redacted)
        "Contact me at [EMAIL_REDACTED] or [PHONE_REDACTED]"
    """

    # Redaction placeholders
    REDACTION_PLACEHOLDERS: ClassVar[dict[PIIType, str]] = {
        PIIType.SSN: "[SSN_REDACTED]",
        PIIType.EMAIL: "[EMAIL_REDACTED]",
        PIIType.PHONE: "[PHONE_REDACTED]",
        PIIType.CREDIT_CARD: "[CREDIT_CARD_REDACTED]",
        PIIType.DATE_OF_BIRTH: "[DOB_REDACTED]",
        PIIType.IP_ADDRESS: "[IP_REDACTED]",
        PIIType.MEDICAL_RECORD: "[MRN_REDACTED]",
        PIIType.PASSPORT: "[PASSPORT_REDACTED]",
        PIIType.DRIVER_LICENSE: "[DL_REDACTED]",
    }

    # Regex patterns for PII detection (compiled for performance)
    _patterns: dict[PIIType, re.Pattern[str]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Compile regex patterns for PII detection."""
        self._patterns = {
            # US Social Security Number: XXX-XX-XXXX or XXXXXXXXX
            PIIType.SSN: re.compile(
                r"\b(?:\d{3}-\d{2}-\d{4}|\d{9})\b",
                re.IGNORECASE,
            ),
            # Email addresses
            PIIType.EMAIL: re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                re.IGNORECASE,
            ),
            # US Phone numbers (various formats)
            PIIType.PHONE: re.compile(
                r"\b(?:\+?1[-.\s]?)?"  # Optional country code
                r"(?:\(?\d{3}\)?[-.\s]?)"  # Area code
                r"\d{3}[-.\s]?\d{4}\b",  # Number
                re.IGNORECASE,
            ),
            # Credit card numbers (major card types)
            PIIType.CREDIT_CARD: re.compile(
                r"\b(?:"
                r"4\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}|"  # Visa
                r"5[1-5]\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}|"  # Mastercard
                r"3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}|"  # Amex
                r"6(?:011|5\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}"  # Discover
                r")\b",
                re.IGNORECASE,
            ),
            # Date of birth patterns (MM/DD/YYYY, DD-MM-YYYY, etc.)
            PIIType.DATE_OF_BIRTH: re.compile(
                r"\b(?:DOB|Date of Birth|Born|Birthday)[:.\s]*"
                r"(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b",
                re.IGNORECASE,
            ),
            # IPv4 addresses
            PIIType.IP_ADDRESS: re.compile(
                r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
                r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
            ),
            # Medical Record Numbers (common formats)
            PIIType.MEDICAL_RECORD: re.compile(
                r"\b(?:MRN|Medical Record|Patient ID)[:.\s#]*[A-Z0-9]{6,12}\b",
                re.IGNORECASE,
            ),
            # Passport numbers (US format)
            PIIType.PASSPORT: re.compile(
                r"\b(?:Passport)[:.\s#]*[A-Z0-9]{6,9}\b",
                re.IGNORECASE,
            ),
            # Driver's License (generic format)
            PIIType.DRIVER_LICENSE: re.compile(
                r"\b(?:DL|Driver'?s?\s*License|License\s*#?)[:.\s]*[A-Z0-9]{5,15}\b",
                re.IGNORECASE,
            ),
        }

    def detect(self, text: str) -> list[PIIMatch]:
        """Detect all PII in the given text.

        Args:
            text: The text to scan for PII.

        Returns:
            List of PIIMatch objects representing detected PII.
        """
        matches: list[PIIMatch] = []

        for pii_type, pattern in self._patterns.items():
            for match in pattern.finditer(text):
                matches.append(
                    PIIMatch(
                        pii_type=pii_type,
                        original=match.group(),
                        start=match.start(),
                        end=match.end(),
                        redacted=self.REDACTION_PLACEHOLDERS[pii_type],
                    )
                )

        # Sort by position (end to start for safe replacement)
        matches.sort(key=lambda m: m.start, reverse=True)
        return matches

    def redact(self, text: str) -> tuple[str, list[PIIMatch]]:
        """Detect and redact all PII in the given text.

        Args:
            text: The text to redact PII from.

        Returns:
            Tuple of (redacted_text, list of PIIMatch objects).
        """
        matches = self.detect(text)
        redacted_text = text

        # Replace from end to start to preserve positions
        for match in matches:
            redacted_text = (
                redacted_text[: match.start] + match.redacted + redacted_text[match.end :]
            )

        if matches:
            logger.info(
                "PII redacted from text",
                extra={
                    "pii_types": [m.pii_type.value for m in matches],
                    "count": len(matches),
                },
            )

        return redacted_text, matches

    def redact_for_logging(self, text: str) -> str:
        """Redact PII for safe logging.

        This is a convenience method that only returns the redacted text.

        Args:
            text: The text to redact PII from.

        Returns:
            The redacted text.
        """
        redacted_text, _ = self.redact(text)
        return redacted_text

    def contains_pii(self, text: str) -> bool:
        """Check if text contains any PII.

        Args:
            text: The text to check.

        Returns:
            True if PII is detected, False otherwise.
        """
        return any(pattern.search(text) for pattern in self._patterns.values())


# Singleton holder to avoid global statement
_default_redactor_holder: list[PIIRedactor | None] = [None]


def get_redactor() -> PIIRedactor:
    """Get the default PIIRedactor instance (singleton)."""
    if _default_redactor_holder[0] is None:
        _default_redactor_holder[0] = PIIRedactor()
    return _default_redactor_holder[0]


def redact_pii(text: str) -> str:
    """Convenience function to redact PII from text.

    Args:
        text: The text to redact PII from.

    Returns:
        The redacted text.
    """
    return get_redactor().redact_for_logging(text)


def contains_pii(text: str) -> bool:
    """Convenience function to check if text contains PII.

    Args:
        text: The text to check.

    Returns:
        True if PII is detected, False otherwise.
    """
    return get_redactor().contains_pii(text)
