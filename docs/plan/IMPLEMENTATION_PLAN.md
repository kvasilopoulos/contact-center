# Contact-Center Mini AI Orchestrator - Implementation Plan

## Overview
Build a scalable FastAPI service that classifies customer messages into three categories (informational, service_action, safety_compliance) using a single LLM call, with E2E workflows for each category.

---

## 1. Project Structure

```
contact-center-orchestrator/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # CI pipeline (lint, test, build)
│       └── cd.yml                    # CD pipeline (deploy)
├── docker/
│   ├── Dockerfile                    # Production container
│   └── docker-compose.yml            # Local development stack
├── docs/
│   ├── architecture.md               # System architecture documentation
│   └── diagrams/                     # Architecture diagrams (Mermaid)
├── src/
│   └── orchestrator/
│       ├── __init__.py
│       ├── main.py                   # FastAPI app entry point
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py           # Pydantic settings
│       ├── api/
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py         # API router
│       │       └── endpoints/
│       │           ├── classify.py   # Classification endpoint
│       │           └── health.py     # Health/readiness endpoints
│       ├── models/
│       │   ├── __init__.py
│       │   ├── requests.py           # Request schemas
│       │   └── responses.py          # Response schemas
│       ├── services/
│       │   ├── __init__.py
│       │   ├── classifier.py         # AI classifier service
│       │   └── llm_client.py         # LLM client (OpenAI)
│       └── workflows/
│           ├── __init__.py
│           ├── base.py               # Base workflow interface
│           ├── informational.py      # Informational workflow
│           ├── service_action.py     # Service action workflow
│           └── safety_compliance.py  # Safety compliance workflow
├── tests/
│   ├── conftest.py                   # Pytest fixtures
│   ├── unit/                         # Unit tests
│   ├── integration/                  # Integration tests
│   └── e2e/                          # End-to-end tests
├── pyproject.toml                    # Project config & dependencies
├── .pre-commit-config.yaml           # Pre-commit hooks
├── README.md                         # Setup instructions
└── Makefile                          # Common commands
```

---

## 2. Core Components

### 2.1 API Layer (`src/orchestrator/api/`)
- **Health endpoints**: `/health` (liveness), `/ready` (readiness)
- **Classification endpoint**: `POST /api/v1/classify`

### 2.2 Models (`src/orchestrator/models/`)
**Request Schema:**
```python
class ClassificationRequest(BaseModel):
    message: str                    # Customer message text
    channel: ChannelType = "chat"   # chat, voice, mail
    metadata: dict = {}             # Optional context
```

**Response Schema:**
```python
class ClassificationResponse(BaseModel):
    request_id: str                 # Unique request ID
    category: CategoryType          # informational, service_action, safety_compliance
    confidence: float               # 0.0 - 1.0
    decision_path: str              # Explanation of classification
    next_step: NextStepInfo         # Recommended action
    processing_time_ms: float       # Latency tracking
```

### 2.3 AI Classifier (`src/orchestrator/services/classifier.py`)
- Single LLM call using structured output
- **Primary: OpenAI API** (gpt-4o-mini for cost-efficiency)
- Prompt engineering with clear category definitions
- JSON response parsing with validation

### 2.4 Workflows (`src/orchestrator/workflows/`)
Each workflow handles post-classification logic:
- **Informational**: FAQ lookup, knowledge base search
- **Service Action**: Ticket creation, order lookup
- **Safety Compliance**: Urgent flagging, compliance logging, escalation

---

## 3. AI Classifier Design

### 3.1 Prompt Template
```
You are a customer service classifier for a pharmacy/healthcare contact center.

Classify the following customer message into exactly ONE category:

CATEGORIES:
1. informational - Questions seeking information (policies, product details, general inquiries)
2. service_action - Requests requiring action (open ticket, track order, refund, account changes)
3. safety_compliance - Health/safety concerns (adverse reactions, medication issues, emergencies)

CUSTOMER MESSAGE:
{message}

Respond in JSON format:
{
  "category": "<category_name>",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>"
}
```

### 3.2 Confidence Scale
- **0.9 - 1.0**: High confidence, clear category match
- **0.7 - 0.9**: Moderate confidence, proceed with category
- **0.5 - 0.7**: Low confidence, may need human review
- **< 0.5**: Uncertain, escalate to human agent

### 3.3 Acceptance Criteria
- Confidence >= 0.5 for automated processing
- Safety compliance always gets priority if detected
- Low confidence triggers fallback workflow

---

## 4. E2E Workflow Designs

### 4.1 Informational Workflow
```
Message → Classify → [informational] → Search FAQ/KB → Generate Response → Return
                                                     ↓ (if no match)
                                              Suggest Contact Options
```
**Implementation**: Mock FAQ lookup, return suggested resources

### 4.2 Service Action Workflow
```
Message → Classify → [service_action] → Extract Intent → Prepare Action → Return Next Steps
                                        (ticket/order/refund)    ↓
                                                         [External System Stub]
```
**Implementation**: Intent extraction, ticket template generation, order lookup stub

### 4.3 Safety Compliance Workflow
```
Message → Classify → [safety_compliance] → Log to Compliance System → Flag Urgent
                                                     ↓                     ↓
                                              [Audit Trail]        [Escalation Queue]
```
**Implementation**: Compliance logging, PII redaction, urgent flagging, escalation stub

---

## 5. Scalability Approach

### 5.1 Architecture for Scale
- **Stateless API**: No server-side session state
- **Async handlers**: FastAPI async endpoints for I/O bound operations
- **Connection pooling**: Reuse LLM client connections
- **Horizontal scaling**: Multiple container replicas behind load balancer

### 5.2 Spike Handling
- **Rate limiting**: Token bucket algorithm per client
- **Circuit breaker**: Fail-fast when LLM service is degraded
- **Queue-based processing**: Optional async processing for bursts
- **Graceful degradation**: Fallback responses when overloaded

### 5.3 Configuration
```python
# settings.py - configurable limits
class Settings:
    max_concurrent_requests: int = 100
    llm_timeout_seconds: float = 30.0
    rate_limit_requests_per_minute: int = 60
```

---

## 6. Testing Strategy

### 6.1 Unit Tests
- Classifier prompt formatting
- Response parsing and validation
- Workflow logic (each category)
- Model serialization

### 6.2 Integration Tests
- API endpoint testing with TestClient
- LLM client mocking
- Full request/response cycle

### 6.3 E2E Tests
- Docker container testing
- Real LLM calls (optional, configurable)
- Multi-category scenarios

### 6.4 Test Coverage Target: 80%+

---

## 7. CI/CD Pipeline

### 7.1 CI Pipeline (`.github/workflows/ci.yml`)
```yaml
Triggers: push, pull_request
Jobs:
  - lint: ruff, mypy
  - test: pytest with coverage
  - security: bandit, safety
  - build: docker build
```

### 7.2 CD Pipeline (`.github/workflows/cd.yml`)
```yaml
Triggers: push to main, tags
Jobs:
  - build: docker build & push
  - deploy: kubernetes/docker deployment
```

### 7.3 Pre-commit Hooks
- ruff (linting + formatting)
- mypy (type checking)
- pytest (run tests)
- bandit (security)

---

## 8. Monitoring Approach

### 8.1 Metrics (Prometheus format)
- `classification_requests_total` (counter)
- `classification_latency_seconds` (histogram)
- `classification_confidence` (histogram)
- `classification_category` (counter by category)
- `llm_errors_total` (counter)

### 8.2 Logging
- Structured JSON logging
- Request tracing (request_id)
- PII redaction in logs

### 8.3 Health Checks
- `/health` - basic liveness
- `/ready` - dependency checks (LLM availability)

---

## 9. Compliance & Security

### 9.1 Sensitive Data Handling
- PII detection and redaction in logs
- Safety compliance messages stored securely
- Audit trail for compliance category

### 9.2 Security Measures
- Input validation (message length limits)
- Rate limiting
- No secrets in code (environment variables)

---

## 10. Implementation Order

### Phase 1: Foundation
1. Project setup (pyproject.toml, structure)
2. Configuration management (settings.py)
3. FastAPI app skeleton (main.py)
4. Health endpoints

### Phase 2: Core Classifier
5. Request/Response models
6. LLM client (OpenAI)
7. Classifier service with prompt
8. Classification endpoint

### Phase 3: Workflows
9. Base workflow interface
10. Informational workflow
11. Service action workflow
12. Safety compliance workflow

### Phase 4: Production Readiness
13. Docker configuration
14. Pre-commit hooks
15. Unit & integration tests
16. CI/CD pipeline

### Phase 5: Documentation
17. README with setup instructions
18. Architecture documentation
19. API documentation (auto-generated)

---

## 11. Key Files to Create

| File | Purpose |
|------|---------|
| `pyproject.toml` | Dependencies, project config |
| `src/orchestrator/main.py` | FastAPI application |
| `src/orchestrator/config/settings.py` | Configuration |
| `src/orchestrator/models/requests.py` | Request schemas |
| `src/orchestrator/models/responses.py` | Response schemas |
| `src/orchestrator/services/classifier.py` | AI classifier |
| `src/orchestrator/services/llm_client.py` | LLM integration |
| `src/orchestrator/workflows/*.py` | Category workflows |
| `docker/Dockerfile` | Container definition |
| `docker/docker-compose.yml` | Local dev stack |
| `.github/workflows/ci.yml` | CI pipeline |
| `tests/conftest.py` | Test fixtures |
| `README.md` | Documentation |
| `docs/architecture.md` | Architecture docs |

---

## 12. Verification Plan

### Local Testing
```bash
# Set OpenAI API key
export OPENAI_API_KEY=your-key-here

# Install dependencies with uv
uv sync

# Run service
make run

# Test classification
curl -X POST http://localhost:8000/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{"message": "What is your refund policy?"}'
```

### Automated Tests
```bash
make test          # Run all tests
make test-cov      # With coverage report
```

### Docker Testing
```bash
docker-compose up --build
# Test endpoints against containerized service
```

---

## Assumptions & Tradeoffs

### Assumptions
1. OpenAI API key is available (OPENAI_API_KEY env var)
2. Single LLM call is sufficient for classification accuracy
3. Chat channel implementation covers core patterns for other channels
4. External system integrations are stubbed (not implemented)

### Tradeoffs
1. **Simplicity over features**: Minimal viable implementation
2. **OpenAI over local LLM**: Better accuracy, but requires API costs
3. **Sync over async queues**: Simpler, but limits burst handling
4. **Monolith over microservices**: Easier to deploy, but less granular scaling

### Technology Choices
- **Package Manager**: uv (fast, modern Python package manager)
- **LLM Provider**: OpenAI API (gpt-4o-mini for cost efficiency)
- **Testing**: pytest with coverage
- **Linting**: ruff (fast, comprehensive)
