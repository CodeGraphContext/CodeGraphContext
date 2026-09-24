from pathlib import Path

import pytest

from codegraphcontext.tools.languages.solidity_remappings import (
    apply_solidity_remapping,
    load_solidity_remappings,
    parse_remapping_line,
    resolve_solidity_import_path,
)
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser

FOUNDRY_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sample_projects"
    / "sample_project_solidity_foundry"
)
SOLIDITY_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sample_projects"
    / "sample_project_solidity"
)


@pytest.fixture(scope="module")
def solidity_available():
    try:
        from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

        get_tree_sitter_manager().get_language_safe("solidity")
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Solidity grammar unavailable: {exc}")


@pytest.fixture
def parser(solidity_available):
    return TreeSitterParser("solidity").language_specific_parser


def test_parse_remapping_line():
    assert parse_remapping_line("forge-std/=lib/forge-std/src/") == (
        "forge-std/",
        "lib/forge-std/src/",
    )
    assert parse_remapping_line("# comment") is None
    assert parse_remapping_line("") is None


def test_load_foundry_toml_remappings():
    cfg = load_solidity_remappings(FOUNDRY_DIR)
    assert "forge-std/" in cfg.aliases
    assert cfg.aliases["forge-std/"] == "lib/helper/src/"
    rewritten = apply_solidity_remapping("forge-std/Helper.sol", cfg)
    assert rewritten == "lib/helper/src/Helper.sol"


def test_resolve_remapped_import_to_filesystem():
    effective, resolved = resolve_solidity_import_path(
        "forge-std/Helper.sol",
        importer_file=FOUNDRY_DIR / "src" / "App.sol",
        repo_path=FOUNDRY_DIR,
    )
    assert effective == "lib/helper/src/Helper.sol"
    assert resolved is not None
    assert resolved.replace("\\", "/").endswith("lib/helper/src/Helper.sol")


def test_parser_applies_remapping(parser):
    result = parser.parse(FOUNDRY_DIR / "src" / "App.sol", repo_path=FOUNDRY_DIR)
    assert result["imports"]
    imp = result["imports"][0]
    assert imp["raw_source"] == "forge-std/Helper.sol"
    assert imp["source"] == "lib/helper/src/Helper.sol"
    assert imp["remapped"] is True
    assert imp.get("resolved_path")
    call_names = {c["name"] for c in result["function_calls"]}
    assert "ping" in call_names


def test_modifier_invocation_emits_call(parser):
    result = parser.parse(SOLIDITY_DIR / "Greeter.sol")
    mod_calls = [
        c for c in result["function_calls"] if c.get("call_kind") == "modifier_invocation"
    ]
    assert any(c["name"] == "nonEmpty" for c in mod_calls)
    non_empty = next(c for c in mod_calls if c["name"] == "nonEmpty")
    assert non_empty["context"][0] == "greet"


def test_using_for_rewrites_member_call(parser):
    result = parser.parse(SOLIDITY_DIR / "UsingCounter.sol")
    assert any(u["library"] == "MathLib" and u["type"] == "uint256" for u in result["using_directives"])
    add_calls = [c for c in result["function_calls"] if c["name"] == "add"]
    assert add_calls
    assert any(
        c.get("inferred_obj_type") == "MathLib" or (c.get("full_name") or "").startswith("MathLib.")
        for c in add_calls
    )


def test_emit_and_revert_call_kinds(parser):
    result = parser.parse(SOLIDITY_DIR / "Greeter.sol")
    emit_calls = [c for c in result["function_calls"] if c.get("call_kind") == "emit"]
    assert any(c["name"] == "Greeted" for c in emit_calls)
    greeted = next(c for c in emit_calls if c["name"] == "Greeted")
    assert greeted["context"][0] == "bump"

    revert_calls = [c for c in result["function_calls"] if c.get("call_kind") == "revert_error"]
    assert any(c["name"] == "EmptyName" for c in revert_calls)
