mock_provider "aws" {}

run "cognito_wiring" {
  command = plan

  variables {
    name_prefix = "secgenai-test"
    region      = "us-east-1"
  }

  assert {
    condition     = aws_cognito_user_pool.main.name == "secgenai-test-users"
    error_message = "Cognito user pool name is not prefixed"
  }

  assert {
    condition     = aws_cognito_user_pool_client.api.name == "secgenai-test-api-client"
    error_message = "Cognito app client name is not prefixed"
  }

  assert {
    condition     = contains(aws_cognito_user_pool_client.api.explicit_auth_flows, "ALLOW_USER_PASSWORD_AUTH")
    error_message = "Cognito client must allow user password auth for API token issuance"
  }
}
