
import pytest
import asyncio
import io
import json
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from codegraphcontext.server import MCPServer

class TestMCPServer:
    """
    Integration tests for the MCP Server.
    We mock the underlying DB and Logic handlers to verify the Server routes requests correctly.
    """

    @pytest.fixture
    def mock_server(self):
        with patch('codegraphcontext.server.get_database_manager') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            
            with patch('codegraphcontext.server.JobManager') as mock_job_cls, \
                 patch('codegraphcontext.server.GraphBuilder'), \
                 patch('codegraphcontext.server.CodeFinder'), \
                 patch('codegraphcontext.server.CodeWatcher'):
                
                server = MCPServer()
                # Mock handle_tool_call to avoid needing to mock every handler import
                # BUT here we want to test handle_tool_call logic too? 
                # Let's mock the internal handlers instead.
                
                return server

    def test_initialize_returns_result_not_internal_error(self, mock_server, monkeypatch, capsys):
        """The stdio `initialize` handshake must return a result, not an internal error.

        Regression guard: server.py once referenced the module-level LLM_SYSTEM_PROMPT
        while importing only build_system_prompt, so every `initialize` request raised
        NameError and was returned as a -32603 error. That fails the handshake, which
        makes the server unusable for any stdio MCP client.
        """
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
        }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request) + "\n"))

        async def run_test():
            await mock_server._run_loop(asyncio.get_running_loop())

        asyncio.run(run_test())

        response = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "error" not in response, response.get("error")
        assert response["result"]["instructions"]
        assert response["result"]["serverInfo"]["systemPrompt"]

    def test_tool_routing(self, mock_server):
        """Test that handle_tool_call routes to the correct internal method."""
        async def run_test():
            # Mock specific handler wrapper
            mock_server.find_code_tool = MagicMock(return_value={"result": "found"})
            
            # Act
            result = await mock_server.handle_tool_call("find_code", {"query": "test"})
            
            # Assert
            mock_server.find_code_tool.assert_called_once_with(query="test")
            assert result == {"result": "found"}
            
        asyncio.run(run_test())

    def test_unknown_tool(self, mock_server):
        """Test unknown tool returns error."""
        async def run_test():
            result = await mock_server.handle_tool_call("unknown_tool", {})
            assert "error" in result
            assert "Unknown tool" in result["error"]
        
        asyncio.run(run_test())

    def test_add_code_to_graph_routing(self, mock_server):
        """Verify routing for complex tools."""
        async def run_test():
            # Mock the handler function imported in server.py
            with patch('codegraphcontext.server.indexing_handlers.add_code_to_graph') as mock_handler:
                mock_handler.return_value = {"job_id": "123"}
                
                # The tool on the server instance simply calls this handler
                # We must ensure the arguments are passed correctly (including wrappers)
                
                result = await mock_server.handle_tool_call("add_code_to_graph", {"path": "."})
                
                # We can't strictly assert called_once because arguments are complex (bound methods)
                # But we can check result
                assert result == {"job_id": "123"}
        
        asyncio.run(run_test())

    def test_tools_list_omits_disabled_tools_from_mcp_json(self, tmp_path):
        """Tools listed by the server should exclude mcp.json disabledTools entries."""
        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "CodeGraphContext": {
                            "tools": {
                                "disabledTools": [
                                    "analyze_code_relationships",
                                    "codegraphcontext_find_code",
                                    "add_code_to_folder",
                                ]
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch('codegraphcontext.server.get_database_manager') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            with patch('codegraphcontext.server.JobManager'), \
                 patch('codegraphcontext.server.GraphBuilder'), \
                 patch('codegraphcontext.server.CodeFinder'), \
                 patch('codegraphcontext.server.CodeWatcher'):
                server = MCPServer(cwd=tmp_path)

        assert "analyze_code_relationships" not in server.tools
        assert "find_code" not in server.tools
        assert "add_code_to_graph" not in server.tools

    def test_disabled_tool_call_returns_unknown_tool(self, tmp_path):
        """Disabled tools should not be executable even if invoked explicitly."""
        mcp_file = tmp_path / "mcp.json"
        mcp_file.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "CodeGraphContext": {
                            "tools": {
                                "disabledTools": ["find_code"]
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        with patch('codegraphcontext.server.get_database_manager') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            with patch('codegraphcontext.server.JobManager'), \
                 patch('codegraphcontext.server.GraphBuilder'), \
                 patch('codegraphcontext.server.CodeFinder'), \
                 patch('codegraphcontext.server.CodeWatcher'):
                server = MCPServer(cwd=tmp_path)

        async def run_test():
            result = await server.handle_tool_call("find_code", {"query": "test"})
            assert result == {"error": "Tool 'find_code' is disabled in mcp.json (disabledTools)."}

        asyncio.run(run_test())

    def test_complexity_path_is_not_aliased_into_repo_path(self, mock_server):
        """#1532: path is a file disambiguator; copying it into repo_path made
        STARTS WITH never match absolute f.path and returned results: null."""
        async def run_test():
            mock_server.calculate_cyclomatic_complexity_tool = MagicMock(
                return_value={"success": True, "results": {"complexity": 3}}
            )

            await mock_server.handle_tool_call(
                "calculate_cyclomatic_complexity",
                {"function_name": "parse", "path": "src/foo.py"},
            )

            kwargs = mock_server.calculate_cyclomatic_complexity_tool.call_args.kwargs
            assert kwargs["function_name"] == "parse"
            assert kwargs["path"] == "src/foo.py"
            assert "repo_path" not in kwargs

        asyncio.run(run_test())

    def test_complexity_repo_path_is_not_aliased_into_path(self, mock_server):
        """Reverse direction was already guarded; keep it that way."""
        async def run_test():
            mock_server.calculate_cyclomatic_complexity_tool = MagicMock(
                return_value={"success": True, "results": {"complexity": 3}}
            )

            await mock_server.handle_tool_call(
                "calculate_cyclomatic_complexity",
                {"function_name": "parse", "repo_path": "/abs/repo"},
            )

            kwargs = mock_server.calculate_cyclomatic_complexity_tool.call_args.kwargs
            assert kwargs["function_name"] == "parse"
            assert kwargs["repo_path"] == "/abs/repo"
            assert "path" not in kwargs

        asyncio.run(run_test())

    def test_other_tools_still_alias_path_into_repo_path(self, mock_server):
        """General path/repo_path aliasing must keep working for tools where
        the two keys mean the same thing."""
        async def run_test():
            mock_server.find_code_tool = MagicMock(return_value={"result": "found"})

            await mock_server.handle_tool_call(
                "find_code",
                {"query": "x", "path": "/some/repo"},
            )

            kwargs = mock_server.find_code_tool.call_args.kwargs
            assert kwargs["query"] == "x"
            assert kwargs["path"] == "/some/repo"
            assert kwargs["repo_path"] == "/some/repo"

        asyncio.run(run_test())

    def test_switch_context_refuses_while_job_running(self, mock_server):
        """#1536: must not tear down the DB under an in-flight indexing job."""
        from codegraphcontext.core.jobs import JobManager, JobStatus

        jobs = JobManager()
        job_id = jobs.create_job("/big/monorepo")
        jobs.update_job(job_id, status=JobStatus.RUNNING)
        mock_server.job_manager = jobs

        with patch("codegraphcontext.server._teardown_db_manager") as teardown:
            result = mock_server.switch_context_tool(context_path="global")

        assert "error" in result
        assert job_id in result["error"]
        assert result["active_jobs"][0]["job_id"] == job_id
        assert result["active_jobs"][0]["status"] == "running"
        assert result["active_jobs"][0]["path"] == "/big/monorepo"
        teardown.assert_not_called()

    def test_switch_context_refuses_while_job_pending(self, mock_server):
        """Race window starts at create_job, before pipeline flips to RUNNING."""
        from codegraphcontext.core.jobs import JobManager

        jobs = JobManager()
        job_id = jobs.create_job("/still/pending")
        mock_server.job_manager = jobs

        with patch("codegraphcontext.server._teardown_db_manager") as teardown:
            result = mock_server.switch_context_tool(context_path="global")

        assert "error" in result
        assert job_id in result["error"]
        assert result["active_jobs"][0]["status"] == "pending"
        teardown.assert_not_called()

    def test_switch_context_global_proceeds_without_active_jobs(self, mock_server):
        """With no active jobs, switch_context may tear down and rebuild."""
        from codegraphcontext.core.jobs import JobManager
        from codegraphcontext.cli.config_manager import ResolvedContext

        mock_server.job_manager = JobManager()
        mock_server.resolved_context = ResolvedContext(
            mode="per-repo",
            context_name="",
            database="kuzudb",
            db_path="/tmp/old-db",
            cgcignore_path="/tmp/.cgcignore",
            is_local=True,
        )
        mock_server.code_watcher = MagicMock()
        mock_server.code_watcher.observer.is_alive.return_value = False

        new_manager = MagicMock()
        with patch("codegraphcontext.server._teardown_db_manager") as teardown, \
             patch("codegraphcontext.server.get_database_manager", return_value=new_manager) as get_db, \
             patch("codegraphcontext.server.GraphBuilder"), \
             patch("codegraphcontext.server.CodeFinder"), \
             patch("codegraphcontext.server.CodeWatcher"), \
             patch("codegraphcontext.server._default_global_db_path", return_value="/tmp/global-db"), \
             patch("codegraphcontext.server.load_config", return_value={"DEFAULT_DATABASE": "kuzudb"}):
            result = mock_server.switch_context_tool(context_path="global")

        assert result.get("status") == "ok", result
        teardown.assert_called_once()
        get_db.assert_called_once()
        new_manager.get_driver.assert_called_once()
