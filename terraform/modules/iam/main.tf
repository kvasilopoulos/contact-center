# ============================================
# IAM Module - Roles and Policies
# ============================================

# ECS Task Execution Role
resource "aws_iam_role" "task_execution_role" {
  name = "${var.environment}-orchestrator-task-execution-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name = "${var.environment}-orchestrator-task-execution-role"
  }
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "task_execution_role_policy" {
  role       = aws_iam_role.task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Additional policy for Secrets Manager access
resource "aws_iam_role_policy" "task_execution_secrets_policy" {
  name = "${var.environment}-orchestrator-secrets-policy"
  role = aws_iam_role.task_execution_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:*:*:secret:${var.environment}/orchestrator/*"
      }
    ]
  })
}

# ECS Task Role (for application permissions)
resource "aws_iam_role" "task_role" {
  name = "${var.environment}-orchestrator-task-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name = "${var.environment}-orchestrator-task-role"
  }
}

# Task role policy for CloudWatch Logs
resource "aws_iam_role_policy" "task_role_cloudwatch_policy" {
  name = "${var.environment}-orchestrator-cloudwatch-policy"
  role = aws_iam_role.task_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Task role policy for X-Ray (optional, for distributed tracing)
resource "aws_iam_role_policy" "task_role_xray_policy" {
  name = "${var.environment}-orchestrator-xray-policy"
  role = aws_iam_role.task_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      }
    ]
  })
}
