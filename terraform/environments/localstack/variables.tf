variable "region" {
  description = "AWS region presented by LocalStack"
  type        = string
  default     = "us-east-1"
}

variable "localstack_endpoint" {
  description = "LocalStack edge endpoint"
  type        = string
  default     = "http://127.0.0.1:4566"
}
