# src/codegraphcontext/server.py
import urllib.parse
import asyncio
import json
import importlib
import stdlibs
import sys
import traceback
import os
import re
from datetime import datetime
from pathlib import Path
from dataclasses import asdict

from typing import Any, Dict, Coroutine, Optional, List

from .prompts import LLM_SYSTEM_PROMPT
from .core import get_database_manager
from .core.jobs import JobManager, JobStatus
from .core.watcher import CodeWatcher
from .tools.graph_builder import GraphBuilder
from .tools.code_finder import CodeFinder
from .tools.package_resolver import get_local_package_path
from .utils.debug_log import debug_log, info_logger, error_logger, warning_logger, debug_logger

# Import Tool Definitions and Handlers
from .tool_definitions import TOOLS
from .tools.handlers import (
    analysis_handlers,
    indexing_handlers,
    management_handlers,
    query_handlers,
    watcher_handlers
)

DEFAULT_EDIT_DISTANCE = 2
DEFAULT_FUZZY_SEARCH = False

class MCPServer:
    """
    The main MCP Server class.
    
    This class orchestrates all the major components of the application, including:
    - Database connection management (`DatabaseManager` or `FalkorDBManager`)
    - Background job tracking (`JobManager`)
    - File system watching for live updates (`CodeWatcher`)
    - Tool handlers for graph building, code searching, etc.
    - The main JSON-RPC communication loop for interacting with an AI assistant.
    """

    def __init__(self, loop=None):
        """
        Initializes the MCP server and its components. 
        
        Args:
            loop: The asyncio event loop to use. If not provided, it gets the current
                  running loop or creates a new one.
        """
        try:
            # Initialize the database manager (Neo4j or FalkorDB Lite based on env var)
            # to fail fast if credentials/configuration are wrong.
            self.db_manager = get_database_manager()
            self.db_manager.get_driver() 
        except ValueError as e:
            raise ValueError(f"Database configuration error: {e}")

        # Initialize managers for jobs and file watching.
        self.job_manager = JobManager()
        
        # Get the current event loop to pass to thread-sensitive components like the graph builder.
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        self.loop = loop

        # Initialize all the tool handlers, passing them the necessary managers and the event loop.
        self.graph_builder = GraphBuilder(self.db_manager, self.job_manager, loop)
        self.code_finder = CodeFinder(self.db_manager)
        self.code_watcher = CodeWatcher(self.graph_builder, self.job_manager)
        
        # Define the tool manifest that will be exposed to the AI assistant.
        self._init_tools()

    def _init_tools(self):
        """
        Defines the complete tool manifest for the LLM.
        """
        self.tools = TOOLS

    def get_database_status(self) -> dict:
        """Returns the current connection status of the Neo4j database."""
        return {"connected": self.db_manager.is_connected()}
        

    # --- Tool Wrappers ---
    # These methods delegate to the functional handlers, injecting the necessary dependencies.

    def execute_cypher_query_tool(self, **args) -> Dict[str, Any]:
        return query_handlers.execute_cypher_query(self.db_manager, **args)
    
    def visualize_graph_query_tool(self, **args) -> Dict[str, Any]:
        return query_handlers.visualize_graph_query(self.db_manager, **args)

    def find_dead_code_tool(self, **args) -> Dict[str, Any]:
        return analysis_handlers.find_dead_code(self.code_finder, **args)

    def calculate_cyclomatic_complexity_tool(self, **args) -> Dict[str, Any]:
        return analysis_handlers.calculate_cyclomatic_complexity(self.code_finder, **args)

    def find_most_complex_functions_tool(self, **args) -> Dict[str, Any]:
        return analysis_handlers.find_most_complex_functions(self.code_finder, **args)

    def analyze_code_relationships_tool(self, **args) -> Dict[str, Any]:
        return analysis_handlers.analyze_code_relationships(self.code_finder, **args)

    def find_code_tool(self, **args) -> Dict[str, Any]:
        return analysis_handlers.find_code(self.code_finder, **args)

    def list_indexed_repositories_tool(self, **args) -> Dict[str, Any]:
        return management_handlers.list_indexed_repositories(self.code_finder, **args)

    def delete_repository_tool(self, **args) -> Dict[str, Any]:
        return management_handlers.delete_repository(self.graph_builder, **args)

    def check_job_status_tool(self, **args) -> Dict[str, Any]:
        return management_handlers.check_job_status(self.job_manager, **args)
    
    def list_jobs_tool(self) -> Dict[str, Any]:
        return management_handlers.list_jobs(self.job_manager)

    def list_watched_paths_tool(self, **args) -> Dict[str, Any]:
        return watcher_handlers.list_watched_paths(self.code_watcher, **args)

    def unwatch_directory_tool(self, **args) -> Dict[str, Any]:
        return watcher_handlers.unwatch_directory(self.code_watcher, **args)

    def add_code_to_graph_tool(self, **args) -> Dict[str, Any]:
        return indexing_handlers.add_code_to_graph(
            self.graph_builder, 
            self.job_manager, 
            self.loop, 
            self.list_indexed_repositories_tool, # Pass the wrapper or bound method so it executes correctly
            **args
        )
    
    def add_package_to_graph_tool(self, **args) -> Dict[str, Any]:
        return indexing_handlers.add_package_to_graph(
            self.graph_builder, 
            self.job_manager, 
            self.loop, 
            self.list_indexed_repositories_tool, 
            **args
        )

    def watch_directory_tool(self, **args) -> Dict[str, Any]:
        # watch_directory needs to call metadata tools.
        return watcher_handlers.watch_directory(
            self.code_watcher,
            self.list_indexed_repositories_tool,
            self.add_code_to_graph_tool,
            **args
        )

    def load_bundle_tool(self, **args) -> Dict[str, Any]:
        return management_handlers.load_bundle(self.code_finder, **args)
    
    def search_registry_bundles_tool(self, **args) -> Dict[str, Any]:
        return management_handlers.search_registry_bundles(self.code_finder, **args)
    
    def get_repository_stats_tool(self, **args) -> Dict[str, Any]:
        return management_handlers.get_repository_stats(self.code_finder, **args)


    async def handle_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes a tool call from the AI assistant to the appropriate handler function. 
        """
        tool_map: Dict[str, Coroutine] = {
            "add_package_to_graph": self.add_package_to_graph_tool,
            "find_dead_code": self.find_dead_code_tool,
            "find_code": self.find_code_tool,
            "analyze_code_relationships": self.analyze_code_relationships_tool,
            "watch_directory": self.watch_directory_tool,
            "execute_cypher_query": self.execute_cypher_query_tool,
            "add_code_to_graph": self.add_code_to_graph_tool,
            "check_job_status": self.check_job_status_tool,
            "list_jobs": self.list_jobs_tool,
            "calculate_cyclomatic_complexity": self.calculate_cyclomatic_complexity_tool,
            "find_most_complex_functions": self.find_most_complex_functions_tool,
            "list_indexed_repositories": self.list_indexed_repositories_tool,
            "delete_repository": self.delete_repository_tool,
            "visualize_graph_query": self.visualize_graph_query_tool,
            "list_watched_paths": self.list_watched_paths_tool,
            "unwatch_directory": self.unwatch_directory_tool,
            "load_bundle": self.load_bundle_tool,
            "search_registry_bundles": self.search_registry_bundles_tool,
            "get_repository_stats": self.get_repository_stats_tool
        }
        handler = tool_map.get(tool_name)
        if handler:
            # Run the synchronous tool function in a separate thread to avoid
            # blocking the main asyncio event loop.
            return await asyncio.to_thread(handler, **args)
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def run(self):
        """
        Runs the main server loop, listening for JSON-RPC requests from stdin.
        """
        # info_logger("MCP Server is running. Waiting for requests...")
        print("MCP Server is running. Waiting for requests...", file=sys.stderr, flush=True)
        self.code_watcher.start()
        
        loop = asyncio.get_event_loop()
        while True:
            try:
                # Read a request from the standard input.
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    debug_logger("Client disconnected (EOF received). Shutting down.")
                    break
                
                request = json.loads(line.strip())
                method = request.get('method')
                params = request.get('params', {})
                request_id = request.get('id')
                
                response = {}
                # Route the request based on the JSON-RPC method.
                if method == 'initialize':
                    response = {
                        "jsonrpc": "2.0", "id": request_id,
                        "result": {
                            "protocolVersion": "2025-03-26",
                            "serverInfo": {
                                "name": "CodeGraphContext", "version": "0.1.0",
                                "systemPrompt": LLM_SYSTEM_PROMPT
                            },
                            "capabilities": {"tools": {"listTools": True}},
                        }
                    }
                elif method == 'tools/list':
                    # Return the list of tools defined in _init_tools.
                    response = {
                        "jsonrpc": "2.0", "id": request_id,
                        "result": {"tools": list(self.tools.values())}
                    }
                elif method == 'tools/call':
                    # Execute a tool call and return the result.
                    tool_name = params.get('name')
                    args = params.get('arguments', {})
                    result = await self.handle_tool_call(tool_name, args)
                    
                    if "error" in result:
                        response = {
                            "jsonrpc": "2.0", "id": request_id,
                            "error": {"code": -32000, "message": "Tool execution error", "data": result}
                        }
                    else:
                        response = {
                            "jsonrpc": "2.0", "id": request_id,
                            "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
                        }
                elif method == 'notifications/initialized':
                    # This is a notification, no response needed.
                    pass
                else:
                    # Handle unknown methods.
                    if request_id is not None:
                        response = {
                            "jsonrpc": "2.0", "id": request_id,
                            "error": {"code": -32601, "message": f"Method not found: {method}"}
                        }
                
                # Send the response to standard output if it's not a notification.
                if request_id is not None and response:
                    print(json.dumps(response), flush=True)

            except Exception as e:
                error_logger(f"Error processing request: {e}\n{traceback.format_exc()}")
                request_id = "unknown"
                if 'request' in locals() and isinstance(request, dict):
                    request_id = request.get('id', "unknown")

                error_response = {
                    "jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32603, "message": f"Internal error: {str(e)}", "data": traceback.format_exc()}
                }
                print(json.dumps(error_response), flush=True)

    def shutdown(self):
        """Gracefully shuts down the server and its components."""
        debug_logger("Shutting down server...")
        self.code_watcher.stop()
        self.db_manager.close_driver()
