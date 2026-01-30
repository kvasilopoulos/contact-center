"""Tests for PII redaction utilities."""

import pytest

from app.utils.pii_redaction import PIIRedactor, PIIType, contains_pii, redact_pii


class TestPIIRedactor:
    """Tests for PIIRedactor class."""

    @pytest.fixture
    def redactor(self) -> PIIRedactor:
        """Create a PIIRedactor instance."""
        return PIIRedactor()

    def test_detect_ssn_with_dashes(self, redactor: PIIRedactor) -> None:
        """Test SSN detection with dashes."""
        text = "My SSN is 123-45-6789"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.SSN
        assert matches[0].original == "123-45-6789"

    def test_detect_ssn_without_dashes(self, redactor: PIIRedactor) -> None:
        """Test SSN detection without dashes."""
        text = "SSN: 123456789"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.SSN
        assert matches[0].original == "123456789"

    def test_detect_email(self, redactor: PIIRedactor) -> None:
        """Test email detection."""
        text = "Contact me at john.doe@example.com"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.EMAIL
        assert matches[0].original == "john.doe@example.com"

    def test_detect_phone_with_country_code(self, redactor: PIIRedactor) -> None:
        """Test phone number detection with country code."""
        text = "Call me at +1-555-123-4567"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.PHONE

    def test_detect_phone_parentheses(self, redactor: PIIRedactor) -> None:
        """Test phone number detection with parentheses."""
        text = "Phone: (555) 123-4567"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.PHONE

    def test_detect_credit_card_visa(self, redactor: PIIRedactor) -> None:
        """Test Visa credit card detection."""
        text = "Card: 4111-1111-1111-1111"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.CREDIT_CARD

    def test_detect_credit_card_amex(self, redactor: PIIRedactor) -> None:
        """Test Amex credit card detection."""
        text = "Amex: 3782 822463 10005"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.CREDIT_CARD

    def test_detect_ip_address(self, redactor: PIIRedactor) -> None:
        """Test IP address detection."""
        text = "Server IP: 192.168.1.1"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.IP_ADDRESS
        assert matches[0].original == "192.168.1.1"

    def test_detect_dob(self, redactor: PIIRedactor) -> None:
        """Test date of birth detection."""
        text = "DOB: 01/15/1990"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.DATE_OF_BIRTH

    def test_detect_medical_record(self, redactor: PIIRedactor) -> None:
        """Test medical record number detection."""
        text = "MRN: ABC123456"
        matches = redactor.detect(text)
        assert len(matches) == 1
        assert matches[0].pii_type == PIIType.MEDICAL_RECORD

    def test_redact_single_pii(self, redactor: PIIRedactor) -> None:
        """Test redaction of a single PII."""
        text = "My email is test@example.com"
        redacted, matches = redactor.redact(text)
        assert redacted == "My email is [EMAIL_REDACTED]"
        assert len(matches) == 1

    def test_redact_multiple_pii(self, redactor: PIIRedactor) -> None:
        """Test redaction of multiple PII types."""
        text = "Contact: test@example.com, Phone: 555-123-4567, SSN: 123-45-6789"
        redacted, matches = redactor.redact(text)
        assert "[EMAIL_REDACTED]" in redacted
        assert "[PHONE_REDACTED]" in redacted
        assert "[SSN_REDACTED]" in redacted
        assert len(matches) == 3
        # Original PII should not be present
        assert "test@example.com" not in redacted
        assert "555-123-4567" not in redacted
        assert "123-45-6789" not in redacted

    def test_redact_preserves_non_pii_text(self, redactor: PIIRedactor) -> None:
        """Test that non-PII text is preserved."""
        text = "Hello, my email is user@test.com and I need help."
        redacted, _ = redactor.redact(text)
        assert "Hello," in redacted
        assert "and I need help." in redacted
        assert "[EMAIL_REDACTED]" in redacted

    def test_redact_no_pii(self, redactor: PIIRedactor) -> None:
        """Test text with no PII."""
        text = "This is a normal message with no sensitive data."
        redacted, matches = redactor.redact(text)
        assert redacted == text
        assert len(matches) == 0

    def test_redact_for_logging(self, redactor: PIIRedactor) -> None:
        """Test redact_for_logging convenience method."""
        text = "SSN: 123-45-6789"
        redacted = redactor.redact_for_logging(text)
        assert redacted == "SSN: [SSN_REDACTED]"

    def test_contains_pii_true(self, redactor: PIIRedactor) -> None:
        """Test contains_pii returns True when PII is present."""
        assert redactor.contains_pii("Email: test@example.com")
        assert redactor.contains_pii("SSN: 123-45-6789")
        assert redactor.contains_pii("Phone: 555-123-4567")

    def test_contains_pii_false(self, redactor: PIIRedactor) -> None:
        """Test contains_pii returns False when no PII is present."""
        assert not redactor.contains_pii("Hello, this is a test message.")
        assert not redactor.contains_pii("Order #12345 has been shipped.")


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_redact_pii_function(self) -> None:
        """Test redact_pii convenience function."""
        text = "Contact: user@example.com"
        result = redact_pii(text)
        assert result == "Contact: [EMAIL_REDACTED]"

    def test_contains_pii_function(self) -> None:
        """Test contains_pii convenience function."""
        assert contains_pii("Email: test@test.com")
        assert not contains_pii("No PII here")


class TestEdgeCases:
    """Tests for edge cases and complex scenarios."""

    @pytest.fixture
    def redactor(self) -> PIIRedactor:
        """Create a PIIRedactor instance."""
        return PIIRedactor()

    def test_multiple_same_type_pii(self, redactor: PIIRedactor) -> None:
        """Test multiple instances of the same PII type."""
        text = "Emails: a@b.com and c@d.com"
        redacted, matches = redactor.redact(text)
        assert redacted.count("[EMAIL_REDACTED]") == 2
        assert len(matches) == 2

    def test_adjacent_pii(self, redactor: PIIRedactor) -> None:
        """Test PII that appears adjacent to each other."""
        text = "123-45-6789 test@example.com"
        redacted, matches = redactor.redact(text)
        assert "[SSN_REDACTED]" in redacted
        assert "[EMAIL_REDACTED]" in redacted

    def test_pii_in_context(self, redactor: PIIRedactor) -> None:
        """Test PII detection in realistic context."""
        text = (
            "Patient John Doe (MRN: PAT123456) reported an adverse reaction. "
            "Contact: john.doe@email.com, Phone: (555) 987-6543. "
            "DOB: 03/15/1985. Please review urgently."
        )
        redacted, matches = redactor.redact(text)
        # PII should be redacted
        assert "PAT123456" not in redacted
        assert "john.doe@email.com" not in redacted
        assert "(555) 987-6543" not in redacted
        # Non-PII should be preserved
        assert "Patient John Doe" in redacted
        assert "reported an adverse reaction" in redacted
        assert "Please review urgently" in redacted

    def test_empty_string(self, redactor: PIIRedactor) -> None:
        """Test empty string input."""
        redacted, matches = redactor.redact("")
        assert redacted == ""
        assert len(matches) == 0

    def test_unicode_text(self, redactor: PIIRedactor) -> None:
        """Test text with unicode characters."""
        text = "Email: test@example.com, Message: Hello 你好 مرحبا"
        redacted, matches = redactor.redact(text)
        assert "[EMAIL_REDACTED]" in redacted
        assert "你好" in redacted
        assert "مرحبا" in redacted
