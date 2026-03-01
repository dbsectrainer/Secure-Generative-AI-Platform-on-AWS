output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "IDs of private application subnets"
  value       = aws_subnet.private_app[*].id
}

output "private_data_subnet_ids" {
  description = "IDs of private data subnets"
  value       = aws_subnet.private_data[*].id
}

output "lambda_security_group_id" {
  description = "Security group ID for Lambda orchestrator functions"
  value       = aws_security_group.lambda_orchestrator.id
}

output "vpc_endpoints_security_group_id" {
  description = "Security group ID for Interface VPC endpoint ENIs"
  value       = aws_security_group.vpc_endpoints.id
}

output "s3_gateway_endpoint_id" {
  description = "ID of the S3 Gateway endpoint"
  value       = aws_vpc_endpoint.s3_gateway.id
}

output "interface_endpoint_ids" {
  description = "Map of interface VPC endpoint IDs"
  value       = { for k, v in aws_vpc_endpoint.interface : k => v.id }
}

output "nat_gateway_ids" {
  description = "IDs of NAT gateways"
  value       = aws_nat_gateway.main[*].id
}

output "private_app_route_table_ids" {
  description = "IDs of private application route tables"
  value       = aws_route_table.private_app[*].id
}
