# Deploy to AWS

Step-by-step guide to deploy the Contact Center AI Orchestrator on ECS Fargate with Terraform.

## Prerequisites

- AWS account with appropriate IAM permissions
- Terraform 1.5.0+
- Docker
- OpenAI API key

## 1. Configure Variables

Create `terraform/terraform.tfvars`:

```hcl
openai_api_key = "sk-your-openai-api-key"

# Optional overrides
aws_region       = "us-east-1"
project_name     = "cost-center-orchestrator"
container_cpu    = 256
container_memory = 512
min_capacity     = 1
max_capacity     = 2
```

### Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | `us-east-1` | AWS region |
| `project_name` | `cost-center-orchestrator` | Resource name prefix |
| `container_cpu` | `256` | CPU units (0.25 vCPU) |
| `container_memory` | `512` | Memory in MB |
| `min_capacity` / `max_capacity` | `1` / `2` | Auto-scaling task count range |
| `cpu_target_value` / `memory_target_value` | `70` / `80` | Scaling threshold (%) |

**Production example:** higher CPU/memory, `min_capacity=2`, `max_capacity=10`, `log_level=WARNING`.

## 2. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

## 3. Build and Push Image

After Terraform creates the ECR repository:

```bash
docker build -t cost-center-orchestrator:latest .
terraform output deployment_commands   # run the printed commands to push
```

## 4. Verify

```bash
terraform output alb_url
curl $(terraform output -raw alb_url)/api/v1/health
```

## 5. Stream Logs

```bash
aws logs tail /ecs/cost-center-orchestrator --follow
```

## Cleanup

```bash
cd terraform && terraform destroy
```
