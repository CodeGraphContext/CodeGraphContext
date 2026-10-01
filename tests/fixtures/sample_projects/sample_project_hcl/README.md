# sample_project_hcl

HCL2 fixture: Terraform (`main.tf`, `terraform.tfvars`) and Terragrunt (`terragrunt.hcl`).
Covers blocks with one and two labels, `variable`/`output`/`locals`/`inputs`, bare `.tfvars`
assignments, a literal module source, a relative dependency path, and the
`find_in_parent_folders(...)` idiom that must not become an import.
