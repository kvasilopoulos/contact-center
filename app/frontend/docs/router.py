"""Documentation routes for rendering markdown files."""

import logging
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import markdown
import yaml

logger = logging.getLogger(__name__)

router = APIRouter()

# Templates: app/frontend/docs -> app/frontend/templates
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# Docs directory: project root / docs
DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs"
SIDEBAR_CONFIG = Path(__file__).parent / "sidebar.yaml"
DOCS_TEMPLATE = "docs.html"


def load_sidebar_config() -> dict[str, Any]:
    """Load sidebar configuration from YAML file."""
    try:
        content = SIDEBAR_CONFIG.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}
    except FileNotFoundError:
        logger.warning("Sidebar config not found", extra={"path": str(SIDEBAR_CONFIG)})
        return {"sections": []}
    except Exception as e:
        logger.error("Failed to load sidebar config", extra={"error": str(e)})
        return {"sections": []}


def extract_toc_from_markdown(content: str) -> list[dict[str, str]]:
    """Extract table of contents from markdown headers."""
    toc = []
    for text_line in content.split("\n"):
        stripped_line = text_line.strip()
        if stripped_line.startswith("#"):
            level = 0
            while level < len(stripped_line) and stripped_line[level] == "#":
                level += 1

            if level <= 3:
                title = stripped_line[level:].strip()
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
    mermaid_blocks = []

    def store_mermaid(match):
        idx = len(mermaid_blocks)
        mermaid_code = match.group(1).strip()
        mermaid_blocks.append(mermaid_code)
        return f"<!--MERMAID_PLACEHOLDER_{idx}-->"

    content = re.sub(
        r"```\s*mermaid\s*[\r\n]+(.*?)[\r\n]+```",
        store_mermaid,
        content,
        flags=re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )

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
    html = md.convert(content)

    for idx, mermaid_code in enumerate(mermaid_blocks):
        placeholder = f"<!--MERMAID_PLACEHOLDER_{idx}-->"
        cleaned_code = mermaid_code.strip()
        cleaned_code = re.sub(r"<br\s*/?>", " ", cleaned_code, flags=re.IGNORECASE)
        cleaned_code = re.sub(r" +", " ", cleaned_code)
        cleaned_code = "\n".join(line.rstrip() for line in cleaned_code.split("\n"))
        mermaid_html = f'<div class="mermaid">\n{cleaned_code}\n</div>'
        html = html.replace(placeholder, mermaid_html)

    return html


def url_to_file_path(url_path: str) -> str:
    """Convert URL path to file path."""
    file_mappings = {
        "implementation-plan": "IMPLEMENTATION_PLAN",
    }
    parts = url_path.split("/")
    converted_parts = []
    for part in parts:
        if part in file_mappings:
            converted_parts.append(file_mappings[part])
        else:
            converted_parts.append(part)
    return "/".join(converted_parts)


def get_markdown_file(page: str) -> tuple[str, str]:
    """Get markdown file content and title."""
    page = page.replace("..", "").strip("/")
    file_page = url_to_file_path(page)
    file_path = DOCS_DIR / f"{file_page}.md"

    if not file_path.exists():
        file_path = DOCS_DIR / file_page
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Documentation page not found")

    try:
        file_path = file_path.resolve()
        docs_resolved = DOCS_DIR.resolve()
        if not str(file_path).startswith(str(docs_resolved)):
            raise HTTPException(status_code=404, detail="Invalid documentation path") from None
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Invalid documentation path") from exc

    try:
        content = file_path.read_text(encoding="utf-8")
        title = page.replace("-", " ").replace("_", " ").title()
        for text_line in content.split("\n"):
            if text_line.startswith("# "):
                title = text_line[2:].strip()
                break
        return content, title
    except Exception as e:
        logger.error(
            "Failed to read markdown file",
            extra={"path": str(file_path), "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to load documentation") from e


@router.get("/{page:path}", response_class=HTMLResponse, response_model=None)
async def docs_page(request: Request, page: str = "") -> HTMLResponse | RedirectResponse:
    """Render a specific documentation page."""
    sidebar_config = load_sidebar_config()

    if not page or page == "":
        first_page = None
        if sidebar_config.get("sections"):
            for section in sidebar_config["sections"]:
                if section.get("pages"):
                    first_page = section["pages"][0].get("path")
                    break

        if first_page:
            return RedirectResponse(url=f"/docs/{first_page}", status_code=302)
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

    content, title = get_markdown_file(page)
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
            "current_page": page,
        },
    )
