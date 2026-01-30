# ============================================
# Variables for AWS Fargate Deployment
# ============================================

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "cost-center-orchestrator"
}

# ============================================
# Network Configuration
# ============================================

variable "vpc_id" {
  description = "VPC ID (leave empty to use default VPC)"
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "List of subnet IDs (leave empty to use all subnets in the VPC)"
  type        = list(string)
  default     = []
}

# ============================================
# Container Configuration
# ============================================

variable "container_image" {
  description = "Docker image URI for the application (ECR repository URL)"
  type        = string
  default     = ""
}

variable "container_port" {
  description = "Port exposed by the container"
  type        = number
  default     = 8000
}

variable "container_cpu" {
  description = "CPU units for the container (256 = 0.25 vCPU, 512 = 0.5 vCPU, 1024 = 1 vCPU)"
  type        = number
  default     = 256
}

variable "container_memory" {
  description = "Memory in MB for the container"
  type        = number
  default     = 512
}

# ============================================
# Scaling Configuration
# ============================================

variable "desired_count" {
  description = "Desired number of tasks"
  type        = number
  default     = 1
}

variable "min_capacity" {
  description = "Minimum number of tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of tasks for auto-scaling"
  type        = number
  default     = 2
}

variable "cpu_target_value" {
  description = "Target CPU utilization percentage for auto-scaling"
  type        = number
  default     = 70
}

variable "memory_target_value" {
  description = "Target memory utilization percentage for auto-scaling"
  type        = number
  default     = 80
}

# ============================================
# Application Configuration
# ============================================

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "openai_api_key" {
  description = "OpenAI API key (will be stored in Secrets Manager)"
  type        = string
  sensitive   = true
}
