.PHONY: help install install-dev test test-cov lint format type-check security run docker-build docker-run clean

# Default target
help:
	@echo "Contact Center AI Orchestrator - Available commands:"
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

# Installation
install:
	uv sync --no-dev

install-dev:
	uv sync
	pre-commit install

# Run development server
run:
	uv run uvicorn orchestrator.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ -v --cov=src/orchestrator --cov-report=term-missing --cov-report=html

# Code quality
lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

type-check:
	uv run ty check src/

security:
	uv run bandit -r src/ -ll

# Run all checks
check: lint type-check test

# Docker commands
docker-build:
	docker build -f docker/Dockerfile -t contact-center-orchestrator:latest .

docker-run:
	docker-compose -f docker/docker-compose.yml up --build

docker-down:
	docker-compose -f docker/docker-compose.yml down

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
