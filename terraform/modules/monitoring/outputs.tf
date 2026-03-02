output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "dashboard_arn" {
  description = "ARN of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_arn
}

output "bedrock_error_alarm_arn" {
  description = "ARN of the Bedrock Lambda error alarm"
  value       = aws_cloudwatch_metric_alarm.bedrock_errors.arn
}

output "rag_error_alarm_arn" {
  description = "ARN of the RAG orchestrator Lambda error alarm"
  value       = aws_cloudwatch_metric_alarm.rag_errors.arn
}

output "xray_log_group_name" {
  description = "Name of the X-Ray CloudWatch log group"
  value       = aws_cloudwatch_log_group.xray.name
}
