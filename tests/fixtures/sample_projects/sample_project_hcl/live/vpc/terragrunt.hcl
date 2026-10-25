include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "registry.example.com/group/vpc/aws?version=3.0.0"
}

inputs = {
  cidr = "10.0.0.0/16"
}
