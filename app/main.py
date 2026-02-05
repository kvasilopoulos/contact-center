"""FastAPI application entry point."""

from app.core import configure_logging, get_settings
from app.factory import create_app

_settings = get_settings()
configure_logging(_settings.log_level, environment=_settings.environment)
app = create_app()
