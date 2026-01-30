# Solution Design

Production-ready FastAPI service that classifies customer messages into three categories (**informational**, **service_action**, **safety_compliance**) using OpenAI GPT-4o-mini, then routes through category-specific workflows. Designed for scalability, reliability, and healthcare compliance.

**Where to go next**: [System Architecture](architecture) for components and classification flow; [Evaluation & Testing](evaluation) for test strategy and sample results.

## 1. Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| **Single LLM Call** | Minimize latency (<500ms p95), reduce costs (~$0.01–0.03/req) | Less sophisticated reasoning; sufficient for clear categories |
| **Structured JSON Output** | Consistent responses, transparency via decision_path, easier debugging | Requires prompt engineering |
| **Workflow-Based Routing** | Clear separation, easy to extend, testable | More structure vs. inline logic |
| **Horizontal Scaling** | Stateless service, FastAPI async, simple load balancing | External LLM dependency |
| **Safety-First Bias** | Healthcare context requires conservative approach | Higher false positive rate acceptable |

## 2. Classification Flow (Summary)

Request path: **Validate** → **Rate limit / Circuit breaker** → **Classifier** → **OpenAI** → **Parse** → **Route to workflow** → **Build response**. See the [Classification flow diagram](architecture#1-component-overview--classification-flow) and workflow details in [System Architecture](architecture#2-workflow-execution).

## 3. Scalability & Resilience (Summary)

- **Auto-scaling**: ECS Fargate 2–10 tasks (CPU/memory ~70%).
- **Spike handling**: Token bucket rate limit (60 req/min), circuit breaker on LLM errors, async I/O, connection pooling.

Full details: [System Architecture → Scalability & Resilience](architecture#3-scalability--resilience).

## 4. Testing, Evaluation & Operations (Summary)

- **Testing**: Unit (80%+), integration (all endpoints), E2E (all categories). Quality gates: coverage >80%, all tests pass, type check, security scan.
- **Evaluation**: Accuracy, latency, confidence, edge cases — see [Evaluation & Testing](evaluation).
- **Monitoring & CI/CD**: Metrics, logging, health checks, CI/CD pipeline — see [System Architecture → Monitoring, Security & CI/CD](architecture#4-monitoring-security--cicd).

## 5. Compliance & Security

- **Input validation**: Message length (5000 chars), channel (chat/voice/mail).
- **PII redaction**: Automatic in safety compliance logs.
- **Audit trail**: Compliance records for safety reports.
- **Secrets**: AWS Secrets Manager in production.
- **Network**: ECS tasks in private subnets, security groups.

## 6. Assumptions & Trade-offs

**Assumptions**

- OpenAI API available/responsive (mitigated with circuit breaker and retry).
- Single LLM call sufficient accuracy (mitigated with prompt engineering).
- External systems stubbed (interfaces defined for future integration).

**Trade-offs**

- **OpenAI vs local LLM**: Higher accuracy vs. API cost and latency dependency.
- **Sync vs queue**: Simpler architecture vs. limited burst handling.
- **Monolith vs microservices**: Easier deployment vs. less granular scaling.
- **Safety-first bias**: Prevents missed adverse events vs. higher false positive rate.
