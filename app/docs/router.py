"""Documentation routes for rendering markdown files."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import markdown  # type: ignore[import-untyped]
import structlog
import yaml

logger = structlog.get_logger(__name__)

router = APIRouter()

# Setup templates - now in /app/templates
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Docs directory
DOCS_DIR = Path(__file__).parent.parent.parent / "docs"
SIDEBAR_CONFIG = Path(__file__).parent / "sidebar.yaml"
DOCS_TEMPLATE = "docs.html"


def load_sidebar_config() -> dict[str, Any]:
    """Load sidebar configuration from YAML file."""
    try:
        content = SIDEBAR_CONFIG.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}
    except FileNotFoundError:
        logger.warning("Sidebar config not found", path=str(SIDEBAR_CONFIG))
        return {"sections": []}
    except Exception as e:
        logger.error("Failed to load sidebar config", error=str(e))
        return {"sections": []}


def extract_toc_from_markdown(content: str) -> list[dict[str, str]]:
    """Extract table of contents from markdown headers."""
    toc = []
    for text_line in content.split("\n"):
        stripped_line = text_line.strip()
        if stripped_line.startswith("#"):
            # Count the number of # to determine level
            level = 0
            while level < len(stripped_line) and stripped_line[level] == "#":
                level += 1

            if level <= 3:  # Only include h1, h2, h3 in TOC
                title = stripped_line[level:].strip()
                # Create anchor from title
                anchor = title.lower().replace(" ", "-").replace(".", "").replace(",", "")
                toc.append(
                    {
                        "level": level,
                        "title": title,
                        "anchor": anchor,
                    }
                )
    return toc


def render_markdown(content: str) -> str:
    """Render markdown content to HTML with extensions."""
    md = markdown.Markdown(
        extensions=[
            "extra",
            "codehilite",
            "toc",
            "tables",
            "fenced_code",
        ],
        extension_configs={
            "codehilite": {
                "css_class": "highlight",
                "linenums": False,
            },
            "toc": {
                "anchorlink": True,
            },
        },
    )
    return md.convert(content)


def url_to_file_path(url_path: str) -> str:
    """Convert URL path to file path.
    
    URLs use lowercase with hyphens: aws-quick-start
    Files use original case with underscores: AWS_QUICK_START
    
    This function tries to find the actual file by checking multiple variations.
    """
    # Common file name mappings for known files (only filenames, not directories)
    file_mappings = {
        "aws-quick-start": "AWS_QUICK_START",
        "aws-deployment": "AWS_DEPLOYMENT",
        "aws-setup-summary": "AWS_SETUP_SUMMARY",
        "implementation-plan": "IMPLEMENTATION_PLAN",
    }
    
    # Split path into directory and filename
    parts = url_path.split("/")
    converted_parts = []
    
    for part in parts:
        # Check if we have a direct mapping for this filename
        if part in file_mappings:
            converted_parts.append(file_mappings[part])
        else:
            # Keep as is (for lowercase names like "architecture", "evaluation", "plan")
            converted_parts.append(part)
    
    return "/".join(converted_parts)


def get_markdown_file(page: str) -> tuple[str, str]:
    """Get markdown file content and title."""
    # Sanitize page path to prevent directory traversal
    page = page.replace("..", "").strip("/")
    
    # Convert URL format to file path format
    file_page = url_to_file_path(page)

    # Try to find the file with converted name
    file_path = DOCS_DIR / f"{file_page}.md"

    if not file_path.exists():
        # Try with .md extension if not provided
        file_path = DOCS_DIR / file_page
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Documentation page not found")

    # Ensure the file is within docs directory
    try:
        file_path = file_path.resolve()
        DOCS_DIR.resolve()
        if not str(file_path).startswith(str(DOCS_DIR.resolve())):
            raise HTTPException(status_code=404, detail="Invalid documentation path") from None
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Invalid documentation path") from exc

    # Read the file
    try:
        content = file_path.read_text(encoding="utf-8")
        # Extract title from first h1 or use filename
        title = page.replace("-", " ").replace("_", " ").title()
        for text_line in content.split("\n"):
            if text_line.startswith("# "):
                title = text_line[2:].strip()
                break
        return content, title
    except Exception as e:
        logger.error("Failed to read markdown file", path=str(file_path), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to load documentation") from e


@router.get("/", response_class=HTMLResponse)
async def docs_home(request: Request) -> HTMLResponse:
    """Render documentation home page."""
    sidebar_config = load_sidebar_config()

    # Get the first page from sidebar config or use a default
    first_page = None
    if sidebar_config.get("sections"):
        for section in sidebar_config["sections"]:
            if section.get("pages"):
                first_page = section["pages"][0].get("path")
                break

    if first_page:
        # Load the first page content
        try:
            content, title = get_markdown_file(first_page)
            html_content = render_markdown(content)
            toc = extract_toc_from_markdown(content)

            return templates.TemplateResponse(
                request=request,
                name=DOCS_TEMPLATE,
                context={
                    "title": title,
                    "content": html_content,
                    "toc": toc,
                    "sidebar": sidebar_config,
                    "current_page": first_page,
                },
            )
        except HTTPException:
            pass

    # Fallback to welcome page
    return templates.TemplateResponse(
        request=request,
        name=DOCS_TEMPLATE,
        context={
            "title": "Documentation",
            "content": "<h1>Welcome to Documentation</h1><p>Please configure the sidebar to get started.</p>",
            "toc": [],
            "sidebar": sidebar_config,
            "current_page": "",
        },
    )


@router.get("/{page:path}", response_class=HTMLResponse)
async def docs_page(request: Request, page: str) -> HTMLResponse:
    """Render a specific documentation page."""
    sidebar_config = load_sidebar_config()

    # Get markdown content
    content, title = get_markdown_file(page)

    # Render markdown to HTML
    html_content = render_markdown(content)

    # Extract TOC
    toc = extract_toc_from_markdown(content)

    return templates.TemplateResponse(
        request=request,
        name=DOCS_TEMPLATE,
        context={
            "title": title,
            "content": html_content,
            "toc": toc,
            "sidebar": sidebar_config,
            "current_page": page,
        },
    )
