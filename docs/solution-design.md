# Solution Design

Production-ready FastAPI service that classifies customer messages into **informational**, **service_action**, and **safety_compliance** using OpenAI GPT-4o-mini, then routes through category-specific workflows.

**See also:** [System Architecture](architecture) for flow and components; [Evaluation & Testing](evaluation) for test strategy and results.

## Evaluation Criteria Mapping

| Criteria | Implementation |
|----------|-----------------|
| **Scalability** | Stateless FastAPI, auto-scaling ECS (2–10 tasks), token-bucket rate limiting, async I/O |
| **Code reusability** | Workflow pattern, prompt templating, Pydantic models |
| **System reliability** | Circuit breaker, retry with backoff, 80%+ test coverage |
| **Compliance** | PII redaction in logs, input validation, audit logging |
| **Evaluation** | DeepEval LLM evals, feedback endpoint |
| **Online monitoring** | Confident AI telemetry, structured logging |

## Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|------------|
| **Single LLM call** | Lower latency (<500ms p95), lower cost | Less complex reasoning; sufficient for clear categories |
| **Structured JSON output** | Consistent responses, transparent decision_path | Depends on prompt engineering |
| **Workflow-based routing** | Clear separation, easy to extend, testable | More structure vs. inline logic |
| **Horizontal scaling** | Stateless service, FastAPI async, simple load balancing | External LLM dependency |
| **Safety-first bias** | Healthcare context requires conservative handling | Higher false positive rate acceptable |
| **PII redaction** | HIPAA-style compliance, data protection | Some processing overhead |

## Classification Flow (Summary)

**Validate** → **Rate limit / circuit breaker** → **Classifier** → **OpenAI** → **Parse** → **Route to workflow** → **Build response**. Details and diagrams: [Architecture → Classification flow](architecture#1-component-overview--classification-flow).

## Scalability & Resilience

- **Auto-scaling:** ECS Fargate 2–10 tasks (CPU/memory ~70%).
- **Spike handling:** Token-bucket rate limit (60 req/min), circuit breaker on LLM errors, async I/O, connection pooling.

## Compliance & Security

### PII Redaction

| PII Type | Redacted As |
|----------|-------------|
| SSN, Email, Phone | `[SSN_REDACTED]`, `[EMAIL_REDACTED]`, etc. |
| Credit Card, Medical Record, IP | `[CREDIT_CARD_REDACTED]`, etc. |

Implementation: `app/utils/pii_redaction.py` (regex-based, configurable).

### Security Controls

- **Input:** Message length (5000 chars), channel (chat/voice/mail).
- **Audit:** Compliance records for safety reports.
- **Secrets:** AWS Secrets Manager in production.
- **Network:** ECS in private subnets, security groups.
- **Rate limiting:** 60 req/min to limit abuse.

## Assumptions & Trade-offs

**Assumptions:** OpenAI API available (mitigated with circuit breaker and retry). Single LLM call sufficient (mitigated with prompt engineering). External systems stubbed (interfaces defined for integration).

**Trade-offs:** OpenAI vs local LLM (accuracy vs cost/latency). Sync vs queue (simpler vs limited burst handling). Safety-first bias (fewer missed safety events vs higher false positives).
