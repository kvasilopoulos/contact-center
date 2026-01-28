"""Circuit breaker pattern implementation for resilient external service calls."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
from types import TracebackType
from typing import Any, TypeVar

import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests are rejected immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str = "Circuit breaker is open", retry_after: float = 0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class CircuitBreaker:
    """Circuit breaker for external service calls.

    Implements the circuit breaker pattern to fail fast when an external service
    is experiencing issues, preventing cascade failures and allowing recovery.

    States:
    - CLOSED: Normal operation. Failures are counted.
    - OPEN: Service is failing. Requests are rejected immediately.
    - HALF_OPEN: Testing recovery. Limited requests are allowed.

    Example:
        ```python
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)


        async def call_external_service():
            async with breaker:
                return await external_api.call()
        ```
    """

    failure_threshold: int = 5  # Failures before opening circuit
    recovery_timeout: float = 30.0  # Seconds before trying again
    half_open_max_calls: int = 3  # Test calls in half-open state
    success_threshold: int = 2  # Successes needed to close circuit

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, transitioning if needed."""
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout
        ):
            self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self.state == CircuitState.OPEN

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0

        logger.info(
            "Circuit breaker state change",
            old_state=old_state.value,
            new_state=new_state.value,
        )

    async def __aenter__(self) -> "CircuitBreaker":
        """Enter the circuit breaker context."""
        await self._before_call()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit the circuit breaker context."""
        if exc_type is None:
            await self._on_success()
        elif exc_val is not None and isinstance(exc_val, Exception):
            await self._on_failure(exc_val)
        return False  # Don't suppress exceptions

    async def _before_call(self) -> None:
        """Check if call is allowed."""
        async with self._lock:
            state = self.state

            if state == CircuitState.OPEN:
                retry_after = self.recovery_timeout - (time.monotonic() - self._last_failure_time)
                raise CircuitBreakerOpen(
                    "Circuit breaker is open - service is unavailable",
                    retry_after=max(0, retry_after),
                )

            if state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpen(
                        "Circuit breaker is half-open - max test calls reached",
                        retry_after=1.0,
                    )
                self._half_open_calls += 1

    async def _on_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _on_failure(self, error: Exception) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            logger.warning(
                "Circuit breaker recorded failure",
                failure_count=self._failure_count,
                threshold=self.failure_threshold,
                error=str(error),
            )

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open returns to open
                self._transition_to(CircuitState.OPEN)
            elif (
                self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold
            ):
                self._transition_to(CircuitState.OPEN)

    async def call(self, func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: Async function to execute.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.

        Returns:
            Result from the function.

        Raises:
            CircuitBreakerOpen: If circuit is open.
            Exception: If the function raises an exception.
        """
        result: T
        async with self:
            result = await func(*args, **kwargs)
        return result

    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._transition_to(CircuitState.CLOSED)
        self._failure_count = 0
        self._last_failure_time = 0.0
        logger.info("Circuit breaker manually reset")

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
