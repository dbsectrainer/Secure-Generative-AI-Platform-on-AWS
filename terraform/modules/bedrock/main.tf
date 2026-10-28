terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

# ── CloudWatch Log Group for Lambda ──────────────────────────────────────────

resource "aws_cloudwatch_log_group" "bedrock_lambda" {
  name              = "/aws/lambda/${var.name_prefix}-bedrock-orchestrator"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

# ── Lambda Function Package ───────────────────────────────────────────────────

data "archive_file" "bedrock_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambda/bedrock_integration"
  output_path = "${path.module}/bedrock_lambda.zip"
}

# ── Lambda Function ───────────────────────────────────────────────────────────

resource "aws_lambda_function" "bedrock_orchestrator" {
  filename         = data.archive_file.bedrock_lambda.output_path
  function_name    = "${var.name_prefix}-bedrock-orchestrator"
  role             = var.lambda_role_arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.13"
  source_code_hash = data.archive_file.bedrock_lambda.output_base64sha256
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb

  environment {
    variables = {
      BEDROCK_MODEL_ID     = var.bedrock_model_id
      BEDROCK_REGION       = var.region
      DOCUMENT_BUCKET      = var.document_bucket_name
      MAX_TOKENS           = tostring(var.max_tokens)
      LOG_LEVEL            = var.log_level
      POWERTOOLS_LOG_LEVEL = var.log_level
      POWERTOOLS_SERVICE_NAME = "${var.name_prefix}-bedrock-orchestrator"
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config {
    mode = "Active"
  }

  reserved_concurrent_executions = var.reserved_concurrent_executions

  depends_on = [aws_cloudwatch_log_group.bedrock_lambda]

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-bedrock-orchestrator"
  })
}

# ── Lambda Alias (for canary / blue-green deployments) ────────────────────────

resource "aws_lambda_alias" "live" {
  name             = "live"
  description      = "Live traffic alias"
  function_name    = aws_lambda_function.bedrock_orchestrator.function_name
  function_version = aws_lambda_function.bedrock_orchestrator.version
}

# ── CloudWatch Alarms ─────────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.name_prefix}-bedrock-orchestrator-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = var.error_alarm_threshold
  alarm_description   = "Lambda error rate exceeded threshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    FunctionName = aws_lambda_function.bedrock_orchestrator.function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.name_prefix}-bedrock-orchestrator-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  extended_statistic  = "p95"
  threshold           = var.duration_alarm_threshold_ms
  alarm_description   = "Lambda p95 duration exceeded threshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    FunctionName = aws_lambda_function.bedrock_orchestrator.function_name
  }

  tags = var.tags
}

# ── Bedrock Guardrails ────────────────────────────────────────────────────────

resource "aws_bedrock_guardrail" "main" {
  count                     = var.enable_bedrock_guardrail ? 1 : 0
  name                      = "${var.name_prefix}-guardrail"
  description               = "Guardrail for ${var.name_prefix} Bedrock orchestrator"
  blocked_input_messaging   = "Your request contains content that is not allowed."
  blocked_outputs_messaging = "The model response was blocked due to content policy."

  content_policy_config {
    filters_config {
      type            = "HATE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "VIOLENCE"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "SEXUAL"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "MISCONDUCT"
      input_strength  = "HIGH"
      output_strength = "HIGH"
    }
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "NAME"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "AWS_ACCESS_KEY"
      action = "BLOCK"
    }
    pii_entities_config {
      type   = "AWS_SECRET_KEY"
      action = "BLOCK"
    }
  }

  tags = var.tags
}
