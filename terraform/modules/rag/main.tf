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

# ── Lambda package archives ───────────────────────────────────────────────────

data "archive_file" "ingestion" {
  type        = "zip"
  source_dir  = "${path.module}/../../../rag/ingestion"
  output_path = "${path.module}/ingestion_lambda.zip"
  excludes    = ["tests", "__pycache__"]
}

data "archive_file" "embedding" {
  type        = "zip"
  source_dir  = "${path.module}/../../../rag/embedding"
  output_path = "${path.module}/embedding_lambda.zip"
  excludes    = ["tests", "__pycache__"]
}

data "archive_file" "retrieval" {
  type        = "zip"
  source_dir  = "${path.module}/../../../rag/retrieval"
  output_path = "${path.module}/retrieval_lambda.zip"
  excludes    = ["tests", "__pycache__"]
}

data "archive_file" "orchestrator" {
  type        = "zip"
  source_dir  = "${path.module}/../../../rag/orchestrator"
  output_path = "${path.module}/orchestrator_lambda.zip"
  excludes    = ["tests", "__pycache__"]
}

# ── CloudWatch Log Groups ─────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${var.name_prefix}-rag-ingestion"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "embedding" {
  name              = "/aws/lambda/${var.name_prefix}-rag-embedding"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "retrieval" {
  name              = "/aws/lambda/${var.name_prefix}-rag-retrieval"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "orchestrator" {
  name              = "/aws/lambda/${var.name_prefix}-rag-orchestrator"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

# ── Lambda: Document Ingestion ────────────────────────────────────────────────

resource "aws_lambda_function" "ingestion" {
  filename         = data.archive_file.ingestion.output_path
  function_name    = "${var.name_prefix}-rag-ingestion"
  role             = var.ingestion_lambda_role_arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.13"
  source_code_hash = data.archive_file.ingestion.output_base64sha256
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb

  environment {
    variables = {
      DOCUMENT_BUCKET      = var.document_bucket_name
      EMBEDDING_LAMBDA_ARN = aws_lambda_function.embedding.arn
      CHUNK_SIZE           = tostring(var.chunk_size)
      CHUNK_OVERLAP        = tostring(var.chunk_overlap)
      LOG_LEVEL            = var.log_level
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config { mode = "Active" }

  reserved_concurrent_executions = var.reserved_concurrent_executions

  depends_on = [aws_cloudwatch_log_group.ingestion]

  tags = merge(var.tags, { Name = "${var.name_prefix}-rag-ingestion" })
}

# ── Lambda: Embedding Generation ─────────────────────────────────────────────

resource "aws_lambda_function" "embedding" {
  filename         = data.archive_file.embedding.output_path
  function_name    = "${var.name_prefix}-rag-embedding"
  role             = var.embedding_lambda_role_arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.13"
  source_code_hash = data.archive_file.embedding.output_base64sha256
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb

  environment {
    variables = {
      BEDROCK_EMBEDDING_MODEL_ID = var.embedding_model_id
      BEDROCK_REGION             = var.region
      OPENSEARCH_ENDPOINT        = var.opensearch_endpoint
      OPENSEARCH_INDEX           = var.opensearch_index
      LOG_LEVEL                  = var.log_level
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config { mode = "Active" }

  reserved_concurrent_executions = var.reserved_concurrent_executions

  depends_on = [aws_cloudwatch_log_group.embedding]

  tags = merge(var.tags, { Name = "${var.name_prefix}-rag-embedding" })
}

# ── Lambda: Retrieval ─────────────────────────────────────────────────────────

resource "aws_lambda_function" "retrieval" {
  filename         = data.archive_file.retrieval.output_path
  function_name    = "${var.name_prefix}-rag-retrieval"
  role             = var.retrieval_lambda_role_arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.13"
  source_code_hash = data.archive_file.retrieval.output_base64sha256
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb

  environment {
    variables = {
      BEDROCK_EMBEDDING_MODEL_ID = var.embedding_model_id
      BEDROCK_REGION             = var.region
      OPENSEARCH_ENDPOINT        = var.opensearch_endpoint
      OPENSEARCH_INDEX           = var.opensearch_index
      TOP_K                      = tostring(var.retrieval_top_k)
      LOG_LEVEL                  = var.log_level
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config { mode = "Active" }

  reserved_concurrent_executions = var.reserved_concurrent_executions

  depends_on = [aws_cloudwatch_log_group.retrieval]

  tags = merge(var.tags, { Name = "${var.name_prefix}-rag-retrieval" })
}

# ── Lambda: RAG Orchestrator ──────────────────────────────────────────────────

resource "aws_lambda_function" "orchestrator" {
  filename         = data.archive_file.orchestrator.output_path
  function_name    = "${var.name_prefix}-rag-orchestrator"
  role             = var.orchestrator_lambda_role_arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.13"
  source_code_hash = data.archive_file.orchestrator.output_base64sha256
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb

  environment {
    variables = {
      BEDROCK_MODEL_ID     = var.inference_model_id
      BEDROCK_REGION       = var.region
      RETRIEVAL_LAMBDA_ARN = aws_lambda_function.retrieval.arn
      MAX_TOKENS           = tostring(var.max_tokens)
      TOP_K                = tostring(var.retrieval_top_k)
      PROMPT_MODE          = var.prompt_mode
      LOG_LEVEL            = var.log_level
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tracing_config { mode = "Active" }

  reserved_concurrent_executions = var.reserved_concurrent_executions

  depends_on = [aws_cloudwatch_log_group.orchestrator]

  tags = merge(var.tags, { Name = "${var.name_prefix}-rag-orchestrator" })
}

# ── CloudWatch Alarms ─────────────────────────────────────────────────────────

resource "aws_cloudwatch_metric_alarm" "orchestrator_errors" {
  alarm_name          = "${var.name_prefix}-rag-orchestrator-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = var.error_alarm_threshold
  alarm_description   = "RAG orchestrator Lambda error rate exceeded threshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    FunctionName = aws_lambda_function.orchestrator.function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "orchestrator_duration" {
  alarm_name          = "${var.name_prefix}-rag-orchestrator-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  extended_statistic  = "p95"
  threshold           = var.duration_alarm_threshold_ms
  alarm_description   = "RAG orchestrator Lambda p95 duration exceeded threshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_sns_topic_arns

  dimensions = {
    FunctionName = aws_lambda_function.orchestrator.function_name
  }

  tags = var.tags
}
