# syntax=docker/dockerfile:1

# =========================
# Cost Center AI Orchestrator - Single-Stage Runtime Image
# =========================

FROM python:3.11-slim

WORKDIR /app

# Install OS-level dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Python dependency management (project-local virtualenv managed by uv)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-cache

# Create unprivileged user and ensure /app is owned by them
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Copy application code and prompt templates
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser prompts/ ./prompts/
COPY --chown=appuser:appuser docs/ ./docs/

# Environment configuration
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

USER appuser

# Expose application port
EXPOSE 8000

# Healthcheck (uses the same endpoint as docker-compose)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Entrypoint: run the app via uv so it uses the managed environment
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
