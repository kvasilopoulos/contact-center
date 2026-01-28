# AWS Fargate Deployment with Terraform

Simple Terraform configuration to deploy the Cost Center AI Orchestrator to AWS Fargate.

## Features

- **Uses Default VPC** - No custom networking required
- **Fargate** - Serverless containers, pay only for what you use
- **Auto Scaling** - Scales based on CPU/Memory usage
- **Application Load Balancer** - Distributes traffic across tasks
- **ECR** - Private Docker registry
- **Secrets Manager** - Secure API key storage

## Architecture

```
Internet → ALB → ECS Fargate Tasks (Default VPC) → OpenAI API
                        ↓
                 Secrets Manager
```

## Prerequisites

1. **AWS CLI** configured with credentials
   ```bash
   aws configure
   ```

2. **Terraform** (1.5.0+)
   ```bash
   terraform --version
   ```

3. **Docker** for building images
   ```bash
   docker --version
   ```

4. **OpenAI API Key**
   Get from: https://platform.openai.com/api-keys

## Quick Start

### 1. Set OpenAI API Key

```bash
export TF_VAR_openai_api_key="sk-your-openai-api-key"
```

### 2. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform apply
```

This creates:
- ECS Fargate cluster (1 task with 0.25 vCPU, 0.5 GB)
- Application Load Balancer
- ECR repository
- Security groups
- IAM roles
- SSM Parameter (SecureString)

**Duration:** ~5 minutes

### 3. Build and Push Docker Image

```bash
# Get ECR URL
ECR_URL=$(terraform output -raw ecr_repository_url)
REGION=$(terraform output -raw aws_region)

# Authenticate
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ECR_URL

# Build and push
cd ..
docker build -t cost-center-orchestrator:latest .
docker tag cost-center-orchestrator:latest $ECR_URL:latest
docker push $ECR_URL:latest
```

### 4. Update Service with Image

```bash
cd terraform
terraform apply -var="container_image=$ECR_URL:latest" -auto-approve
```

### 5. Test the API

```bash
ALB_URL=$(terraform output -raw alb_url)

# Health check
curl $ALB_URL/api/v1/health

# Test classification
curl -X POST $ALB_URL/api/v1/classify \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is your refund policy?",
    "channel": "chat"
  }'
```

## Using the Deploy Script

A helper script is provided for easier deployment:

```bash
# Deploy infrastructure
export TF_VAR_openai_api_key="sk-..."
./scripts/deploy.sh deploy

# Build and push image, update service
./scripts/deploy.sh push

# Show deployment info
./scripts/deploy.sh info

# Destroy everything
./scripts/deploy.sh destroy
```

## Configuration

### Variables

Edit variables in `terraform apply` command or create a `terraform.tfvars` file:

```hcl
# terraform.tfvars
aws_region       = "us-east-1"
project_name     = "cost-center-orchestrator"
container_cpu    = 256      # 0.25 vCPU (cost-optimized)
container_memory = 512      # 0.5 GB (cost-optimized)
desired_count    = 1        # Number of tasks (cost-optimized)
min_capacity     = 1        # Min tasks for auto-scaling
max_capacity     = 2        # Max tasks for auto-scaling
```

### Scaling

The service auto-scales based on:
- **CPU**: Scales out when > 70%
- **Memory**: Scales out when > 80%

To manually scale:
```bash
terraform apply -var="desired_count=3"
```

## Updating the Application

### Deploy New Version

```bash
# 1. Build new image
docker build -t cost-center-orchestrator:v2 .

# 2. Tag and push
docker tag cost-center-orchestrator:v2 $ECR_URL:latest
docker push $ECR_URL:latest

# 3. Update service
cd terraform
terraform apply -var="container_image=$ECR_URL:latest" -auto-approve
```

Or simply:
```bash
./scripts/deploy.sh push
```

### Rollback

```bash
# Push previous image tag
docker tag cost-center-orchestrator:v1 $ECR_URL:latest
docker push $ECR_URL:latest

# Force new deployment
cd terraform
terraform apply -var="container_image=$ECR_URL:latest" -auto-approve
```

## Monitoring

### Check Service Status

```bash
CLUSTER=$(terraform output -raw ecs_cluster_name)
SERVICE=$(terraform output -raw ecs_service_name)

# Service details
aws ecs describe-services --cluster $CLUSTER --services $SERVICE

# List tasks
aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE

# Task details
TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER --service-name $SERVICE --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster $CLUSTER --tasks $TASK_ARN
```

### View Metrics in AWS Console

1. Go to ECS Console
2. Select your cluster
3. View Service → Metrics tab
4. Monitor CPU, Memory, Request count

## Cost Estimation

### Fargate Pricing (us-east-1)

| Configuration | vCPU | Memory | Cost/hour | Cost/month* |
|--------------|------|--------|-----------|-------------|
| **Current (Optimized)** | **0.25** | **0.5 GB** | **$0.0134** | **~$9.78** |
| Standard     | 0.5  | 1 GB   | $0.0247   | ~$18.03     |
| Enhanced     | 1    | 2 GB   | $0.0494   | ~$36.06     |

*Based on 1 task running 24/7

### Additional Costs

- **ALB**: ~$16-20/month (fixed)
- **Data Transfer**: ~$1/month (10GB)
- **ECR Storage**: ~$0.10/GB/month
- **SSM Parameter Store**: ~$0.00/month (FREE!)

### Total Estimate (Optimized Config)

- **1 task × 0.25 vCPU, 0.5 GB**: ~$9.78/month ✅
- **ALB**: ~$18/month
- **ECR + Data Transfer**: ~$1.10/month
- **SSM Parameter**: ~$0.00/month (FREE!)
- **Total**: **~$28.88/month** 🎉

**Savings: $61.12/month (68% reduction from $90)**

### Cost Optimization

✅ **Already optimized!** Current configuration uses:
- 1 task (instead of 2)
- 0.25 vCPU (instead of 0.5)
- 0.5 GB RAM (instead of 1 GB)
- SSM Parameter Store (instead of Secrets Manager)

**To scale up for production:**
   ```bash
   terraform apply -var="desired_count=2" -var="container_cpu=512" -var="container_memory=1024"
   ```

3. **Schedule scaling** (requires additional setup):
   - Scale down to 1 task during off-hours
   - Scale to 0 on weekends (requires custom setup)

## Troubleshooting

### Tasks Not Starting

Check task status:
```bash
aws ecs describe-services --cluster $CLUSTER --services $SERVICE --query 'services[0].events[0:5]'
```

Common issues:
- Invalid OpenAI API key in Secrets Manager
- Insufficient IAM permissions
- Image not found in ECR
- Resource limits too low

### Health Check Failures

Check ALB target health:
```bash
TARGET_GROUP=$(terraform output -raw target_group_arn 2>/dev/null || \
  aws elbv2 describe-target-groups --query 'TargetGroups[?contains(TargetGroupName, `cost-center`)].TargetGroupArn | [0]' --output text)
  
aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP
```

### Deployment Stuck

Force new deployment:
```bash
aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment
```

## Cleanup

### Destroy All Resources

```bash
cd terraform
terraform destroy
```

Or:
```bash
./scripts/deploy.sh destroy
```

**Note:** This will delete:
- ECS cluster and tasks
- Load balancer
- ECR repository and images
- Security groups
- IAM roles
- Secrets

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use IAM roles** instead of access keys
3. **Rotate API keys** regularly
4. **Review security groups** - restrict to known IPs if needed
5. **Enable MFA** on AWS account
6. **Use separate AWS accounts** for prod/dev

## Additional Resources

- [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/)
- [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/intro.html)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

## Support

For issues:
1. Check AWS ECS console for task errors
2. Review service events
3. Check security group rules
4. Verify OpenAI API key in Secrets Manager
