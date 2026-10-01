# Terragrunt side: an include, a module source and a dependency on a sibling configuration.
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "registry.example.com/group/s3-bucket/aws?version=2.1.0"
}

dependency "vpc" {
  config_path = "../vpc"
}

inputs = {
  bucket_name = "example-artifacts"
}
