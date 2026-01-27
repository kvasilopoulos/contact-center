# Terraform Infrastructure

This directory contains Terraform configuration for deploying the Contact Center AI Orchestrator to AWS ECS.

## Structure

```
terraform/
├── main.tf                 # Main infrastructure configuration
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── environments/           # Environment-specific configurations
│   ├── staging.tfvars      # Staging environment variables
│   └── production.tfvars   # Production environment variables
└── modules/                # Reusable Terraform modules
    ├── vpc/                # VPC and networking
    ├── security_groups/    # Security group configurations
    ├── iam/                # IAM roles and policies
    ├── ecs/                # ECS cluster
    ├── alb/                # Application Load Balancer
    ├── secrets/            # Secrets Manager
    ├── ecs_service/        # ECS service and task definitions
    └── monitoring/         # CloudWatch alarms
```

## Quick Start

### Initialize Terraform

```bash
cd terraform
terraform init
```

### Plan Deployment

```bash
# Staging
terraform plan \
  -var-file=environments/staging.tfvars \
  -var="container_image=ghcr.io/your-org/repo:tag" \
  -var="openai_api_key=$OPENAI_API_KEY"

# Production
terraform plan \
  -var-file=environments/production.tfvars \
  -var="container_image=ghcr.io/your-org/repo:tag" \
  -var="openai_api_key=$OPENAI_API_KEY"
```

### Apply Changes

```bash
# Staging
terraform apply \
  -var-file=environments/staging.tfvars \
  -var="container_image=ghcr.io/your-org/repo:tag" \
  -var="openai_api_key=$OPENAI_API_KEY"

# Production
terraform apply \
  -var-file=environments/production.tfvars \
  -var="container_image=ghcr.io/your-org/repo:tag" \
  -var="openai_api_key=$OPENAI_API_KEY"
```

## Environment Variables

Required variables:
- `container_image`: Docker image URI
- `openai_api_key`: OpenAI API key (set via `TF_VAR_openai_api_key`)

Optional variables:
- `acm_certificate_arn`: ACM certificate for HTTPS
- `sns_alert_topic_arn`: SNS topic for CloudWatch alarms

## Outputs

After deployment, Terraform provides these outputs:

```bash
# Get ALB URL
terraform output alb_url

# Get ECS cluster name
terraform output ecs_cluster_name

# Get all outputs
terraform output
```

## State Management

For production use, configure remote state:

```hcl
# Uncomment in main.tf
backend "s3" {
  bucket         = "your-terraform-state-bucket"
  key            = "orchestrator/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "terraform-state-lock"
  encrypt        = true
}
```

## Module Documentation

### VPC Module
Creates VPC with public and private subnets, NAT gateways, and routing tables.

### Security Groups Module
Configures security groups for ALB and ECS tasks.

### IAM Module
Creates task execution role and task role with required permissions.

### ECS Module
Sets up ECS cluster with Fargate capacity providers.

### ALB Module
Creates Application Load Balancer, target group, and listeners.

### Secrets Module
Manages secrets in AWS Secrets Manager.

### ECS Service Module
Configures ECS service, task definition, and auto-scaling policies.

### Monitoring Module
Sets up CloudWatch alarms for monitoring.

## Troubleshooting

### State Lock Issues

```bash
# Force unlock (use with caution)
terraform force-unlock LOCK_ID
```

### Destroy Resources

```bash
terraform destroy \
  -var-file=environments/staging.tfvars \
  -var="container_image=ghcr.io/your-org/repo:tag" \
  -var="openai_api_key=$OPENAI_API_KEY"
```

### Validate Configuration

```bash
terraform validate
```

### Format Configuration

```bash
terraform fmt -recursive
```

## Best Practices

1. **Use workspaces** for multiple environments
2. **Enable remote state** with S3 backend
3. **Use state locking** with DynamoDB
4. **Never commit** sensitive values
5. **Review plans** before applying
6. **Tag resources** appropriately
7. **Use modules** for reusability

## Additional Resources

- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [Full Deployment Guide](../docs/AWS_DEPLOYMENT.md)
- [Quick Start Guide](../docs/AWS_QUICK_START.md)
