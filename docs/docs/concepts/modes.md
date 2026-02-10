# CLI Mode vs. MCP Mode

CodeGraphContext has a "dual personality".

## 🛠️ Mode 1: The CLI Tool
**"I want to ask questions."**

In this mode, YOU are the intelligent agent. You use terminal commands (`cgc analyze`) to explore the codebase.
*   **Best for:** Architecture reviews, refactoring planning, exploring new codebases.
*   **Interface:** Terminal.

## 🤖 Mode 2: The MCP Server
**"I want my AI to know the answers."**

In this mode, the AI (Cursor/Claude) is the agent. It asks the questions.
*   **Best for:** Coding assistance, "Chat with Codebase", debugging help.
*   **Interface:** Natural Language Chat in your IDE.

---

**Crucially: They share the same database.**
You can `cgc index` a repo in your terminal, and then immediately ask your AI about it.
