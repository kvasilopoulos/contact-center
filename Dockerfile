# syntax=docker/dockerfile:1

# =========================
# Cost Center AI Orchestrator - Multi-Stage Production Image
# =========================

# ---------
# Builder
# ---------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Python dependency management
COPY pyproject.toml uv.lock ./
ENV UV_SYSTEM_PYTHON=1
RUN uv sync --frozen --no-dev --no-cache

# ---------
# Production
# ---------
FROM python:3.11-slim AS production

# Create unprivileged user and app dir owned by them (safer: /app never root-owned)
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir /app \
    && chown -R appuser:appuser /app
WORKDIR /app

# Install runtime dependencies only
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies and runtime binaries from builder (explicit, not entire bin)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy application code (correct ownership from the start)
COPY --chown=appuser:appuser app/ ./app/

# Environment configuration
ENV PATH="/usr/local/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

USER appuser

# Expose application port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Entrypoint
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
