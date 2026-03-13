import pytest
from unittest.mock import MagicMock

from codegraphcontext.tools.languages.vue import VueTreeSitterParser, pre_scan_vue
from codegraphcontext.tools.languages.svelte import SvelteTreeSitterParser, pre_scan_svelte


@pytest.fixture
def vue_parser():
    wrapper = MagicMock()
    wrapper.language_name = "vue"
    return VueTreeSitterParser(wrapper)


@pytest.fixture
def svelte_parser():
    wrapper = MagicMock()
    wrapper.language_name = "svelte"
    return SvelteTreeSitterParser(wrapper)


def test_vue_parser_extracts_typescript_block(vue_parser, temp_test_dir):
    source = """<template><div>{{ msg }}</div></template>
<script lang=\"ts\">
import { greet } from './helpers'
function hello(name: string) {
  return greet(name)
}
</script>
"""
    vue_file = temp_test_dir / "App.vue"
    vue_file.write_text(source)

    result = vue_parser.parse(vue_file)

    functions = {fn["name"]: fn for fn in result["functions"]}
    assert "hello" in functions
    # Ensure line numbers point to the original .vue file, not the extracted script snippet.
    assert functions["hello"]["line_number"] == 4
    assert any(imp.get("source") == "./helpers" for imp in result["imports"])
    assert result["lang"] == "vue"


def test_svelte_parser_extracts_javascript_block(svelte_parser, temp_test_dir):
    source = """<script>
  import { onMount } from 'svelte'
  function hello() {
    console.log('world')
  }
</script>

<h1>Hello</h1>
"""
    svelte_file = temp_test_dir / "Component.svelte"
    svelte_file.write_text(source)

    result = svelte_parser.parse(svelte_file)

    functions = {fn["name"]: fn for fn in result["functions"]}
    assert "hello" in functions
    assert functions["hello"]["line_number"] == 3
    assert any(imp.get("source") == "svelte" for imp in result["imports"])
    assert result["lang"] == "svelte"


def test_sfc_pre_scan_collects_symbols(temp_test_dir):
    vue_file = temp_test_dir / "Widget.vue"
    vue_file.write_text(
        """<script lang=\"ts\">\nclass Widget {}\nfunction makeWidget() {}\n</script>\n"""
    )

    svelte_file = temp_test_dir / "Widget.svelte"
    svelte_file.write_text(
        """<script>\nfunction makeGreeting() {}\n</script>\n"""
    )

    wrapper = MagicMock()
    wrapper.language_name = "vue"

    vue_map = pre_scan_vue([vue_file], wrapper)
    svelte_map = pre_scan_svelte([svelte_file], wrapper)

    assert "Widget" in vue_map
    assert str(vue_file.resolve()) in vue_map["Widget"]
    assert "makeWidget" in vue_map
    assert str(vue_file.resolve()) in vue_map["makeWidget"]

    assert "makeGreeting" in svelte_map
    assert str(svelte_file.resolve()) in svelte_map["makeGreeting"]
