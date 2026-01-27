# AWS ECS Deployment - Quick Start Guide

This guide helps you get the Contact Center AI Orchestrator deployed to AWS ECS in minutes.

## Prerequisites Checklist

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured
- [ ] Terraform 1.5.0+ installed
- [ ] GitHub repository with Actions enabled
- [ ] OpenAI API key

## 5-Step Deployment

### Step 1: Configure AWS IAM for GitHub Actions (5 minutes)

Create the OIDC provider and IAM role:

```bash
# Set your variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export GITHUB_ORG="your-github-org"
export GITHUB_REPO="your-repo-name"

# Create OIDC provider (skip if already exists)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Create IAM role for staging
aws iam create-role \
  --role-name github-actions-orchestrator-staging \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::'$AWS_ACCOUNT_ID':oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:'$GITHUB_ORG'/'$GITHUB_REPO':*"
        }
      }
    }]
  }'

# Attach required policies (simplified for quick start - use AdministratorAccess)
aws iam attach-role-policy \
  --role-name github-actions-orchestrator-staging \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

# Repeat for production
aws iam create-role \
  --role-name github-actions-orchestrator-production \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::'$AWS_ACCOUNT_ID':oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:'$GITHUB_ORG'/'$GITHUB_REPO':*"
        }
      }
    }]
  }'

aws iam attach-role-policy \
  --role-name github-actions-orchestrator-production \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

### Step 2: Configure GitHub Secrets (2 minutes)

Add these secrets in GitHub repository settings (`Settings` → `Secrets and variables` → `Actions`):

```bash
# Get your role ARNs
aws iam get-role --role-name github-actions-orchestrator-staging --query 'Role.Arn' --output text
aws iam get-role --role-name github-actions-orchestrator-production --query 'Role.Arn' --output text
```

Add to GitHub Secrets:
- `OPENAI_API_KEY`: Your OpenAI API key
- `AWS_ROLE_ARN_STAGING`: Output from first command above
- `AWS_ROLE_ARN_PRODUCTION`: Output from second command above

### Step 3: Review Configuration (2 minutes)

Edit `terraform/environments/staging.tfvars` if needed:

```hcl
# Default values are good for getting started
# Optionally customize:
# - aws_region
# - container_cpu / container_memory
# - min_capacity / max_capacity
```

### Step 4: Deploy (Automatic via GitHub Actions)

**Option A: Deploy Staging**

```bash
# Just push to main branch
git add .
git commit -m "Configure AWS deployment"
git push origin main
```

The GitHub Actions workflow will:
1. Build Docker image
2. Push to GitHub Container Registry
3. Deploy infrastructure with Terraform
4. Deploy application to ECS
5. Run health checks

**Option B: Deploy Production**

```bash
# Create and push a version tag
git tag v1.0.0
git push origin v1.0.0
```

### Step 5: Verify Deployment (2 minutes)

Wait for GitHub Actions to complete (check the Actions tab), then:

```bash
# If deploying locally with Terraform, get the ALB URL
cd terraform
terraform output alb_url

# Test the health endpoint
curl $(terraform output -raw alb_url)/api/v1/health

# Expected response:
# {"status": "healthy", ...}
```

## Accessing Your Application

After deployment completes:

1. **Get the URL**:
   ```bash
   cd terraform
   terraform output alb_url
   ```

2. **Test Classification API**:
   ```bash
   ALB_URL=$(terraform output -raw alb_url)
   
   curl -X POST "${ALB_URL}/api/v1/classify" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "I need help with my account",
       "session_id": "test-123"
     }'
   ```

3. **View Logs**:
   ```bash
   aws logs tail /ecs/contact-center-orchestrator-staging --follow
   ```

## What Was Created?

Your infrastructure now includes:

- ✅ **VPC** with public and private subnets across 2 availability zones
- ✅ **Application Load Balancer** for distributing traffic
- ✅ **ECS Cluster** with Fargate tasks running your application
- ✅ **Auto Scaling** configured for CPU and memory thresholds
- ✅ **CloudWatch Logs** for centralized logging
- ✅ **CloudWatch Alarms** for monitoring
- ✅ **Secrets Manager** storing your OpenAI API key securely
- ✅ **Security Groups** controlling network access
- ✅ **IAM Roles** for secure service permissions

## Estimated Costs

For a staging environment with default settings:

- **ECS Fargate**: ~$20-30/month (2 tasks, 0.5 vCPU, 1GB RAM each)
- **ALB**: ~$20/month
- **NAT Gateways**: ~$65/month (2 gateways)
- **Data Transfer**: Variable based on usage
- **CloudWatch Logs**: ~$5/month (depends on log volume)

**Total**: Approximately **$110-120/month** for staging

💡 **Cost Savings Tips**:
- Use single NAT Gateway for staging (edit VPC module)
- Reduce log retention from 30 to 7 days
- Use FARGATE_SPOT for non-production (already configured)

## Next Steps

1. **Custom Domain**: Set up Route 53 and ACM certificate for HTTPS
2. **Monitoring**: Configure SNS alerts for CloudWatch alarms
3. **Optimize**: Monitor actual resource usage and adjust CPU/memory
4. **Security**: Implement AWS WAF for additional protection
5. **Backup**: Configure automated backups if needed

## Cleanup

To destroy all resources and avoid charges:

```bash
cd terraform

# Destroy staging
terraform destroy -var-file=environments/staging.tfvars

# Destroy production (if deployed)
terraform destroy -var-file=environments/production.tfvars
```

## Troubleshooting

### Deployment Stuck or Failed

Check the GitHub Actions logs for details. Common issues:

1. **IAM Permissions**: Ensure the GitHub Actions role has proper permissions
2. **Secrets**: Verify `OPENAI_API_KEY` is set correctly
3. **Quotas**: Check AWS service quotas (especially VPC, ECS limits)

### Can't Access Application

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster contact-center-orchestrator-staging \
  --services contact-center-orchestrator-service

# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --names staging-orchestrator-tg \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)
```

### Health Checks Failing

```bash
# View recent logs
aws logs tail /ecs/contact-center-orchestrator-staging \
  --follow \
  --format short

# Check for errors in task startup
```

## Getting Help

- Full documentation: See `docs/AWS_DEPLOYMENT.md`
- AWS ECS docs: https://docs.aws.amazon.com/ecs/
- Terraform docs: https://registry.terraform.io/providers/hashicorp/aws/

## Success! 🎉

Your Contact Center AI Orchestrator is now running on AWS ECS with:
- ✅ Production-ready infrastructure
- ✅ Auto-scaling capabilities
- ✅ Automated deployments via GitHub Actions
- ✅ Comprehensive monitoring and logging
