# Terraform side: resources, a data source, a registry module, a local module and the variables around them.
provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "artifacts" {
  bucket = var.bucket_name
  tags   = local.tags
}

data "aws_caller_identity" "current" {}

module "network" {
  source = "registry.example.com/group/network/aws?version=1.0.0"
  name   = var.bucket_name
}

module "logs" {
  source = "./modules/bucket"
  name   = "${var.bucket_name}-logs"
}

variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "bucket_name" {
  description = <<-EOT
    Name of the artifact bucket.
    Must be globally unique.
  EOT
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
