mock_provider "aws" {}
mock_provider "archive" {}

run "rag_wiring" {
  command = plan

  variables {
    name_prefix                  = "secgenai-test"
    region                       = "us-east-1"
    account_id                   = "123456789012"
    private_subnet_ids           = ["subnet-1"]
    lambda_security_group_id     = "sg-1"
    kms_key_arn                  = "arn:aws:kms:us-east-1:123456789012:key/test"
    document_bucket_name         = "test-documents"
    document_bucket_arn          = "arn:aws:s3:::test-documents"
    opensearch_endpoint          = "https://example.aoss.amazonaws.com"
    ingestion_lambda_role_arn    = "arn:aws:iam::123456789012:role/ingest"
    embedding_lambda_role_arn    = "arn:aws:iam::123456789012:role/embed"
    retrieval_lambda_role_arn    = "arn:aws:iam::123456789012:role/retrieve"
    orchestrator_lambda_role_arn = "arn:aws:iam::123456789012:role/orchestrator"
    guardrail_id                 = "guardrail-test"
    guardrail_version            = "1"
    auth_required                = true
    auth_jwks_url                = "https://issuer.test/.well-known/jwks.json"
    auth_issuer                  = "https://issuer.test"
    auth_audience                = "client-test"
  }

  assert {
    condition     = length(aws_lambda_function.orchestrator.layers) == 2
    error_message = "RAG orchestrator must attach the prompt-builder layer"
  }

  assert {
    condition     = aws_lambda_function.orchestrator.environment[0].variables["BEDROCK_GUARDRAIL_ID"] == "guardrail-test"
    error_message = "RAG orchestrator must receive the configured guardrail ID"
  }

  assert {
    condition     = aws_lambda_function.orchestrator.environment[0].variables["AUTH_REQUIRED"] == "true"
    error_message = "RAG orchestrator must receive the auth configuration"
  }

  assert {
    condition     = aws_s3_bucket_notification.documents.bucket == "test-documents"
    error_message = "S3 ObjectCreated notification must target the document bucket"
  }

  assert {
    condition     = contains(flatten([for lf in aws_s3_bucket_notification.documents.lambda_function : lf.events]), "s3:ObjectCreated:*")
    error_message = "S3 notification must trigger on ObjectCreated"
  }
}
