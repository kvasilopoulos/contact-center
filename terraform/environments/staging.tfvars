# ============================================
# Staging Environment Variables
# ============================================

environment  = "staging"
aws_region   = "us-east-1"
project_name = "contact-center-orchestrator"

# VPC Configuration
vpc_cidr             = "10.0.0.0/16"
public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]

# ECS Configuration
# container_image will be passed from CI/CD pipeline
container_port   = 8000
container_cpu    = 512
container_memory = 1024

# Auto-scaling Configuration
desired_count        = 2
min_capacity         = 1
max_capacity         = 5
cpu_target_value     = 70
memory_target_value  = 80

# Application Configuration
log_level          = "INFO"
log_retention_days = 7

# Secrets - will be set via environment variable TF_VAR_openai_api_key
# openai_api_key = "set-via-env-var"

# Optional: ACM certificate ARN for HTTPS
# acm_certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID"

# Optional: SNS topic for alerts
# sns_alert_topic_arn = "arn:aws:sns:us-east-1:ACCOUNT_ID:orchestrator-alerts-staging"
