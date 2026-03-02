variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "scope" {
  description = "WAF scope: REGIONAL (API Gateway / ALB) or CLOUDFRONT"
  type        = string
  default     = "REGIONAL"

  validation {
    condition     = contains(["REGIONAL", "CLOUDFRONT"], var.scope)
    error_message = "scope must be REGIONAL or CLOUDFRONT"
  }
}

variable "rate_limit_requests_per_5min" {
  description = "Maximum requests per IP per 5-minute window before rate limiting kicks in"
  type        = number
  default     = 1000
}

variable "max_request_body_bytes" {
  description = "Maximum allowed request body size in bytes (to block token flooding)"
  type        = number
  default     = 65536  # 64 KB
}

variable "block_anonymous_ip" {
  description = "Enable the AWS Managed Anonymous IP List rule (blocks Tor, VPN exit nodes)"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days for WAF logs"
  type        = number
  default     = 30
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for encrypting WAF CloudWatch log group"
  type        = string
}

variable "alarm_sns_topic_arns" {
  description = "SNS topic ARNs for WAF CloudWatch alarm notifications"
  type        = list(string)
  default     = []
}

variable "blocked_requests_alarm_threshold" {
  description = "Number of blocked requests per 5-minute period that triggers alarm"
  type        = number
  default     = 100
}

variable "rate_limit_alarm_threshold" {
  description = "Number of rate-limited requests per 5-minute period that triggers alarm"
  type        = number
  default     = 50
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
