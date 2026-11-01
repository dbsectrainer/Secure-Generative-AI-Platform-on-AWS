mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:user/audit"
      user_id    = "AIDAEXAMPLE"
    }
  }

  mock_data "aws_region" {
    defaults = {
      name = "eu-west-1"
    }
  }
}

mock_provider "archive" {}

run "full_stack_plan" {
  command = plan

  assert {
    condition     = length(module.api.routes) == 4
    error_message = "Expected four API routes (invoke, embed, retrieve, query)"
  }

  assert {
    condition     = module.rag.ingestion_lambda_name == "secgenai-dev-rag-ingestion"
    error_message = "RAG ingestion Lambda name is not wired with the environment prefix"
  }

  assert {
    condition     = module.rag.orchestrator_lambda_name == "secgenai-dev-rag-orchestrator"
    error_message = "RAG orchestrator Lambda name is not wired with the environment prefix"
  }

  assert {
    condition     = module.bedrock.lambda_function_name == "secgenai-dev-bedrock-orchestrator"
    error_message = "Bedrock orchestrator Lambda name is not wired"
  }
}
