terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    # Values are supplied via -backend-config flags or environment variables.
    # Example:
    #   terraform init \
    #     -backend-config="bucket=<tfstate-bucket>" \
    #     -backend-config="key=dev/terraform.tfstate" \
    #     -backend-config="region=eu-west-1" \
    #     -backend-config="dynamodb_table=<tfstate-lock-table>" \
    #     -backend-config="kms_key_id=<kms-key-arn>" \
    #     -backend-config="encrypt=true"
    encrypt = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

locals {
  env         = "dev"
  name_prefix = "${var.project_name}-${local.env}"

  common_tags = {
    Project     = var.project_name
    Environment = local.env
    ManagedBy   = "Terraform"
    Owner       = var.owner
  }
}

# ── Data sources ──────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── Network Module ────────────────────────────────────────────────────────────

module "network" {
  source = "../../modules/network"

  name_prefix               = local.name_prefix
  vpc_cidr                  = var.vpc_cidr
  public_subnet_cidrs       = var.public_subnet_cidrs
  private_app_subnet_cidrs  = var.private_app_subnet_cidrs
  private_data_subnet_cidrs = var.private_data_subnet_cidrs
  availability_zones        = var.availability_zones
  enable_nat_gateway        = var.enable_nat_gateway
  region                    = var.region
  account_id                = data.aws_caller_identity.current.account_id
  kms_key_arn               = module.s3.kms_key_arn
  tags                      = local.common_tags
}

# ── S3 Module ─────────────────────────────────────────────────────────────────

module "s3" {
  source = "../../modules/s3"

  name_prefix              = local.name_prefix
  account_id               = data.aws_caller_identity.current.account_id
  kms_admin_role_arn       = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${local.name_prefix}-role-terraform-deploy"
  lambda_role_arns         = [module.iam.lambda_orchestrator_role_arn]
  ingestion_role_arns      = [module.iam.lambda_ingestion_role_arn]
  kms_deletion_window_days = 7
  tags                     = local.common_tags
}

# ── IAM Module ────────────────────────────────────────────────────────────────

module "iam" {
  source = "../../modules/iam"

  name_prefix                  = local.name_prefix
  account_id                   = data.aws_caller_identity.current.account_id
  region                       = var.region
  document_bucket_arn          = module.s3.bucket_arn
  kms_key_arn                  = module.s3.kms_key_arn
  bedrock_model_ids            = var.bedrock_model_ids
  create_terraform_deploy_role = var.create_terraform_deploy_role
  github_org                   = var.github_org
  github_repo                  = var.github_repo
  tags                         = local.common_tags
}

# ── Bedrock Module ────────────────────────────────────────────────────────────

module "bedrock" {
  source = "../../modules/bedrock"

  name_prefix              = local.name_prefix
  region                   = var.region
  lambda_role_arn          = module.iam.lambda_orchestrator_role_arn
  private_subnet_ids       = module.network.private_app_subnet_ids
  lambda_security_group_id = module.network.lambda_security_group_id
  document_bucket_name     = module.s3.bucket_id
  kms_key_arn              = module.s3.kms_key_arn
  bedrock_model_id         = var.bedrock_model_id
  max_tokens               = var.max_tokens
  log_retention_days       = 7
  enable_bedrock_guardrail = true
  tags                     = local.common_tags
}
