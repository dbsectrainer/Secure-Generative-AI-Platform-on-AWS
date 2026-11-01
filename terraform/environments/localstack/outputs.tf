output "document_bucket_name" {
  description = "LocalStack S3 bucket created by the s3 module"
  value       = module.s3.bucket_id
}

output "document_bucket_arn" {
  description = "LocalStack S3 bucket ARN"
  value       = module.s3.bucket_arn
}

output "kms_key_arn" {
  description = "LocalStack KMS key ARN"
  value       = module.s3.kms_key_arn
}

output "orchestrator_role_arn" {
  description = "Orchestrator IAM role ARN"
  value       = module.iam.lambda_orchestrator_role_arn
}

output "embedding_role_arn" {
  description = "Embedding IAM role ARN"
  value       = module.iam.lambda_embedding_role_arn
}

output "retrieval_role_arn" {
  description = "Retrieval IAM role ARN"
  value       = module.iam.lambda_retrieval_role_arn
}

output "rag_orchestrator_role_arn" {
  description = "RAG orchestrator IAM role ARN"
  value       = module.iam.lambda_rag_orchestrator_role_arn
}
