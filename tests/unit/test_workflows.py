"""Tests for workflow implementations."""

import pytest

from app.workflows import (
    InformationalWorkflow,
    SafetyComplianceWorkflow,
    ServiceActionWorkflow,
    WorkflowResult,
)


class TestInformationalWorkflow:
    """Tests for the InformationalWorkflow."""

    @pytest.fixture
    def workflow(self) -> InformationalWorkflow:
        return InformationalWorkflow()

    @pytest.mark.asyncio
    async def test_category_property(self, workflow: InformationalWorkflow) -> None:
        """Test workflow category property."""
        assert workflow.category == "informational"

    @pytest.mark.asyncio
    async def test_faq_match_refund(self, workflow: InformationalWorkflow) -> None:
        """Test FAQ match for refund question."""
        result = await workflow.execute(
            message="What is your refund policy?",
            confidence=0.9,
            metadata={},
        )

        assert isinstance(result, WorkflowResult)
        assert result.action == "provide_information"
        assert "refund" in result.description.lower()
        assert result.priority == "low"
        assert result.data is not None
        assert result.data["faq_category"] == "policies"

    @pytest.mark.asyncio
    async def test_faq_match_shipping(self, workflow: InformationalWorkflow) -> None:
        """Test FAQ match for shipping question."""
        result = await workflow.execute(
            message="What are the shipping options?",
            confidence=0.85,
            metadata={},
        )

        assert result.action == "provide_information"
        assert result.data is not None
        assert result.data["faq_category"] == "delivery"

    @pytest.mark.asyncio
    async def test_no_faq_match(self, workflow: InformationalWorkflow) -> None:
        """Test response when no FAQ match found."""
        result = await workflow.execute(
            message="Can you tell me about quantum physics?",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "suggest_contact"
        assert (
            "help center" in result.description.lower() or "support" in result.description.lower()
        )

    @pytest.mark.asyncio
    async def test_low_confidence_escalation(self, workflow: InformationalWorkflow) -> None:
        """Test escalation for low confidence."""
        result = await workflow.execute(
            message="Something unclear",
            confidence=0.3,  # Below threshold
            metadata={},
        )

        assert result.action == "escalate_to_agent"
        assert result.external_system == "agent_queue"
        assert result.priority == "medium"


class TestServiceActionWorkflow:
    """Tests for the ServiceActionWorkflow."""

    @pytest.fixture
    def workflow(self) -> ServiceActionWorkflow:
        return ServiceActionWorkflow()

    @pytest.mark.asyncio
    async def test_category_property(self, workflow: ServiceActionWorkflow) -> None:
        """Test workflow category property."""
        assert workflow.category == "service_action"

    @pytest.mark.asyncio
    async def test_ticket_creation(self, workflow: ServiceActionWorkflow) -> None:
        """Test ticket creation intent."""
        result = await workflow.execute(
            message="I need to open a ticket because my order never arrived",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "create_ticket"
        assert result.external_system == "ticketing_system"
        assert result.priority == "medium"
        assert result.data is not None
        assert "ticket_template" in result.data

    @pytest.mark.asyncio
    async def test_order_tracking_with_ref(self, workflow: ServiceActionWorkflow) -> None:
        """Test order tracking with order reference."""
        result = await workflow.execute(
            message="Where is my order ORD-12345?",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "track_order"
        assert result.external_system == "order_management"
        assert result.data is not None
        assert result.data["order_reference"] == "ORD-12345"

    @pytest.mark.asyncio
    async def test_order_tracking_without_ref(self, workflow: ServiceActionWorkflow) -> None:
        """Test order tracking without order reference."""
        result = await workflow.execute(
            message="Where is my order?",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "request_order_id"
        assert "order number" in result.description.lower()

    @pytest.mark.asyncio
    async def test_refund_request(self, workflow: ServiceActionWorkflow) -> None:
        """Test refund request handling."""
        result = await workflow.execute(
            message="I want a refund for order #123456",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "initiate_refund"
        assert result.external_system == "refund_system"
        assert result.priority == "medium"

    @pytest.mark.asyncio
    async def test_cancellation_request(self, workflow: ServiceActionWorkflow) -> None:
        """Test order cancellation handling."""
        result = await workflow.execute(
            message="Please cancel my order",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "cancel_order"
        assert result.priority == "high"

    @pytest.mark.asyncio
    async def test_account_update_password(self, workflow: ServiceActionWorkflow) -> None:
        """Test password reset request."""
        result = await workflow.execute(
            message="I need to reset my password",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "update_account"
        assert result.data is not None
        assert result.data["update_type"] == "password"
        assert result.data["requires_verification"] is True

    @pytest.mark.asyncio
    async def test_order_reference_from_metadata(self, workflow: ServiceActionWorkflow) -> None:
        """Test order reference from metadata."""
        result = await workflow.execute(
            message="Track my order please",
            confidence=0.9,
            metadata={"order_id": "ORD-789"},
        )

        assert result.action == "track_order"
        assert result.data is not None
        assert result.data["order_reference"] == "ORD-789"

    @pytest.mark.asyncio
    async def test_low_confidence_escalation(self, workflow: ServiceActionWorkflow) -> None:
        """Test escalation for low confidence."""
        result = await workflow.execute(
            message="Help me with something",
            confidence=0.3,
            metadata={},
        )

        assert result.action == "escalate_to_agent"
        assert result.external_system == "agent_queue"


class TestSafetyComplianceWorkflow:
    """Tests for the SafetyComplianceWorkflow."""

    @pytest.fixture
    def workflow(self) -> SafetyComplianceWorkflow:
        return SafetyComplianceWorkflow()

    @pytest.mark.asyncio
    async def test_category_property(self, workflow: SafetyComplianceWorkflow) -> None:
        """Test workflow category property."""
        assert workflow.category == "safety_compliance"

    @pytest.mark.asyncio
    async def test_urgent_severity_emergency(self, workflow: SafetyComplianceWorkflow) -> None:
        """Test urgent severity for emergency."""
        result = await workflow.execute(
            message="I can't breathe after taking the medication, going to ER",
            confidence=0.95,
            metadata={},
        )

        assert result.action == "urgent_escalation"
        assert result.priority == "urgent"
        assert result.external_system == "urgent_escalation_queue"
        assert result.data is not None
        assert result.data["severity"] == "urgent"
        assert result.data["sla_minutes"] == 15

    @pytest.mark.asyncio
    async def test_high_severity_adverse_reaction(self, workflow: SafetyComplianceWorkflow) -> None:
        """Test high severity for adverse reaction."""
        result = await workflow.execute(
            message="I experienced nausea and dizziness after taking the pills",
            confidence=0.9,
            metadata={},
        )

        assert result.action == "pharmacist_review"
        assert result.priority == "high"
        assert result.external_system == "pharmacist_queue"
        assert result.data is not None
        assert result.data["severity"] == "high"
        assert result.data["sla_minutes"] == 120

    @pytest.mark.asyncio
    async def test_standard_severity(self, workflow: SafetyComplianceWorkflow) -> None:
        """Test standard severity for general safety concern."""
        result = await workflow.execute(
            message="I'm not sure if this medication is right for me",
            confidence=0.85,
            metadata={},
        )

        assert result.action == "compliance_review"
        assert result.priority == "high"  # Safety is always high priority
        assert result.external_system == "compliance_review_queue"
        assert result.data is not None
        assert result.data["severity"] == "standard"

    @pytest.mark.asyncio
    async def test_compliance_record_created(self, workflow: SafetyComplianceWorkflow) -> None:
        """Test that compliance record is created."""
        result = await workflow.execute(
            message="I had a reaction to the medication",
            confidence=0.9,
            metadata={"customer_id": "C123"},
        )

        assert result.data is not None
        assert "compliance_record_id" in result.data
        assert result.data["compliance_record_id"].startswith("COMP-")

    @pytest.mark.asyncio
    async def test_pii_redaction(self, workflow: SafetyComplianceWorkflow) -> None:
        """Test that PII is redacted in response."""
        result = await workflow.execute(
            message="My name is John Smith, email john@example.com, had a reaction",
            confidence=0.9,
            metadata={},
        )

        assert result.data is not None
        assert "redacted_summary" in result.data
        assert "john@example.com" not in result.data["redacted_summary"]
        assert "[EMAIL REDACTED]" in result.data["redacted_summary"]

    @pytest.mark.asyncio
    async def test_always_requires_escalation(self, workflow: SafetyComplianceWorkflow) -> None:
        """Test that safety compliance always requires human review."""
        # Even with high confidence, should require escalation
        assert workflow.requires_escalation(0.99) is True
        assert workflow.requires_escalation(0.5) is True
        assert workflow.requires_escalation(0.1) is True
