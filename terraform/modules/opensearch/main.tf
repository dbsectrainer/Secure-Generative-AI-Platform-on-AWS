terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# ── OpenSearch Serverless Encryption Policy ───────────────────────────────────

locals {
  # Use the module-created endpoint when enabled; otherwise trust the IDs
  # supplied by the caller (for environments with a separately managed VPC).
  source_vpce_ids = var.create_vpc_endpoint ? [aws_opensearchserverless_vpc_endpoint.main[0].id] : var.vpce_ids

  encryption_policy = merge(
    {
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${var.name_prefix}-vectors"]
        }
      ]
    },
    var.kms_key_arn != "" ? { KmsKeyArn = var.kms_key_arn } : { AWSOwnedKey = true }
  )
}

resource "aws_opensearchserverless_security_policy" "encryption" {
  name        = "${var.name_prefix}-enc-policy"
  type        = "encryption"
  description = "Encryption policy for ${var.name_prefix} vector collection"

  policy = jsonencode(local.encryption_policy)
}

# ── OpenSearch Serverless Network Policy ──────────────────────────────────────

resource "aws_opensearchserverless_security_policy" "network" {
  name        = "${var.name_prefix}-net-policy"
  type        = "network"
  description = "Network policy restricting access to VPC endpoint"

  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${var.name_prefix}-vectors"]
        },
        {
          ResourceType = "dashboard"
          Resource     = ["collection/${var.name_prefix}-vectors"]
        }
      ]
      AllowFromPublic = false
      SourceVPCEs     = local.source_vpce_ids
    }
  ])
}

# ── OpenSearch Serverless Data Access Policy ──────────────────────────────────

resource "aws_opensearchserverless_access_policy" "data" {
  name        = "${var.name_prefix}-data-policy"
  type        = "data"
  description = "Data access policy for Lambda RAG roles"

  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "collection"
          Resource     = ["collection/${var.name_prefix}-vectors"]
          Permission = [
            "aoss:CreateCollectionItems",
            "aoss:DeleteCollectionItems",
            "aoss:UpdateCollectionItems",
            "aoss:DescribeCollectionItems"
          ]
        },
        {
          ResourceType = "index"
          Resource     = ["index/${var.name_prefix}-vectors/*"]
          Permission = [
            "aoss:CreateIndex",
            "aoss:DeleteIndex",
            "aoss:UpdateIndex",
            "aoss:DescribeIndex",
            "aoss:ReadDocument",
            "aoss:WriteDocument"
          ]
        }
      ]
      Principal = var.lambda_role_arns
    }
  ])
}

# ── OpenSearch Serverless Collection ─────────────────────────────────────────

resource "aws_opensearchserverless_collection" "vectors" {
  name        = "${var.name_prefix}-vectors"
  type        = "VECTORSEARCH"
  description = "Vector database for ${var.name_prefix} RAG pipeline"

  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
    aws_opensearchserverless_access_policy.data,
  ]

  tags = var.tags
}

# ── VPC Endpoint for OpenSearch Serverless ────────────────────────────────────

resource "aws_opensearchserverless_vpc_endpoint" "main" {
  count      = var.create_vpc_endpoint ? 1 : 0
  name       = "${var.name_prefix}-aoss-vpce"
  subnet_ids = var.private_subnet_ids
  vpc_id     = var.vpc_id

  security_group_ids = [var.lambda_security_group_id]
}
