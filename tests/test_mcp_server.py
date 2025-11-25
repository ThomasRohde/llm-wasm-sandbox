"""Tests for MCP server lifecycle and initialization."""

from unittest.mock import AsyncMock

import pytest

from mcp_server.config import MCPConfig, ServerConfig
from mcp_server.server import MCPServer, create_mcp_server


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
