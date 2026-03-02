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

output "opensearch_collection_endpoint" {
  description = "HTTPS endpoint for the OpenSearch Serverless collection"
  value       = module.opensearch.collection_endpoint
}

output "rag_orchestrator_lambda_arn" {
  description = "ARN of the RAG orchestrator Lambda function"
  value       = module.rag.orchestrator_lambda_arn
}

output "waf_web_acl_arn" {
  description = "ARN of the WAF Web ACL"
  value       = module.waf.web_acl_arn
}

output "guardduty_detector_id" {
  description = "GuardDuty detector ID"
  value       = module.security.guardduty_detector_id
}
