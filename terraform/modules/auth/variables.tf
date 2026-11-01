variable "name_prefix" {
  description = "Prefix applied to all resource names"
  type        = string
}

variable "region" {
  description = "AWS region hosting the Cognito user pool"
  type        = string
}

variable "tags" {
  description = "Map of tags applied to all resources"
  type        = map(string)
  default     = {}
}
