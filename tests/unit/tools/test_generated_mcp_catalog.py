from pathlib import Path
import runpy

from codegraphcontext.tool_definitions import TOOLS


def test_documentation_build_emits_every_current_tool_and_full_schema(tmp_path):
    root = Path(__file__).resolve().parents[3]
    hook = runpy.run_path(str(root / "docs/hooks/mcp_catalog.py"))
    output = hook["generate"](tmp_path)
    text = output.read_text()
    assert {line.removeprefix("## ") for line in text.splitlines() if line.startswith("## ")} == set(TOOLS)
    for tool in TOOLS.values():
        for prop in tool["inputSchema"].get("properties", {}):
            assert f'"{prop}"' in text
    assert "nested mutation" in text
    assert "0.4.16" not in text


def test_schema_generator_preserves_nested_constraints_and_markdown_cells():
    root = Path(__file__).resolve().parents[3]
    render = runpy.run_path(str(root / "docs/hooks/mcp_catalog.py"))["render_catalog"]
    schema = {"type": "object", "required": ["value"], "properties": {"value": {"type": "string", "enum": ["a", "b"], "description": "a | b"}}}
    text = render({"example": {"description": "example tool", "inputSchema": schema}}, "test")
    assert "| value | yes | string |" in text
    assert "a \\| b" in text
    assert '"enum": [' in text and '"required": [' in text
