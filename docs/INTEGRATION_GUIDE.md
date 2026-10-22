# Integrating CodeGraphContext with ChatGPT and Claude

The new **CGC Gateway** (HTTP API) allows you to use CodeGraphContext as a set of tools for ChatGPT and Claude. This is superior to a CLI tool because it follows standard web protocols that these models already support.

## 1. Start the API Gateway

Run the following command in your terminal:

```bash
cgc api start --port 8000
```

This starts a FastAPI server at `http://localhost:8000`. You can verify it's running by visiting `http://localhost:8000/docs` in your browser.

### Local CLI reads while the gateway owns an embedded database

On macOS and Linux, `cgc list`, `cgc stats`, and `cgc stats <repository-path>`
automatically use a matching local gateway started with `cgc api start`. This
allows reads while that gateway owns a LadybugDB or KùzuDB database. The CLI
prints `Reading through local CGC Gateway...` and retains the ordinary tables,
overall extended-type counts, scoped DISTINCT counts, and empty/missing-repository
messages. Repository paths and `--context` still select the intended context.

Discovery uses the gateway's actual configured port, including non-default ports.
It is published only after the shared REST/MCP server successfully opens its
database, not by `/health` alone. The backend, canonical database path, and
resolved global/per-repo/named context must all match; an implicit fallback to a
different backend is not guessed. Runtime database/path overrides must match too.

If `CGC_API_KEY` is configured, use the same key configuration in the gateway and
CLI. Internal read requests prove possession of the key without transmitting the
key itself. Ordinary REST/MCP authentication remains unchanged. A verified live
gateway's authentication failure, database-read failure, or concurrent context
change produces a CLI error; it does not silently bypass that gateway. Retry a
context-change error after selecting the intended context.

Missing, malformed, unsafe, stale, or unreachable discovery falls back to the
normal direct CLI path. Discovery uses owner-only POSIX state under
`~/.codegraphcontext/gateways/`, a per-instance key, signed requests/responses,
and a fresh request nonce. A live PID by itself is not trusted. The CLI connects
only to `127.0.0.1` or `::1`, uses no HTTP proxy/netrc credentials or redirects,
and bounds connection establishment to 0.3 seconds and the whole HTTP exchange
to five seconds. The response is limited to 4 MiB.

Context switches take the same lock as delegated read collection. The old
identity is withdrawn before database teardown, and a new generation is
published only after successful initialization. Failed switches leave no usable
old record. Shutdown removes only the current instance's record; a crashed
gateway's leftover record can be rejected without opening its database first.

Automatic discovery currently requires a regular `cgc api start` process, a
fixed nonzero port, and a loopback or wildcard bind. Wildcard binds map to the
matching loopback address. Windows, `--reload`, direct `uvicorn` launches,
non-loopback-specific binds, and other database backends keep their existing
direct CLI behavior. Mutation commands such as `update`, `index`, and `delete`
also keep the existing single-owner policy: use the running server's interface
or stop it before opening the embedded database from another process.

## 2. Integration with ChatGPT

There are two ways to use CodeGraphContext with ChatGPT:

### Option A: Native MCP Server (Recommended)
ChatGPT now supports the **Model Context Protocol (MCP)** natively. This allows the AI to discover all tools automatically without you needing to provide an OpenAPI schema.

1.  **Expose your local server**:
    ```bash
    ngrok http 8000
    ```
    Copy the `https` URL (e.g., `https://random-id.ngrok-free.app`).

2.  **Add MCP Server in ChatGPT**:
    - Go to **Settings** -> **Connected accounts** -> **Connectors** (or "MCP Servers").
    - Click **Add MCP Server**.
    - **Name**: CodeGraphContext
    - **MCP Server URL**: `https://your-id.ngrok-free.app/api/v1/mcp`
    - **Authentication**: No Auth
    - Click **Create**.

> [!TIP]
> If you get a **405 Method Not Allowed** error, ensure you are using the full path `/api/v1/mcp` in the URL field.
>
> The older `/api/v1/mcp/sse` URL (HTTP+SSE transport) still works for existing
> configurations but is deprecated; new setups should use `/api/v1/mcp`
> (Streamable HTTP).

### Option B: Custom GPT Actions (Legacy/Alternative)
If you prefer to create a custom GPT with a specific focus:

1.  **Create a GPT Action**:
    - Go to GPT settings -> **Actions** -> **Create new action**.
    - For **Schema**, use the spec from `https://your-id.ngrok-free.app/openapi.json`.

## 3. Integration with Claude (API)

If you are building an application using the Claude API, you can now call CGC tools via standard HTTP requests.

Example (Python):
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/tools/call",
    json={
        "name": "find_code",
        "arguments": {"query": "class MyClass"}
    }
)
print(response.json())
```

## 4. Why this is better than a CLI tool

- **Persistence**: The server keeps the database connection open and ready.
- **Standards-Compliant**: Uses OpenAPI (Swagger), which is the "native language" of AI tool-calling.
- **Flexible**: Can be used by the `website` frontend, ChatGPT, Claude, or custom scripts.
