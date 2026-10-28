variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of the IAM role for the Lambda function"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for Lambda VPC configuration"
  type        = list(string)
}

variable "lambda_security_group_id" {
  description = "Security group ID for the Lambda function"
  type        = string
}

variable "document_bucket_name" {
  description = "Name of the S3 document bucket"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for encrypting CloudWatch Logs"
  type        = string
  default     = null
}

variable "bedrock_model_id" {
  description = "Bedrock foundation model ID to invoke"
  type        = string
  default     = "anthropic.claude-sonnet-5-5"
}

variable "max_tokens" {
  description = "Maximum number of tokens for Bedrock model response"
  type        = number
  default     = 2048
}

variable "lambda_timeout_seconds" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory_mb" {
  description = "Lambda function memory allocation in MB"
  type        = number
  default     = 512
}

variable "log_retention_days" {
  description = "Number of days to retain Lambda CloudWatch logs"
  type        = number
  default     = 14
}

variable "log_level" {
  description = "Log level for the Lambda function (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrent executions for the Lambda function (-1 for unreserved)"
  type        = number
  default     = 10
}

variable "error_alarm_threshold" {
  description = "Number of Lambda errors per minute that triggers the alarm"
  type        = number
  default     = 5
}

variable "duration_alarm_threshold_ms" {
  description = "Lambda p95 duration in milliseconds that triggers the alarm"
  type        = number
  default     = 25000
}

variable "alarm_sns_topic_arns" {
  description = "List of SNS topic ARNs to notify when alarms trigger"
  type        = list(string)
  default     = []
}

variable "enable_bedrock_guardrail" {
  description = "Whether to create a Bedrock Guardrail resource"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Map of tags applied to all resources"
  type        = map(string)
  default     = {}
}
