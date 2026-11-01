terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

# ── Regional REST API ─────────────────────────────────────────────────────────

resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.name_prefix}-api"
  description = "Secure GenAI Platform API (${var.name_prefix})"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = var.tags
}

locals {
  routes = {
    invoke   = { path = "invoke", lambda_arn = var.bedrock_orchestrator_arn }
    embed    = { path = "embed", lambda_arn = var.embedding_lambda_arn }
    retrieve = { path = "retrieve", lambda_arn = var.retrieval_lambda_arn }
    query    = { path = "query", lambda_arn = var.rag_orchestrator_arn }
  }
}

resource "aws_api_gateway_authorizer" "cognito" {
  count = var.enable_auth ? 1 : 0

  name            = "${var.name_prefix}-cognito-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.main.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [var.cognito_user_pool_arn]
  identity_source = "method.request.header.Authorization"
}

resource "aws_api_gateway_resource" "route" {
  for_each = local.routes

  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = each.value.path
}

resource "aws_api_gateway_method" "post" {
  for_each = local.routes

  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.route[each.key].id
  http_method   = "POST"
  authorization = var.enable_auth ? "COGNITO_USER_POOLS" : "NONE"
  authorizer_id = var.enable_auth ? aws_api_gateway_authorizer.cognito[0].id : null
}

resource "aws_api_gateway_integration" "proxy" {
  for_each = local.routes

  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.route[each.key].id
  http_method = aws_api_gateway_method.post[each.key].http_method

  type                    = "AWS_PROXY"
  integration_http_method = "POST"
  uri                     = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${each.value.lambda_arn}/invocations"
}

resource "aws_lambda_permission" "api" {
  for_each = local.routes

  statement_id  = "AllowApiGatewayInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = each.value.lambda_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode({
      for key, integration in aws_api_gateway_integration.proxy : key => integration.id
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_method.post,
    aws_api_gateway_integration.proxy,
    aws_api_gateway_authorizer.cognito,
  ]
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.stage_name

  xray_tracing_enabled = true

  tags = var.tags
}

resource "aws_wafv2_web_acl_association" "api" {
  count = var.enable_waf ? 1 : 0

  resource_arn = aws_api_gateway_stage.main.arn
  web_acl_arn  = var.waf_web_acl_arn
}
