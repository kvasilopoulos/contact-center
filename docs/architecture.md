# System Architecture

## Overview

The Contact Center AI Orchestrator is a scalable FastAPI service that classifies customer messages using AI and routes them through category-specific workflows.

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│    │   Chat   │    │   Voice  │    │   Mail   │    │   API    │            │
│    │  Widget  │    │   IVR    │    │  Parser  │    │  Client  │            │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘            │
└─────────┼───────────────┼───────────────┼───────────────┼──────────────────┘
          │               │               │               │
          └───────────────┴───────┬───────┴───────────────┘
                                  │
                          ┌───────▼───────┐
                          │  Load Balancer │
                          │   (Optional)   │
                          └───────┬───────┘
                                  │
┌─────────────────────────────────┼─────────────────────────────────────────┐
│                    ORCHESTRATOR SERVICE                                    │
│                                 │                                          │
│  ┌──────────────────────────────▼────────────────────────────────────┐    │
│  │                         FastAPI Application                        │    │
│  │  ┌─────────────────────────────────────────────────────────────┐  │    │
│  │  │                      Middleware Layer                        │  │    │
│  │  │  • Request ID Generation    • Logging    • Rate Limiting    │  │    │
│  │  └─────────────────────────────────────────────────────────────┘  │    │
│  │                                │                                   │    │
│  │  ┌─────────────────────────────▼─────────────────────────────────┐│    │
│  │  │                       API Layer (v1)                          ││    │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  ││    │
│  │  │  │  /health   │  │  /ready    │  │  POST /api/v1/classify │  ││    │
│  │  │  └────────────┘  └────────────┘  └───────────┬────────────┘  ││    │
│  │  └──────────────────────────────────────────────┼────────────────┘│    │
│  │                                                 │                  │    │
│  │  ┌──────────────────────────────────────────────▼────────────────┐│    │
│  │  │                     Services Layer                             ││    │
│  │  │  ┌────────────────────────┐  ┌────────────────────────────┐   ││    │
│  │  │  │   ClassifierService    │  │       LLMClient            │   ││    │
│  │  │  │  • Message analysis    │  │  • OpenAI integration      │   ││    │
│  │  │  │  • Prompt formatting   │◄─┤  • Retry logic             │   ││    │
│  │  │  │  • Confidence scoring  │  │  • Error handling          │   ││    │
│  │  │  └───────────┬────────────┘  └────────────────────────────┘   ││    │
│  │  │              │                                                 ││    │
│  │  └──────────────┼─────────────────────────────────────────────────┘│    │
│  │                 │                                                   │    │
│  │  ┌──────────────▼─────────────────────────────────────────────────┐│    │
│  │  │                     Workflows Layer                             ││    │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   ││    │
│  │  │  │ Informational│  │ ServiceAction│  │ SafetyCompliance   │   ││    │
│  │  │  │   Workflow   │  │   Workflow   │  │     Workflow       │   ││    │
│  │  │  │              │  │              │  │                    │   ││    │
│  │  │  │ • FAQ lookup │  │ • Intent     │  │ • Severity assess  │   ││    │
│  │  │  │ • KB search  │  │   extraction │  │ • Compliance log   │   ││    │
│  │  │  │              │  │ • Action prep│  │ • PII redaction    │   ││    │
│  │  │  └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘   ││    │
│  │  │         │                 │                    │               ││    │
│  │  └─────────┼─────────────────┼────────────────────┼───────────────┘│    │
│  └────────────┼─────────────────┼────────────────────┼────────────────┘    │
│               │                 │                    │                      │
└───────────────┼─────────────────┼────────────────────┼──────────────────────┘
                │                 │                    │
┌───────────────▼─────────────────▼────────────────────▼──────────────────────┐
│                         EXTERNAL SYSTEMS (Stubs)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Knowledge   │  │   Ticketing  │  │    Order     │  │  Compliance  │    │
│  │     Base     │  │    System    │  │  Management  │  │    System    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Classification Flow

```
┌─────────────────┐
│ Incoming Message│
│   + Channel     │
│   + Metadata    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validate Input │
│ • Length check  │
│ • Channel valid │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│    Classifier   │────▶│   OpenAI API    │
│    Service      │◀────│  (gpt-4o-mini)  │
└────────┬────────┘     └─────────────────┘
         │
         │ Returns: category, confidence, reasoning
         ▼
┌─────────────────┐
│  Route to       │
│  Workflow       │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┐
    ▼         ▼              ▼
┌───────┐ ┌───────┐ ┌────────────┐
│ Info  │ │Service│ │  Safety    │
│ Flow  │ │Action │ │ Compliance │
└───┬───┘ └───┬───┘ └─────┬──────┘
    │         │           │
    ▼         ▼           ▼
┌─────────────────────────────┐
│      Build Response         │
│ • Category                  │
│ • Confidence                │
│ • Decision path             │
│ • Next step                 │
│ • Processing time           │
└─────────────────────────────┘
```

## E2E Workflow Designs

### Informational Workflow

```
┌────────────────┐
│ Informational  │
│    Message     │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Confidence     │
│ Check (≥0.5)   │
└───────┬────────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──────┐  ┌──────────────┐
│ Low  │  │ Sufficient   │
│      │  └──────┬───────┘
│      │         │
│      │         ▼
│      │  ┌──────────────┐
│      │  │ Search FAQ   │
│      │  │ Database     │
│      │  └──────┬───────┘
│      │         │
│      │    ┌────┴────┐
│      │    ▼         ▼
│      │ ┌──────┐ ┌──────────┐
│      │ │Match │ │ No Match │
│      │ │Found │ │          │
│      │ └──┬───┘ └────┬─────┘
│      │    │          │
│      │    ▼          ▼
│      │ ┌──────┐ ┌──────────────┐
│      │ │Return│ │Suggest       │
│      │ │FAQ   │ │Contact       │
│      │ │Info  │ │Options       │
│      │ └──────┘ └──────────────┘
│      │
▼      │
┌──────────────┐
│ Escalate to  │
│ Human Agent  │
└──────────────┘
```

### Service Action Workflow

```
┌────────────────┐
│ Service Action │
│    Message     │
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Extract Intent │
└───────┬────────┘
        │
   ┌────┼────┬────┬────┬────┐
   ▼    ▼    ▼    ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
│Open ││Track││Refund││Cancel││Update│
│Ticket││Order││      ││Order ││Acct  │
└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘
   │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼
┌─────────────────────────────────┐
│     Prepare Action Template     │
│  • Extract order reference      │
│  • Validate customer context    │
│  • Generate next steps          │
└─────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│   Return with External System   │
│   Integration Details (Stub)    │
└─────────────────────────────────┘
```

### Safety Compliance Workflow

```
┌────────────────┐
│ Safety Message │
└───────┬────────┘
        │
        ▼
┌────────────────────┐
│  Assess Severity   │
│  • Urgent patterns │
│  • High patterns   │
│  • Standard        │
└───────┬────────────┘
        │
   ┌────┼────────┬────────────┐
   ▼              ▼            ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ URGENT  │ │  HIGH   │ │STANDARD │
│         │ │         │ │         │
│Emergency│ │ Adverse │ │ General │
│symptoms │ │reaction │ │ concern │
└────┬────┘ └────┬────┘ └────┬────┘
     │           │           │
     ▼           ▼           ▼
┌─────────────────────────────────┐
│    Create Compliance Record     │
│    (Audit Trail)                │
└─────────────────────────────────┘
     │           │           │
     ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│15 min   │ │ 2 hour  │ │ 24 hour │
│SLA      │ │ SLA     │ │ SLA     │
│Pharmacst│ │Pharmacst│ │Complianc│
└─────────┘ └─────────┘ └─────────┘
```

## Scalability Design

### Horizontal Scaling

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │  (nginx/ALB)    │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Container 1  │  │  Container 2  │  │  Container N  │
│  (Replica)    │  │  (Replica)    │  │  (Replica)    │
│               │  │               │  │               │
│  FastAPI App  │  │  FastAPI App  │  │  FastAPI App  │
└───────────────┘  └───────────────┘  └───────────────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   OpenAI API    │
                    │ (External LLM)  │
                    └─────────────────┘
```

### Spike Handling Strategy

1. **Rate Limiting**: Token bucket algorithm (60 req/min default)
2. **Circuit Breaker**: Fail-fast when LLM is degraded
3. **Async Processing**: Non-blocking I/O with FastAPI
4. **Connection Pooling**: Reuse HTTP connections to OpenAI

### Configuration for Scale

```python
Settings:
  - max_concurrent_requests: 100
  - rate_limit_requests_per_minute: 60
  - openai_timeout: 30.0
  - openai_max_retries: 3
```

## Monitoring Approach

### Metrics (Prometheus-compatible)

| Metric | Type | Description |
|--------|------|-------------|
| `classification_requests_total` | Counter | Total classification requests |
| `classification_latency_seconds` | Histogram | Request latency |
| `classification_confidence` | Histogram | Confidence score distribution |
| `classification_by_category` | Counter | Requests by category |
| `llm_errors_total` | Counter | LLM API errors |

### Logging

- Structured JSON logging (structlog)
- Request ID tracing
- PII redaction for safety compliance
- Log levels: DEBUG, INFO, WARNING, ERROR

### Health Checks

- `/health` - Liveness probe (is the service running?)
- `/ready` - Readiness probe (are dependencies available?)

## Compliance & Security

### Data Flow Security

```
┌────────────────┐
│ Customer       │
│ Message        │
└───────┬────────┘
        │
        ▼
┌────────────────────────────────┐
│     Input Validation           │
│  • Length limits (5000 chars)  │
│  • Channel validation          │
└───────┬────────────────────────┘
        │
        ▼
┌────────────────────────────────┐
│     Classification             │
│  • Message sent to OpenAI      │
│  • No PII stored locally       │
└───────┬────────────────────────┘
        │
        ▼
┌────────────────────────────────┐
│     Safety Compliance Path     │
│  • PII redacted in logs        │
│  • Compliance record created   │
│  • Audit trail maintained      │
└────────────────────────────────┘
```

### Security Measures

1. **Input Validation**: Message length limits, channel validation
2. **No Secrets in Code**: Environment variables for API keys
3. **Rate Limiting**: Prevent abuse
4. **PII Redaction**: Automatic in safety compliance logs
5. **Audit Trail**: Compliance records for safety reports

## CI/CD Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Commit    │────▶│    CI       │────▶│  CD         │
└─────────────┘     │  Pipeline   │     │  Pipeline   │
                    └──────┬──────┘     └──────┬──────┘
                           │                   │
              ┌────────────┼────────────┐      │
              ▼            ▼            ▼      │
        ┌─────────┐ ┌─────────┐ ┌─────────┐   │
        │  Lint   │ │  Test   │ │  Build  │   │
        │  (ruff) │ │(pytest) │ │(Docker) │   │
        └─────────┘ └─────────┘ └─────────┘   │
                                               │
                    ┌──────────────────────────┘
                    │
              ┌─────┴─────┐
              ▼           ▼
        ┌─────────┐ ┌─────────┐
        │ Staging │ │Production│
        │ Deploy  │ │ Deploy  │
        └─────────┘ └─────────┘
```

## Assumptions & Trade-offs

### Assumptions

1. OpenAI API is available and responsive
2. Single LLM call provides sufficient accuracy
3. Chat channel patterns generalize to voice/mail
4. External systems are stubbed (not implemented)

### Trade-offs

| Decision | Benefit | Cost |
|----------|---------|------|
| OpenAI vs Local LLM | Better accuracy | API costs, latency |
| Sync vs Queue | Simpler architecture | Limited burst handling |
| Monolith vs Microservices | Easier deployment | Less granular scaling |
| In-memory FAQ | Fast lookup | Limited scalability |

## Future Enhancements

1. **Async Queue**: Add Redis/RabbitMQ for spike handling
2. **Semantic Search**: Replace keyword FAQ with embeddings
3. **ML Pipeline**: Train custom classifier on labeled data
4. **Multi-region**: Deploy to multiple regions for latency
5. **Real External Systems**: Integrate actual ticketing, CRM systems
