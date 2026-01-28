# ============================================
# Terraform Outputs
# ============================================

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_url" {
  description = "URL of the Application Load Balancer"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "ssm_parameter_name" {
  description = "Name of the SSM parameter storing OpenAI API key"
  value       = aws_ssm_parameter.openai_api_key.name
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "deployment_commands" {
  description = "Useful commands for deployment"
  value       = <<-EOT
    # Authenticate Docker to ECR
    aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.app.repository_url}
    
    # Build and push Docker image
    docker build -t cost-center-orchestrator:latest .
    docker tag cost-center-orchestrator:latest ${aws_ecr_repository.app.repository_url}:latest
    docker push ${aws_ecr_repository.app.repository_url}:latest
    
    # Test the API
    curl ${aws_lb.main.dns_name}/api/v1/health
  EOT
}
