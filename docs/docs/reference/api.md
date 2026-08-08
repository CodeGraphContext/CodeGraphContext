# HTTP API Reference

CodeGraphContext ships a **CGC Gateway** HTTP server for ChatGPT Actions, Claude connectors, and custom web frontends. It wraps the same MCP tool surface exposed by `cgc mcp start`.

---

## Starting the Server

```bash
cgc api start
cgc api start --host 127.0.0.1 --port 8080
cgc api start --reload   # development only
```

The server loads credentials from the same configuration chain as the CLI (`~/.codegraphcontext/.env`, context resolution, etc.).

---

## Endpoints

### Health & Status

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Liveness probe. Returns `{"status": "ok"}`. Suitable for load balancers and Kubernetes. |
| `GET` | `/` | Simple HTML landing page with links to OpenAPI docs. |
| `GET` | `/api/v1/status` | Database connectivity and active backend name. |

### MCP-over-SSE

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/mcp/sse` | Server-Sent Events stream for MCP clients. |
| `POST` | `/api/v1/mcp/messages` | MCP message ingress for SSE transport. |

### REST Tool Bridge

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/tools` | Lists registered MCP tools and schemas. |
| `POST` | `/api/v1/tools/call` | Invokes a tool by name with JSON arguments. |
| `POST` | `/api/v1/index` | Triggers repository indexing (background job). |
| `POST` | `/api/v1/query` | Executes a read-only Cypher query. |
| `GET` | `/api/v1/repositories` | Lists indexed repositories in the active context. |

Interactive OpenAPI documentation is available at `/docs` while the server is running.

---

## Example: Health Check

```bash
curl -s http://localhost:8000/health
# {"status":"ok"}
```

```bash
curl -s http://localhost:8000/api/v1/status
```

---

## Relationship to MCP

| Interface | Transport | Typical use |
| :--- | :--- | :--- |
| `cgc mcp start` | stdio | Cursor, Claude Desktop, VS Code |
| `cgc api start` | HTTP / SSE | Web apps, ChatGPT Actions, remote agents |

Both paths share the same graph database and tool implementations.
