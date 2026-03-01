output "ingestion_lambda_arn" {
  description = "ARN of the document ingestion Lambda"
  value       = aws_lambda_function.ingestion.arn
}

output "ingestion_lambda_name" {
  description = "Name of the document ingestion Lambda"
  value       = aws_lambda_function.ingestion.function_name
}

output "embedding_lambda_arn" {
  description = "ARN of the embedding generation Lambda"
  value       = aws_lambda_function.embedding.arn
}

output "embedding_lambda_name" {
  description = "Name of the embedding generation Lambda"
  value       = aws_lambda_function.embedding.function_name
}

output "retrieval_lambda_arn" {
  description = "ARN of the retrieval Lambda"
  value       = aws_lambda_function.retrieval.arn
}

output "retrieval_lambda_name" {
  description = "Name of the retrieval Lambda"
  value       = aws_lambda_function.retrieval.function_name
}

output "orchestrator_lambda_arn" {
  description = "ARN of the RAG orchestrator Lambda"
  value       = aws_lambda_function.orchestrator.arn
}

output "orchestrator_lambda_name" {
  description = "Name of the RAG orchestrator Lambda"
  value       = aws_lambda_function.orchestrator.function_name
}
