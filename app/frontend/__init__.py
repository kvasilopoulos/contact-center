"""Frontend package: documentation site and QA interface."""

from app.frontend.docs import docs_router
from app.frontend.qa import qa_router

__all__ = ["docs_router", "qa_router"]
