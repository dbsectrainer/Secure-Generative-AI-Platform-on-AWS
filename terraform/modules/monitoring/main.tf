terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── CloudWatch Log Group: X-Ray ───────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "xray" {
  name              = "/aws/xray/${var.name_prefix}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

# ── CloudWatch Alarms: Bedrock Lambda ─────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "bedrock_errors" {
  alarm_name          = "${var.name_prefix}-bedrock-lambda-errors"
  alarm_description   = "Bedrock orchestrator Lambda error rate exceeded threshold"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.bedrock_lambda_function_name
  }

  alarm_actions = var.alarm_sns_topic_arns
  ok_actions    = var.alarm_sns_topic_arns

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "bedrock_duration" {
  alarm_name          = "${var.name_prefix}-bedrock-lambda-duration"
  alarm_description   = "Bedrock orchestrator Lambda p95 duration exceeded threshold"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = var.duration_alarm_threshold_ms
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.bedrock_lambda_function_name
  }

  alarm_actions = var.alarm_sns_topic_arns
  ok_actions    = var.alarm_sns_topic_arns

  tags = var.tags
}

# ── CloudWatch Alarms: RAG Orchestrator Lambda ────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "rag_errors" {
  alarm_name          = "${var.name_prefix}-rag-orchestrator-errors"
  alarm_description   = "RAG orchestrator Lambda error rate exceeded threshold"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_alarm_threshold
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.rag_orchestrator_function_name
  }

  alarm_actions = var.alarm_sns_topic_arns
  ok_actions    = var.alarm_sns_topic_arns

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "rag_duration" {
  alarm_name          = "${var.name_prefix}-rag-orchestrator-duration"
  alarm_description   = "RAG orchestrator Lambda p95 duration exceeded threshold"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = var.duration_alarm_threshold_ms
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.rag_orchestrator_function_name
  }

  alarm_actions = var.alarm_sns_topic_arns
  ok_actions    = var.alarm_sns_topic_arns

  tags = var.tags
}

# ── CloudWatch Dashboard ──────────────────────────────────────────────────────

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name_prefix}-genai-platform"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "## Secure GenAI Platform – ${var.name_prefix}"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Bedrock Lambda – Invocations & Errors"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.bedrock_lambda_function_name, { stat = "Sum", period = 300, label = "Invocations" }],
            ["AWS/Lambda", "Errors", "FunctionName", var.bedrock_lambda_function_name, { stat = "Sum", period = 300, label = "Errors", color = "#d62728" }]
          ]
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Bedrock Lambda – Duration (p50 / p95 / p99)"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.bedrock_lambda_function_name, { stat = "p50", period = 300, label = "p50" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.bedrock_lambda_function_name, { stat = "p95", period = 300, label = "p95" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.bedrock_lambda_function_name, { stat = "p99", period = 300, label = "p99" }]
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          title  = "Bedrock Lambda – Throttles & Concurrent Executions"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Throttles", "FunctionName", var.bedrock_lambda_function_name, { stat = "Sum", period = 300, label = "Throttles" }],
            ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", var.bedrock_lambda_function_name, { stat = "Maximum", period = 300, label = "ConcurrentExec" }]
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 8
        height = 6
        properties = {
          title  = "RAG Orchestrator – Invocations & Errors"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.rag_orchestrator_function_name, { stat = "Sum", period = 300, label = "Invocations" }],
            ["AWS/Lambda", "Errors", "FunctionName", var.rag_orchestrator_function_name, { stat = "Sum", period = 300, label = "Errors", color = "#d62728" }]
          ]
          view    = "timeSeries"
          stacked = false
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 7
        width  = 8
        height = 6
        properties = {
          title  = "RAG Orchestrator – Duration (p50 / p95 / p99)"
          region = var.region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.rag_orchestrator_function_name, { stat = "p50", period = 300, label = "p50" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.rag_orchestrator_function_name, { stat = "p95", period = 300, label = "p95" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.rag_orchestrator_function_name, { stat = "p99", period = 300, label = "p99" }]
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 7
        width  = 8
        height = 6
        properties = {
          title  = "X-Ray – Service Map Errors"
          region = var.region
          metrics = [
            ["AWS/X-Ray", "ErrorRate", { stat = "Average", period = 300, label = "ErrorRate" }],
            ["AWS/X-Ray", "ThrottleRate", { stat = "Average", period = 300, label = "ThrottleRate" }],
            ["AWS/X-Ray", "FaultRate", { stat = "Average", period = 300, label = "FaultRate" }]
          ]
          view = "timeSeries"
        }
      }
    ]
  })
}
