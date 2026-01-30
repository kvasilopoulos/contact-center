"""Application factory: builds the FastAPI app with middlewares, handlers, and routes."""

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
from app.core import get_settings
from app.frontend import docs_router, qa_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.prompts import load_prompts, registry
from app.schemas import ErrorResponse

logger = logging.getLogger(__name__)

# Templates: app/frontend/templates (landing page)
_templates_dir = Path(__file__).parent / "frontend" / "templates"
_templates = Jinja2Templates(directory=str(_templates_dir))


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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "A scalable AI-powered service that classifies customer messages "
            "into categories: informational, service_action, and safety_compliance."
        ),
        lifespan=lifespan,
        docs_url=None,
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Swagger UI at /swagger (markdown docs at /docs via docs_router)
    @app.get("/swagger", include_in_schema=False)
    async def swagger_ui_html() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "/openapi.json",
            title=f"{app.title} - Swagger UI",
            swagger_favicon_url=(
                "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
                "fill='none' stroke='%23222' stroke-width='2' stroke-linecap='round' "
                "stroke-linejoin='round'%3E%3Cpath d='M3 18v-6a9 9 0 0 1 18 0v6'/%3E%3Cpath "
                "d='M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 "
                "0 0 0 2-2v-3a2 2 0 0 0-2-2H3z'/%3E%3C/svg%3E"
            ),
        )

    # Middleware order: last added runs first (outermost). So add in reverse order of execution.
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_requests_per_minute,
        burst_size=settings.rate_limit_requests_per_minute * 2,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    # Routes: landing first, then API, then UI interface, then docs (under /docs)
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def landing_page(request: Request) -> HTMLResponse:
        return _templates.TemplateResponse(
            request=request,
            name="landing.html",
        )

    app.include_router(v1_router)
    app.include_router(qa_router, prefix="", tags=["QA"], include_in_schema=False)
    app.include_router(docs_router, prefix="/docs", tags=["documentation"], include_in_schema=False)

    return app
