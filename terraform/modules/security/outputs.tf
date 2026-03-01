output "guardduty_detector_id" {
  description = "GuardDuty detector ID"
  value       = aws_guardduty_detector.main.id
}

output "guardduty_detector_arn" {
  description = "GuardDuty detector ARN"
  value       = "arn:aws:guardduty:${var.region}:${var.account_id}:detector/${aws_guardduty_detector.main.id}"
}

output "access_analyzer_arn" {
  description = "IAM Access Analyzer ARN"
  value       = aws_accessanalyzer_analyzer.main.arn
}

output "access_analyzer_name" {
  description = "IAM Access Analyzer name"
  value       = aws_accessanalyzer_analyzer.main.analyzer_name
}

output "config_recorder_name" {
  description = "AWS Config configuration recorder name"
  value       = aws_config_configuration_recorder.main.name
}

output "config_bucket_name" {
  description = "S3 bucket name for AWS Config delivery"
  value       = aws_s3_bucket.config.id
}

output "config_bucket_arn" {
  description = "S3 bucket ARN for AWS Config delivery"
  value       = aws_s3_bucket.config.arn
}
