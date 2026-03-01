variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "kms_admin_role_arn" {
  description = "ARN of the IAM role that will administer the KMS key"
  type        = string
}

variable "lambda_role_arns" {
  description = "List of Lambda IAM role ARNs that need KMS decrypt and S3 read access"
  type        = list(string)
  default     = []
}

variable "ingestion_role_arns" {
  description = "List of IAM role ARNs used for document ingestion (S3 write)"
  type        = list(string)
  default     = []
}

variable "ingestion_lambda_arn" {
  description = "ARN of the Lambda function triggered on S3 object creation (empty to disable)"
  type        = string
  default     = ""
}

variable "access_log_bucket_id" {
  description = "S3 bucket ID for storing S3 access logs (empty to disable logging)"
  type        = string
  default     = ""
}

variable "kms_deletion_window_days" {
  description = "Number of days before KMS key is deleted after scheduling deletion"
  type        = number
  default     = 30
}

variable "noncurrent_version_expiration_days" {
  description = "Number of days after which non-current object versions expire"
  type        = number
  default     = 90
}

variable "tags" {
  description = "Map of tags applied to all resources"
  type        = map(string)
  default     = {}
}
