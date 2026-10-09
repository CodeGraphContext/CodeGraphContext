# A stack that consumes the local module and depends on its sibling.
include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_terragrunt_dir()}/../../modules/bucket"
}

dependency "vpc" {
  config_path = "../vpc"
}

dependencies {
  paths = ["../vpc"]
}

inputs = {
  name = "example-app"
}
