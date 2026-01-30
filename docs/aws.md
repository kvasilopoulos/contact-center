# AWS Deployment

Deploy the Cost Center AI Orchestrator to AWS ECS Fargate using Terraform. This page covers quick start, infrastructure, configuration, and operations.

## Quick Start

### Prerequisites

- AWS account with appropriate permissions
- Terraform 1.5.0+
- OpenAI API key
- Docker (for building images)

### 1. Configure Variables

Create `terraform/terraform.tfvars`:

```hcl
openai_api_key = "sk-your-openai-api-key"

# Optional
aws_region       = "us-east-1"
project_name     = "cost-center-orchestrator"
container_cpu    = 256
container_memory = 512
min_capacity     = 1
max_capacity     = 2
```

### 2. Deploy

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 3. Build and Push Image

After Terraform creates ECR:

```bash
docker build -t cost-center-orchestrator:latest .
terraform output deployment_commands   # run the shown commands to push
```

### 4. Verify

```bash
terraform output alb_url
curl $(terraform output -raw alb_url)/api/v1/health
```

## Infrastructure Overview

```
Internet → Application Load Balancer → ECS Fargate tasks (auto-scaling)
                                            ↓
                                    SSM Parameter Store (OpenAI key)
```

| Resource | Description |
|----------|-------------|
| **ECS Cluster** | Fargate cluster for containers |
| **ECS Service** | Auto-scaling (default 1–2 tasks) |
| **ALB** | Load balancer, health checks |
| **ECR** | Container registry |
| **SSM Parameter** | Secure OpenAI API key storage |
| **Security Groups** | ALB (HTTP), ECS (ALB only) |

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | `us-east-1` | AWS region |
| `project_name` | `cost-center-orchestrator` | Resource prefix |
| `container_cpu` | `256` | CPU units (0.25 vCPU) |
| `container_memory` | `512` | Memory (MB) |
| `min_capacity` / `max_capacity` | `1` / `2` | Task count range |
| `cpu_target_value` / `memory_target_value` | `70` / `80` | Scaling threshold % |

**Example – production:** higher CPU/memory, `min_capacity=2`, `max_capacity=10`, `log_level=WARNING`.

## Auto Scaling & Health

- **Scaling:** CPU >70% or memory >80% → scale out; cooldowns 60s (out), 300s (in).
- **Health:** ALB and container health checks use `/api/v1/health` (e.g. 30s interval).

## CI/CD

**GitHub Actions:** Configure secrets `AWS_ROLE_ARN`, `OPENAI_API_KEY`. Push to `main` → staging; version tag → production. Workflow: build → push image → Terraform apply → smoke tests.

**Manual:** `export TF_VAR_openai_api_key="sk-..."` then `cd terraform && terraform apply`.

## Monitoring & Rollback

- **Logs:** CloudWatch Logs group `/ecs/{project_name}`. Stream: `aws logs tail /ecs/cost-center-orchestrator --follow`.
- **Metrics:** CPUUtilization, MemoryUtilization (ECS); RequestCount, TargetResponseTime, 5XX (ALB).
- **Rollback:** `terraform apply -var="container_image=ECR_URL:previous-tag"` or update ECS task definition to a previous revision.

## Cost & Cleanup

**Default (1 task, 0.25 vCPU, 512MB):** ~$30–40/month (Fargate + ALB + data).

**Cleanup:** `cd terraform && terraform destroy`.
