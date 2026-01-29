"""UI router for serving frontend interfaces."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["UI"])

# Set up templates directory
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request) -> HTMLResponse:
    """Serve the main question-answering interface."""
    return templates.TemplateResponse(
        request=request,
        name="qa_interface.html",
    )


@router.get("/classify-ui", response_class=HTMLResponse, include_in_schema=False)
async def classify_ui(request: Request) -> HTMLResponse:
    """Serve the classification interface (alternative route)."""
    return templates.TemplateResponse(
        request=request,
        name="qa_interface.html",
    )
