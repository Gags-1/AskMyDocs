variable "project_name" {
  description = "Project name used for AWS resource naming"
  type        = string
  default     = "askmydocs"
}


variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}


variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}


variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.0.1.0/24"
}


variable "my_ip" {
  description = "Your public IP address for SSH access"
  type        = string
}
