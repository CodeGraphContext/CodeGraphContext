"""Tests for Vue and Svelte single-file component (SFC) parsers.

Vue and Svelte files mix template markup, scoped styles, and a script block.
The SFC parsers split out the `<script>` block and reuse the existing
JavaScript/TypeScript parsers to extract symbols, while remapping line numbers
back to their position in the original SFC file.
"""

from unittest.mock import MagicMock

import pytest

from codegraphcontext.tools.languages.svelte import SvelteTreeSitterParser, pre_scan_svelte
from codegraphcontext.tools.languages.vue import VueTreeSitterParser, pre_scan_vue
from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser
from codegraphcontext.utils.tree_sitter_manager import get_tree_sitter_manager


def _make_wrapper(language_name):
    manager = get_tree_sitter_manager()
    if not manager.is_language_available(language_name):
        pytest.skip(f"{language_name} tree-sitter grammar is not available in this environment")
    wrapper = MagicMock()
    wrapper.language_name = language_name
    wrapper.language = manager.get_language_safe(language_name)
    wrapper.parser = manager.create_parser(language_name)
    return wrapper


@pytest.fixture(scope="module")
def svelte_parser():
    return SvelteTreeSitterParser(_make_wrapper("svelte"))


@pytest.fixture(scope="module")
def vue_parser():
    return VueTreeSitterParser(_make_wrapper("vue"))


# --- registry / dispatch -------------------------------------------------

def test_tree_sitter_dispatches_svelte_parser():
    parser = TreeSitterParser("svelte")
    assert isinstance(parser.language_specific_parser, SvelteTreeSitterParser)


def test_tree_sitter_dispatches_vue_parser():
    parser = TreeSitterParser("vue")
    assert isinstance(parser.language_specific_parser, VueTreeSitterParser)


# --- Svelte --------------------------------------------------------------

def test_parse_svelte_script_symbols(svelte_parser, temp_test_dir):
    code = """<script>
  import { onMount } from 'svelte';

  let count = 0;

  function increment() {
    count += 1;
  }
</script>

<button on:click={increment}>
  Clicked {count} times
</button>

<style>
  button { color: red; }
</style>
"""
    f = temp_test_dir / "Counter.svelte"
    f.write_text(code)

    result = svelte_parser.parse(f)

    assert result["lang"] == "svelte"

    function_names = {fn["name"] for fn in result["functions"]}
    assert "increment" in function_names

    import_names = {imp["name"] for imp in result["imports"]}
    assert "svelte" in import_names

    # Line numbers should map back to the original SFC, not a 1-based script slice.
    increment = next(fn for fn in result["functions"] if fn["name"] == "increment")
    assert increment["line_number"] == 6


# --- Vue -----------------------------------------------------------------

def test_parse_vue_script_symbols(vue_parser, temp_test_dir):
    code = """<template>
  <button @click="increment">{{ count }}</button>
</template>

<script>
import { ref } from 'vue';

export default {
  setup() {
    const count = ref(0);
    function increment() {
      count.value += 1;
    }
    return { count, increment };
  },
};
</script>

<style scoped>
button { color: blue; }
</style>
"""
    f = temp_test_dir / "Counter.vue"
    f.write_text(code)

    result = vue_parser.parse(f)

    assert result["lang"] == "vue"

    function_names = {fn["name"] for fn in result["functions"]}
    assert "increment" in function_names or "setup" in function_names

    import_names = {imp["name"] for imp in result["imports"]}
    assert "vue" in import_names

    # The <script> block starts on line 5, so symbols inside it must be offset.
    setup = next((fn for fn in result["functions"] if fn["name"] == "setup"), None)
    if setup is not None:
        assert setup["line_number"] >= 9


def test_parse_vue_typescript_script(vue_parser, temp_test_dir):
    code = """<template>
  <div>{{ title }}</div>
</template>

<script lang="ts">
import { defineComponent } from 'vue';

interface Props {
  name: string;
}

function buildTitle(name: string): string {
  return 'Hello ' + name;
}
</script>
"""
    f = temp_test_dir / "Titled.vue"
    f.write_text(code)

    result = vue_parser.parse(f)

    function_names = {fn["name"] for fn in result["functions"]}
    assert "buildTitle" in function_names

    # TypeScript-only buckets from the delegated parser must survive aggregation.
    interface_names = {iface["name"] for iface in result.get("interfaces", [])}
    assert "Props" in interface_names


# --- pre-scan ------------------------------------------------------------

def test_pre_scan_svelte_indexes_functions(temp_test_dir):
    code = """<script>
  function helper() {}
</script>

<p>hello</p>
"""
    f = temp_test_dir / "scanner.svelte"
    f.write_text(code)

    wrapper = _make_wrapper("svelte")
    imports_map = pre_scan_svelte([f], wrapper)
    assert "helper" in imports_map


def test_pre_scan_vue_indexes_functions(temp_test_dir):
    code = """<script>
function helper() {}
</script>

<template><p>hello</p></template>
"""
    f = temp_test_dir / "scanner.vue"
    f.write_text(code)

    wrapper = _make_wrapper("vue")
    imports_map = pre_scan_vue([f], wrapper)
    assert "helper" in imports_map
