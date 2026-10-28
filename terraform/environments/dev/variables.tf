variable "project_name" {
  description = "Project name used as a prefix for all resources"
  type        = string
  default     = "secgenai"
}

variable "owner" {
  description = "Owner tag value for all resources"
  type        = string
  default     = "platform-team"
}

variable "region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "eu-west-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.0.0/24", "10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_app_subnet_cidrs" {
  description = "CIDR blocks for private application subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24", "10.0.12.0/24"]
}

variable "private_data_subnet_cidrs" {
  description = "CIDR blocks for private data subnets (one per AZ)"
  type        = list(string)
  default     = ["10.0.20.0/24", "10.0.21.0/24", "10.0.22.0/24"]
}

variable "availability_zones" {
  description = "Availability zones to deploy into"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

variable "enable_nat_gateway" {
  description = "Whether to provision NAT gateways"
  type        = bool
  default     = true
}

variable "bedrock_model_ids" {
  description = "List of Bedrock foundation model IDs that Lambda may invoke"
  type        = list(string)
  default     = ["anthropic.claude-sonnet-5-5"]
}

variable "bedrock_model_id" {
  description = "Default Bedrock foundation model ID"
  type        = string
  default     = "anthropic.claude-sonnet-5-5"
}

variable "max_tokens" {
  description = "Maximum tokens for Bedrock model response"
  type        = number
  default     = 2048
}

variable "create_terraform_deploy_role" {
  description = "Whether to create the Terraform deploy OIDC role"
  type        = bool
  default     = false
}

variable "github_org" {
  description = "GitHub organisation for OIDC trust"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository for OIDC trust"
  type        = string
  default     = ""
}
