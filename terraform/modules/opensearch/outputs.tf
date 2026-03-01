output "collection_endpoint" {
  description = "HTTPS endpoint for the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.vectors.collection_endpoint
}

output "collection_arn" {
  description = "ARN of the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.vectors.arn
}

output "collection_id" {
  description = "ID of the OpenSearch Serverless collection"
  value       = aws_opensearchserverless_collection.vectors.id
}

output "vpc_endpoint_id" {
  description = "ID of the VPC endpoint for OpenSearch Serverless (if created)"
  value       = var.create_vpc_endpoint ? aws_opensearchserverless_vpc_endpoint.main[0].id : null
}
