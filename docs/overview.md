# Overview

## The Problem

A contact center handles a continuous stream of customer messages that span very different domains: policy inquiries, service requests (refunds, cancellations, order tracking), and safety-critical reports (adverse drug reactions, medical emergencies). These messages arrive through multiple channels (chat, voice, mail) and each category demands a fundamentally different response: an informational question can be answered from a knowledge base, a service request must trigger an action in an external system, and a safety report must be escalated immediately with full audit compliance.

Routing these messages manually is slow, inconsistent, and does not scale. The goal of this project is to automate the classification and initial routing of customer messages using an LLM, while maintaining the reliability, traceability, and compliance guarantees that a production contact center requires.

## The Solution

The **Contact Center AI Orchestrator** is a FastAPI service that accepts a customer message, classifies it into one of three categories using a single OpenAI GPT-4.1 call, and then dispatches it through a category-specific workflow that determines the concrete next step.

The three categories and their workflows are:

- **Informational** -- Policy questions, FAQs, product inquiries. The workflow searches a knowledge base and returns an answer or suggests contacting support.
- **Service Action** -- Ticket creation, order tracking, refunds, cancellations. The workflow extracts the user's intent and prepares the appropriate action template.
- **Safety Compliance** -- Adverse reactions, health concerns, emergencies. The workflow assesses severity, creates a compliance audit record, redacts PII, and escalates to the appropriate team with an SLA based on urgency.

## Design Philosophy

Three principles shape every architectural decision in this system:

**Separation of classification from action.** The LLM decides *what the message is*. The workflow engine decides *what to do about it*. This separation means the classification model can be swapped, retrained, or A/B tested without touching business logic, and new workflows can be added without modifying the classifier.

**Resilience over throughput.** The system depends on an external LLM API that can fail, slow down, or become temporarily unavailable. Rather than optimizing for peak throughput, the architecture prioritizes graceful degradation: rate limiting protects the system from demand spikes, circuit breaking prevents cascade failures when the LLM is down, and confidence thresholds ensure uncertain classifications are escalated to humans rather than acted on automatically.

**Safety-first bias.** In a healthcare-adjacent context, a missed safety report is far more costly than a false positive. The system is intentionally biased toward classifying ambiguous messages as safety-critical and always requires human review for safety compliance cases, regardless of confidence.

## How It Fits Together

```
Client Message
      │
      ▼
  Validation → Rate Limiter → Circuit Breaker → LLM Classification
                                                        │
                                                   Parse Result
                                                        │
                                          ┌─────────────┼─────────────┐
                                          ▼             ▼             ▼
                                   Informational   Service Action   Safety Compliance
                                     Workflow        Workflow          Workflow
                                          │             │             │
                                          └─────────────┼─────────────┘
                                                        ▼
                                                  JSON Response
                                                   + Telemetry
```

Every request passes through the same middleware chain (validation, rate limiting, request tracing) before reaching the classifier. The classifier calls the LLM once and returns a structured result with category, confidence score, and reasoning. The dispatch layer routes the result to the appropriate workflow, and the workflow returns a concrete action with priority, description, and any external system references.

## Quick Links

| Topic | Description |
|-------|-------------|
| [Solution Design](solution-design) | Why each architectural pattern was chosen and what trade-offs were accepted |
| [System Architecture](architecture) | Component diagrams, request flow, workflow details, and API surface |
| [Evaluation & Testing](evaluation) | Test strategy, quality gates, and the feedback loop |
| [AWS Deployment](aws) | Deploy to ECS Fargate with Terraform |
| [Frontend](frontend) | Documentation UI and customization |

## Run Locally

```bash
uv sync                                          # install dependencies
cp .env.example .env                              # add OPENAI_API_KEY
uv run uvicorn app.main:app --reload              # start server
```

- Documentation UI: `http://localhost:8000/docs`
- Swagger: `http://localhost:8000/swagger`
- ReDoc: `http://localhost:8000/redoc`
