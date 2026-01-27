output "openai_api_key_arn" {
  description = "ARN of the OpenAI API key secret"
  value       = aws_secretsmanager_secret.openai_api_key.arn
  sensitive   = true
}

output "openai_api_key_name" {
  description = "Name of the OpenAI API key secret"
  value       = aws_secretsmanager_secret.openai_api_key.name
}
