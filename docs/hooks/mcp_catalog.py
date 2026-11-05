"""Generate MCP schema documentation at build time from the actual registry."""
import json
from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[2]


def render_catalog(tools, version):
    lines = ["# Generated MCP tool catalog", "", f"Source package version: **{version}**. Registered tools: **{len(tools)}**.", "",
        "Generated during each documentation build from `tool_definitions.py`. "
        "The connected server's `tools/list` is authoritative for its installed version and disabled-tool configuration.", "",
        "See [workflows and limitations](mcp.md) before interpreting results. Schemas describe inputs; they do not certify backend feature parity.", ""]
    for name, tool in tools.items():
        schema = tool["inputSchema"]
        lines.extend([f"## {name}", "", tool["description"], "", "| Argument | Required | Type | Default | Description |", "| --- | --- | --- | --- | --- |"])
        for key, prop in schema.get("properties", {}).items():
            default = json.dumps(prop["default"], ensure_ascii=False) if "default" in prop else "-"
            values = [key, "yes" if key in schema.get("required", []) else "no", prop.get("type", "any"), default, prop.get("description", "")]
            lines.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in values) + " |")
        lines.extend(["", "### Complete input schema", "", "Enums, nested mutation steps and other constraints are included below.", "", "```json", json.dumps(schema, indent=2, ensure_ascii=False), "```", ""])
    return "\n".join(lines)


def generate(docs_dir):
    tools = runpy.run_path(str(ROOT / "src/codegraphcontext/tool_definitions.py"))["TOOLS"]
    version = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.MULTILINE).group(1)
    output = Path(docs_dir) / "reference/mcp-catalog.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_catalog(tools, version), encoding="utf-8")
    return output


def on_pre_build(config, **kwargs):
    generate(config["docs_dir"])


if __name__ == "__main__":
    print(generate(ROOT / "docs/docs"))
