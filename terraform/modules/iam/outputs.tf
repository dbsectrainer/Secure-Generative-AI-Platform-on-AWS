output "lambda_orchestrator_role_arn" {
  description = "ARN of the Lambda Bedrock orchestrator IAM role"
  value       = aws_iam_role.lambda_bedrock_orchestrator.arn
}

output "lambda_orchestrator_role_name" {
  description = "Name of the Lambda Bedrock orchestrator IAM role"
  value       = aws_iam_role.lambda_bedrock_orchestrator.name
}

output "lambda_ingestion_role_arn" {
  description = "ARN of the Lambda document ingestion IAM role"
  value       = aws_iam_role.lambda_document_ingestion.arn
}

output "lambda_ingestion_role_name" {
  description = "Name of the Lambda document ingestion IAM role"
  value       = aws_iam_role.lambda_document_ingestion.name
}

output "terraform_deploy_role_arn" {
  description = "ARN of the Terraform deploy IAM role (empty when not created)"
  value       = var.create_terraform_deploy_role ? aws_iam_role.terraform_deploy[0].arn : ""
}

output "deny_privilege_escalation_policy_arn" {
  description = "ARN of the deny-privilege-escalation IAM policy"
  value       = aws_iam_policy.deny_privilege_escalation.arn
}
