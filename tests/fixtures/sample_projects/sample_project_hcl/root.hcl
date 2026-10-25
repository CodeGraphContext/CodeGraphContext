# Terragrunt root configuration, included by every stack under live/.
remote_state {
  backend = "s3"
  config = {
    bucket = "example-terraform-state"
    key    = "${path_relative_to_include()}/terraform.tfstate"
  }
}

generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite"
  contents  = "provider \"aws\" {}"
}
