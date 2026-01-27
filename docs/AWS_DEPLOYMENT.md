# AWS ECS Deployment Guide

This guide provides comprehensive instructions for deploying the Contact Center AI Orchestrator to AWS ECS using Terraform.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Architecture](#architecture)
4. [Setup Instructions](#setup-instructions)
5. [Deployment Process](#deployment-process)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)

## Overview

The Contact Center AI Orchestrator is deployed to AWS ECS (Elastic Container Service) using Fargate, which provides serverless compute for containers. The infrastructure is managed using Terraform and deployed automatically via GitHub Actions.

### Key Components

- **ECS Fargate**: Serverless container orchestration
- **Application Load Balancer (ALB)**: Traffic distribution and health checking
- **VPC**: Isolated network with public and private subnets
- **Secrets Manager**: Secure storage for API keys
- **CloudWatch**: Logging and monitoring
- **Auto Scaling**: Automatic scaling based on CPU and memory utilization

## Prerequisites

### Required Tools

- AWS CLI (v2.x or higher)
- Terraform (v1.5.0 or higher)
- Docker (for local testing)
- Git

### AWS Account Requirements

1. **AWS Account** with appropriate permissions
2. **IAM Roles** for GitHub Actions OIDC
3. **Domain name** (optional, for custom domain)
4. **ACM Certificate** (optional, for HTTPS)

### Required Secrets

The following secrets need to be configured:

- `OPENAI_API_KEY`: OpenAI API key for the application
- `AWS_ROLE_ARN_STAGING`: AWS IAM role ARN for staging deployments
- `AWS_ROLE_ARN_PRODUCTION`: AWS IAM role ARN for production deployments

## Architecture

### Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────┐
│                          Internet                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Application Load    │
              │      Balancer        │
              └──────────┬───────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌────────┐     ┌────────┐     ┌────────┐
    │  ECS   │     │  ECS   │     │  ECS   │
    │ Task 1 │     │ Task 2 │     │ Task N │
    └────────┘     └────────┘     └────────┘
         │               │               │
         └───────────────┼───────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   AWS Secrets        │
              │     Manager          │
              └──────────────────────┘
```

### Network Architecture

- **Public Subnets**: ALB resides here
- **Private Subnets**: ECS tasks run here
- **NAT Gateways**: Enable outbound internet access from private subnets
- **Security Groups**: Control traffic flow

## Setup Instructions

### Step 1: Configure AWS IAM Role for GitHub Actions

Create an OIDC provider and IAM role for GitHub Actions:

```bash
# Create OIDC provider (one-time setup)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

Create IAM role with the following trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/YOUR_REPO:*"
        }
      }
    }
  ]
}
```

Attach the following policies to the role:
- `AmazonEC2FullAccess`
- `AmazonECS_FullAccess`
- `AmazonVPCFullAccess`
- `IAMFullAccess`
- `SecretsManagerReadWrite`
- `CloudWatchFullAccess`
- `ElasticLoadBalancingFullAccess`

### Step 2: Configure GitHub Secrets

Add the following secrets to your GitHub repository:

1. Go to `Settings` → `Secrets and variables` → `Actions`
2. Add the following secrets:

   ```
   OPENAI_API_KEY: Your OpenAI API key
   AWS_ROLE_ARN_STAGING: arn:aws:iam::ACCOUNT_ID:role/github-actions-staging
   AWS_ROLE_ARN_PRODUCTION: arn:aws:iam::ACCOUNT_ID:role/github-actions-production
   ```

### Step 3: Configure Terraform Backend (Optional but Recommended)

For production use, configure an S3 backend for Terraform state:

1. Create an S3 bucket:

```bash
aws s3 mb s3://your-terraform-state-bucket --region us-east-1
```

2. Create a DynamoDB table for state locking:

```bash
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1
```

3. Uncomment the backend configuration in `terraform/main.tf`:

```hcl
backend "s3" {
  bucket         = "your-terraform-state-bucket"
  key            = "orchestrator/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "terraform-state-lock"
  encrypt        = true
}
```

### Step 4: Review and Customize Configuration

Edit the environment-specific variable files:

- `terraform/environments/staging.tfvars`
- `terraform/environments/production.tfvars`

Customize values such as:
- Container CPU and memory allocations
- Auto-scaling thresholds
- Log retention periods
- VPC CIDR blocks

## Deployment Process

### Automated Deployment via GitHub Actions

The CD pipeline automatically deploys to AWS ECS when:

1. **Staging**: On every push to `main` branch
2. **Production**: On version tags (e.g., `v1.0.0`)

#### Manual Deployment Trigger

You can manually trigger a deployment:

1. Go to `Actions` → `CD Pipeline`
2. Click `Run workflow`
3. Select the environment (staging or production)
4. Click `Run workflow`

### Manual Deployment via Terraform

If you need to deploy manually:

#### Deploy to Staging

```bash
# Navigate to terraform directory
cd terraform

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan \
  -var-file=environments/staging.tfvars \
  -var="container_image=ghcr.io/your-org/your-repo:latest" \
  -var="openai_api_key=$OPENAI_API_KEY"

# Apply the changes
terraform apply \
  -var-file=environments/staging.tfvars \
  -var="container_image=ghcr.io/your-org/your-repo:latest" \
  -var="openai_api_key=$OPENAI_API_KEY"
```

#### Deploy to Production

```bash
terraform plan \
  -var-file=environments/production.tfvars \
  -var="container_image=ghcr.io/your-org/your-repo:v1.0.0" \
  -var="openai_api_key=$OPENAI_API_KEY"

terraform apply \
  -var-file=environments/production.tfvars \
  -var="container_image=ghcr.io/your-org/your-repo:v1.0.0" \
  -var="openai_api_key=$OPENAI_API_KEY"
```

### Deployment Workflow

1. **Build**: Docker image is built and pushed to GitHub Container Registry
2. **Infrastructure**: Terraform provisions/updates AWS resources
3. **Deploy**: ECS service is updated with the new task definition
4. **Health Check**: Automated smoke tests verify the deployment
5. **Monitoring**: CloudWatch alarms monitor the application

## Monitoring and Maintenance

### CloudWatch Dashboards

Access CloudWatch dashboards:

```bash
# Get the ECS cluster name
terraform output ecs_cluster_name

# Navigate to CloudWatch in AWS Console
# Services → CloudWatch → Dashboards
```

### CloudWatch Alarms

The following alarms are configured:

1. **High CPU Utilization** (threshold: 85%)
2. **High Memory Utilization** (threshold: 85%)
3. **Unhealthy Targets** (threshold: > 0)
4. **High 5xx Errors** (threshold: > 10 in 5 minutes)
5. **High Response Time** (threshold: > 5 seconds)

### Viewing Logs

```bash
# Get the log group name
terraform output cloudwatch_log_group

# View logs via AWS CLI
aws logs tail /ecs/contact-center-orchestrator-staging --follow
```

### Accessing the Application

```bash
# Get the ALB URL
terraform output alb_url

# Test the health endpoint
curl $(terraform output -raw alb_url)/api/v1/health
```

### Scaling the Service

Scaling is automatic based on CPU and memory utilization. To manually adjust:

```bash
# Update desired_count in the tfvars file
# Then apply the changes
terraform apply -var-file=environments/staging.tfvars
```

## Troubleshooting

### Common Issues

#### 1. Deployment Fails During Apply

**Symptoms**: Terraform apply fails with timeout

**Solution**:
```bash
# Check ECS service events
aws ecs describe-services \
  --cluster CLUSTER_NAME \
  --services SERVICE_NAME \
  --query 'services[0].events[:10]'

# Check task status
aws ecs list-tasks \
  --cluster CLUSTER_NAME \
  --service-name SERVICE_NAME

# View task details
aws ecs describe-tasks \
  --cluster CLUSTER_NAME \
  --tasks TASK_ARN
```

#### 2. Tasks Failing to Start

**Symptoms**: ECS tasks continuously restart

**Possible causes**:
- Missing environment variables
- Invalid Secrets Manager permissions
- Container health check failures
- Insufficient CPU/memory

**Solution**:
```bash
# Check container logs
aws logs get-log-events \
  --log-group-name /ecs/contact-center-orchestrator-staging \
  --log-stream-name orchestrator/TASK_ID
```

#### 3. Load Balancer Health Checks Failing

**Symptoms**: Targets marked as unhealthy

**Solution**:
- Verify health check path: `/api/v1/health`
- Check security group rules allow ALB → ECS traffic on port 8000
- Review application logs for errors

#### 4. Secret Access Issues

**Symptoms**: Container fails to start with secret retrieval errors

**Solution**:
```bash
# Verify secret exists
aws secretsmanager describe-secret \
  --secret-id staging/orchestrator/openai_api_key

# Check task execution role has permissions
aws iam get-role-policy \
  --role-name staging-orchestrator-task-execution-role \
  --policy-name staging-orchestrator-secrets-policy
```

### Rollback Procedure

If a deployment fails, rollback to the previous version:

```bash
# Option 1: Via Terraform (redeploy previous image)
terraform apply \
  -var-file=environments/staging.tfvars \
  -var="container_image=PREVIOUS_IMAGE_TAG"

# Option 2: Via AWS CLI
aws ecs update-service \
  --cluster CLUSTER_NAME \
  --service SERVICE_NAME \
  --task-definition PREVIOUS_TASK_DEFINITION_ARN
```

### Getting Help

1. Check CloudWatch Logs for application errors
2. Review ECS service events for deployment issues
3. Verify security group rules and network connectivity
4. Check IAM permissions for task execution and task roles

## Cost Optimization

### Recommendations

1. **Use FARGATE_SPOT**: Already configured in capacity providers for cost savings
2. **Right-size containers**: Monitor CPU and memory usage, adjust allocations
3. **Optimize log retention**: Reduce CloudWatch log retention period if not needed
4. **Use NAT Gateway efficiently**: Consider sharing NAT gateways across environments

### Cost Monitoring

```bash
# Use AWS Cost Explorer to monitor spending
# Services → Cost Management → Cost Explorer

# Set up budget alerts
aws budgets create-budget \
  --account-id ACCOUNT_ID \
  --budget file://budget.json
```

## Security Best Practices

1. **Secrets**: Never commit secrets to Git. Use AWS Secrets Manager or GitHub Secrets
2. **IAM Roles**: Use least-privilege principle for IAM roles
3. **Network**: ECS tasks in private subnets, only ALB in public subnets
4. **Container**: Non-root user specified in Dockerfile
5. **HTTPS**: Configure ACM certificate for production
6. **Security Groups**: Restrict access to only required ports

## Next Steps

1. Configure custom domain name with Route 53
2. Set up ACM certificate for HTTPS
3. Configure SNS topics for CloudWatch alarms
4. Implement distributed tracing with X-Ray
5. Set up AWS WAF for additional security
6. Configure backup and disaster recovery procedures

## Additional Resources

- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/)
