# Overview

**Cost Center AI Orchestrator** is a FastAPI service that classifies customer messages using AI and routes them through category-specific workflows. It is designed for contact-center use with scalability, reliability, and compliance in mind.

## What It Does

- **Classify** incoming messages (chat, voice, mail) into three categories: **informational**, **service_action**, **safety_compliance**
- **Route** each message to the right workflow (FAQ lookup, ticketing, or safety/compliance)
- **Expose** a REST API for classification, plus a documentation UI and QA interface

## Quick Links

| Topic | Description |
|-------|-------------|
| [Solution Design](solution-design) | Design rationale, compliance, and trade-offs |
| [System Architecture](architecture) | Components, classification flow, and API |
| [Evaluation & Testing](evaluation) | Test strategy and sample results |
| [AWS](aws) | Deploy to ECS with Terraform |
| [Frontend](frontend) | Documentation UI and how to customize it |

## Run Locally

```bash
# Install and run
uv run uvicorn app.main:app --reload

# Docs UI
open http://localhost:8000/docs

# API docs
open http://localhost:8000/swagger
```

Set `OPENAI_API_KEY` in the environment for classification to work.

## Main Features

- **Single LLM call** per message for low latency
- **Workflow-based routing** (informational, service action, safety compliance)
- **Rate limiting** and **circuit breaker** for resilience
- **PII redaction** in logs
- **Structured logging** and optional **Confident AI** telemetry
