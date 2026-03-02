variable "name_prefix" {
  description = "Prefix for all resource names"
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
  description = "KMS CMK ARN for encrypting the AWS Config S3 bucket"
  type        = string
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for security alarm notifications"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
