variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for the OpenSearch Serverless VPC endpoint"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the VPC endpoint"
  type        = list(string)
}

variable "lambda_security_group_id" {
  description = "Security group ID to attach to the VPC endpoint"
  type        = string
}

variable "lambda_role_arns" {
  description = "IAM role ARNs granted data access to the collection"
  type        = list(string)
}

variable "vpce_ids" {
  description = "OpenSearch Serverless VPC endpoint IDs for the network policy"
  type        = list(string)
  default     = []
}

variable "create_vpc_endpoint" {
  description = "Whether to create a VPC endpoint for OpenSearch Serverless"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
