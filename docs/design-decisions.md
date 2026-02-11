# Design Decisions

This document explains *why* the system is built the way it is. For diagrams and component details, see [Architecture](architecture). For test strategy, see [Evaluation & Testing](evaluation).

---

## Classification: A Single LLM Call

The classifier uses a single call to OpenAI GPT-4.1 with structured JSON output validation. This is the most consequential design decision in the system and deserves explanation.

**Why a single call instead of a multi-step chain?** A chain-of-thought pipeline (classify, then verify, then extract metadata) would improve reasoning on edge cases, but it multiplies latency and cost proportionally. In a contact center, response time directly affects customer experience. A single call with a well-engineered prompt achieves strong separation between categories while keeping latency in the hundreds of milliseconds rather than seconds. If a message is ambiguous, the confidence score signals uncertainty and the system escalates to a human rather than attempting to reason further.

**Why structured output?** OpenAI's structured output mode (`responses.parse()`) guarantees that the response conforms to a Pydantic schema. This eliminates an entire class of runtime failures: malformed JSON, missing fields, invalid enum values. The LLM is constrained to return exactly `{category, confidence, reasoning}` with validated types and ranges. This is strictly preferable to parsing free-form text.

**Why GPT-4.1?** GPT-4.1 offers strong instruction-following and structured output capabilities, making it well-suited for a classification task that maps messages to one of three categories. The system is model-agnostic: the model is a configuration variable, and the prompt registry supports A/B testing between models.

---

## Rate Limiting: Protecting a Constrained Resource

The LLM API is the system's most constrained dependency. It has hard rate limits, per-token costs, and variable latency under load. When incoming request volume exceeds what the LLM can process, the system must decide: queue, reject, or degrade. This service chooses to reject excess traffic early and transparently.

### Why Rate Limiting Is Necessary

Without rate limiting, a traffic spike (whether organic or adversarial) would flood the LLM API with concurrent requests. This creates three compounding problems:

1. **Upstream saturation.** The LLM provider throttles or drops requests, causing unpredictable failures deep in the pipeline.
2. **Resource exhaustion.** Each pending LLM call holds an open connection and memory. Unbounded concurrency can exhaust connection pools and memory, degrading the entire service.
3. **Cost amplification.** LLM calls are priced per token. An uncontrolled burst can generate significant costs before any human notices.

Rate limiting addresses all three by capping throughput at a sustainable level. Clients that exceed the limit receive an immediate `429 Too Many Requests` with a `Retry-After` header, which is a clear, actionable signal that the system is under pressure.

### Why Token Bucket

The token bucket algorithm is chosen over simpler alternatives (fixed window, sliding window) because it naturally handles bursty traffic. A fixed window counter resets abruptly, allowing a burst at the boundary of two windows. A sliding window is more precise but requires storing per-request timestamps. The token bucket refills continuously and allows short bursts (up to 2x the sustained rate) while enforcing the average rate over time. This matches the real traffic pattern of a contact center, where messages tend to arrive in clusters.

### Why In-Memory (and What Changes at Scale)

The current implementation stores token buckets in a per-process dictionary. This is a deliberate MVP trade-off: it requires no external infrastructure, has zero latency overhead, and works correctly for a single-process deployment. In a multi-instance deployment, each instance enforces its own limit independently, so the aggregate rate could exceed the configured ceiling by a factor of the instance count. The documented migration path is to move the bucket state to Redis, which provides atomic operations and shared state across instances.

---

## Circuit Breaker: Preventing Cascade Failure

The circuit breaker is the system's most important resilience mechanism. It protects not just this service, but the downstream LLM provider, from the pathological behavior that occurs when a dependency fails and callers keep retrying.

### The Failure Cascade Problem

When the LLM API becomes unavailable (outage, rate limit, network partition), every incoming request blocks waiting for a timeout. During this period:

- Connection pools fill up with stalled requests.
- Response times spike from milliseconds to the timeout ceiling (typically 30 seconds).
- Clients experience hangs rather than clear errors, and may retry, which doubles the load.
- If the LLM is merely overloaded rather than down, the retry storm makes recovery harder.

This is a classic cascade failure: the downstream problem propagates upstream and amplifies itself.

### How the Circuit Breaker Solves It

The circuit breaker tracks consecutive failures. After a configurable threshold of failures, it *opens* the circuit: subsequent requests are rejected immediately with a `503 Service Unavailable` and a `Retry-After` header, without ever calling the LLM. This has three benefits:

1. **Fail fast.** Clients get a clear error in milliseconds instead of waiting for a timeout.
2. **Relieve pressure.** The failing LLM API receives zero traffic during the open period, giving it time to recover.
3. **Bounded impact.** Connection pools and memory are freed immediately instead of being held by stalled requests.

After a recovery timeout, the circuit enters a *half-open* state and allows a small number of test requests through. If those succeed, the circuit closes and normal operation resumes. If they fail, the circuit reopens. This probing mechanism ensures the system recovers automatically without operator intervention.

---

## Workflow Pattern: Strategy Over Switch Statements

A naive implementation would use a switch statement in the classification endpoint: `if category == "informational": do_faq_lookup(); elif ...`. This couples routing logic to business logic, makes testing harder (you must mock the entire endpoint to test a workflow), and means adding a new category requires modifying the router.

The strategy pattern decouples these concerns. Each workflow is an independent class with a single `execute()` method. The dispatch layer is a dictionary lookup. Adding a new category means writing a new workflow class and registering it, nothing else changes.

---

## Prompt Management: Version Control for LLM Behavior

Prompt engineering is iterative. A small change in wording can meaningfully shift classification behavior. The system treats prompts as versioned artifacts, not inline strings.

Prompts are stored as YAML files with semantic versioning, Jinja2 templates for variable injection, and explicit metadata (description, changelog, parameters). A prompt registry manages active versions and supports A/B experiments that split traffic between prompt variants with configurable weights.

This means a prompt change follows the same workflow as a code change: edit a YAML file, test it, review it in a PR, deploy it. The active version can be changed at runtime without redeploying the service.

---

## PII Redaction: Defense in Depth

Customer messages in a healthcare-adjacent context frequently contain sensitive information: email addresses, phone numbers, Social Security numbers, medical record numbers. The system applies regex-based PII detection and redaction at two points:

1. **In safety compliance workflows** before building the response, so PII never leaves the system in API responses.
2. **In structured logging** to ensure PII does not leak into log aggregation systems.

This is defense in depth: even if a downstream consumer mishandles the response, the PII has already been stripped. The redactor detects common PII patterns (SSN, email, phone, credit card, date of birth, IP address, medical record number, passport, driver's license) and replaces them with typed placeholders like `[EMAIL_REDACTED]`.

---

## Confidence Thresholds and Human Escalation

Not every classification is trustworthy. The system uses a configurable confidence threshold (default 0.5) below which a message is flagged for human review. This serves as a safety net: the LLM's uncertainty is made explicit and actionable rather than hidden.

The threshold is intentionally conservative. A higher threshold would escalate more messages but increase human workload. A lower threshold would reduce escalation but risk acting on uncertain classifications. The default represents a balance point that errs toward caution, consistent with the safety-first design philosophy.

For safety compliance specifically, human review is always required regardless of confidence, because the domain does not tolerate autonomous action on potentially life-critical messages.

---

## Assumptions and Technical Debt

### Assumptions

| Assumption | Mitigation |
|------------|------------|
| OpenAI API is generally available | Circuit breaker + graceful degradation |
| Messages are under 5000 characters | Configurable validation limit |
| One category per message | Future: multi-label classification |
| English-language messages | Future: multi-lingual support |

### Acknowledged Technical Debt

| Current State | Target State | Rationale for Deferral |
|---------------|-------------|----------------------|
| In-memory rate limiting | Redis-backed | Adequate for single-instance; Redis adds operational complexity |
| No response caching | Redis with TTL | LLM calls are not idempotent by default; caching requires careful key design |
| In-memory state | PostgreSQL persistence | Current scope does not require durable storage |
| FAQ keyword matching | Vector similarity search | Sufficient for a bounded FAQ set; vector search adds an embedding dependency |

---

## CI/CD and Quality Gates

**Continuous Integration** runs on every push and pull request: Ruff (lint + format), ty (type checking), Bandit (security scanning), pytest (unit, integration, E2E), and DeepEval (LLM output quality). The Docker image is built and validated as part of the pipeline.

**Continuous Deployment** is triggered by version tags. The pipeline pushes the container image to GitHub Container Registry, applies Terraform to the target environment, and runs smoke tests against the deployed service.

**Pre-commit hooks** enforce the same quality gates locally: uv-lock consistency, Ruff, ty, Bandit, trailing whitespace, YAML validation, and private key detection. This ensures that most issues are caught before code reaches the CI pipeline.

