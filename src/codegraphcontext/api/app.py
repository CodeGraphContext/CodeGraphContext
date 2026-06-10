# src/codegraphcontext/api/app.py
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from .router import router
from .mcp_sse import handle_sse, handle_messages

def create_app() -> FastAPI:
    app = FastAPI(
        title="CodeGraphContext Gateway",
        description="HTTP API gateway for CodeGraphContext MCP server. Enables integration with ChatGPT Actions, Claude, and web frontends.",
        version="0.1.0"
    )

    # Enable CORS for the website/frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # In production, restrict this
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        """Liveness probe for load balancers and k8s."""
        return {"status": "ok"}

    # MCP-over-SSE Endpoints
    app.add_api_route("/api/v1/mcp/sse", handle_sse, methods=["GET"])
    app.add_api_route("/api/v1/mcp/messages", handle_messages, methods=["POST"])

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return """
        <!DOCTYPE html>
        <html>
            <head>
                <title>CGC Gateway</title>
                <style>
                    body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #0f172a; color: white; margin: 0; }
                    .card { background: #1e293b; padding: 2rem; border-radius: 1rem; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); text-align: center; max-width: 400px; border: 1px solid #334155; }
                    h1 { color: #38bdf8; margin-top: 0; }
                    p { color: #94a3b8; line-height: 1.6; }
                    .btn { display: inline-block; background: #38bdf8; color: #0f172a; padding: 0.75rem 1.5rem; border-radius: 0.5rem; text-decoration: none; font-weight: bold; margin-top: 1rem; transition: background 0.2s; }
                    .btn:hover { background: #7dd3fc; }
                    .links { margin-top: 1.5rem; font-size: 0.9rem; }
                    .links a { color: #38bdf8; text-decoration: none; margin: 0 0.5rem; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>CGC Gateway</h1>
                    <p>CodeGraphContext HTTP API is running. This gateway allows ChatGPT and Claude to interact with your code graph.</p>
                    <a href="/docs" class="btn">View API Docs</a>
                    <div class="links">
                        <a href="/openapi.json">OpenAPI Spec</a>
                        <a href="https://github.com/Shashankss1205/CodeGraphContext" target="_blank">GitHub</a>
                    </div>
                </div>
            </body>
        </html>
        """

    return app

app = create_app()
