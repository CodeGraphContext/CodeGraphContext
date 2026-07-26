# Integrating CodeGraphContext with ChatGPT and Claude

The new **CGC Gateway** (HTTP API) allows you to use CodeGraphContext as a set of tools for ChatGPT and Claude. This is superior to a CLI tool because it follows standard web protocols that these models already support.

## 1. Start the API Gateway

Run the following command in your terminal:

```bash
cgc api start --port 8000
```

This starts a FastAPI server at `http://localhost:8000`. You can verify it's running by visiting `http://localhost:8000/docs` in your browser.

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
    - **MCP Server URL**: `https://your-id.ngrok-free.app/api/v1/mcp/sse`
    - **Authentication**: No Auth
    - Click **Create**.

> [!TIP]
> If you get a **405 Method Not Allowed** error, ensure you are using the full path `/api/v1/mcp/sse` in the URL field.

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
