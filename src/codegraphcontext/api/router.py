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

router = APIRouter()

# Global server instance (initialized on startup)
_server_instance: MCPServer = None

def get_server() -> MCPServer:
    global _server_instance
    if _server_instance is None:
        # Note: In a real production app, we'd handle initialization better
        _server_instance = MCPServer(cwd=Path.cwd())
    return _server_instance

@router.get("/status", response_model=ApiResponse)
async def get_status(server: MCPServer = Depends(get_server)):
    status = server.db_manager.is_connected()
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
        result = await server.handle_tool_call(request.name, request.arguments)
        if "error" in result:
            return ApiResponse(status="error", error=result["error"])
        return ApiResponse(status="ok", data=result)
    except Exception as e:
        return ApiResponse(status="error", error=str(e))

@router.post("/index", response_model=ApiResponse)
async def index_repository(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
    server: MCPServer = Depends(get_server)
):
    # Map to add_code_to_graph tool
    args = {
        "path": request.path,
        "repo_name": request.repo_name,
        "branch": request.branch,
        "force": request.force
    }
    
    # We call handle_tool_call which is async
    # But add_code_to_graph starts a background job anyway
    result = await server.handle_tool_call("add_code_to_graph", args)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
        
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
    result = await server.handle_tool_call("execute_cypher_query", {
        "query": request.query,
        "params": request.params
    })
    
    if "error" in result:
        return ApiResponse(status="error", error=result["error"])
        
    return ApiResponse(status="ok", data=result)

@router.get("/repositories", response_model=ApiResponse)
async def list_repositories(server: MCPServer = Depends(get_server)):
    result = await server.handle_tool_call("list_indexed_repositories", {})
    return ApiResponse(status="ok", data=result)
