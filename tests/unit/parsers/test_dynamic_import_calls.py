"""Runtime import() calls must reach the JS/TS call resolver (#1863)."""

import pytest

from codegraphcontext.tools.tree_sitter_parser import TreeSitterParser


@pytest.mark.parametrize(
    "language,suffix", [("javascript", ".js"), ("typescript", ".ts"), ("tsx", ".tsx")]
)
def test_dynamic_import_call_metadata_and_ownership(tmp_path, language, suffix):
    source = """import './static.js';
export function load() { return import('./lazy.js'); }
export const arrow = () => typeof import('./arrow.js', {with: {type: 'json'}});
export class Loader { method() { return import('./method.js'); } }
export function chunk() { return import(/* webpackChunkName: 'chunk' */ './chunk.js'); }
"""
    path = tmp_path / ("loader" + suffix)
    path.write_text(source, encoding="utf-8")
    result = TreeSitterParser(language).parse(path)
    assert not result.get("error"), result
    calls = [
        call
        for call in result["function_calls"]
        if call.get("call_kind") == "dynamic_import"
    ]
    calls.sort(key=lambda call: call["line_number"])
    assert len(calls) == 4
    for call, (name, argument, line) in zip(
        calls,
        [
            ("load", "'./lazy.js'", 2),
            ("arrow", "'./arrow.js'", 3),
            ("method", "'./method.js'", 4),
            ("chunk", "'./chunk.js'", 5),
        ],
    ):
        assert call["name"] == "import"
        assert call["args"] == [argument]
        assert call["line_number"] == line
        assert call["context"][0] == name
        assert call["context"][2] == line
        assert call["lang"] == (
            "javascript" if language == "javascript" else "typescript"
        )
        assert call["full_name"].startswith("import(")
    assert calls[2]["class_context"][0] == "Loader"


@pytest.mark.parametrize(
    "language,suffix", [("javascript", ".js"), ("typescript", ".ts"), ("tsx", ".tsx")]
)
def test_computed_imports_keep_their_own_argument_and_methods_are_not_imports(
    tmp_path, language, suffix
):
    path = tmp_path / ("computed" + suffix)
    path.write_text(
        """function load(name) {
    import(name);
    import(`./${name}.js`);
    object.import('./ordinary.js');
    require('./required.js');
}
""",
        encoding="utf-8",
    )
    calls = TreeSitterParser(language).parse(path)["function_calls"]
    dynamic = [call for call in calls if call.get("call_kind") == "dynamic_import"]
    dynamic.sort(key=lambda call: call["line_number"])
    assert [call["args"] for call in dynamic] == [["name"], ["`./${name}.js`"]]
    assert any(
        call["name"] == "require" and call.get("call_kind") != "dynamic_import"
        for call in calls
    )


@pytest.mark.parametrize("language,suffix", [("typescript", ".ts"), ("tsx", ".tsx")])
def test_type_imports_are_not_runtime_calls_but_cast_values_are(
    tmp_path, language, suffix
):
    path = tmp_path / ("typed" + suffix)
    path.write_text(
        """type A = typeof import('./types');
type B = import('./types').Thing;
interface I { value: import('./types').Thing; }
declare const typed: typeof import('./types');
function generic<T extends import('./types').Thing>() {}
function load() {
    const value: typeof import('./types') = import('./runtime');
    const cast = import('./cast') as import('./types').Thing;
    return import('./checked') satisfies import('./types').Thing;
}
""",
        encoding="utf-8",
    )
    result = TreeSitterParser(language).parse(path)
    assert not result.get("error"), result
    dynamic = [
        call
        for call in result["function_calls"]
        if call.get("call_kind") == "dynamic_import"
    ]
    dynamic.sort(key=lambda call: call["line_number"])
    assert [call["args"] for call in dynamic] == [
        ["'./runtime'"],
        ["'./cast'"],
        ["'./checked'"],
    ]
    assert all(call["context"][0] == "load" for call in dynamic)


@pytest.mark.parametrize("language", ["vue", "svelte"])
@pytest.mark.parametrize("script_lang", ["js", "ts"])
def test_sfc_script_delegation_preserves_dynamic_import_locations(
    tmp_path, language, script_lang
):
    path = tmp_path / ("Component." + language)
    path.write_text(
        f"""<script lang="{script_lang}">
export function load() {{ return import('./lazy.js'); }}
</script>
""",
        encoding="utf-8",
    )
    result = TreeSitterParser(language).parse(path)
    calls = [
        call
        for call in result["function_calls"]
        if call.get("call_kind") == "dynamic_import"
    ]
    assert len(calls) == 1
    assert calls[0]["args"] == ["'./lazy.js'"]
    assert calls[0]["context"] == ("load", "function_declaration", 2)
    assert calls[0]["line_number"] == 2
