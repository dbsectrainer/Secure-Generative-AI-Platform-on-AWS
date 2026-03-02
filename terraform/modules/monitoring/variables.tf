variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for encrypting CloudWatch log groups"
  type        = string
}

variable "bedrock_lambda_function_name" {
  description = "Name of the Bedrock orchestrator Lambda function to monitor"
  type        = string
}

variable "rag_orchestrator_function_name" {
  description = "Name of the RAG orchestrator Lambda function to monitor"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "error_alarm_threshold" {
  description = "Lambda error count threshold to trigger alarm"
  type        = number
  default     = 5
}

variable "duration_alarm_threshold_ms" {
  description = "Lambda p95 duration threshold (ms) to trigger alarm"
  type        = number
  default     = 30000
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for CloudWatch alarm notifications"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
