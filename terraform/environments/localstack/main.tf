terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# LocalStack target for infrastructure tests. This environment intentionally
# provisions only modules that LocalStack Community supports (KMS, S3, IAM).
# Bedrock Guardrails, OpenSearch Serverless, WAF, GuardDuty, and Config are
# validated with Terraform mock-provider tests instead.
provider "aws" {
  region                      = var.region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3     = var.localstack_endpoint
    iam    = var.localstack_endpoint
    kms    = var.localstack_endpoint
    sts    = var.localstack_endpoint
    lambda = var.localstack_endpoint
    logs   = var.localstack_endpoint
    ec2    = var.localstack_endpoint
  }
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix = "secgenai-local"
  common_tags = {
    Project     = "secure-genai-platform"
    Environment = "localstack"
    ManagedBy   = "Terraform"
  }
}

resource "aws_iam_role" "kms_admin" {
  name = "${local.name_prefix}-kms-admin"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

module "s3" {
  source = "../../modules/s3"

  name_prefix         = local.name_prefix
  account_id          = data.aws_caller_identity.current.account_id
  kms_admin_role_arn  = aws_iam_role.kms_admin.arn
  lambda_role_arns    = [module.iam.lambda_orchestrator_role_arn]
  ingestion_role_arns = [module.iam.lambda_ingestion_role_arn]
  manage_lifecycle    = false
  tags                = local.common_tags
}

module "iam" {
  source = "../../modules/iam"

  name_prefix                  = local.name_prefix
  account_id                   = data.aws_caller_identity.current.account_id
  region                       = var.region
  document_bucket_arn          = module.s3.bucket_arn
  kms_key_arn                  = module.s3.kms_key_arn
  bedrock_model_ids            = ["anthropic.claude-sonnet-5-5"]
  embedding_model_id           = "amazon.titan-embed-text-v2:0"
  create_terraform_deploy_role = false
  tags                         = local.common_tags
}
