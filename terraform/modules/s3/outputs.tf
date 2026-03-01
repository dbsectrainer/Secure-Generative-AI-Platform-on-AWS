output "bucket_id" {
  description = "Name (ID) of the S3 document bucket"
  value       = aws_s3_bucket.documents.id
}

output "bucket_arn" {
  description = "ARN of the S3 document bucket"
  value       = aws_s3_bucket.documents.arn
}

output "kms_key_arn" {
  description = "ARN of the KMS CMK used to encrypt S3 objects"
  value       = aws_kms_key.s3_documents.arn
}

output "kms_key_id" {
  description = "ID of the KMS CMK"
  value       = aws_kms_key.s3_documents.key_id
}

output "kms_key_alias" {
  description = "Alias of the KMS CMK"
  value       = aws_kms_alias.s3_documents.name
}
