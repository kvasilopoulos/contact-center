"""Application configuration settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings.

    All settings can be overridden via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Contact Center"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="The environment the application is running in"
    )
    debug: bool = Field(default=False, description="Whether to run the application in debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="The log level to use"
    )

    # Server
    host: str = Field(default="0.0.0.0", description="The host to bind the server to")
    port: int = Field(default=8000, description="The port to bind the server to")

    # OpenAI Configuration
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = "gpt-4.1"
    # Realtime model for audio-based interactions (WebSocket API)
    openai_realtime_model: str = "gpt-4o-realtime-preview"
    openai_timeout: float = 30.0
    openai_max_retries: int = 3

    # Classification
    min_confidence_threshold: float = 0.5
    max_message_length: int = 5000

    # Production telemetry (Confident AI / DeepEval)
    confident_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Confident AI API key for production monitoring; when set, all classification responses are sent as telemetry.",
    )

    # Rate Limiting
    rate_limit_requests_per_minute: int = 60


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


__all__ = ["Settings", "get_settings"]
