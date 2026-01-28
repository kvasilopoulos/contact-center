"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import time
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.api.v1 import router as v1_router
from app.config import get_settings
from app.middleware.rate_limit import RateLimitMiddleware
from app.schemas import ErrorResponse

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Application lifespan manager."""
    settings = get_settings()
    logger.info(
        "Starting application",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
    yield
    logger.info("Shutting down application")


# Get settings for app initialization
_settings = get_settings()

app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    description=(
        "A scalable AI-powered service that classifies customer messages "
        "into categories: informational, service_action, and safety_compliance."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=_settings.rate_limit_requests_per_minute,
    burst_size=_settings.rate_limit_requests_per_minute * 2,
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"

    logger.info(
        "Request completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        process_time_ms=round(process_time, 2),
    )

    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="validation_error",
            message="Request validation failed",
            request_id=request_id,
            details={"errors": exc.errors()},
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Unhandled exception",
        request_id=request_id,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred",
            request_id=request_id,
        ).model_dump(),
    )


# Include routers
app.include_router(v1_router)
