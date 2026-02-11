# API Reference

Endpoints, middleware, application bootstrap, and code map. For architecture diagrams, see [Architecture](architecture). For design rationale, see [Design Decisions](design-decisions).

---

## API Surface

### Classification

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/classify` | Classify a text message |
| `POST` | `/api/v1/classify/voice` | Classify an audio message (WAV upload) |

**Request** (`POST /api/v1/classify`):
```json
{
  "message": "I am experiencing side effects from my medication",
  "channel": "chat",
  "metadata": {}
}
```

**Response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-15T10:30:00Z",
  "category": "safety_compliance",
  "confidence": 0.92,
  "decision_path": "Message reports medication side effects - safety compliance",
  "next_step": {
    "action": "pharmacist_review",
    "description": "Flagged for pharmacist review due to reported adverse reaction",
    "priority": "high",
    "requires_human_review": true,
    "external_system": "compliance_system"
  },
  "processing_time_ms": 312.5
}
```

### Health and Readiness

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Liveness probe (Kubernetes/ECS) |
| `GET` | `/api/v1/ready` | Readiness probe (checks dependencies) |

The health endpoint always returns `200` if the process is alive. The readiness endpoint checks whether the OpenAI API key is configured and returns `degraded` if critical dependencies are not available.

### Documentation

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/docs` | Interactive documentation UI |
| `GET` | `/swagger` | Swagger UI |
| `GET` | `/redoc` | ReDoc |
| `GET` | `/openapi.json` | OpenAPI schema |

---

## Middleware Stack

Middleware is applied in order. The outermost middleware executes first:

| Layer | Responsibility |
|-------|---------------|
| **Rate Limiting** | Token bucket per client; rejects excess traffic with 429 |
| **CORS** | Allows cross-origin requests (configured for all origins in development) |
| **Request ID + Timing** | Assigns request ID, measures processing time, adds response headers |
| **Exception Handling** | Catches unhandled exceptions, returns structured error responses |

---

## Application Bootstrap

The application is assembled through a factory pattern (`app/factory.py`):

1. **Load settings** from environment variables via `pydantic-settings`.
2. **Configure logging** (human-readable in development, structured JSON in production).
3. **Create the FastAPI app** with middleware, exception handlers, and route registration.
4. **On startup** (lifespan event): load prompt templates from YAML files into the prompt registry.

The factory pattern ensures the application can be created identically in production, tests, and local development, with only environment variables differing.

---

## Code Map

| Module | Responsibility |
|--------|---------------|
| `app/main.py` | Entry point: load settings, configure logging, create app |
| `app/factory.py` | Application assembly: middleware, routes, exception handlers |
| `app/core/config.py` | Settings from environment (via pydantic-settings) |
| `app/core/logging.py` | Logging configuration: dev formatter vs JSON formatter |
| `app/core/telemetry.py` | Optional Confident AI / DeepEval integration |
| `app/api/v1/endpoints/classify.py` | Classification endpoints |
| `app/api/v1/endpoints/health.py` | Health and readiness probes |
| `app/middleware/rate_limit.py` | Token bucket rate limiter |
| `app/middleware/circuit_breaker.py` | Circuit breaker state machine |
| `app/services/classification.py` | Classifier service (orchestrates LLM call) |
| `app/services/llm.py` | OpenAI client wrapper with retry and circuit breaker |
| `app/services/dispatch.py` | Routes classification result to workflow |
| `app/workflows/informational.py` | FAQ lookup and escalation |
| `app/workflows/service_action.py` | Intent extraction and action templating |
| `app/workflows/safety_compliance.py` | Severity assessment, audit records, PII redaction |
| `app/prompts/registry.py` | Versioned prompt management and A/B experiments |
| `app/prompts/loader.py` | YAML prompt file loader |
| `app/prompts/template.py` | Prompt data model with Jinja2 rendering |
| `app/schemas/` | Pydantic models for requests, responses, and LLM output |
| `app/utils/pii_redaction.py` | Regex-based PII detection and masking |
| `app/utils/audio.py` | WAV to PCM16 conversion for voice classification |
