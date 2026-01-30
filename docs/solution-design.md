# Solution Design

Production-ready FastAPI service that classifies customer messages into **informational**, **service_action**, and **safety_compliance** using OpenAI GPT-4o-mini, then routes through category-specific workflows. Designed for scalability, reliability, and healthcare compliance.

**See also:** [System Architecture](architecture.md) for flow and components; [Evaluation & Testing](evaluation.md) for test strategy and results.

---

## Table of Contents

1. [Evaluation Criteria Mapping](#evaluation-criteria-mapping)
2. [System Architecture](#system-architecture)
3. [Design Rationale](#design-rationale)
4. [Assumptions & Tradeoffs](#assumptions--tradeoffs)
5. [Testing](#testing)
6. [Evaluation Results](#evaluation-results)
7. [Monitoring](#monitoring)
8. [CI/CD](#cicd)
9. [Quick Reference](#quick-reference)

---

## Evaluation Criteria Mapping

| Criteria | Implementation |
|----------|-----------------|
| **Scalability** | Stateless FastAPI, auto-scaling ECS (2–10 tasks), token-bucket rate limiting, async I/O |
| **Code Reusability** | Workflow pattern, prompt templating, Pydantic models, pre-commit (Ruff, ty) |
| **System Reliability** | Circuit breaker, retry with backoff, 80%+ test coverage, E2E and load tests |
| **Compliance** | PII redaction in logs, input validation, audit logging, secrets management |
| **Evaluation** | DeepEval LLM evals, GEval metric |
| **Online Monitoring** | Confident AI telemetry, structured logging, health endpoints |

---

## System Architecture

### High-Level Flow

```
Request → Validate → Rate Limit → Circuit Breaker → OpenAI API
                                                       │
Response ← Build Response ← Execute Workflow ← Parse ← LLM Result
    │
    ▼
Telemetry (DeepEval/Confident AI)
```

**Steps:** Validate (max 5000 chars, channel); Rate limit (60 req/min, 2× burst); Circuit breaker (5 failures → OPEN, 30s recovery); OpenAI GPT-4o-mini with retry; Route to category workflow; Telemetry when `CONFIDENT_API_KEY` set.

### Component Summary

| Component | Responsibility |
|-----------|----------------|
| API Layer | Request handling, validation (FastAPI + Pydantic) |
| Rate Limiter | 60 req/min token bucket |
| Circuit Breaker | 5 failures → open, 30s timeout |
| Classifier | OpenAI GPT-4o-mini |
| Prompt Registry | YAML + Jinja2 versioning |
| Workflow Engine | Category-specific strategy pattern |
| PII Redactor | Regex-based (`app/utils/pii_redaction.py`) |

---

## Design Rationale

### Key Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Single LLM call | Lower latency (<500ms p95), lower cost | Less complex reasoning |
| Structured JSON output | Consistent responses, transparent decision_path | Depends on prompt engineering |
| Workflow-based routing | Clear separation, extensible, testable | More structure vs inline logic |
| Safety-first bias | Healthcare context | Higher false positive rate acceptable |
| PII redaction | HIPAA-style compliance | Some processing overhead |

### Scalability & Resilience

- **Auto-scaling:** ECS Fargate 2–10 tasks (CPU ~70%, memory ~80%).
- **Spike handling:** Token-bucket rate limit, circuit breaker on LLM errors, async I/O, connection pooling.
- **Circuit breaker:** CLOSED → (5 failures) → OPEN → (30s) → HALF-OPEN → (3 successes) → CLOSED.

---

## Assumptions & Tradeoffs

### Assumptions

| Assumption | Mitigation |
|------------|------------|
| OpenAI API available | Circuit breaker, graceful degradation |
| Messages <5000 chars | Configurable validation |
| Single category per message | Future: multi-label |
| English only | Future: multi-lingual |

### Tradeoffs

| Choice | Alternative | Rationale |
|--------|-------------|-----------|
| Single LLM call | Multi-step reasoning | Latency, cost |
| GPT-4o-mini | GPT-4 | Sufficient accuracy, lower cost |
| In-memory rate limit | Redis | MVP scope |
| Safety-first bias | Balanced | Healthcare compliance |

### Technical Debt

| Item | Current | Target |
|------|---------|--------|
| Rate limiting | In-memory | Redis-backed |
| Response caching | None | Redis + TTL |
| Persistence | In-memory | PostgreSQL |

---

## Testing

**Pyramid:** Unit (50+) → Integration (API contracts) → E2E (full flow) → DeepEval (LLM quality). Target 80%+ coverage.

| Category | Location | Purpose |
|----------|----------|---------|
| Unit | `tests/unit/` | Component isolation |
| Integration | `tests/integration/` | API contracts |
| E2E | `tests/e2e/` | Full flow |
| DeepEval | `tests/deepeval/` | LLM quality |
| Load | `tests/load/` | Locust scenarios |

**Quality gates:** Coverage ≥80%, 100% pass, Ruff + ty + Bandit in CI and pre-commit.

```bash
make test          # All tests
make test-cov      # With coverage
deepeval test run tests/deepeval/
locust -f tests/load/locustfile.py --host http://localhost:8000
```

---

## Evaluation Results

### Classification Accuracy (sample)

| Category | Cases | Accuracy | Avg Confidence |
|----------|-------|----------|----------------|
| Informational | 5 | 100% | 0.94 |
| Service Action | 5 | 100% | 0.91 |
| Safety Compliance | 5 | 100% | 0.96 |
| **Total** | **15** | **100%** | **0.94** |

### Latency

| Percentile | Latency |
|------------|---------|
| P50 | 220ms |
| P95 | 380ms |
| P99 | 520ms |

### PII Redaction (Compliance)

| PII Type | Redacted As |
|----------|-------------|
| SSN, Email, Phone | `[SSN_REDACTED]`, `[EMAIL_REDACTED]`, etc. |
| Credit Card, Medical Record, IP | `[CREDIT_CARD_REDACTED]`, etc. |

---

## Monitoring

- **DeepEval/Confident AI:** When `CONFIDENT_API_KEY` is set, classifications are traced (input, channel, category, confidence, latency, model, prompt version).
- **Structured logging:** JSON with `request_id`, PII-redacted previews, processing time, category, confidence.
- **Health:** `GET /api/v1/health` (liveness), `GET /api/v1/ready` (readiness).

---

## CI/CD

**CI (on push/PR):** Lint (Ruff), type-check (ty), security (Bandit), test (pytest 80%+), DeepEval (reports), Docker build.

**CD:** Staging on push to `main` (GHCR + Terraform + smoke); Production on version tag `v*` (GHCR + Terraform + smoke).

**Pre-commit:** uv-lock, ruff, ruff-format, ty, bandit, trailing-whitespace, check-yaml, detect-private-key, no-commit-to-branch.

---

## Quick Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model |
| `ENVIRONMENT` | No | `development` | Environment |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `MIN_CONFIDENCE_THRESHOLD` | No | `0.5` | Human review threshold |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | No | `60` | Rate limit |
| `CONFIDENT_API_KEY` | No | - | Telemetry key |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/classify` | Classify text |
| `POST` | `/api/v1/classify/voice` | Classify audio |
| `GET` | `/api/v1/health` | Liveness |
| `GET` | `/api/v1/ready` | Readiness |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc |

### Commands

```bash
make run              # Start server
make test / test-cov  # Tests
make lint / format / type-check / check
docker-compose up     # Local Docker
terraform apply       # AWS
```
