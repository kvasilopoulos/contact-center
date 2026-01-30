# Cost Center AI Orchestrator

A scalable FastAPI service that classifies customer messages into categories (informational, service_action, safety_compliance) using AI, with end-to-end workflows for each category.

**Where to look**: To see how the app is built, open `app/factory.py`. To follow a classify request, start at `app/api/v1/endpoints/classify.py` → `ClassifierService` → `app/services/workflow_router.py` → workflows. See [System Architecture](docs/architecture.md) for the full application flow.

## Features

- **AI-Powered Classification**: Single LLM call using OpenAI GPT-4o-mini
- **Three Categories**:
  - `informational`: Policy questions, FAQs, product inquiries
  - `service_action`: Ticket creation, order tracking, refunds
  - `safety_compliance`: Adverse reactions, health concerns (priority handling)
- **Multi-Channel Support**: Designed for chat, voice, and mail (chat implemented)
- **Workflow Automation**: Category-specific workflows with next-step recommendations
- **Production Ready**: Docker, CI/CD, monitoring, comprehensive tests

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- OpenAI API key
- Docker (optional)
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) (optional, for public demos)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd cost-center-orchestrator

# Install uv if you haven't already
# On macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# On Windows:
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install all dependencies (including dev dependencies)
uv sync

# Copy environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
```

> **Note**: This project uses `uv` for dependency management. The `uv sync` command reads `pyproject.toml` and creates/updates the `uv.lock` file, ensuring reproducible builds across all environments.

### Running the Service

```bash
# Development server
make run

# Or directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 🌐 Public Demo with Cloudflare Tunnel

Want to share your local API publicly? Use the built-in tunnel with automatic DNS updates:

```bash
# Quick setup (2 minutes)
# See QUICK_START.md for detailed instructions

# 1. Get Netlify token and add to .env
# 2. Start your API
make run

# 3. Start tunnel (in another terminal)
make tunnel
```

Your API will be automatically available at `https://demo.kvasilopoulos.com` with automatic DNS updates! 

📖 **Full guide:** [QUICK_START.md](QUICK_START.md) | [Token Setup](docs/NETLIFY_TOKEN_SETUP.md)

### Using Docker

```bash
# Build and run with docker-compose
docker-compose up --build

# Or build manually
docker build -t cost-center-orchestrator .
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key cost-center-orchestrator
```

## Deployment Options

### 🚀 Option 1: Render.com (Easiest - Free Tier Available)

Deploy to the cloud in 5 minutes with free HTTPS:

1. Push your code to GitHub
2. Go to https://render.com and sign up
3. Click "New +" → "Blueprint"
4. Connect your repo (will detect `render.yaml`)
5. Set `OPENAI_API_KEY` environment variable
6. Deploy!

**Result:** Your API at `https://your-app.onrender.com`

📖 **Full guide:** [docs/RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md)

**Free tier:** Perfect for demos (sleeps after 15 min inactivity)  
**Paid tier:** $7/month for always-on service

### ☁️ Option 2: AWS Fargate (Production-Ready)

Deploy to AWS Fargate with Terraform in ~10 minutes:

```bash
# Set OpenAI API key
export TF_VAR_openai_api_key="sk-..."

# Deploy infrastructure
cd terraform
terraform init
terraform apply

# Build and push Docker image
./scripts/deploy.sh push
```

**Features:**
- ✅ Serverless containers with AWS Fargate
- ✅ Uses default VPC (no custom networking)
- ✅ Auto-scaling based on CPU and memory
- ✅ Application Load Balancer
- ✅ Secure secrets management
- ✅ Simple single-file Terraform configuration

**Documentation:**
- 📘 [Terraform README](terraform/README.md) - Complete deployment guide

**Estimated Cost:** ~$90/month (2 tasks with 0.5 vCPU, 1 GB each)

## API Usage

### Classify a Message

```bash
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is your refund policy for prescription products?",
    "channel": "chat"
  }'
```

**Response:**
```json
{
  "request_id": "abc123",
  "timestamp": "2024-01-15T10:30:00Z",
  "category": "informational",
  "confidence": 0.95,
  "decision_path": "Customer asking about refund policy - informational inquiry",
  "next_step": {
    "action": "provide_information",
    "description": "Found relevant FAQ: We offer a 30-day refund policy...",
    "priority": "low",
    "requires_human_review": false
  },
  "processing_time_ms": 245.5
}
```

### Health Check

```bash
# Liveness
curl http://localhost:8000/api/v1/health

# Readiness
curl http://localhost:8000/api/v1/ready
```

### API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

## Project Structure

```
cost-center-orchestrator/
├── app/
│   ├── api/v1/endpoints/     # API endpoints
│   ├── config/               # Configuration
│   ├── models/               # Pydantic models
│   ├── services/             # Business logic
│   └── workflows/            # Category workflows
├── tests/
│   ├── unit/                 # Unit tests
│   └── integration/          # Integration tests
├── Dockerfile                # Production container
├── docker-compose.yml        # Local run
├── .github/workflows/        # CI/CD pipelines
└── docs/                     # Documentation
```

## Development

This project uses modern Python tooling from Astral for an extremely fast and consistent development experience:

- **[uv](https://github.com/astral-sh/uv)** - Ultra-fast package manager and dependency resolver
- **[Ruff](https://github.com/astral-sh/ruff)** - Lightning-fast linter and formatter (replaces Black, isort, flake8)
- **[ty](https://github.com/astral-sh/ty)** - Extremely fast Python type checker (10x-100x faster than mypy/Pyright), written in Rust

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
uv run pytest tests/unit/test_classifier.py -v
```

### Code Quality

#### Linting and Formatting

This project uses **Ruff** for both linting and formatting:

```bash
# Lint code (check for issues)
make lint
# or: uv run ruff check app/ tests/

# Format code (auto-fix formatting)
make format
# or: uv run ruff format app/ tests/

# Format and fix linting issues
uv run ruff format app/ tests/
uv run ruff check --fix app/ tests/
```

Ruff configuration is in `pyproject.toml` under `[tool.ruff]`:
- Line length: 100 characters
- Enabled rules: pycodestyle, Pyflakes, isort, flake8-bugbear, pyupgrade, and more
- Auto-formatting with double quotes and proper imports

#### Type Checking

This project uses **ty**, Astral's extremely fast type checker (10x-100x faster than mypy):

```bash
# Run type checker
make type-check
# or: uv run ty check app/
```

ty configuration is in `pyproject.toml` under `[tool.ty]`. ty automatically provides:
- Comprehensive diagnostics with rich contextual information
- Support for partially typed code
- Advanced typing features (intersection types, sophisticated narrowing)
- Fast incremental analysis

#### Run All Checks

```bash
# Run lint, type-check, and test
make check
```

### Pre-commit Hooks

Pre-commit hooks automatically run uv, Ruff, and ty before each commit:

```bash
# Install hooks
make install-dev
# or: uv sync && pre-commit install

# Run manually on all files
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

**Hooks configured:**
- **uv-lock**: Automatically updates `uv.lock` when `pyproject.toml` changes
- **ruff**: Lints and auto-fixes Python code
- **ruff-format**: Formats Python code
- **ty**: Type checks Python code (extremely fast, from Astral)
- **bandit**: Security vulnerability scanner
- Plus standard hooks (trailing whitespace, YAML validation, etc.)

### Package Management with uv

```bash
# Add a new dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Remove a dependency
uv remove <package-name>

# Update dependencies
uv lock --upgrade

# Sync environment to match lock file
uv sync

# Install production dependencies only
uv sync --no-dev
```

## Configuration

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model to use |
| `ENVIRONMENT` | `development` | Environment name |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MIN_CONFIDENCE_THRESHOLD` | `0.5` | Threshold for human review |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `60` | Rate limit |

See `.env.example` for all options.

## Architecture

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation including:
- System design overview
- Scalability approach
- Workflow diagrams
- Monitoring strategy

## License

MIT
