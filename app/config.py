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
    app_name: str = "Contact Center AI Orchestrator"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # OpenAI Configuration
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = "gpt-4o-mini"
    # Default speech model for audio transcription / speech tasks
    openai_speech_model: str = "gpt-4o-mini-transcribe"
    # Realtime model for audio-based interactions (WebSocket API)
    openai_realtime_model: str = "gpt-4o-realtime-preview"
    openai_timeout: float = 30.0
    openai_max_retries: int = 3

    # Classification
    min_confidence_threshold: float = 0.5
    max_message_length: int = 5000

    # Rate Limiting
    rate_limit_requests_per_minute: int = 60
    max_concurrent_requests: int = 100

    # Monitoring
    enable_metrics: bool = True
    metrics_path: str = "/metrics"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


__all__ = ["Settings", "get_settings"]
