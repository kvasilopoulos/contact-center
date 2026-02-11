# Contact Center AI Orchestrator

## The Problem

A contact center handles customer messages across different domains: FAQs, service requests, and safety reports. Each category needs a fundamentally different response path. Manual routing is slow, inconsistent, and does not scale.

## The Solution — One LLM Call, Three Workflows

FastAPI service: message in → GPT-4.1 classification → workflow dispatch → structured response.

Three categories:

- **Informational** → FAQ/knowledge base lookup
- **Service Action** → intent extraction + action template (cancel, refund, track)
- **Safety Compliance** → severity assessment, audit record, PII redaction, mandatory human escalation

## Key Design Decisions

- **Single LLM call** — latency in hundreds of ms, not seconds; structured output via Pydantic eliminates parsing failures
- **Classification separated from action** — swap models or add workflows independently
- **Safety-first bias** — ambiguous messages default to safety; human review always required for safety cases
- **Confidence thresholds** — low confidence → escalate to human, never act on uncertainty

## Resilience Patterns

- **Rate limiting** (token bucket) — reject excess traffic early with `429 + Retry-After`; protects LLM cost and availability
- **Circuit breaker** — after N consecutive failures, fail fast with `503`; auto-recovery via half-open probing
- Both prevent cascade failures when the LLM API degrades

## Production Concerns

- **PII redaction** — regex-based, applied before API response and in logs (defense in depth)
- **Prompt versioning** — YAML + Jinja2, semantic versioning, A/B experiments, no redeploy needed
- **CI/CD** — Ruff, type checking, Bandit, pytest, DeepEval; Docker + Terraform deployment

## Known Trade-offs & Next Steps

| Current State | Target State | Rationale for Deferral |
|---------------|-------------|----------------------|
| In-memory rate limiting | Redis-backed | Adequate for single-instance |
| No response caching | Redis with TTL | LLM calls require careful cache key design |
| In-memory state | PostgreSQL persistence | Current scope does not require durable storage |
| FAQ keyword matching | Vector similarity search | Sufficient for bounded FAQ set |
| Single-label classification | Multi-label | Future requirement |
| English-only | Multilingual | Future requirement |
