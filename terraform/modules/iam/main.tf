terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── IAM Role: Lambda Bedrock Orchestrator ─────────────────────────────────────

resource "aws_iam_role" "lambda_bedrock_orchestrator" {
  name                 = "${var.name_prefix}-role-lambda-bedrock-orchestrator"
  permissions_boundary = var.permissions_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAssume"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_policy" "lambda_bedrock_orchestrator" {
  name        = "${var.name_prefix}-policy-lambda-bedrock-orchestrator"
  description = "Permissions for Lambda Bedrock orchestrator"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          for model in var.bedrock_model_ids :
          "arn:aws:bedrock:${var.region}::foundation-model/${model}"
        ]
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = var.region
          }
        }
      },
      {
        Sid    = "S3DocumentRead"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:ListBucket"
        ]
        Resource = [
          var.document_bucket_arn,
          "${var.document_bucket_arn}/*"
        ]
      },
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = var.kms_key_arn
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/*"
      },
      {
        Sid    = "XRayTrace"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
          "xray:GetSamplingRules",
          "xray:GetSamplingTargets"
        ]
        Resource = "*"
      },
      {
        Sid    = "VPCAccess"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AssignPrivateIpAddresses",
          "ec2:UnassignPrivateIpAddresses"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_policy" "deny_privilege_escalation" {
  name        = "${var.name_prefix}-policy-deny-privilege-escalation"
  description = "Explicitly deny IAM privilege escalation actions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyIAMEscalation"
        Effect = "Deny"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:SetDefaultPolicyVersion",
          "iam:PassRole",
          "sts:AssumeRole"
        ]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:PrincipalARN" = [
              "arn:aws:iam::${var.account_id}:role/${var.name_prefix}-role-terraform-deploy"
            ]
          }
        }
      },
      {
        Sid    = "DenyKMSAdminActions"
        Effect = "Deny"
        Action = [
          "kms:ScheduleKeyDeletion",
          "kms:DisableKey",
          "kms:DeleteImportedKeyMaterial"
        ]
        Resource = "*"
      },
      {
        Sid    = "DenyS3BucketAdminActions"
        Effect = "Deny"
        Action = [
          "s3:DeleteBucket",
          "s3:DeleteBucketPolicy",
          "s3:PutBucketPublicAccessBlock"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_bedrock_orchestrator" {
  role       = aws_iam_role.lambda_bedrock_orchestrator.name
  policy_arn = aws_iam_policy.lambda_bedrock_orchestrator.arn
}

resource "aws_iam_role_policy_attachment" "lambda_deny_escalation" {
  role       = aws_iam_role.lambda_bedrock_orchestrator.name
  policy_arn = aws_iam_policy.deny_privilege_escalation.arn
}

# ── IAM Role: Lambda Document Ingestion ───────────────────────────────────────

resource "aws_iam_role" "lambda_document_ingestion" {
  name                 = "${var.name_prefix}-role-lambda-doc-ingestion"
  permissions_boundary = var.permissions_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAssume"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_policy" "lambda_document_ingestion" {
  name        = "${var.name_prefix}-policy-lambda-doc-ingestion"
  description = "Permissions for Lambda document ingestion function"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3DocumentWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectTagging",
          "s3:GetObject",
          "s3:GetObjectAttributes"
        ]
        Resource = "${var.document_bucket_arn}/*"
      },
      {
        Sid    = "S3ListBucket"
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = var.document_bucket_arn
      },
      {
        Sid    = "KMSEncrypt"
        Effect = "Allow"
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = var.kms_key_arn
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/aws/lambda/*"
      },
      {
        Sid    = "VPCAccess"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_document_ingestion" {
  role       = aws_iam_role.lambda_document_ingestion.name
  policy_arn = aws_iam_policy.lambda_document_ingestion.arn
}

resource "aws_iam_role_policy_attachment" "lambda_ingestion_deny_escalation" {
  role       = aws_iam_role.lambda_document_ingestion.name
  policy_arn = aws_iam_policy.deny_privilege_escalation.arn
}

# ── IAM Role: Terraform Deploy (OIDC for GitHub Actions) ─────────────────────

resource "aws_iam_role" "terraform_deploy" {
  count                = var.create_terraform_deploy_role ? 1 : 0
  name                 = "${var.name_prefix}-role-terraform-deploy"
  permissions_boundary = var.permissions_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowGitHubActionsOIDC"
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${var.account_id}:oidc-provider/token.actions.githubusercontent.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
          }
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "terraform_deploy_admin" {
  count      = var.create_terraform_deploy_role ? 1 : 0
  role       = aws_iam_role.terraform_deploy[0].name
  policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

# Additional IAM management permission for Terraform deploy role
resource "aws_iam_policy" "terraform_deploy_iam" {
  count       = var.create_terraform_deploy_role ? 1 : 0
  name        = "${var.name_prefix}-policy-terraform-deploy-iam"
  description = "Scoped IAM permissions for Terraform deployment"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "IAMManagement"
        Effect = "Allow"
        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:AttachRolePolicy",
          "iam:DetachRolePolicy",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies",
          "iam:PassRole",
          "iam:CreatePolicy",
          "iam:DeletePolicy",
          "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion",
          "iam:GetPolicy",
          "iam:GetPolicyVersion",
          "iam:ListPolicyVersions",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:TagPolicy",
          "iam:UntagPolicy",
          "iam:PutRolePermissionsBoundary",
          "iam:CreateInstanceProfile",
          "iam:DeleteInstanceProfile",
          "iam:AddRoleToInstanceProfile",
          "iam:RemoveRoleFromInstanceProfile",
          "iam:GetInstanceProfile",
          "iam:ListInstanceProfilesForRole"
        ]
        Resource = [
          "arn:aws:iam::${var.account_id}:role/${var.name_prefix}-*",
          "arn:aws:iam::${var.account_id}:policy/${var.name_prefix}-*",
          "arn:aws:iam::${var.account_id}:instance-profile/${var.name_prefix}-*"
        ]
      },
      {
        Sid    = "DenySecurityServiceModification"
        Effect = "Deny"
        Action = [
          "cloudtrail:StopLogging",
          "cloudtrail:DeleteTrail",
          "guardduty:DeleteDetector",
          "config:DeleteConfigurationRecorder",
          "config:StopConfigurationRecorder"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "terraform_deploy_iam" {
  count      = var.create_terraform_deploy_role ? 1 : 0
  role       = aws_iam_role.terraform_deploy[0].name
  policy_arn = aws_iam_policy.terraform_deploy_iam[0].arn
}
