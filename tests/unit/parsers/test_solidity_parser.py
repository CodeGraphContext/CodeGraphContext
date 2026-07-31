from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.solidity import (
    SOLIDITY_BUILT_INS,
    SOLIDITY_QUERIES,
    SolidityTreeSitterParser,
    pre_scan_solidity,
)
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager

FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "sample_projects"
    / "sample_project_solidity"
)


@pytest.fixture(scope="module")
def solidity_available():
    try:
        manager = get_tree_sitter_manager()
        manager.get_language_safe("solidity")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Solidity grammar unavailable: {exc}")


@pytest.fixture
def parser(solidity_available):
    wrapper = TreeSitterParser("solidity")
    return wrapper.language_specific_parser


def test_queries_cover_core_captures():
    for key in ("functions", "classes", "imports", "calls", "variables"):
        assert key in SOLIDITY_QUERIES
        assert "@" in SOLIDITY_QUERIES[key]


def test_parse_greeter_extracts_types_and_members(parser):
    path = FIXTURE_DIR / "Greeter.sol"
    result = parser.parse(path)

    assert result["lang"] == "solidity"
    class_names = {c["name"] for c in result["classes"]}
    assert "Greeter" in class_names
    assert "Greeted" in class_names or "EmptyName" in class_names

    interface_names = {i["name"] for i in result.get("interfaces", [])}
    # Greeter.sol does not declare an interface; BaseGreeter does via import target.
    assert "IGreeter" not in interface_names

    greeter = next(c for c in result["classes"] if c["name"] == "Greeter")
    assert "BaseGreeter" in greeter["bases"]

    func_names = {f["name"] for f in result["functions"]}
    assert "greet" in func_names
    assert "bump" in func_names
    assert "constructor" in func_names
    assert "nonEmpty" in func_names
    assert "receive" in func_names

    greet = next(f for f in result["functions"] if f["name"] == "greet")
    assert greet["class_context"] == "Greeter"
    assert "name" in greet["args"]

    import_sources = {imp.get("source") or imp.get("full_import_name") for imp in result["imports"]}
    assert "./BaseGreeter.sol" in import_sources
    assert "./MathLib.sol" in import_sources

    named = [imp for imp in result["imports"] if imp.get("name") == "BaseGreeter"]
    assert named, "named import {BaseGreeter} should be captured"

    call_names = {c["name"] for c in result["function_calls"]}
    assert "add" in call_names
    assert "setPrefix" in call_names
    # Built-ins / abi noise should not dominate.
    assert "encodePacked" not in call_names or "abi" not in {
        (c.get("full_name") or "").split(".")[0] for c in result["function_calls"]
    }

    var_names = {v["name"] for v in result["variables"]}
    assert "greetCount" in var_names


def test_parse_base_and_interface(parser):
    base = parser.parse(FIXTURE_DIR / "BaseGreeter.sol")
    base_cls = next(c for c in base["classes"] if c["name"] == "BaseGreeter")
    assert "IGreeter" in base_cls["bases"]

    iface = parser.parse(FIXTURE_DIR / "IGreeter.sol")
    assert any(i["name"] == "IGreeter" for i in iface["interfaces"])
    assert any(f["name"] == "greet" for f in iface["functions"])

    lib = parser.parse(FIXTURE_DIR / "MathLib.sol")
    assert any(c["name"] == "MathLib" for c in lib["classes"])
    assert any(f["name"] == "add" and f["class_context"] == "MathLib" for f in lib["functions"])


def test_pre_scan_maps_symbols():
    files = sorted(FIXTURE_DIR.glob("*.sol"))
    mapping = pre_scan_solidity(files, MagicMock())
    assert "Greeter" in mapping
    assert "IGreeter" in mapping
    assert "MathLib" in mapping
    assert "BaseGreeter" in mapping
    # File-stem mapping for path imports
    assert "Greeter" in mapping


def test_tree_sitter_parser_dispatch(solidity_available):
    wrapper = TreeSitterParser("solidity")
    assert isinstance(wrapper.language_specific_parser, SolidityTreeSitterParser)
    result = wrapper.parse(FIXTURE_DIR / "MathLib.sol")
    assert result["functions"]
    assert SOLIDITY_BUILT_INS  # sanity: filter set exported
