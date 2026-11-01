output "user_pool_id" {
  description = "Cognito user pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "Cognito user pool ARN for the API Gateway authorizer"
  value       = aws_cognito_user_pool.main.arn
}

output "client_id" {
  description = "Cognito app client ID (JWT audience)"
  value       = aws_cognito_user_pool_client.api.id
}

output "issuer" {
  description = "Cognito JWT issuer"
  value       = local.issuer
}

output "jwks_url" {
  description = "Cognito JWKS endpoint"
  value       = "${local.issuer}/.well-known/jwks.json"
}
