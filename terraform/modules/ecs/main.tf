# ============================================
# ECS Cluster Module
# ============================================

resource "aws_ecs_cluster" "main" {
  name = var.cluster_name
  
  setting {
    name  = "containerInsights"
    value = var.enable_container_insights ? "enabled" : "disabled"
  }
  
  tags = {
    Name        = var.cluster_name
    Environment = var.environment
  }
}

# CloudWatch Log Group for Container Insights
resource "aws_cloudwatch_log_group" "ecs_cluster" {
  count             = var.enable_container_insights ? 1 : 0
  name              = "/aws/ecs/containerinsights/${var.cluster_name}/performance"
  retention_in_days = 30
  
  tags = {
    Name = "${var.cluster_name}-container-insights"
  }
}

# ECS Cluster Capacity Providers (for Fargate)
resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name
  
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
  
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 1
  }
}
