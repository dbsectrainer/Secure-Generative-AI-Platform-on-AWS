terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── GuardDuty ─────────────────────────────────────────────────────────────────

resource "aws_guardduty_detector" "main" {
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = false  # Not using EKS in this platform
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = false  # Not using EC2 in this platform
        }
      }
    }
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-guardduty"
  })
}

# ── GuardDuty SNS notification for findings ───────────────────────────────────

resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  name        = "${var.name_prefix}-guardduty-findings"
  description = "Route GuardDuty HIGH/CRITICAL findings to SNS"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
    detail = {
      severity = [{ numeric = [">=", 7] }]  # HIGH (7.0+) and CRITICAL (9.0+)
    }
  })

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "guardduty_sns" {
  count = length(var.alarm_sns_topic_arns) > 0 ? 1 : 0

  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "GuardDutySNSTarget"
  arn       = var.alarm_sns_topic_arns[0]
}

# ── AWS Config: Configuration Recorder ───────────────────────────────────────

resource "aws_iam_role" "config" {
  name = "${var.name_prefix}-role-config"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "sts:AssumeRole"
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

resource "aws_iam_role_policy_attachment" "config_service" {
  role       = aws_iam_role.config.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

resource "aws_s3_bucket" "config" {
  bucket        = "${var.name_prefix}-config-${var.account_id}"
  force_destroy = false

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-config-bucket"
  })
}

resource "aws_s3_bucket_versioning" "config" {
  bucket = aws_s3_bucket.config.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "config" {
  bucket = aws_s3_bucket.config.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "config" {
  bucket = aws_s3_bucket.config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "config" {
  bucket = aws_s3_bucket.config.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSConfigBucketPermissionsCheck"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.config.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      },
      {
        Sid    = "AWSConfigBucketDelivery"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.config.arn}/AWSLogs/${var.account_id}/Config/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"    = "bucket-owner-full-control"
            "aws:SourceAccount" = var.account_id
          }
        }
      },
      {
        Sid    = "DenyNonTLSAccess"
        Effect = "Deny"
        Principal = "*"
        Action   = "s3:*"
        Resource = [
          aws_s3_bucket.config.arn,
          "${aws_s3_bucket.config.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_config_configuration_recorder" "main" {
  name     = "${var.name_prefix}-config-recorder"
  role_arn = aws_iam_role.config.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }

  depends_on = [aws_iam_role_policy_attachment.config_service]
}

resource "aws_config_delivery_channel" "main" {
  name           = "${var.name_prefix}-config-delivery"
  s3_bucket_name = aws_s3_bucket.config.id

  snapshot_delivery_properties {
    delivery_frequency = "Six_Hours"
  }

  depends_on = [aws_config_configuration_recorder.main]
}

resource "aws_config_configuration_recorder_status" "main" {
  name       = aws_config_configuration_recorder.main.name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.main]
}

# ── AWS Config Rules ──────────────────────────────────────────────────────────

locals {
  managed_config_rules = {
    "s3-bucket-public-read-prohibited"           = {}
    "s3-bucket-public-write-prohibited"          = {}
    "s3-bucket-ssl-requests-only"               = {}
    "s3-bucket-server-side-encryption-enabled"  = {}
    "iam-no-inline-policy"                       = {}
    "iam-root-access-key-check"                  = {}
    "iam-user-mfa-enabled"                       = {}
    "restricted-ssh"                             = {}
    "restricted-common-ports"                    = {}
    "vpc-flow-logs-enabled"                      = {}
    "cloud-trail-enabled"                        = {}
    "guardduty-enabled-centralized"              = {}
    "kms-cmk-not-scheduled-for-deletion"         = {}
    "lambda-function-public-access-prohibited"   = {}
    "lambda-inside-vpc"                          = {}
    "cloudtrail-s3-dataevents-enabled"           = {}
    "cloudtrail-log-file-validation-enabled"     = {}
  }
}

resource "aws_config_config_rule" "managed" {
  for_each = local.managed_config_rules

  name = each.key

  source {
    owner             = "AWS"
    source_identifier = upper(replace(each.key, "-", "_"))
  }

  depends_on = [aws_config_configuration_recorder_status.main]

  tags = var.tags
}

# ── IAM Access Analyzer ───────────────────────────────────────────────────────

resource "aws_accessanalyzer_analyzer" "main" {
  analyzer_name = "${var.name_prefix}-access-analyzer"
  type          = "ACCOUNT"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-access-analyzer"
  })
}

# ── CloudWatch Alarm: Config non-compliant resources ─────────────────────────

resource "aws_cloudwatch_metric_alarm" "config_non_compliant" {
  alarm_name          = "${var.name_prefix}-config-non-compliant"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "NonCompliantRules"
  namespace           = "AWS/Config"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "AWS Config detected non-compliant resources"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arns

  tags = var.tags
}

# ── CloudWatch Alarm: GuardDuty findings ─────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "guardduty_high_findings" {
  alarm_name          = "${var.name_prefix}-guardduty-high-findings"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FindingCount"
  namespace           = "AWS/GuardDuty"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "GuardDuty detected new findings"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    DetectorId = aws_guardduty_detector.main.id
  }

  tags = var.tags
}
