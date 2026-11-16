# MCP tools reference

The current catalog is generated from `src/codegraphcontext/tool_definitions.py`
during every documentation build. It includes every registered tool, required
argument, type, default, enum and nested schema for the source package version.

- [MCP workflows and result interpretation](docs/reference/mcp.md)
- [Online generated input schemas](https://codegraphcontext.github.io/reference/mcp-catalog/)
- [Runtime source registry](../src/codegraphcontext/tool_definitions.py)

For the installed server, call MCP `tools/list`. Disabled tools and older
installed packages can differ from the current source documentation. To build
locally, install `mkdocs` and `mkdocs-material`, then run `mkdocs build --clean`
from `docs/`. The pre-build hook regenerates the schema catalog automatically.
