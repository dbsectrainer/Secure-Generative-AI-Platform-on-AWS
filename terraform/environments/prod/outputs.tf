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

output "api_invoke_url" {
  description = "Base URL of the deployed GenAI API stage"
  value       = module.api.invoke_url
}

output "api_routes" {
  description = "Map of API route name to invoke URL"
  value       = module.api.routes
}

output "opensearch_endpoint" {
  description = "OpenSearch Serverless collection endpoint"
  value       = module.opensearch.collection_endpoint
}

output "guardrail_id" {
  description = "Bedrock Guardrail ID applied to model calls"
  value       = module.bedrock.guardrail_id
}

output "guardrail_version" {
  description = "Published Bedrock Guardrail version"
  value       = module.bedrock.guardrail_version
}

output "rag_ingestion_function_name" {
  description = "Name of the RAG ingestion Lambda"
  value       = module.rag.ingestion_lambda_name
}

output "rag_embedding_function_name" {
  description = "Name of the RAG embedding Lambda"
  value       = module.rag.embedding_lambda_name
}

output "rag_retrieval_function_name" {
  description = "Name of the RAG retrieval Lambda"
  value       = module.rag.retrieval_lambda_name
}

output "rag_orchestrator_function_name" {
  description = "Name of the RAG orchestrator Lambda"
  value       = module.rag.orchestrator_lambda_name
}

output "waf_web_acl_arn" {
  description = "ARN of the REGIONAL WAF Web ACL"
  value       = module.waf.web_acl_arn
}

output "config_recorder_name" {
  description = "Name of the AWS Config recorder"
  value       = module.security.config_recorder_name
}
