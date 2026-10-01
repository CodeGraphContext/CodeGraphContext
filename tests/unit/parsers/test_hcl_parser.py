"""HCL2 extraction for Terraform / OpenTofu (`.tf`, `.tfvars`) and Terragrunt (`.hcl`).

Blocks carry an address rather than a bare name (`azurerm_key_vault.this`, not `this`), and the
references that make a configuration navigable are the ones naming another unit of code: a module
`source`, a Terragrunt `terraform { source }`, an `include { path }` and a
`dependency { config_path }`.

Imports merge into Module nodes by name alone, which drives two rules. Only a reference written as
a quoted string becomes an import, because `find_in_parent_folders("root.hcl")` names no single
target and would pull every configuration using that idiom onto one node. And a reference relative
to the file that writes it is resolved against that file, because `../..` and
`${get_terragrunt_dir()}/../this` name something different from every file.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.hcl import HclTreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

FIXTURE = Path(__file__).parents[2] / "fixtures" / "sample_projects" / "sample_project_hcl"

TERRAFORM = """# a comment before the body
resource "azurerm_storage_account" "this" {
  name = var.account_name
}

data "azurerm_client_config" "current" {}

module "network" {
  source = "registry.example.com/group/network/azure?version=1.0.0"
}

module "interpolated" {
  source = "registry.example.com/group/vnet/azure?version=${var.v}"
}

variable "account_name" {
  description = "Name of the storage account"
  default     = "examplestorage"
}

output "account_id" {
  value = azurerm_storage_account.this.id
}

locals {
  environment = "test"
}
"""

TERRAGRUNT = """include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "registry.example.com/group/storage-account/azure?version=2.1.0"
}

dependency "vault" {
  config_path = "../vault"
}

inputs = {
  account_name = "examplestorage"
}
"""

TFVARS = """location = "westeurope"
tags     = { owner = "platform" }
"""


@pytest.fixture(scope="module")
def parser():
    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "hcl"
    wrapper.language = manager.get_language_safe("hcl")
    wrapper.parser = manager.create_parser("hcl")
    return HclTreeSitterParser(wrapper)


def parse(parser, tmp_path, name, source):
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return parser.parse(str(path))


@pytest.fixture(scope="module")
def terraform(parser, tmp_path_factory):
    return parse(parser, tmp_path_factory.mktemp("tf"), "main.tf", TERRAFORM)


@pytest.fixture(scope="module")
def terragrunt(parser, tmp_path_factory):
    return parse(parser, tmp_path_factory.mktemp("tg"), "terragrunt.hcl", TERRAGRUNT)


@pytest.mark.parametrize("name", ["main.tf", "terragrunt.hcl", "terraform.tfvars"])
def test_the_sample_project_parses(parser, name):
    result = parser.parse(str(FIXTURE / name))
    assert result["classes"] or result["variables"]


class TestTerraform:
    def test_blocks_use_their_terraform_address(self, terraform):
        names = {c["name"] for c in terraform["classes"]}
        assert {"azurerm_storage_account.this", "data.azurerm_client_config.current",
                "module.network"} <= names

    def test_the_block_type_is_kept_where_the_backends_store_it(self, terraform):
        by_name = {c["name"]: c for c in terraform["classes"]}
        assert by_name["azurerm_storage_account.this"]["node_type"] == "resource"

    def test_a_leading_comment_does_not_hide_the_body(self, terraform):
        """The comment is a sibling of the body, so the body is not the first child."""
        assert terraform["classes"], "no blocks were extracted at all"

    def test_variables_outputs_and_locals(self, terraform):
        by_name = {v["name"]: v for v in terraform["variables"]}
        assert {"var.account_name", "output.account_id", "local.environment"} <= set(by_name)
        assert by_name["var.account_name"]["value"] == '"examplestorage"'
        assert by_name["var.account_name"]["docstring"] == "Name of the storage account"

    def test_module_sources_are_imports_including_interpolated_ones(self, terraform):
        sources = {i["source"] for i in terraform["imports"]}
        assert "registry.example.com/group/network/azure?version=1.0.0" in sources
        assert "registry.example.com/group/vnet/azure?version=${var.v}" in sources

    def test_hcl_has_no_functions(self, terraform):
        assert terraform["functions"] == []


class TestTerragrunt:
    def test_the_terraform_source_is_an_import(self, terragrunt):
        sources = {i["source"] for i in terragrunt["imports"]}
        assert "registry.example.com/group/storage-account/azure?version=2.1.0" in sources

    def test_an_unresolved_expression_is_not_an_import(self, terragrunt):
        assert not any("find_in_parent_folders" in i["source"] for i in terragrunt["imports"])

    def test_a_relative_path_resolves_against_its_own_file(self, terragrunt):
        resolved = [s for s in {i["source"] for i in terragrunt["imports"]} if s.endswith("/vault")]
        assert resolved and all(s.startswith("/") for s in resolved)

    def test_top_level_inputs_become_a_variable(self, terragrunt):
        assert "inputs" in {v["name"] for v in terragrunt["variables"]}


class TestInterpolatedPaths:
    def test_the_two_kinds_of_interpolation_are_treated_differently(self, parser, tmp_path):
        """`get_repo_root()` names the same file from every configuration, so they should meet on
        one node. `get_terragrunt_dir()` names a different one from each, so they must not."""
        source = ('include "root" { path = "${get_repo_root()}/common/shared.hcl" }\n'
                  'dependency "sibling" { config_path = "${get_terragrunt_dir()}/../this" }\n')
        names = {i["source"] for i in parse(parser, tmp_path, "terragrunt.hcl", source)["imports"]}
        assert "${get_repo_root()}/common/shared.hcl" in names
        assert not any("get_terragrunt_dir" in n for n in names)
        assert any(n.startswith("/") and n.endswith("/this") for n in names), names


class TestTfvars:
    def test_bare_assignments_become_variables(self, parser, tmp_path):
        by_name = {v["name"]: v for v in parse(parser, tmp_path, "terraform.tfvars", TFVARS)["variables"]}
        assert {"location", "tags"} <= set(by_name)
        assert by_name["location"]["value"] == '"westeurope"'


def test_an_empty_file_yields_nothing(parser, tmp_path):
    result = parse(parser, tmp_path, "empty.tf", "")
    assert result["classes"] == result["variables"] == result["imports"] == []
