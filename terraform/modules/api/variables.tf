variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "prod"
}

variable "bedrock_orchestrator_arn" {
  description = "ARN of the Bedrock orchestrator Lambda"
  type        = string
}

variable "embedding_lambda_arn" {
  description = "ARN of the embedding Lambda"
  type        = string
}

variable "retrieval_lambda_arn" {
  description = "ARN of the retrieval Lambda"
  type        = string
}

variable "rag_orchestrator_arn" {
  description = "ARN of the RAG orchestrator Lambda"
  type        = string
}

variable "waf_web_acl_arn" {
  description = "ARN of a REGIONAL WAF Web ACL to associate with the stage (empty to disable)"
  type        = string
  default     = ""
}

variable "enable_waf" {
  description = "Whether to associate a WAF Web ACL with the API stage"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Map of tags applied to all resources"
  type        = map(string)
  default     = {}
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito user pool used by the API authorizer"
  type        = string
}

variable "enable_auth" {
  description = "Whether to require Cognito authentication on API routes"
  type        = bool
  default     = true
}
