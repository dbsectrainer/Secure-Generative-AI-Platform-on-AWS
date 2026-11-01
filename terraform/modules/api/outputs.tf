output "rest_api_id" {
  description = "ID of the REST API"
  value       = aws_api_gateway_rest_api.main.id
}

output "invoke_url" {
  description = "Base invoke URL for the stage"
  value       = "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.region}.amazonaws.com/${aws_api_gateway_stage.main.stage_name}"
}

output "stage_arn" {
  description = "ARN of the API Gateway stage"
  value       = aws_api_gateway_stage.main.arn
}

output "routes" {
  description = "Map of route key to POST invoke URL"
  value = {
    for key, resource in aws_api_gateway_resource.route :
    key => "https://${aws_api_gateway_rest_api.main.id}.execute-api.${var.region}.amazonaws.com/${aws_api_gateway_stage.main.stage_name}/${resource.path_part}"
  }
}
