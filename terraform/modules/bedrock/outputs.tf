output "lambda_function_name" {
  description = "Name of the Bedrock orchestrator Lambda function"
  value       = aws_lambda_function.bedrock_orchestrator.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Bedrock orchestrator Lambda function"
  value       = aws_lambda_function.bedrock_orchestrator.arn
}

output "lambda_alias_arn" {
  description = "ARN of the Lambda live alias"
  value       = aws_lambda_alias.live.arn
}

output "lambda_version" {
  description = "Published version of the Lambda function"
  value       = aws_lambda_function.bedrock_orchestrator.version
}

output "log_group_name" {
  description = "Name of the CloudWatch log group for the Lambda function"
  value       = aws_cloudwatch_log_group.bedrock_lambda.name
}

output "guardrail_id" {
  description = "ID of the Bedrock Guardrail (empty when not enabled)"
  value       = var.enable_bedrock_guardrail ? aws_bedrock_guardrail.main[0].guardrail_id : ""
}

output "guardrail_arn" {
  description = "ARN of the Bedrock Guardrail (empty when not enabled)"
  value       = var.enable_bedrock_guardrail ? aws_bedrock_guardrail.main[0].guardrail_arn : ""
}
