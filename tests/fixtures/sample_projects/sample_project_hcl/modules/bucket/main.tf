# A local module, consumed by main.tf and by the Terragrunt stack under live/app.
variable "name" {
  description = "Bucket name"
  type        = string
}

resource "aws_s3_bucket" "this" {
  bucket = var.name
}

output "arn" {
  value = aws_s3_bucket.this.arn
}
