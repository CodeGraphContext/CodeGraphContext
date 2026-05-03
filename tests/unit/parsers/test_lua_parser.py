from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.lua import LuaTreeSitterParser, pre_scan_lua
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def lua_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("lua"):
        pytest.skip("Lua tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "lua"
    wrapper.language = manager.get_language_safe("lua")
    wrapper.parser = manager.create_parser("lua")
    return LuaTreeSitterParser(wrapper)


def test_tree_sitter_dispatches_lua_parser():
    parser = TreeSitterParser("lua")

    assert isinstance(parser.language_specific_parser, LuaTreeSitterParser)


def test_parse_lua_functions_imports_and_calls(lua_parser, temp_test_dir):
    code = """
local M = {}
local helper = require("helpers.path")

local function local_named(a, b)
  print(a)
  return helper.join(a, b)
end

function M.named(self, value)
  local x = local_named(value, "suffix")
  return x
end

M.assigned = function(v)
  return tostring(v)
end

function M:method(value)
  return self.named(self, value)
end
"""
    f = temp_test_dir / "sample.lua"
    f.write_text(code)

    result = lua_parser.parse(f)

    assert result["lang"] == "lua"

    functions_by_full_name = {fn["full_name"]: fn for fn in result["functions"]}
    assert {"local_named", "M.named", "M.assigned", "M.method"}.issubset(functions_by_full_name)
    assert functions_by_full_name["M.named"]["name"] == "named"
    assert functions_by_full_name["M.named"]["class_context"] == "M"
    assert functions_by_full_name["M.method"]["args"] == ["self", "value"]

    imports = result["imports"]
    assert any(imp["name"] == "helpers.path" and imp["alias"] == "helper" for imp in imports)

    calls_by_full_name = {call["full_name"]: call for call in result["function_calls"]}
    assert calls_by_full_name["helper.join"]["name"] == "join"
    assert calls_by_full_name["local_named"]["context"][0] == "named"
    assert calls_by_full_name["self.named"]["name"] == "named"

    variables = {var["name"] for var in result["variables"]}
    assert {"M", "helper", "x"}.issubset(variables)


def test_pre_scan_lua_indexes_simple_and_qualified_names(temp_test_dir):
    code = """
local function helper()
end

function M.run()
  helper()
end
"""
    f = temp_test_dir / "scanner.lua"
    f.write_text(code)

    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "lua"
    wrapper.language = manager.get_language_safe("lua")
    wrapper.parser = manager.create_parser("lua")

    imports_map = pre_scan_lua([f], wrapper)

    assert "helper" in imports_map
    assert "run" in imports_map
    assert "M.run" in imports_map
