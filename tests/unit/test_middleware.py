"""Tests for middleware components."""

import asyncio
import time

import pytest

from orchestrator.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, CircuitState
from orchestrator.middleware.rate_limit import TokenBucket


class TestTokenBucket:
    """Tests for the TokenBucket rate limiter."""

    def test_initial_capacity(self) -> None:
        """Test that bucket starts with full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.available_tokens == 10

    def test_consume_tokens(self) -> None:
        """Test consuming tokens from bucket."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)

        assert bucket.consume(1) is True
        assert bucket.available_tokens == 9

        assert bucket.consume(5) is True
        assert bucket.available_tokens == 4

    def test_consume_fails_when_empty(self) -> None:
        """Test that consume fails when not enough tokens."""
        bucket = TokenBucket(capacity=2, refill_rate=0.1)

        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False  # Bucket empty

    def test_refill_over_time(self) -> None:
        """Test that tokens refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)  # 100 tokens/sec

        bucket.consume(10)  # Empty the bucket
        assert bucket.available_tokens < 1

        time.sleep(0.05)  # Wait 50ms

        # Should have refilled ~5 tokens (100 * 0.05)
        tokens = bucket.available_tokens
        assert tokens >= 4
        assert tokens <= 7  # Allow some timing tolerance

    def test_capacity_limit(self) -> None:
        """Test that tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=100.0)

        time.sleep(0.1)  # Wait for potential overfill

        assert bucket.available_tokens <= 10


class TestCircuitBreaker:
    """Tests for the CircuitBreaker."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        """Create a circuit breaker for testing."""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.1,  # 100ms for fast tests
            half_open_max_calls=2,
            success_threshold=2,
        )

    def test_initial_state_closed(self, breaker: CircuitBreaker) -> None:
        """Test that circuit starts closed."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True
        assert breaker.is_open is False

    @pytest.mark.asyncio
    async def test_success_keeps_closed(self, breaker: CircuitBreaker) -> None:
        """Test that successful calls keep circuit closed."""
        async with breaker:
            pass  # Simulate success

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failures_open_circuit(self, breaker: CircuitBreaker) -> None:
        """Test that failures open the circuit."""
        for _ in range(3):  # failure_threshold = 3
            try:
                async with breaker:
                    raise ValueError("Simulated failure")
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self, breaker: CircuitBreaker) -> None:
        """Test that open circuit rejects calls."""
        # Open the circuit
        for _ in range(3):
            try:
                async with breaker:
                    raise ValueError("Simulated failure")
            except ValueError:
                pass

        # Try to call - should be rejected
        with pytest.raises(CircuitBreakerOpen):
            async with breaker:
                pass

    @pytest.mark.asyncio
    async def test_recovery_to_half_open(self, breaker: CircuitBreaker) -> None:
        """Test that circuit transitions to half-open after timeout."""
        # Open the circuit
        for _ in range(3):
            try:
                async with breaker:
                    raise ValueError("Simulated failure")
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Should now be half-open
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes(self, breaker: CircuitBreaker) -> None:
        """Test that successes in half-open state close the circuit."""
        # Open the circuit
        for _ in range(3):
            try:
                async with breaker:
                    raise ValueError("Simulated failure")
            except ValueError:
                pass

        # Wait for recovery
        await asyncio.sleep(0.15)

        # Successful calls in half-open
        for _ in range(2):  # success_threshold = 2
            async with breaker:
                pass

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self, breaker: CircuitBreaker) -> None:
        """Test that failure in half-open state reopens circuit."""
        # Open the circuit
        for _ in range(3):
            try:
                async with breaker:
                    raise ValueError("Simulated failure")
            except ValueError:
                pass

        # Wait for recovery
        await asyncio.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # Fail in half-open
        try:
            async with breaker:
                raise ValueError("Failure in half-open")
        except ValueError:
            pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_call_method(self, breaker: CircuitBreaker) -> None:
        """Test the call() convenience method."""

        async def success_func() -> str:
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"

    def test_reset(self, breaker: CircuitBreaker) -> None:
        """Test manual reset."""
        breaker._failure_count = 5
        breaker._state = CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    def test_get_stats(self, breaker: CircuitBreaker) -> None:
        """Test getting circuit breaker statistics."""
        stats = breaker.get_stats()

        assert "state" in stats
        assert "failure_count" in stats
        assert "failure_threshold" in stats
        assert stats["state"] == "closed"

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_exception_has_retry_after(
        self, breaker: CircuitBreaker
    ) -> None:
        """Test that CircuitBreakerOpen includes retry_after."""
        # Open the circuit
        for _ in range(3):
            try:
                async with breaker:
                    raise ValueError("Simulated failure")
            except ValueError:
                pass

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            async with breaker:
                pass

        assert exc_info.value.retry_after >= 0
