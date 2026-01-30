"""Load testing with Locust for the Cost Center AI Orchestrator.

Run with:
    locust -f tests/load/locustfile.py --host http://localhost:8000

Or for headless mode:
    locust -f tests/load/locustfile.py --host http://localhost:8000 \
        --users 10 --spawn-rate 2 --run-time 60s --headless

Web UI available at http://localhost:8089 when running in normal mode.
"""

import random

from locust import HttpUser, between, task

# Sample messages for each category
INFORMATIONAL_MESSAGES = [
    "What is your refund policy?",
    "How do I track my order?",
    "What are your business hours?",
    "Do you offer international shipping?",
    "What payment methods do you accept?",
    "Can I change my delivery address?",
    "What is the warranty period for products?",
    "How do I reset my password?",
]

SERVICE_ACTION_MESSAGES = [
    "I need to cancel my order #12345",
    "I want to return this product",
    "Please process a refund for my purchase",
    "I need to update my shipping address",
    "Can you help me change my subscription?",
    "I'd like to open a support ticket",
    "My order hasn't arrived yet",
    "I need to speak with a manager",
]

SAFETY_COMPLIANCE_MESSAGES = [
    "I experienced a severe headache after taking the medication",
    "The product caused an allergic reaction",
    "I'm having side effects from the treatment",
    "My child accidentally ingested this product",
    "I noticed the product was contaminated",
    "I feel dizzy after using your supplement",
    "The medication is making me nauseous",
    "I had a bad reaction to the prescription",
]

ALL_MESSAGES = INFORMATIONAL_MESSAGES + SERVICE_ACTION_MESSAGES + SAFETY_COMPLIANCE_MESSAGES


class ClassificationUser(HttpUser):
    """Simulates a user making classification requests."""

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    @task(10)
    def classify_random_message(self) -> None:
        """Send a random classification request."""
        message = random.choice(ALL_MESSAGES)
        channel = random.choice(["chat", "mail"])

        self.client.post(
            "/api/v1/classify",
            json={
                "message": message,
                "channel": channel,
                "metadata": {"load_test": True},
            },
            name="/api/v1/classify",
        )

    @task(5)
    def classify_informational(self) -> None:
        """Send an informational classification request."""
        message = random.choice(INFORMATIONAL_MESSAGES)

        self.client.post(
            "/api/v1/classify",
            json={
                "message": message,
                "channel": "chat",
            },
            name="/api/v1/classify [informational]",
        )

    @task(3)
    def classify_service_action(self) -> None:
        """Send a service action classification request."""
        message = random.choice(SERVICE_ACTION_MESSAGES)

        self.client.post(
            "/api/v1/classify",
            json={
                "message": message,
                "channel": "mail",
            },
            name="/api/v1/classify [service_action]",
        )

    @task(2)
    def classify_safety_compliance(self) -> None:
        """Send a safety compliance classification request."""
        message = random.choice(SAFETY_COMPLIANCE_MESSAGES)

        self.client.post(
            "/api/v1/classify",
            json={
                "message": message,
                "channel": "voice",
            },
            name="/api/v1/classify [safety_compliance]",
        )

    @task(1)
    def health_check(self) -> None:
        """Check the health endpoint."""
        self.client.get("/api/v1/health", name="/api/v1/health")

    @task(1)
    def readiness_check(self) -> None:
        """Check the readiness endpoint."""
        self.client.get("/api/v1/ready", name="/api/v1/ready")


class HighVolumeUser(HttpUser):
    """Simulates a high-volume API user (for burst testing)."""

    wait_time = between(0.1, 0.5)  # Very short wait times
    weight = 1  # Lower weight than ClassificationUser

    @task
    def rapid_classification(self) -> None:
        """Send rapid classification requests to test rate limiting."""
        message = random.choice(ALL_MESSAGES)

        response = self.client.post(
            "/api/v1/classify",
            json={
                "message": message,
                "channel": "chat",
            },
            name="/api/v1/classify [burst]",
        )

        # Track rate limit responses
        if response.status_code == 429:
            # This is expected behavior under high load
            pass


class MetricsUser(HttpUser):
    """User that monitors metrics endpoint."""

    wait_time = between(5, 10)
    weight = 1

    @task
    def scrape_metrics(self) -> None:
        """Scrape Prometheus metrics."""
        self.client.get("/metrics", name="/metrics")
