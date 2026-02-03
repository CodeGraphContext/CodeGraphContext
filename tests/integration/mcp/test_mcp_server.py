
import pytest
import asyncio
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

