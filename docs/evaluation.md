# Evaluation & Testing

Test strategy, quality philosophy, and the feedback loop for continuous improvement. For architecture details, see [System Architecture](architecture). For design rationale, see [Solution Design](solution-design).

---

## Testing Philosophy

The test suite is designed around a principle: **test the behavior, not the implementation.** Unit tests verify that individual components produce correct outputs for given inputs. Integration tests verify that the API contracts are honored. E2E tests verify that a message entering the system produces the expected classification and workflow result. LLM evaluation tests verify that the model's outputs are reasonable and consistent.

This layered approach means that internal refactoring (changing how the classifier calls the LLM, restructuring workflow internals) does not break tests, while changes to externally visible behavior (response format, classification logic, workflow actions) are caught immediately.

---

## Test Pyramid

| Level | Location | What It Validates |
|-------|----------|-------------------|
| **Unit** | `tests/unit/` | Component isolation: classifier logic, workflow behavior, middleware state machines, PII redaction patterns, Pydantic model validation, logging configuration |
| **Integration** | `tests/integration/` | API contract validation: request/response shapes, status codes, header behavior, error responses, documentation endpoint availability |
| **End-to-End** | `tests/e2e/` | Full flow: a message enters the system and produces a classified response with a workflow-generated next step |
| **LLM Evaluation** | `tests/deepeval/` | Output quality: LLM classifications are evaluated using GEval (LLM-as-judge) metrics via DeepEval |
| **Load** | `tests/load/` | Performance under concurrent load: Locust scenarios simulate realistic traffic patterns |

---

## What Each Level Covers

### Unit Tests

- **Classifier service:** Verifies that the classifier correctly parses LLM responses, handles parse failures with fallback behavior, clamps confidence scores to valid ranges, and flags low-confidence results for human review.
- **Workflows:** Each workflow is tested in isolation. The informational workflow returns FAQ matches or escalates on low confidence. The service action workflow extracts intents correctly and handles unknown intents. The safety compliance workflow assigns correct severity levels, generates audit records, and redacts PII.
- **Middleware:** The circuit breaker transitions between states correctly (CLOSED to OPEN on failures, OPEN to HALF_OPEN on timeout, HALF_OPEN to CLOSED on successes). The rate limiter correctly tracks token consumption and rejects requests when the bucket is empty.
- **PII redaction:** Every supported PII type (SSN, email, phone, credit card, medical record number, etc.) is detected and replaced with the appropriate placeholder. False positives on non-PII text are minimized.
- **Models:** Pydantic validation rules are tested: message length limits, channel enum constraints, confidence score ranges.

### Integration Tests

- **Classification endpoint:** Verifies the full request/response contract including status codes, response schema, and error handling for invalid inputs.
- **Health endpoints:** Verifies that liveness and readiness probes return the expected shapes and status codes.
- **Documentation endpoints:** Verifies that Swagger, ReDoc, and OpenAPI schema endpoints are accessible.

### End-to-End Tests

- A representative message for each category is submitted through the API. The test verifies that the response contains the correct category, a valid confidence score, and a meaningful next step from the appropriate workflow.
- Edge cases are included: ambiguous messages, very short messages, and messages with multiple possible intents.

### LLM Evaluation (DeepEval)

The system uses DeepEval with GEval metrics to evaluate LLM output quality. GEval uses an LLM-as-judge approach: a separate model evaluates whether the classification output is correct, coherent, and well-reasoned.

This is distinct from traditional accuracy metrics because there is no labeled evaluation dataset. Instead, the evaluation assesses whether the model's reasoning is sound and its confidence calibration is plausible. This approach is more appropriate for an LLM-based system where "ground truth" is often subjective and the reasoning matters as much as the label.

When `CONFIDENT_API_KEY` is configured, evaluation results are sent to Confident AI for tracking over time.

### Load Tests

Locust scenarios simulate concurrent classification requests to measure throughput, latency distribution, and error rates under load. These tests validate that the rate limiter and circuit breaker behave correctly under pressure and that the system degrades gracefully rather than failing catastrophically.

---

## Quality Gates

The CI pipeline enforces the following gates before any code reaches the main branch:

| Gate | Tool | Purpose |
|------|------|---------|
| Lint | Ruff | Code style, import ordering, common errors |
| Format | Ruff | Consistent formatting |
| Type check | ty | Static type correctness |
| Security | Bandit | Known vulnerability patterns |
| Tests | pytest | All unit, integration, and E2E tests pass |
| LLM quality | DeepEval | Classification output quality |
| Container | Docker | Image builds successfully |

Pre-commit hooks enforce Ruff, ty, and Bandit locally, catching most issues before they enter the CI pipeline.

---

## Monitoring and the Feedback Loop

### Production Telemetry

When `CONFIDENT_API_KEY` is configured, the system sends classification traces to Confident AI. Each trace includes the input message, channel, classified category, confidence score, processing time, model used, and prompt version. This provides visibility into classification behavior in production without requiring log analysis.

### Structured Logging

Every classification produces a structured log entry (JSON in production, human-readable in development) containing the request ID, category, confidence, processing time, and a PII-redacted preview of the message. These logs can be aggregated and analyzed for trends: classification distribution shifts, confidence degradation, latency spikes, and error rate changes.

### Continuous Improvement

The system is designed for iterative improvement through a feedback loop:

```
Observe (telemetry, logs, user feedback)
    → Identify issues (misclassifications, low confidence, new patterns)
        → Improve (adjust prompts, add training examples, tune thresholds)
            → Deploy (versioned prompts, A/B experiments)
                → Observe ...
```

The prompt registry and A/B testing infrastructure exist specifically to support this loop. A prompt change can be deployed as an experiment with a traffic split, evaluated against the current version using telemetry data, and promoted or rolled back based on results.

---

## Running Tests

```bash
# All tests
make test

# With coverage report
make test-cov

# Specific test file
uv run pytest tests/unit/test_classifier.py -v

# LLM evaluation (requires OPENAI_API_KEY)
deepeval test run tests/deepeval/

# Load test (requires running server)
locust -f tests/load/locustfile.py --host http://localhost:8000
```
