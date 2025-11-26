"""Tests for MCP server lifecycle and initialization."""

from unittest.mock import AsyncMock

import pytest

from mcp_server.config import MCPConfig, ServerConfig
from mcp_server.server import MCPServer, MCPToolResult, create_mcp_server


class TestMCPServerInitialization:
    """Test MCP server initialization and configuration."""

    def test_create_mcp_server_default_config(self) -> None:
        """Test creating MCP server with default configuration."""
        server = create_mcp_server()

        assert isinstance(server, MCPServer)
        assert isinstance(server.config, MCPConfig)
        assert server.config.server.name == "llm-wasm-sandbox"

    def test_create_mcp_server_custom_config(self) -> None:
        """Test creating MCP server with custom configuration."""
        config = MCPConfig(server=ServerConfig(name="test-server", version="1.0.0"))
        server = create_mcp_server(config)

        assert server.config.server.name == "test-server"
        assert server.config.server.version == "1.0.0"

    def test_server_has_fastmcp_app(self) -> None:
        """Test that server has a FastMCP app instance."""
        server = create_mcp_server()

        assert hasattr(server, "app")
        assert server.app.name == "llm-wasm-sandbox"

    def test_server_has_session_manager(self) -> None:
        """Test that server has a session manager."""
        server = create_mcp_server()

        assert hasattr(server, "session_manager")
        assert server.session_manager is not None

    def test_server_has_logger(self) -> None:
        """Test that server has a logger."""
        server = create_mcp_server()

        assert hasattr(server, "logger")
        assert server.logger is not None


class TestMCPServerTools:
    """Test MCP server tool registration."""

    def test_tools_are_registered(self) -> None:
        """Test that all expected tools are registered."""
        server = create_mcp_server()

        # Check that the app has tools registered
        # FastMCP stores tools in app._tool_manager._tools
        tools = server.app._tool_manager._tools

        expected_tools = [
            "execute_code",
            "list_runtimes",
            "create_session",
            "destroy_session",
            "list_available_packages",
            "cancel_execution",
            "get_workspace_info",
            "reset_workspace",
            "get_metrics",
        ]

        for tool_name in expected_tools:
            assert tool_name in tools, f"Tool {tool_name} not found in registered tools"

    def test_tool_descriptions(self) -> None:
        """Test that tools have proper descriptions."""
        server = create_mcp_server()
        tools = server.app._tool_manager._tools

        # Check a few key tools have descriptions
        assert "execute_code" in tools
        assert "list_runtimes" in tools
        assert "create_session" in tools

        # Verify descriptions contain expected keywords
        execute_tool = tools["execute_code"]
        assert "WebAssembly" in execute_tool.description
        assert "sandbox" in execute_tool.description.lower()


class TestMCPServerLifecycle:
    """Test MCP server lifecycle management."""

    @pytest.mark.asyncio
    async def test_server_shutdown(self) -> None:
        """Test server shutdown cleans up resources."""
        server = create_mcp_server()

        # Mock session manager cleanup
        server.session_manager.cleanup = AsyncMock()

        await server.shutdown()

        # Verify cleanup was called
        server.session_manager.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stdio_transport_start(self) -> None:
        """Test starting server with stdio transport."""
        server = create_mcp_server()

        # Mock the app's run_stdio_async method
        server.app.run_stdio_async = AsyncMock()

        await server.start_stdio()

        server.app.run_stdio_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_transport_start_default_config(self) -> None:
        """Test starting server with HTTP transport using default config."""
        server = create_mcp_server()

        # Mock the app's run_http_async method
        server.app.run_http_async = AsyncMock()

        await server.start_http()

        # Verify HTTP transport was started with default config
        server.app.run_http_async.assert_called_once()
        call_args = server.app.run_http_async.call_args
        assert call_args[1]["host"] == "127.0.0.1"
        assert call_args[1]["port"] == 8080

    @pytest.mark.asyncio
    async def test_http_transport_start_custom_config(self) -> None:
        """Test starting server with HTTP transport using custom config."""
        from mcp_server.transports import HTTPTransportConfig

        server = create_mcp_server()
        http_config = HTTPTransportConfig(host="0.0.0.0", port=9000)

        # Mock the app's run_http_async method
        server.app.run_http_async = AsyncMock()

        await server.start_http(http_config)

        server.app.run_http_async.assert_called_once()
        call_args = server.app.run_http_async.call_args
        assert call_args[1]["host"] == "0.0.0.0"
        assert call_args[1]["port"] == 9000


class TestMCPServerErrorHandling:
    """Test MCP server error handling."""

    def test_server_initialization_with_invalid_config(self) -> None:
        """Test server handles invalid configuration gracefully."""
        # This should work since MCPConfig has defaults
        config = MCPConfig()
        server = create_mcp_server(config)
        assert server is not None

    @pytest.mark.asyncio
    async def test_stdio_start_failure_handling(self) -> None:
        """Test handling of stdio transport start failures."""
        server = create_mcp_server()

        # Mock the app's run_stdio_async to raise an exception
        server.app.run_stdio_async = AsyncMock(side_effect=Exception("Transport error"))

        with pytest.raises(Exception, match="Transport error"):
            await server.start_stdio()

    @pytest.mark.asyncio
    async def test_http_start_failure_handling(self) -> None:
        """Test handling of HTTP transport start failures."""
        server = create_mcp_server()

        # Mock the app's run_http_async to raise an exception
        server.app.run_http_async = AsyncMock(side_effect=Exception("HTTP error"))

        with pytest.raises(Exception, match="HTTP error"):
            await server.start_http()


class TestMCPServerFilesChanged:
    """Test MCP server files_changed response structure."""

    def test_filter_system_files_excludes_pycache(self) -> None:
        """Test that __pycache__/ directories are excluded from client files."""
        files = [
            "data.csv",
            "__pycache__/module.cpython-312.pyc",
            "output.txt",
            "__pycache__/nested/file.pyc",
        ]

        client_files, system_files = MCPServer._filter_system_files(files)

        assert "data.csv" in client_files
        assert "output.txt" in client_files
        assert len(client_files) == 2

        assert "__pycache__/module.cpython-312.pyc" in system_files
        assert "__pycache__/nested/file.pyc" in system_files
        assert len(system_files) == 2

    def test_filter_system_files_excludes_site_packages(self) -> None:
        """Test that site-packages/ directories are excluded from client files."""
        files = [
            "data.csv",
            "site-packages/some_package/module.py",
            "output.txt",
        ]

        client_files, system_files = MCPServer._filter_system_files(files)

        assert "data.csv" in client_files
        assert "output.txt" in client_files
        assert len(client_files) == 2

        assert "site-packages/some_package/module.py" in system_files
        assert len(system_files) == 1

    def test_filter_system_files_excludes_internal_files(self) -> None:
        """Test that internal sandbox files are excluded from client files."""
        files = [
            "data.csv",
            ".metadata.json",
            "user_code.py",
            "user_code.js",
            "__state__.json",
            "output.txt",
        ]

        client_files, system_files = MCPServer._filter_system_files(files)

        assert client_files == ["data.csv", "output.txt"]
        assert set(system_files) == {
            ".metadata.json",
            "user_code.py",
            "user_code.js",
            "__state__.json",
        }

    @pytest.mark.asyncio
    async def test_execute_code_files_changed_structure(self) -> None:
        """Test that execute_code returns files_changed with correct structure."""
        server = create_mcp_server()

        # Get the execute_code tool function
        tools = server.app._tool_manager._tools
        execute_code_tool = tools["execute_code"]

        # Execute code that creates a file
        result = await execute_code_tool.fn(
            code="with open('/app/test_output.txt', 'w') as f: f.write('hello')",
            language="python",
        )

        assert isinstance(result, MCPToolResult)
        assert result.success is True
        assert result.structured_content is not None

        # Verify files_changed is present
        assert "files_changed" in result.structured_content

        files_changed = result.structured_content["files_changed"]
        assert isinstance(files_changed, list)

        # If files were created, verify structure
        if len(files_changed) > 0:
            for file_info in files_changed:
                assert "absolute" in file_info
                assert "relative" in file_info
                assert "filename" in file_info

                # Verify relative path is relative to cwd (contains workspace path)
                assert "workspace" in file_info["relative"]

                # Verify filename is extracted correctly
                assert "/" not in file_info["filename"]

    @pytest.mark.asyncio
    async def test_execute_code_files_changed_deduplication(self) -> None:
        """Test that files appearing in both created and modified are deduplicated."""
        server = create_mcp_server()

        # Get the execute_code tool function
        tools = server.app._tool_manager._tools
        execute_code_tool = tools["execute_code"]

        # Execute code that creates and immediately modifies a file
        result = await execute_code_tool.fn(
            code="""
with open('/app/dedup_test.txt', 'w') as f:
    f.write('first')
with open('/app/dedup_test.txt', 'a') as f:
    f.write('second')
""",
            language="python",
        )

        assert isinstance(result, MCPToolResult)
        assert result.structured_content is not None
        assert "files_changed" in result.structured_content

        files_changed = result.structured_content["files_changed"]

        # Check that the file appears at most once
        filenames = [f["filename"] for f in files_changed]
        assert filenames.count("dedup_test.txt") <= 1

    @pytest.mark.asyncio
    async def test_execute_code_files_changed_excludes_system_files(self) -> None:
        """Test that system files are excluded from files_changed."""
        server = create_mcp_server()

        # Get the execute_code tool function
        tools = server.app._tool_manager._tools
        execute_code_tool = tools["execute_code"]

        # Execute simple code (user_code.py is a system file)
        result = await execute_code_tool.fn(
            code="print('hello')",
            language="python",
        )

        assert isinstance(result, MCPToolResult)
        assert result.structured_content is not None
        assert "files_changed" in result.structured_content

        files_changed = result.structured_content["files_changed"]
        filenames = [f["filename"] for f in files_changed]

        # System files should not appear
        assert "user_code.py" not in filenames
        assert ".metadata.json" not in filenames
        assert "__state__.json" not in filenames
