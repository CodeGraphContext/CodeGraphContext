from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.elixir import ElixirTreeSitterParser, pre_scan_elixir
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


@pytest.fixture(scope="module")
def elixir_parser():
    manager = get_tree_sitter_manager()
    if not manager.is_language_available("elixir"):
        pytest.skip("Elixir tree-sitter grammar is not available in this environment")

    wrapper = MagicMock()
    wrapper.language_name = "elixir"
    wrapper.language = manager.get_language_safe("elixir")
    wrapper.parser = manager.create_parser("elixir")
    return ElixirTreeSitterParser(wrapper)


def test_parse_elixir_modules(elixir_parser, temp_test_dir):
    code = """
defmodule MyApp.Worker do
  use GenServer

  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts)
  end
end

defprotocol MyApp.Serializable do
  def serialize(data)
end
"""
    f = temp_test_dir / "sample.ex"
    f.write_text(code)

    result = elixir_parser.parse(f)

    modules = result.get("modules", [])
    assert len(modules) == 2
    assert any(m["name"] == "MyApp.Worker" and m["type"] == "defmodule" for m in modules)
    assert any(m["name"] == "MyApp.Serializable" and m["type"] == "defprotocol" for m in modules)


def test_parse_elixir_functions(elixir_parser, temp_test_dir):
    code = """
defmodule MyApp.Server do
  def handle_call(:get, _from, state) do
    {:reply, state, state}
  end

  defp do_work(state) do
    process(state)
  end

  defmacro my_macro(expr) do
    quote do
      unquote(expr)
    end
  end
end
"""
    f = temp_test_dir / "funcs.ex"
    f.write_text(code)

    result = elixir_parser.parse(f)

    functions = result["functions"]
    assert len(functions) == 3

    handle_call = next(fn for fn in functions if fn["name"] == "handle_call")
    assert handle_call["visibility"] == "public"
    assert handle_call["type"] == "def"

    do_work = next(fn for fn in functions if fn["name"] == "do_work")
    assert do_work["visibility"] == "private"
    assert do_work["type"] == "defp"

    my_macro = next(fn for fn in functions if fn["name"] == "my_macro")
    assert my_macro["visibility"] == "public"
    assert my_macro["type"] == "defmacro"


def test_parse_elixir_imports(elixir_parser, temp_test_dir):
    code = """
defmodule MyApp.Worker do
  use GenServer
  alias MyApp.Repo
  import Ecto.Query
  require Logger
end
"""
    f = temp_test_dir / "imports.ex"
    f.write_text(code)

    result = elixir_parser.parse(f)

    imports = result["imports"]
    assert len(imports) == 4

    assert any(i["name"] == "GenServer" and i["import_type"] == "use" for i in imports)
    assert any(i["name"] == "MyApp.Repo" and i["import_type"] == "alias" for i in imports)
    assert any(i["name"] == "Ecto.Query" and i["import_type"] == "import" for i in imports)
    assert any(i["name"] == "Logger" and i["import_type"] == "require" for i in imports)

    # Alias should have short name as alias
    alias_import = next(i for i in imports if i["import_type"] == "alias")
    assert alias_import["alias"] == "Repo"


def test_parse_elixir_calls(elixir_parser, temp_test_dir):
    code = """
defmodule MyApp.Worker do
  def start_link(opts) do
    GenServer.start_link(__MODULE__, opts)
    Logger.info("starting")
  end
end
"""
    f = temp_test_dir / "calls.ex"
    f.write_text(code)

    result = elixir_parser.parse(f)

    calls = result["function_calls"]
    dot_calls = [c for c in calls if "." in c["full_name"]]
    assert any(c["full_name"] == "GenServer.start_link" for c in dot_calls)
    assert any(c["full_name"] == "Logger.info" for c in dot_calls)


def test_parse_elixir_no_classes(elixir_parser, temp_test_dir):
    code = """
defmodule MyApp do
  def hello, do: :world
end
"""
    f = temp_test_dir / "no_classes.ex"
    f.write_text(code)

    result = elixir_parser.parse(f)
    assert result["classes"] == []


def test_pre_scan_elixir(temp_test_dir):
    code = """
defmodule MyApp.Scanner do
  def scan(input) do
    process(input)
  end

  defp process(data) do
    data
  end
end
"""
    f = temp_test_dir / "scanner.ex"
    f.write_text(code)

    manager = get_tree_sitter_manager()
    wrapper = MagicMock()
    wrapper.language_name = "elixir"
    wrapper.language = manager.get_language_safe("elixir")
    wrapper.parser = manager.create_parser("elixir")

    imports_map = pre_scan_elixir([f], wrapper)

    assert "MyApp.Scanner" in imports_map
    assert "scan" in imports_map
    assert "process" in imports_map
