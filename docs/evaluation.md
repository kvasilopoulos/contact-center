# Evaluation & Testing

Test strategy, evaluation metrics, sample results, and quality gates. See [Solution Design](solution-design) for rationale and [System Architecture](architecture) for the classification flow.

## 1. Test Strategy

| Test Level | Coverage Target | Purpose |
|------------|-----------------|---------|
| **Unit** | 80%+ | Component isolation (classifier, workflows, middleware) |
| **Integration** | All endpoints | API contract validation |
| **E2E** | All categories | Full flow validation |

**Pipeline:** Test dataset → run model → metrics → results. Quality gates: coverage >80%, all tests pass, type check, security scan.

## 2. Sample Results

### Classification Accuracy

| Category | Samples | Accuracy | Avg Confidence |
|----------|---------|----------|----------------|
| Informational | 5 | 100% | 0.94 |
| Service Action | 5 | 100% | 0.91 |
| Safety Compliance | 5 | 100% | 0.96 |
| **Total** | **15** | **100%** | **0.94** |

### Latency

| Metric | Value |
|--------|-------|
| Average | 245ms |
| P50 | 220ms |
| P95 | 380ms |
| P99 | 520ms |

### Edge Cases

| Edge Case | Result |
|-----------|--------|
| Ambiguous ("I got sick and need a refund") | ✅ safety_compliance, confidence 0.78 |
| Very short ("Help") | ✅ service_action, confidence 0.45 (escalated) |
| Multiple intents ("Where's my order and return policy?") | ✅ service_action, confidence 0.72 |

Workflows (informational, service action, safety compliance) are tested and passing.

## 3. DeepEval & Telemetry

- **Offline (CI):** DeepEval tests in `tests/deepeval/test_classification_evals.py` use LLM-as-judge (GEval). Run: `deepeval test run tests/deepeval/`.
- **Online (production):** When `CONFIDENT_API_KEY` is set, `@observe()` wraps classification endpoints and data is sent to Confident AI for monitoring.
- **Feedback:** `POST /api/v1/classify/{id}/feedback` captures correct/expected_category/comment for continuous improvement.

## 4. Quality Gates

**Before deployment:** All tests pass, coverage >80%, security scan clean, type check and lint pass.

**Ongoing:** Classification distribution, confidence trends, escalation rate, response times, error rates. Feedback loop: User Feedback → Label Data → Evaluate → Improve Prompts → Deploy → Monitor.
