# ============================================
# CloudWatch Monitoring Module
# ============================================

# CloudWatch Alarm - High CPU Utilization
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.environment}-orchestrator-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "This metric monitors ECS CPU utilization"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.service_name
  }
  
  alarm_actions = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  
  tags = {
    Name        = "${var.environment}-orchestrator-high-cpu"
    Environment = var.environment
  }
}

# CloudWatch Alarm - High Memory Utilization
resource "aws_cloudwatch_metric_alarm" "high_memory" {
  alarm_name          = "${var.environment}-orchestrator-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "This metric monitors ECS memory utilization"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.service_name
  }
  
  alarm_actions = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  
  tags = {
    Name        = "${var.environment}-orchestrator-high-memory"
    Environment = var.environment
  }
}

# CloudWatch Alarm - Unhealthy Targets
resource "aws_cloudwatch_metric_alarm" "unhealthy_targets" {
  alarm_name          = "${var.environment}-orchestrator-unhealthy-targets"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 0
  alarm_description   = "This metric monitors unhealthy targets in the load balancer"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
  
  alarm_actions = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  
  tags = {
    Name        = "${var.environment}-orchestrator-unhealthy-targets"
    Environment = var.environment
  }
}

# CloudWatch Alarm - High HTTP 5xx Errors
resource "aws_cloudwatch_metric_alarm" "high_5xx_errors" {
  alarm_name          = "${var.environment}-orchestrator-high-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "This metric monitors HTTP 5xx errors from targets"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
  
  alarm_actions = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  
  tags = {
    Name        = "${var.environment}-orchestrator-high-5xx-errors"
    Environment = var.environment
  }
}

# CloudWatch Alarm - High Response Time
resource "aws_cloudwatch_metric_alarm" "high_response_time" {
  alarm_name          = "${var.environment}-orchestrator-high-response-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 5
  alarm_description   = "This metric monitors target response time"
  treat_missing_data  = "notBreaching"
  
  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
  
  alarm_actions = var.sns_topic_arn != "" ? [var.sns_topic_arn] : []
  
  tags = {
    Name        = "${var.environment}-orchestrator-high-response-time"
    Environment = var.environment
  }
}
