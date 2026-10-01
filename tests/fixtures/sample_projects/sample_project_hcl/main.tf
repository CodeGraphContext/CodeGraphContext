# Terraform side: a resource, a data source, a module and the variables around them.
resource "aws_s3_bucket" "artifacts" {
  bucket = var.bucket_name
  tags   = local.tags
}

data "aws_caller_identity" "current" {}

module "network" {
  source = "registry.example.com/group/network/aws?version=1.0.0"
  name   = var.bucket_name
}

variable "bucket_name" {
  description = "Name of the artifact bucket"
  type        = string
  default     = "example-artifacts"
}

output "bucket_arn" {
  description = "ARN of the artifact bucket"
  value       = aws_s3_bucket.artifacts.arn
}

locals {
  tags = { owner = "platform" }
}
