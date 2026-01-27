output "high_cpu_alarm_arn" {
  description = "ARN of the high CPU alarm"
  value       = aws_cloudwatch_metric_alarm.high_cpu.arn
}

output "high_memory_alarm_arn" {
  description = "ARN of the high memory alarm"
  value       = aws_cloudwatch_metric_alarm.high_memory.arn
}

output "unhealthy_targets_alarm_arn" {
  description = "ARN of the unhealthy targets alarm"
  value       = aws_cloudwatch_metric_alarm.unhealthy_targets.arn
}
