# ============================================
# Secrets Manager Module
# ============================================

resource "aws_secretsmanager_secret" "openai_api_key" {
  name        = "${var.environment}/orchestrator/openai_api_key"
  description = "OpenAI API key for Contact Center Orchestrator"
  
  recovery_window_in_days = var.environment == "production" ? 30 : 0
  
  tags = {
    Name        = "${var.environment}-orchestrator-openai-key"
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}
