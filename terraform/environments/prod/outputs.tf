output "vpc_id" {
  description = "ID of the prod VPC"
  value       = module.network.vpc_id
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs"
  value       = module.network.private_app_subnet_ids
}

output "document_bucket_name" {
  description = "Name of the S3 document bucket"
  value       = module.s3.bucket_id
}

output "document_bucket_arn" {
  description = "ARN of the S3 document bucket"
  value       = module.s3.bucket_arn
}

output "kms_key_arn" {
  description = "ARN of the KMS CMK for S3 encryption"
  value       = module.s3.kms_key_arn
}

output "bedrock_lambda_function_name" {
  description = "Name of the Bedrock orchestrator Lambda function"
  value       = module.bedrock.lambda_function_name
}

output "bedrock_lambda_function_arn" {
  description = "ARN of the Bedrock orchestrator Lambda function"
  value       = module.bedrock.lambda_function_arn
}
