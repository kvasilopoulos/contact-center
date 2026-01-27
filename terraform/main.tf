# ============================================
# Contact Center AI Orchestrator - AWS Infrastructure
# Main Terraform Configuration
# ============================================

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Backend configuration for state management
  # Uncomment and configure for production use
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "orchestrator/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-state-lock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "ContactCenterOrchestrator"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# ============================================
# VPC and Networking
# ============================================

module "vpc" {
  source = "./modules/vpc"
  
  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  availability_zones  = data.aws_availability_zones.available.names
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
}

# ============================================
# Security Groups
# ============================================

module "security_groups" {
  source = "./modules/security_groups"
  
  environment = var.environment
  vpc_id      = module.vpc.vpc_id
}

# ============================================
# IAM Roles and Policies
# ============================================

module "iam" {
  source = "./modules/iam"
  
  environment = var.environment
}

# ============================================
# ECS Cluster
# ============================================

module "ecs" {
  source = "./modules/ecs"
  
  environment           = var.environment
  cluster_name          = "${var.project_name}-${var.environment}"
  enable_container_insights = true
}

# ============================================
# Application Load Balancer
# ============================================

module "alb" {
  source = "./modules/alb"
  
  environment         = var.environment
  vpc_id              = module.vpc.vpc_id
  public_subnet_ids   = module.vpc.public_subnet_ids
  alb_security_group_id = module.security_groups.alb_security_group_id
  certificate_arn     = var.acm_certificate_arn
}

# ============================================
# Secrets Manager
# ============================================

module "secrets" {
  source = "./modules/secrets"
  
  environment = var.environment
  openai_api_key = var.openai_api_key
}

# ============================================
# CloudWatch Log Groups
# ============================================

resource "aws_cloudwatch_log_group" "orchestrator" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
  
  tags = {
    Name = "${var.project_name}-${var.environment}-logs"
  }
}

# ============================================
# ECS Service and Task Definition
# ============================================

module "ecs_service" {
  source = "./modules/ecs_service"
  
  environment             = var.environment
  cluster_id              = module.ecs.cluster_id
  cluster_name            = module.ecs.cluster_name
  service_name            = "${var.project_name}-service"
  task_family             = "${var.project_name}-task"
  
  # Container configuration
  container_image         = var.container_image
  container_port          = var.container_port
  container_cpu           = var.container_cpu
  container_memory        = var.container_memory
  
  # Environment variables
  environment_variables   = {
    ENVIRONMENT                      = var.environment
    DEBUG                            = "false"
    LOG_LEVEL                        = var.log_level
    OPENAI_MODEL                     = "gpt-4o-mini"
    OPENAI_TIMEOUT                   = "30.0"
    MIN_CONFIDENCE_THRESHOLD         = "0.5"
    RATE_LIMIT_REQUESTS_PER_MINUTE   = "60"
    MAX_CONCURRENT_REQUESTS          = "100"
  }
  
  # Secrets
  openai_api_key_secret_arn = module.secrets.openai_api_key_arn
  
  # Networking
  vpc_id                  = module.vpc.vpc_id
  private_subnet_ids      = module.vpc.private_subnet_ids
  service_security_group_id = module.security_groups.ecs_service_security_group_id
  
  # Load balancer
  target_group_arn        = module.alb.target_group_arn
  
  # IAM
  task_execution_role_arn = module.iam.task_execution_role_arn
  task_role_arn           = module.iam.task_role_arn
  
  # Auto-scaling
  desired_count           = var.desired_count
  min_capacity            = var.min_capacity
  max_capacity            = var.max_capacity
  cpu_target_value        = var.cpu_target_value
  memory_target_value     = var.memory_target_value
  
  # CloudWatch
  log_group_name          = aws_cloudwatch_log_group.orchestrator.name
  aws_region              = var.aws_region
}

# ============================================
# CloudWatch Alarms
# ============================================

module "monitoring" {
  source = "./modules/monitoring"
  
  environment       = var.environment
  cluster_name      = module.ecs.cluster_name
  service_name      = module.ecs_service.service_name
  alb_arn_suffix    = module.alb.alb_arn_suffix
  target_group_arn_suffix = module.alb.target_group_arn_suffix
  sns_topic_arn     = var.sns_alert_topic_arn
}
