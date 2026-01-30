.PHONY: help install install-dev test test-cov lint format type-check security run docker-build docker-run clean

# Default target
help:
	@echo "Cost Center AI Orchestrator - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make install       Install production dependencies"
	@echo "  make install-dev   Install all dependencies including dev"
	@echo "  make run           Run the development server"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run tests"
	@echo "  make test-cov      Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint          Run linter (ruff)"
	@echo "  make format        Format code (ruff)"
	@echo "  make type-check    Run type checker (ty)"
	@echo "  make security      Run security scanner (bandit)"
	@echo "  make check         Run all checks (lint, type-check, test)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Run with docker-compose"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean         Clean build artifacts"
	@echo "  make tunnel        Start Cloudflare tunnel with Netlify DNS update"

# Installation
install:
	uv sync --no-dev

install-dev:
	uv sync
	pre-commit install

# Run development server
run:
	uv run fastapi dev --port 8001

# Testing
test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

# Code quality
lint:
	uv run ruff check app/ tests/

format:
	uv run ruff format app/ tests/
	uv run ruff check --fix app/ tests/

type-check:
	uv run ty check app/

security:
	uv run bandit -r app/ -ll

# Run all checks
check: lint type-check test

# Docker commands
docker-build:
	docker build -f docker/Dockerfile -t contact-center-orchestrator:latest .

docker-run:
	docker-compose -f docker/docker-compose.yml up --build

docker-down:
	docker-compose -f docker/docker-compose.yml down

# Tunnel with Netlify DNS auto-update
tunnel:
	@echo "Starting Cloudflare tunnel with Netlify DNS auto-update..."
	@echo "Make sure NETLIFY_TOKEN is set in your environment"
	uv run python scripts/tunnel.py

# Clean up
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ty_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
