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

from typing import Any, Dict, Coroutine, Optional, List, Set

from .prompts import LLM_SYSTEM_PROMPT
from .core import get_database_manager
from .core.jobs import JobManager, JobStatus
from .core.watcher import CodeWatcher
from .tools.graph_builder import GraphBuilder
from .tools.code_finder import CodeFinder
from .tools.package_resolver import get_local_package_path
from .utils.debug_log import debug_log, info_logger, error_logger, warning_logger, debug_logger
from .cli.config_manager import (
    resolve_context,
    discover_child_contexts,
    save_workspace_mapping,
    get_workspace_mapping,
)

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

WORKSPACE_PREFIX = "/workspace/"


def _is_path_key(key: str) -> bool:
    """Check if a dict key represents a file path field.

    Matches keys like 'path', 'clone_path', 'caller_file_path', and also
    Cypher-aliased keys like 'f.path', 'n.caller_file_path'.
    """
    # Strip Cypher alias prefix (e.g. "f.path" -> "path")
    bare = key.rsplit(".", 1)[-1] if "." in key else key
    return bare == "path" or bare.endswith("_path")


def _strip_path_value(value):
    """Strip /workspace/ prefix from a single string value."""
    if isinstance(value, str) and value.startswith(WORKSPACE_PREFIX):
        return value[len(WORKSPACE_PREFIX):]
    return value


def _strip_workspace_prefix(obj):
    """Recursively strip /workspace/ prefix from path values in results."""
    if isinstance(obj, dict):
        return {
            k: _strip_path_value(v) if _is_path_key(k) else _strip_workspace_prefix(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [_strip_workspace_prefix(item) for item in obj]
    return obj


# Approximate chars-per-token used for budget conversion.
# GPT-family tokenizers average ~4 chars/token; using 4 is a safe conservative estimate.
_CHARS_PER_TOKEN = 4


def _apply_response_token_limit(tool_name: str, text: str) -> str:
    """Truncate *text* to the configured token budget and append a notice.

    Reads ``MAX_TOOL_RESPONSE_TOKENS`` from the CGC config at call time so
    that live config changes are respected without a server restart.
    Returns *text* unchanged when the limit is 0 (unlimited) or not set.
    """
    from .cli.config_manager import get_config_value

    raw = get_config_value("MAX_TOOL_RESPONSE_TOKENS") or "0"
    try:
        max_tokens = int(raw)
    except ValueError:
        max_tokens = 0

    if max_tokens <= 0:
        return text  # unlimited

    max_chars = max_tokens * _CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text

    notice = (
        f"\n\n[CGC] Response truncated: output exceeded the MAX_TOOL_RESPONSE_TOKENS "
        f"limit of {max_tokens} tokens (tool: {tool_name}). "
        "Increase MAX_TOOL_RESPONSE_TOKENS or narrow your query for full results."
    )
    # Reserve space for the notice inside the budget
    budget = max_chars - len(notice)
    if budget < 0:
        budget = 0
    return text[:budget] + notice


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

    def __init__(self, loop=None, cwd: Path | None = None):
        """
        Initializes the MCP server and its components. 
        
        Args:
            loop: The asyncio event loop to use. If not provided, it gets the current
                  running loop or creates a new one.
            cwd: Working directory used for context resolution. Defaults to Path.cwd().
        """
        self.cwd = (cwd or Path.cwd()).resolve()
        self.discovered_child_contexts: List[dict] = []
        self._context_note_pending = False
        self.disabled_tools: Set[str] = set()

        try:
            ctx = resolve_context(cwd=self.cwd)
            self.resolved_context = ctx

            if ctx.database:
                os.environ['CGC_RUNTIME_DB_TYPE'] = ctx.database

            self.db_manager = get_database_manager(db_path=ctx.db_path)
            self.db_manager.get_driver()

            if not ctx.is_local:
                try:
                    children = discover_child_contexts(self.cwd, max_depth=1)
                    if children:
                        self.discovered_child_contexts = [asdict(c) for c in children]
                        self._context_note_pending = True
                except Exception:
                    pass
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
        self.disabled_tools = self._load_disabled_tools()
        self.tools = {
            name: definition
            for name, definition in TOOLS.items()
            if name not in self.disabled_tools
        }

    def _normalize_tool_name(self, name: Any) -> Optional[str]:
        """Normalize tool names from mcp.json to internal tool identifiers."""
        if not isinstance(name, str):
            return None

        normalized = name.strip()
        if not normalized:
            return None

        if normalized.startswith("codegraphcontext_"):
            normalized = normalized[len("codegraphcontext_"):]

        aliases = {
            "add_code_to_folder": "add_code_to_graph",
        }

        return aliases.get(normalized, normalized)

    def _load_disabled_tools(self) -> Set[str]:
        """Load disabled tool names from `<cwd>/mcp.json` config."""
        mcp_file = self.cwd / "mcp.json"
        if not mcp_file.exists():
            return set()

        try:
            with open(mcp_file, "r", encoding="utf-8") as f:
                mcp_config = json.load(f)
        except Exception as exc:
            warning_logger(f"Failed to read {mcp_file}: {exc}")
            return set()

        disabled_tools = (
            mcp_config
            .get("mcpServers", {})
            .get("CodeGraphContext", {})
            .get("tools", {})
            .get("disabledTools", [])
        )

        if not isinstance(disabled_tools, list):
            warning_logger("mcp.json tools.disabledTools must be a list; ignoring invalid value.")
            return set()

        normalized_disabled: Set[str] = set()
        unknown_tools: List[str] = []

        for name in disabled_tools:
            normalized_name = self._normalize_tool_name(name)
            if not normalized_name:
                continue

            if normalized_name in TOOLS:
                normalized_disabled.add(normalized_name)
            else:
                unknown_tools.append(str(name))

        if unknown_tools:
            warning_logger(
                "Ignoring unknown tools in mcp.json tools.disabledTools: "
                + ", ".join(sorted(set(unknown_tools)))
            )

        return normalized_disabled

    def _get_version(self) -> str:
        try:
            from importlib.metadata import version
            return version("codegraphcontext")
        except Exception:
            return "0.0.0-dev"

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

    def discover_codegraph_contexts_tool(self, **args) -> Dict[str, Any]:
        scan_path = Path(args.get("path", str(self.cwd))).resolve()
        max_depth = int(args.get("max_depth", 1))
        try:
            children = discover_child_contexts(scan_path, max_depth=max_depth)
            if not children:
                return {
                    "status": "no_contexts_found",
                    "message": f"No .codegraphcontext folders found under {scan_path} (depth={max_depth}).",
                    "contexts": [],
                }
            return {
                "status": "ok",
                "message": f"Found {len(children)} context(s) under {scan_path}.",
                "contexts": [asdict(c) for c in children],
            }
        except Exception as e:
            return {"error": f"Discovery failed: {e}"}

    def switch_context_tool(self, **args) -> Dict[str, Any]:
        raw_path = args.get("context_path", "")
        should_save = args.get("save", True)

        if not raw_path:
            return {"error": "context_path is required."}

        target = Path(raw_path).resolve()
        # Accept either the repo dir or the .codegraphcontext dir directly
        if target.name == ".codegraphcontext":
            cgc_dir = target
        else:
            cgc_dir = target / ".codegraphcontext"

        if not cgc_dir.exists() or not cgc_dir.is_dir():
            return {"error": f"No .codegraphcontext directory found at {cgc_dir}."}

        local_db = "falkordb"
        local_yaml = cgc_dir / "config.yaml"
        if local_yaml.exists():
            try:
                import yaml
                with open(local_yaml) as f:
                    raw = yaml.safe_load(f) or {}
                local_db = raw.get("database", "falkordb")
            except Exception:
                pass

        new_db_path = str(cgc_dir / "db" / local_db)

        try:
            # Tear down old connection
            try:
                self.db_manager.close_driver()
            except Exception:
                pass

            os.environ['CGC_RUNTIME_DB_TYPE'] = local_db
            new_manager = get_database_manager(db_path=new_db_path)
            new_manager.get_driver()

            self.db_manager = new_manager
            self.resolved_context = type(self.resolved_context)(
                mode="per-repo",
                context_name="",
                database=local_db,
                db_path=new_db_path,
                cgcignore_path=str(cgc_dir / ".cgcignore"),
                is_local=True,
            )

            # Rebuild dependent components with the new DB manager
            self.graph_builder = GraphBuilder(self.db_manager, self.job_manager, self.loop)
            self.code_finder = CodeFinder(self.db_manager)
            self.code_watcher = CodeWatcher(self.graph_builder, self.job_manager)

            if should_save:
                save_workspace_mapping(self.cwd, cgc_dir)

            self._context_note_pending = False

            return {
                "status": "ok",
                "message": f"Switched to context at {cgc_dir}.",
                "database": local_db,
                "db_path": new_db_path,
                "saved": should_save,
            }
        except Exception as e:
            return {"error": f"Failed to switch context: {e}"}


    async def handle_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes a tool call from the AI assistant to the appropriate handler function. 
        """
        if tool_name in self.disabled_tools:
            return {"error": f"Unknown tool: {tool_name}"}

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
            "get_repository_stats": self.get_repository_stats_tool,
            "discover_codegraph_contexts": self.discover_codegraph_contexts_tool,
            "switch_context": self.switch_context_tool,
        }
        handler = tool_map.get(tool_name)
        if handler:
            result = await asyncio.to_thread(handler, **args)

            if self._context_note_pending and tool_name not in (
                "discover_codegraph_contexts", "switch_context"
            ):
                names = [c["repo_name"] for c in self.discovered_child_contexts]
                note = (
                    "NOTE: No CodeGraphContext database was found at the current workspace root. "
                    f"However, the following child directories have indexed databases: {names}. "
                    "Use the `switch_context` tool to connect to one, or "
                    "`discover_codegraph_contexts` for a deeper scan."
                )
                if isinstance(result, dict):
                    result["_context_discovery_note"] = note
                self._context_note_pending = False

            return result
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
                                "name": "CodeGraphContext", "version": self._get_version(),
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
                    result = _strip_workspace_prefix(result)

                    if "error" in result:
                        response = {
                            "jsonrpc": "2.0", "id": request_id,
                            "error": {"code": -32000, "message": "Tool execution error", "data": result}
                        }
                    else:
                        response_text = json.dumps(result, indent=2)
                        response_text = _apply_response_token_limit(tool_name, response_text)
                        response = {
                            "jsonrpc": "2.0", "id": request_id,
                            "result": {"content": [{"type": "text", "text": response_text}]}
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
