variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for Lambda VPC attachment"
  type        = list(string)
}

variable "lambda_security_group_id" {
  description = "Security group ID for all RAG Lambda functions"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for CloudWatch log group encryption"
  type        = string
}

variable "document_bucket_name" {
  description = "S3 bucket name for source documents"
  type        = string
}

variable "opensearch_endpoint" {
  description = "HTTPS endpoint of the OpenSearch Serverless collection"
  type        = string
}

variable "opensearch_index" {
  description = "OpenSearch index name for document vectors"
  type        = string
  default     = "rag-documents"
}

variable "embedding_model_id" {
  description = "Bedrock embedding model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "inference_model_id" {
  description = "Bedrock inference model ID for the RAG orchestrator"
  type        = string
  default     = "anthropic.claude-sonnet-5-5"
}

variable "ingestion_lambda_role_arn" {
  description = "IAM role ARN for the ingestion Lambda"
  type        = string
}

variable "embedding_lambda_role_arn" {
  description = "IAM role ARN for the embedding Lambda"
  type        = string
}

variable "retrieval_lambda_role_arn" {
  description = "IAM role ARN for the retrieval Lambda"
  type        = string
}

variable "orchestrator_lambda_role_arn" {
  description = "IAM role ARN for the RAG orchestrator Lambda"
  type        = string
}

variable "chunk_size" {
  description = "Target character count per document chunk"
  type        = number
  default     = 1000
}

variable "chunk_overlap" {
  description = "Character overlap between consecutive chunks"
  type        = number
  default     = 200
}

variable "retrieval_top_k" {
  description = "Number of vector search results to return"
  type        = number
  default     = 5
}

variable "max_tokens" {
  description = "Maximum tokens in the Bedrock model response"
  type        = number
  default     = 2048
}

variable "prompt_mode" {
  description = "PromptBuilder mode: rag | citation | summarisation"
  type        = string
  default     = "rag"

  validation {
    condition     = contains(["rag", "citation", "summarisation"], var.prompt_mode)
    error_message = "prompt_mode must be one of: rag, citation, summarisation."
  }
}

variable "lambda_timeout_seconds" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 60
}

variable "lambda_memory_mb" {
  description = "Lambda function memory allocation in MB"
  type        = number
  default     = 512
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrent execution limit per Lambda (−1 = unreserved)"
  type        = number
  default     = -1
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "log_level" {
  description = "Python logging level for all RAG Lambda functions"
  type        = string
  default     = "INFO"
}

variable "error_alarm_threshold" {
  description = "Error count threshold for the orchestrator CloudWatch alarm"
  type        = number
  default     = 5
}

variable "duration_alarm_threshold_ms" {
  description = "p95 duration threshold (ms) for the orchestrator CloudWatch alarm"
  type        = number
  default     = 30000
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs to notify when alarms trigger"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to all resources"
  type        = map(string)
  default     = {}
}
