"""FastAPI application entry point."""

from app.core import configure_logging, get_settings
from app.factory import create_app

configure_logging(get_settings().log_level)
app = create_app()
