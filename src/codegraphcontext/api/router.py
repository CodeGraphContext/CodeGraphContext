# src/codegraphcontext/api/router.py
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, List
from pathlib import Path

from .schemas import (
    IndexRequest, 
    QueryRequest, 
    SearchRequest, 
    ToolCallRequest, 
    ApiResponse
)
from codegraphcontext.server import MCPServer

import socket

router = APIRouter()

# Global server instance (initialized on startup)
_server_instance: MCPServer = None

def get_server() -> MCPServer:
    global _server_instance
    if _server_instance is None:
        # Note: In a real production app, we'd handle initialization better
        _server_instance = MCPServer(cwd=Path.cwd())
    return _server_instance

def raise_service_unavailable(exc: Exception):
    raise HTTPException(
        status_code=503,
        detail="Database service unavailable",
    ) from exc

@router.get("/status", response_model=ApiResponse)
async def get_status(server: MCPServer = Depends(get_server)):
    try:
        status = server.db_manager.is_connected()
    except (OSError, socket.error) as exc:
        raise_service_unavailable(exc)

    return ApiResponse(
        status="ok",
        message="Connected" if status else "Disconnected",
        data={"database": server.resolved_context.database}
    )

@router.get("/tools", response_model=ApiResponse)
async def list_tools(server: MCPServer = Depends(get_server)):
    return ApiResponse(
        status="ok",
        data={"tools": list(server.tools.values())}
    )

@router.post("/tools/call", response_model=ApiResponse)
async def call_tool(
    request: ToolCallRequest,
    server: MCPServer = Depends(get_server)
):
    try:
        result = await server.handle_tool_call(
            request.name,
            request.arguments
        )

        if "error" in result:
            return ApiResponse(
                status="error",
                error=result["error"]
            )

        return ApiResponse(
            status="ok",
            data=result
        )

    except (OSError, socket.error) as exc:
        raise_service_unavailable(exc)

    except Exception as e:
        return ApiResponse(
            status="error",
            error=str(e)
        )
    

@router.post("/index", response_model=ApiResponse)
async def index_repository(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
    server: MCPServer = Depends(get_server)
):
    # The add_code_to_graph handler only understands "path" (and is_dependency);
    # repo_name/branch/force from the request model are not supported by it.
    args = {"path": request.path}

    try:
        result = await server.handle_tool_call(
            "add_code_to_graph",
            args
        )
    except (OSError, socket.error) as exc:
        raise_service_unavailable(exc)

    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )

    return ApiResponse(
        status="ok",
        message="Indexing job started",
        data=result
    )

@router.post("/query", response_model=ApiResponse)
async def execute_query(
    request: QueryRequest,
    server: MCPServer = Depends(get_server)
):
    try:
        result = await server.handle_tool_call(
            "execute_cypher_query",
            {
                "cypher_query": request.query,
                "params": request.params,
            },
        )
    except (OSError, socket.error) as exc:
        raise_service_unavailable(exc)

    if "error" in result:
        return ApiResponse(status="error", error=result["error"])

    return ApiResponse(status="ok", data=result)

@router.get("/repositories", response_model=ApiResponse)
async def list_repositories(
    server: MCPServer = Depends(get_server)
):
    try:
        result = await server.handle_tool_call(
            "list_indexed_repositories",
            {}
        )
    except (OSError, socket.error) as exc:
        raise_service_unavailable(exc)

    return ApiResponse(
        status="ok",
        data=result
    )
