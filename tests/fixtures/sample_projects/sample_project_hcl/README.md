# sample_project_hcl

HCL2 fixture: Terraform (`main.tf`, `terraform.tfvars`, `modules/bucket`) and Terragrunt
(`root.hcl`, `live/*/terragrunt.hcl`).
Covers blocks with one and two labels, `variable`/`output`/`locals`/`inputs`, a heredoc
description, bare `.tfvars` assignments, a registry and a local module source, a local module
consumed from both Terraform and Terragrunt, `dependency` and `dependencies` paths, the
`find_in_parent_folders(...)` idiom that must not become an import, and a `.terraform.lock.hcl`
that must not be indexed.
Every relative reference stays inside this directory, so the exported graph carries no
machine-specific path.
