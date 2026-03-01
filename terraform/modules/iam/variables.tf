variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "document_bucket_arn" {
  description = "ARN of the S3 document bucket"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS CMK used for S3 encryption"
  type        = string
}

variable "bedrock_model_ids" {
  description = "List of Bedrock foundation model IDs the orchestrator may invoke"
  type        = list(string)
  default     = ["anthropic.claude-3-sonnet-20240229-v1:0"]
}

variable "permissions_boundary_arn" {
  description = "ARN of the IAM permissions boundary policy to attach to all roles (empty to disable)"
  type        = string
  default     = ""
}

variable "create_terraform_deploy_role" {
  description = "Whether to create the Terraform deploy role with OIDC trust for GitHub Actions"
  type        = bool
  default     = false
}

variable "github_org" {
  description = "GitHub organisation name (used in OIDC trust policy)"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name (used in OIDC trust policy)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Map of tags applied to all resources"
  type        = map(string)
  default     = {}
}
