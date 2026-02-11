# Contact Center AI Orchestrator

An AI-powered message classification and routing service built with FastAPI. The system ingests customer messages from multiple channels, classifies them through an LLM, and dispatches each to a domain-specific workflow that determines the next action.

**Start here:** [docs/overview](docs/overview.md) for the full project narrative, or open `app/factory.py` to see how the application is assembled. To trace a single request end-to-end, follow `app/api/v1/endpoints/classify.py` into the `Classifier` service, then into `app/services/dispatch.py` and the individual workflows.

---

## Why This Architecture

A contact center receives messages that vary wildly in urgency and intent. A question about refund policy, a request to cancel an order, and a report of an adverse drug reaction all arrive through the same channel but demand completely different handling. The core design challenge is to separate *understanding what the message is* from *deciding what to do about it*, so each concern can evolve independently.

The system addresses this with a two-phase pipeline: a single LLM call classifies the message into one of three categories, and a strategy-pattern workflow engine executes the appropriate business logic. Every resilience mechanism, from rate limiting to circuit breaking, exists to keep this pipeline responsive under real-world conditions where external dependencies are neither infinitely available nor perfectly reliable.

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)
- OpenAI API key

### Install and Run

```bash
uv sync
cp .env.example .env        # then add your OPENAI_API_KEY
make run                     # or: uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker-compose up --build
```

### Classify a Message

```bash
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{"message": "I am experiencing side effects from my medication", "channel": "chat"}'
```

---

## Documentation

| Document | What It Covers |
|----------|---------------|
| [Overview](docs/overview.md) | End-to-end project narrative: problem, solution, and design philosophy |
| [Architecture](docs/architecture.md) | Pipeline diagrams, request flow, workflows, and API surface |
| [Design Decisions](docs/design-decisions.md) | Why each pattern was chosen and what trade-offs were accepted |
| [Evaluation & Testing](docs/evaluation.md) | Test strategy, quality gates, and the feedback loop for continuous improvement |
| [AWS Architecture](docs/aws.md) | Infrastructure overview, scaling, CI/CD, and monitoring |
| [Deploy to AWS](docs/aws-deploy.md) | Step-by-step Terraform deployment guide |
| [Frontend](docs/frontend.md) | Documentation UI rendering system |

---

## Project Layout

```
app/
├── main.py                        # Entry: settings, logging, app creation
├── factory.py                     # Application assembly (middleware, routes, handlers)
├── core/                          # Configuration, logging, telemetry
├── api/v1/endpoints/              # HTTP endpoints (classify, health)
├── middleware/                     # Rate limiting, circuit breaker
├── services/                      # Classification, LLM client, workflow dispatch
├── workflows/                     # Category-specific business logic
├── prompts/                       # Versioned prompt templates (YAML + Jinja2)
├── schemas/                       # Request/response models (Pydantic)
└── utils/                         # PII redaction, audio conversion
tests/
├── unit/                          # Component isolation
├── integration/                   # API contract validation
├── e2e/                           # Full classification flow
├── deepeval/                      # LLM output quality (GEval)
└── load/                          # Locust performance scenarios
```

---

## Configuration

All configuration is managed through environment variables (via `pydantic-settings`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | *(required)* | LLM provider credentials |
| `OPENAI_MODEL` | `gpt-4.1` | Model selection |
| `ENVIRONMENT` | `development` | Controls logging format (dev vs JSON) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MIN_CONFIDENCE_THRESHOLD` | `0.5` | Below this, messages are escalated for human review |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `60` | Sustained request ceiling per client |
| `CONFIDENT_API_KEY` | *(optional)* | Enables production telemetry via Confident AI |

See `.env.example` for the full list.

---

## Development

This project uses the Astral toolchain for speed and consistency:

- **[uv](https://github.com/astral-sh/uv)** for dependency management
- **[Ruff](https://github.com/astral-sh/ruff)** for linting and formatting (replaces Black + isort + flake8)
- **[ty](https://github.com/astral-sh/ty)** for type checking (Rust-based, orders of magnitude faster than mypy)

```bash
make test          # Run all tests
make test-cov      # Tests with coverage report
make lint          # Ruff linting
make format        # Ruff formatting
make type-check    # ty type checking
make check         # All of the above
```

Pre-commit hooks enforce Ruff, ty, and Bandit (security scanning) on every commit.

---

## License

MIT
