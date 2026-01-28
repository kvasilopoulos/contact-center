"""Rate limiting middleware using token bucket algorithm."""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import time

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TokenBucket:
    """Token bucket for rate limiting.

    Implements the token bucket algorithm where tokens are added at a fixed rate
    and consumed on each request. Requests are rejected when the bucket is empty.
    """

    capacity: float  # Maximum tokens in bucket
    refill_rate: float  # Tokens added per second
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = self.capacity

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens from the bucket.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            True if tokens were consumed, False if bucket is empty.
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        self._refill()
        return self.tokens


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm.

    Limits requests per client (identified by IP or API key) to prevent abuse
    and ensure fair usage during traffic spikes.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_size: int | None = None,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """Initialize rate limiter.

        Args:
            app: The ASGI application.
            requests_per_minute: Maximum sustained requests per minute.
            burst_size: Maximum burst size (defaults to 2x per-minute rate).
            exclude_paths: Paths to exclude from rate limiting (e.g., /health).
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.refill_rate = requests_per_minute / 60.0  # tokens per second
        self.burst_size = burst_size or (requests_per_minute * 2)
        self.exclude_paths = set(
            exclude_paths
            or ["/api/v1/health", "/api/v1/ready", "/health", "/docs", "/redoc", "/openapi.json"]
        )

        # Client buckets - in production, use Redis for distributed rate limiting
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=self.burst_size, refill_rate=self.refill_rate)
        )

        logger.info(
            "Rate limiter initialized",
            requests_per_minute=requests_per_minute,
            burst_size=self.burst_size,
        )

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request with rate limiting.

        Args:
            request: Incoming request.
            call_next: Next middleware/handler.

        Returns:
            Response from handler or 429 if rate limited.
        """
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Identify client (prefer API key, fall back to IP)
        client_id = self._get_client_id(request)
        bucket = self._buckets[client_id]

        if not bucket.consume():
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                path=request.url.path,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please slow down.",
                    "retry_after_seconds": int(1 / self.refill_rate),
                },
                headers={
                    "Retry-After": str(int(1 / self.refill_rate)),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket.available_tokens))

        return response

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request.

        Args:
            request: Incoming request.

        Returns:
            Client identifier string.
        """
        # Check for API key header first
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key[:8]}..."  # Truncate for privacy

        # Fall back to client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
