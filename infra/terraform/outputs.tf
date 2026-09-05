output "vpc_id" {
  description = "ID of the AskMyDocs VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "ID of the public subnet"
  value       = aws_subnet.public.id
}

output "security_group_id" {
  description = "ID of the application security group"
  value       = aws_security_group.app.id
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.app.repository_url
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app.id
}

output "ec2_public_ip" {
  description = "Public IP address of AskMyDocs EC2 instance"
  value       = aws_instance.app.public_ip
}

output "github_actions_role_arn" {
  description = "IAM role ARN used by GitHub Actions"
  value       = aws_iam_role.github_actions.arn
}

output "s3_bucket_name" {
  value = aws_s3_bucket.pdf_storage.bucket
}

output "s3_bucket_arn" {
  value = aws_s3_bucket.pdf_storage.arn
}
