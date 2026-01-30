# Cost Center AI Orchestrator - Solution Documentation

## Table of Contents
1. [System Architecture Overview](#1-system-architecture-overview)
2. [Design Rationale](#2-design-rationale)
3. [Assumptions & Tradeoffs](#3-assumptions--tradeoffs)
4. [Code Testing Approach](#4-code-testing-approach)
5. [Evaluation Method & Sample Results](#5-evaluation-method--sample-results)
6. [Online Monitoring Approach](#6-online-monitoring-approach)
7. [CI/CD Pipeline Description](#7-cicd-pipeline-description)

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT CHANNELS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐                 │
│   │  Chat   │    │  Voice  │    │  Mail   │    │   API   │                 │
│   │ Widget  │    │   IVR   │    │ Parser  │    │ Client  │                 │
│   └────┬────┘    └────┬────┘    └────┬────┘    └────┬────┘                 │
│        │              │              │              │                       │
└────────┼──────────────┼──────────────┼──────────────┼───────────────────────┘
         │              │              │              │
         └──────────────┴──────────────┴──────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LOAD BALANCER (ALB/Render)                          │
│                    ┌─────────────────────────────────┐                      │
│                    │  Health Checks │ SSL Termination│                      │
│                    │  Round Robin   │ Request Routing│                      │
│                    └─────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR SERVICE (FastAPI)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        MIDDLEWARE STACK                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  Request ID  │→│ Rate Limiter │→│   Logging    │              │   │
│  │  │  Middleware  │  │(Token Bucket)│  │ (structlog) │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          API ENDPOINTS                               │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │   │
│  │  │ POST /classify │  │ GET /health    │  │ GET /ready     │        │   │
│  │  │ POST /voice    │  │ POST /feedback │  │                │        │   │
│  │  └───────┬────────┘  └────────────────┘  └────────────────┘        │   │
│  └──────────┼──────────────────────────────────────────────────────────┘   │
│             │                                                               │
│  ┌──────────▼──────────────────────────────────────────────────────────┐   │
│  │                      CLASSIFIER SERVICE                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│  │  │   Prompt    │  │    LLM      │  │  Circuit    │                 │   │
│  │  │  Registry   │  │   Client    │  │  Breaker    │                 │   │
│  │  └─────────────┘  └──────┬──────┘  └─────────────┘                 │   │
│  └──────────────────────────┼──────────────────────────────────────────┘   │
│                             │                                               │
│  ┌──────────────────────────▼──────────────────────────────────────────┐   │
│  │                        WORKFLOW ENGINE                               │   │
│  │  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐       │   │
│  │  │  Informational  │ │ Service Action  │ │Safety Compliance│       │   │
│  │  │    Workflow     │ │    Workflow     │ │    Workflow     │       │   │
│  │  └─────────────────┘ └─────────────────┘ └─────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   OpenAI    │  │  Knowledge  │  │  Ticketing  │  │ Compliance  │       │
│  │    API      │  │    Base     │  │   System    │  │   System    │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Request Processing Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         CLASSIFICATION PIPELINE                             │
└────────────────────────────────────────────────────────────────────────────┘

  ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Request │────▶│ Validate │────▶│   Rate   │────▶│  Cache   │
  │ Arrives │     │  Input   │     │  Check   │     │  Lookup  │
  └─────────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
                       │                │                │
                       ▼                ▼                ▼
                  ┌─────────┐     ┌──────────┐     ┌──────────┐
                  │  400    │     │   429    │     │  Cache   │
                  │ Invalid │     │ Exceeded │     │   Hit?   │
                  └─────────┘     └──────────┘     └────┬─────┘
                                                        │
                       ┌────────────────────────────────┴────────┐
                       │                                         │
                       ▼                                         ▼
                 ┌──────────┐                              ┌──────────┐
                 │   Yes    │                              │    No    │
                 │  Return  │                              │  Call    │
                 │  Cached  │                              │   LLM    │
                 └──────────┘                              └────┬─────┘
                                                                │
                                                                ▼
                                                          ┌──────────┐
                                                          │ Circuit  │
                                                          │ Breaker  │
                                                          │  Check   │
                                                          └────┬─────┘
                                                                │
                       ┌────────────────────────────────────────┼────────┐
                       │                                        │        │
                       ▼                                        ▼        ▼
                 ┌──────────┐                              ┌────────┐ ┌──────┐
                 │  CLOSED  │                              │  OPEN  │ │HALF  │
                 │ Proceed  │                              │  Fail  │ │OPEN  │
                 └────┬─────┘                              │  Fast  │ │Test  │
                      │                                    └────────┘ └──────┘
                      ▼
                ┌──────────┐
                │  OpenAI  │
                │   API    │
                │   Call   │
                └────┬─────┘
                     │
                     ▼
               ┌───────────┐
               │  Parse &  │
               │ Validate  │
               │ Response  │
               └─────┬─────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         ▼           ▼           ▼
   ┌───────────┐ ┌────────┐ ┌──────────┐
   │Information│ │Service │ │ Safety   │
   │  Workflow │ │ Action │ │Compliance│
   └─────┬─────┘ └───┬────┘ └────┬─────┘
         │           │           │
         └───────────┼───────────┘
                     │
                     ▼
              ┌────────────┐
              │  Build     │
              │  Response  │
              │ + Telemetry│
              └─────┬──────┘
                    │
                    ▼
              ┌────────────┐
              │  Return    │
              │   JSON     │
              └────────────┘
```

### 1.3 Component Interactions

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| **API Layer** | Request handling, validation, routing | FastAPI + Pydantic |
| **Rate Limiter** | Traffic control, abuse prevention | Token Bucket (Redis for distributed) |
| **Circuit Breaker** | Fault tolerance, cascade prevention | Custom implementation |
| **Classifier Service** | Message classification orchestration | Python async |
| **LLM Client** | OpenAI API integration | openai-python + tenacity |
| **Prompt Registry** | Prompt versioning, A/B testing | YAML + Jinja2 |
| **Workflow Engine** | Category-specific business logic | Strategy pattern |
| **PII Redactor** | Sensitive data protection | Regex patterns |
| **Metrics Collector** | Observability data collection | Prometheus client |
| **Telemetry** | Real-time monitoring | Confident AI (DeepEval) |

### 1.4 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW                                       │
└──────────────────────────────────────────────────────────────────────────┘

  User Request                Classification Response
       │                              ▲
       ▼                              │
  ┌─────────┐                    ┌─────────┐
  │ message │                    │category │
  │ channel │                    │confidence│
  │metadata │                    │next_step│
  └────┬────┘                    │time_ms  │
       │                         └────┬────┘
       ▼                              │
  ╔═════════════════════════════════════════════╗
  ║              ORCHESTRATOR                    ║
  ║  ┌─────────────────────────────────────┐    ║
  ║  │        Input Validation             │    ║
  ║  │  • Max 5000 chars                   │    ║
  ║  │  • Valid channel (chat/voice/mail)  │    ║
  ║  │  • PII detection & redaction        │    ║
  ║  └──────────────┬──────────────────────┘    ║
  ║                 │                            ║
  ║  ┌──────────────▼──────────────────────┐    ║
  ║  │        Prompt Construction          │    ║
  ║  │  • Load template from registry      │    ║
  ║  │  • Render with Jinja2               │    ║
  ║  │  • Select variant (A/B testing)     │    ║
  ║  └──────────────┬──────────────────────┘    ║
  ║                 │                            ║
  ║  ┌──────────────▼──────────────────────┐    ║
  ║  │          LLM Processing             │    ║
  ║  │  • OpenAI API call                  │    ║
  ║  │  • Retry with exponential backoff   │    ║
  ║  │  • Response parsing                 │    ║
  ║  └──────────────┬──────────────────────┘    ║
  ║                 │                            ║
  ║  ┌──────────────▼──────────────────────┐    ║
  ║  │        Workflow Execution           │    ║
  ║  │  • Route to category workflow       │    ║
  ║  │  • Generate next_step               │    ║
  ║  │  • Apply business rules             │    ║
  ║  └──────────────┬──────────────────────┘    ║
  ╚═════════════════╪═══════════════════════════╝
                    │
                    ▼
         ┌──────────────────┐
         │    Telemetry     │
         │  • Metrics       │
         │  • Traces        │
         │  • Logs          │
         └──────────────────┘
```

---

## 2. Design Rationale

### 2.1 Architecture Decisions

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| **FastAPI** | Async support, automatic OpenAPI, Pydantic integration, high performance | Flask, Django REST |
| **Single LLM Call** | Minimize latency, reduce costs, simpler error handling | Multi-step reasoning, agent chain |
| **Token Bucket Rate Limiting** | Smooth traffic, allows bursts, simple implementation | Fixed window, sliding log |
| **Circuit Breaker** | Fail-fast on external failures, prevent cascade | Bulkhead, timeout-only |
| **Prompt Templating** | Version control, A/B testing, separation of concerns | Hardcoded prompts |
| **Structured Logging** | Machine-readable, searchable, traceable | Plain text logs |
| **Workflow Pattern** | Extensible, testable, clear separation | Switch/case, callbacks |

### 2.2 Scalability Design

```
                    HORIZONTAL SCALING ARCHITECTURE
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    AUTO-SCALING GROUP                            │   │
│   │  ┌──────────────────────────────────────────────────────────┐   │   │
│   │  │  Target Tracking Policy                                   │   │   │
│   │  │  • CPU Utilization: 70%                                   │   │   │
│   │  │  • Memory Utilization: 80%                                │   │   │
│   │  │  • Min: 2 tasks, Max: 10 tasks                           │   │   │
│   │  └──────────────────────────────────────────────────────────┘   │   │
│   │                                                                  │   │
│   │  ┌────────┐  ┌────────┐  ┌────────┐       ┌────────┐           │   │
│   │  │Task 1  │  │Task 2  │  │Task 3  │  ...  │Task N  │           │   │
│   │  │        │  │        │  │        │       │        │           │   │
│   │  │ 0.5vCPU│  │ 0.5vCPU│  │ 0.5vCPU│       │ 0.5vCPU│           │   │
│   │  │ 1GB RAM│  │ 1GB RAM│  │ 1GB RAM│       │ 1GB RAM│           │   │
│   │  └────────┘  └────────┘  └────────┘       └────────┘           │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   Stateless Design: No shared state between instances                    │
│   Session Affinity: Not required (each request is independent)           │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Resilience Patterns

**Circuit Breaker State Machine:**
```
           ┌─────────────────────────────────────────┐
           │                                         │
           ▼                                         │
      ┌─────────┐    5 failures    ┌─────────┐      │
      │ CLOSED  │─────────────────▶│  OPEN   │      │
      │         │                  │         │      │
      └────┬────┘                  └────┬────┘      │
           │                            │           │
           │                  30s timeout           │
           │                            │           │
           │                            ▼           │
           │                      ┌──────────┐      │
           │    3 successes       │HALF-OPEN │      │
           │◀─────────────────────│          │      │
           │                      └────┬─────┘      │
           │                           │            │
           │                    1 failure           │
           │                           │            │
           │                           └────────────┘
           │
     All requests succeed
```

---

## 3. Assumptions & Tradeoffs

### 3.1 Key Assumptions

| Assumption | Impact | Mitigation |
|------------|--------|------------|
| **OpenAI API availability >99.9%** | Classification depends on external API | Circuit breaker, graceful degradation |
| **Messages are <5000 characters** | Input validation rejects longer messages | Configurable limit, truncation option |
| **Single category per message** | Simplifies routing logic | Future: multi-label classification |
| **English language only** | Prompt optimized for English | Future: language detection, multi-lingual prompts |
| **Synchronous classification acceptable** | Latency target <500ms P95 | Async queue for batch processing |

### 3.2 Tradeoffs Made

| Tradeoff | Chosen Approach | Alternative | Why |
|----------|----------------|-------------|-----|
| **Latency vs Accuracy** | Single LLM call | Multi-step reasoning | User experience, cost efficiency |
| **Cost vs Quality** | GPT-4o-mini | GPT-4 | Sufficient accuracy at lower cost |
| **Simplicity vs Features** | In-memory rate limiting | Redis (distributed) | MVP scope, easy to upgrade |
| **Consistency vs Availability** | Eventual consistency | Strong consistency | Higher availability for read-heavy workload |
| **Security vs Performance** | PII redaction in logs | No redaction | Compliance requirements |

### 3.3 Technical Debt Acknowledged

| Item | Current State | Target State | Priority |
|------|--------------|--------------|----------|
| Distributed rate limiting | In-memory per instance | Redis-backed | High |
| Response caching | None | Redis with TTL | Medium |
| Async job queue | Synchronous only | Celery + Redis | Low |
| Database persistence | None | PostgreSQL | Medium |

---

## 4. Code Testing Approach

### 4.1 Test Pyramid

```
                    ┌─────────────────┐
                    │   DeepEval      │  ← LLM Quality (3 tests)
                    │   LLM Evals     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    E2E Tests    │  ← Full Flow (5 tests)
                    │                 │
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │     Integration Tests       │  ← API Contracts (12 tests)
              │                             │
              └──────────────┬──────────────┘
                             │
    ┌────────────────────────▼────────────────────────┐
    │                  Unit Tests                      │  ← Component Logic (50+ tests)
    │   Classifier │ Workflows │ Middleware │ Models  │
    └─────────────────────────────────────────────────┘

    Target: 80%+ code coverage
```

### 4.2 Test Categories

| Category | Purpose | Location | Coverage |
|----------|---------|----------|----------|
| **Unit Tests** | Isolated component testing | `tests/unit/` | 80%+ |
| **Integration Tests** | API endpoint contracts | `tests/integration/` | All endpoints |
| **E2E Tests** | Full classification flow | `tests/e2e/` | All categories |
| **DeepEval Tests** | LLM output quality | `tests/deepeval/` | Representative samples |
| **Load Tests** | Performance under stress | `tests/load/` | Key scenarios |

### 4.3 Test Fixtures & Mocking

```python
# Example fixture structure
@pytest.fixture
def mock_llm_client():
    """Mock LLM client for unit tests."""
    client = MagicMock(spec=LLMClient)
    client.complete_with_template = AsyncMock(return_value=(
        {"category": "informational", "confidence": 0.95, "reasoning": "FAQ question"},
        {"version": "1.0.0", "variant": "default", "model": "gpt-4o-mini"}
    ))
    return client

@pytest.fixture
def classifier_service(mock_llm_client, test_settings):
    """Classifier service with mocked dependencies."""
    return ClassifierService(settings=test_settings, llm_client=mock_llm_client)
```

### 4.4 Quality Gates

| Gate | Threshold | Enforcement |
|------|-----------|-------------|
| Code Coverage | ≥80% | CI blocks merge |
| Test Pass Rate | 100% | CI blocks merge |
| Lint (Ruff) | 0 errors | Pre-commit + CI |
| Type Check (ty) | 0 errors | Pre-commit + CI |
| Security (Bandit) | 0 high/medium | CI blocks merge |
| DeepEval Accuracy | ≥50% confidence | CI reports |

---

## 5. Evaluation Method & Sample Results

### 5.1 Evaluation Framework

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      EVALUATION PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│   │   Golden    │───▶│   Run       │───▶│   Compare   │                │
│   │   Dataset   │    │   Model     │    │   Results   │                │
│   └─────────────┘    └─────────────┘    └──────┬──────┘                │
│                                                 │                        │
│                                                 ▼                        │
│                                          ┌─────────────┐                │
│                                          │   Metrics   │                │
│                                          │  Dashboard  │                │
│                                          └─────────────┘                │
│                                                                          │
│   Metrics Collected:                                                     │
│   • Accuracy (per category)                                             │
│   • Confidence distribution                                             │
│   • Latency (P50, P95, P99)                                            │
│   • Error rate                                                          │
│   • Edge case handling                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 DeepEval Integration

The system uses DeepEval's GEval metric (LLM-as-judge) for continuous evaluation:

```python
# tests/deepeval/test_classification_evals.py
@pytest.mark.evaluation
def test_informational_classification():
    test_case = LLMTestCase(
        input="What is your return policy?",
        actual_output='{"category": "informational", "confidence": 0.95}',
        expected_output='{"category": "informational"}'
    )
    metric = GEval(
        name="Classification Correctness",
        criteria="The actual category matches the expected category",
        threshold=0.5
    )
    assert_test(test_case, [metric])
```

### 5.3 Sample Results

#### Classification Accuracy

| Category | Test Cases | Accuracy | Avg Confidence |
|----------|-----------|----------|----------------|
| Informational | 5 | 100% | 0.94 |
| Service Action | 5 | 100% | 0.91 |
| Safety Compliance | 5 | 100% | 0.96 |
| **Total** | **15** | **100%** | **0.94** |

#### Latency Performance

| Percentile | Latency |
|------------|---------|
| P50 | 220ms |
| P95 | 380ms |
| P99 | 520ms |
| Average | 245ms |

#### Confidence Distribution

```
High (0.9-1.0):     ████████████████████████████████████████ 80%
Moderate (0.7-0.9): ████████ 15%
Low (0.5-0.7):      ██ 4%
Very Low (<0.5):    ▌ 1%
```

#### Edge Case Results

| Edge Case | Input | Result | Confidence |
|-----------|-------|--------|------------|
| Ambiguous | "I got sick and need a refund" | safety_compliance | 0.78 |
| Very short | "Help" | service_action | 0.45 (escalated) |
| Multi-intent | "Where's my order and return policy?" | service_action | 0.72 |

---

## 6. Online Monitoring Approach

### 6.1 Observability Stack

The monitoring approach uses **DeepEval with Confident AI** for LLM quality monitoring and **structured logging** for operational observability.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      OBSERVABILITY ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                      LLM QUALITY (DeepEval)                      │   │
│   │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │   │
│   │  │  @observe()  │───▶│ Confident AI │───▶│   Quality    │      │   │
│   │  │  Decorator   │    │  Dashboard   │    │  Monitoring  │      │   │
│   │  └──────────────┘    └──────────────┘    └──────────────┘      │   │
│   │                                                                  │   │
│   │  Features:                                                       │   │
│   │  • Every classification traced to Confident AI                  │   │
│   │  • Input/output pairs logged for evaluation                     │   │
│   │  • Accuracy tracking over time                                  │   │
│   │  • Confidence distribution analysis                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         LOGS (structlog)                         │   │
│   │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │   │
│   │  │  Structured  │───▶│  CloudWatch  │───▶│ Log Insights │      │   │
│   │  │  JSON Logs   │    │    Logs      │    │   Queries    │      │   │
│   │  └──────────────┘    └──────────────┘    └──────────────┘      │   │
│   │                                                                  │   │
│   │  Logged Data:                                                    │   │
│   │  • Request ID, timestamp, category, confidence                  │   │
│   │  • Processing time, channel, model used                         │   │
│   │  • PII-redacted message previews                                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    FEEDBACK LOOP                                 │   │
│   │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │   │
│   │  │ POST         │───▶│   Feedback   │───▶│   Quality    │      │   │
│   │  │ /feedback    │    │   Storage    │    │ Improvement  │      │   │
│   │  └──────────────┘    └──────────────┘    └──────────────┘      │   │
│   │                                                                  │   │
│   │  User feedback on classification correctness enables:           │   │
│   │  • Accuracy measurement in production                           │   │
│   │  • Identification of misclassified messages                     │   │
│   │  • Prompt improvement opportunities                             │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 DeepEval Telemetry

When `CONFIDENT_API_KEY` is set, all classification responses are automatically sent to Confident AI:

| Data Captured | Description |
|---------------|-------------|
| Input Message | The customer message (PII-redacted in logs) |
| Channel | Communication channel (chat, voice, mail) |
| Category | Classification result |
| Confidence | Confidence score (0-1) |
| Processing Time | Request duration in ms |
| Model | LLM model used |
| Prompt Version | Version of prompt template |

### 6.3 Health Endpoints

| Endpoint | Purpose | Check |
|----------|---------|-------|
| `GET /api/v1/health` | Liveness probe | Service is running |
| `GET /api/v1/ready` | Readiness probe | Dependencies loaded |

### 6.4 Feedback Endpoint

The feedback endpoint enables continuous quality improvement:

```bash
# Submit feedback on a classification
POST /api/v1/classify/{request_id}/feedback
{
    "correct": false,
    "expected_category": "safety_compliance",
    "comment": "Message mentioned health concerns"
}
```

This feedback data enables:
- Accuracy measurement in production
- Identification of systematic misclassifications
- Prompt improvement based on real-world failures

### 6.5 Logging Strategy

**Structured Log Format:**
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "info",
  "logger": "app.services.classifier",
  "request_id": "abc-123-def",
  "message": "Message classified",
  "category": "informational",
  "confidence": 0.95,
  "channel": "chat",
  "processing_time_ms": 245.5,
  "prompt_version": "1.0.0",
  "model": "gpt-4o-mini"
}
```

**PII Redaction in Logs:**
```
Before: "Patient SSN 123-45-6789 reported adverse reaction"
After:  "Patient SSN [SSN_REDACTED] reported adverse reaction"
```

---

## 7. CI/CD Pipeline Description

### 7.1 Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CI/CD PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  TRIGGER: Push to main/develop OR Pull Request to main                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    CONTINUOUS INTEGRATION                        │    │
│  │                                                                  │    │
│  │   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │    │
│  │   │  Lint  │  │  Type  │  │Security│  │  Test  │  │DeepEval│   │    │
│  │   │ (Ruff) │  │ (ty)   │  │(Bandit)│  │(pytest)│  │ (LLM)  │   │    │
│  │   └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘   │    │
│  │       │           │           │           │           │         │    │
│  │       ▼           ▼           ▼           ▼           ▼         │    │
│  │   ┌──────────────────────────────────────────────────────────┐ │    │
│  │   │                    BUILD (Docker)                         │ │    │
│  │   │  • Multi-platform (amd64, arm64)                         │ │    │
│  │   │  • Layer caching                                          │ │    │
│  │   │  • Import verification                                    │ │    │
│  │   └──────────────────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                      │                                   │
│                                      ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                   CONTINUOUS DEPLOYMENT                          │    │
│  │                                                                  │    │
│  │   ┌────────────────────┐      ┌────────────────────┐            │    │
│  │   │      STAGING       │      │    PRODUCTION      │            │    │
│  │   │  (on: push main)   │      │ (on: version tag)  │            │    │
│  │   │                    │      │                    │            │    │
│  │   │  • Push to GHCR    │      │  • Push to GHCR    │            │    │
│  │   │  • Terraform apply │      │  • Terraform apply │            │    │
│  │   │  • Smoke tests     │      │  • Smoke tests     │            │    │
│  │   └────────────────────┘      └────────────────────┘            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 CI Jobs Detail

| Job | Tool | Purpose | Blocking |
|-----|------|---------|----------|
| **lint** | Ruff | Code style, import order | Yes |
| **type-check** | ty | Static type analysis | Yes |
| **security** | Bandit | Security vulnerability scan | Yes |
| **test** | pytest | Unit/integration tests, coverage | Yes |
| **deepeval** | DeepEval | LLM quality evaluation | No (reports only) |
| **build** | Docker | Container build verification | Yes |

### 7.3 CD Environments

| Environment | Trigger | Infrastructure | Validation |
|-------------|---------|---------------|------------|
| **Staging** | Push to `main` | AWS ECS (staging.tfvars) | Health check, smoke tests |
| **Production** | Version tag (`v*`) | AWS ECS (production.tfvars) | Health check, smoke tests |

### 7.4 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    hooks:
      - id: uv-lock           # Update lock file

  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff              # Lint
      - id: ruff-format       # Format

  - repo: local
    hooks:
      - id: ty                # Type check
      - id: bandit            # Security scan

  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: detect-private-key
      - id: no-commit-to-branch  # Protect main
```

### 7.5 Deployment Flow

```
Developer                    CI/CD                     Infrastructure
    │                          │                             │
    │  git push                │                             │
    ├─────────────────────────▶│                             │
    │                          │                             │
    │                          │  Run CI checks              │
    │                          │  (lint, type, test, build)  │
    │                          │                             │
    │                          │  All checks pass?           │
    │                          ├────────────────────────────▶│
    │                          │                             │
    │                          │  terraform plan             │
    │                          │  terraform apply            │
    │                          │                             │
    │                          │                             │  Deploy ECS task
    │                          │                             │  Update service
    │                          │                             │
    │                          │  Health check (10 retries)  │
    │                          │◀────────────────────────────┤
    │                          │                             │
    │  Deployment complete     │                             │
    │◀─────────────────────────┤                             │
    │                          │                             │
```

---

## Appendix A: Quick Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model to use |
| `ENVIRONMENT` | No | `development` | Environment name |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `MIN_CONFIDENCE_THRESHOLD` | No | `0.5` | Human review threshold |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | No | `60` | Rate limit |
| `CONFIDENT_API_KEY` | No | - | DeepEval telemetry key for production monitoring |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/classify` | Classify text message |
| `POST` | `/api/v1/classify/voice` | Classify audio message |
| `POST` | `/api/v1/classify/{id}/feedback` | Submit classification feedback |
| `GET` | `/api/v1/classify/{id}/feedback` | Get submitted feedback |
| `GET` | `/api/v1/health` | Liveness check |
| `GET` | `/api/v1/ready` | Readiness check |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc documentation |

### Commands

```bash
# Development
make run              # Start development server
make test             # Run tests
make test-cov         # Run tests with coverage
make lint             # Lint code
make format           # Format code
make type-check       # Type check
make check            # Run all checks

# Deployment
docker-compose up     # Local Docker
terraform apply       # AWS deployment

# Evaluation
deepeval test run tests/deepeval/  # Run LLM evals
```

---

*Document Version: 1.0.0*
*Last Updated: 2024*
