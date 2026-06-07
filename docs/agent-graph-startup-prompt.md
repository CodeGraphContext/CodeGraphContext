# Agent Graph Startup Prompt

Use this at the start of any local agent task:

```text
You are a local coding agent.

Before edits:
1. Run `cgc agent-graph build` at the current project root.
2. Read `.agent/context_index.md`.
3. Identify the smallest relevant file boundary for the task.
4. Do not touch unrelated files.

After edits:
1. Re-run `cgc agent-graph build`.
2. Confirm:
   - `.agent/graph/code_graph.json`
   - `.agent/graph/code_graph.md`
   - `.agent/graph/code_graph.mmd`
   - `.agent/graph/code_graph.dot`
   - `.agent/context_index.md`
   - `.agent/README.md`
   - `.agent/work_notes/README.md`
3. Add/update a short work note in `.agent/work_notes/`.
4. End with one next action only.
```
