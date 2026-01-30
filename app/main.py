"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import time
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.api.v1 import router as v1_router
from app.config import get_settings
from app.docs.router import router as docs_router
from app.logging_config import configure_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.prompts import load_prompts, registry
from app.schemas import ErrorResponse
from app.ui import router as ui_router

configure_logging(get_settings().log_level)
logger = logging.getLogger(__name__)

# Setup templates for landing page
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Application lifespan manager."""
    settings = get_settings()
    logger.info(
        "Starting application",
        extra={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
    )

    # Load prompt templates from YAML files
    try:
        load_prompts()
        logger.info(
            "Prompts loaded successfully",
            extra={
                "registry_stats": registry.get_stats(),
                "available_prompts": registry.list_prompts(),
            },
        )
    except FileNotFoundError as e:
        logger.error(
            "Failed to load prompts - prompts directory not found",
            extra={
                "error": str(e),
                "hint": "Create a 'prompts/' directory at project root with YAML prompt files",
            },
        )
        raise
    except Exception as e:
        logger.error(
            "Failed to load prompts",
            extra={"error": str(e)},
            exc_info=True,
        )
        raise

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
    docs_url=None,
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    """Serve Swagger UI with a custom favicon."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - Swagger UI",
        swagger_favicon_url=(
            "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
            "fill='none' stroke='%23222' stroke-width='2' stroke-linecap='round' "
            "stroke-linejoin='round'%3E%3Cpath d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 "
            "2 0 0 1 2 2z'/%3E%3Cpath d='M13 8H3'/%3E%3Cpath d='M17 12H3'/%3E%3Cpath "
            "d='M21 16H3'/%3E%3C/svg%3E"
        ),
    )


# CORS middleware (Starlette types expect factory, class is valid at runtime)
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
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"

    logger.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time_ms": round(process_time, 2),
        },
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
        extra={"request_id": request_id, "error": str(exc)},
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


# Landing page route - must be before other routers to take precedence
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def landing_page(request: Request) -> HTMLResponse:
    """Serve the landing page with navigation cards."""
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
    )


# Include routers
# API routes must come before docs router to avoid being caught by catch-all
app.include_router(v1_router)
app.include_router(ui_router, prefix="", tags=["UI"], include_in_schema=False)
# Docs router mounted at root - API routes take precedence, so /api/* won't be caught
# The docs router / route won't match because landing page is registered first
app.include_router(docs_router, prefix="", tags=["documentation"], include_in_schema=False)
