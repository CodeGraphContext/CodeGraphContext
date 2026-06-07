# Agent Graph Local Usage

## Install

```powershell
cd C:\Users\jrchi\Documents\Codex\2026-06-06\files-mentioned-by-the-user-pasted\CodeGraphContext
python -m pip install -e .
```

If installation fails on Windows while building `kuzu`, use this local agent-graph fallback:

```powershell
python -m pip install -e . --no-deps
python -m pip install fastapi inquirerpy mcp nbconvert stdlibs watchdog python-dotenv tree-sitter tree-sitter-c-sharp "tree-sitter-language-pack<1.0.0,>=0.6.0" nbformat pathspec "redis<6,>=5" "falkordb<1.6,>=1.0" "protobuf==3.20.3" ladybug neo4j uvicorn
```

## Verify CLI

```powershell
cgc --help
cgc agent-graph --help
```

## Run from Any Project

```powershell
cd <target-project-root>
cgc agent-graph build
```

Expected artifacts:

- `.agent/graph/code_graph.json`
- `.agent/graph/code_graph.md`
- `.agent/graph/code_graph.mmd`
- `.agent/graph/code_graph.dot`
- `.agent/context_index.md`
- `.agent/README.md`
- `.agent/work_notes/README.md`

## Quick Validation

```powershell
python -m json.tool .agent\graph\code_graph.json
Get-Content .agent\graph\code_graph.mmd -TotalCount 1
```

Expected Mermaid header:

```text
flowchart TD
```
