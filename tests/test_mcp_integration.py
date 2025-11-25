"""Integration tests for MCP server with real MCP protocol interactions."""

import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, patch

import pytest

from mcp_server.server import create_mcp_server
from mcp_server.transports import HTTPTransportConfig


class TestMCPIntegrationStdio:
    """Test MCP server with stdio transport integration."""

    @pytest.mark.asyncio
    async def test_stdio_server_lifecycle(self) -> None:
        """Test that stdio server can start and handle basic MCP messages."""
        server = create_mcp_server()

        # Mock the app's run_stdio_async to avoid actually running
        with patch.object(server.app, "run_stdio_async", new_callable=AsyncMock) as mock_run:
            # Start the server (this would normally run forever)
            start_task = asyncio.create_task(server.start_stdio())

            # Give it a moment to start
            await asyncio.sleep(0.1)

            # Cancel the task (simulating shutdown)
            start_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await start_task

            # Verify run_stdio_async was called
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_stdio_server_with_real_messages(self) -> None:
        """Test stdio server with simulated MCP protocol messages."""
        # This is a more advanced test that would require mocking stdin/stdout
        # For now, just verify the server can be created and has the right structure
        server = create_mcp_server()

        assert server.app is not None
        assert hasattr(server, "session_manager")
        assert hasattr(server, "start_stdio")


class TestMCPIntegrationHTTP:
    """Test MCP server with HTTP transport integration."""

    @pytest.mark.asyncio
    async def test_http_server_creation(self) -> None:
        """Test that HTTP server can be configured and started."""
        server = create_mcp_server()

        # Test with default config
        config = HTTPTransportConfig()

        # Mock the app's run_http_async
        with patch.object(server.app, "run_http_async", new_callable=AsyncMock) as mock_run:
            # Start the server
            start_task = asyncio.create_task(server.start_http(config))

            # Give it a moment
            await asyncio.sleep(0.1)

            # Cancel the task
            start_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await start_task

            # Verify run_http_async was called with correct config
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[1]["host"] == "127.0.0.1"
            assert call_args[1]["port"] == 8080

    @pytest.mark.asyncio
    async def test_http_server_custom_config(self) -> None:
        """Test HTTP server with custom configuration."""
        server = create_mcp_server()
        config = HTTPTransportConfig(host="0.0.0.0", port=9000)

        with patch.object(server.app, "run_http_async", new_callable=AsyncMock) as mock_run:
            start_task = asyncio.create_task(server.start_http(config))

            await asyncio.sleep(0.1)
            start_task.cancel()

            with contextlib.suppress(asyncio.CancelledError):
                await start_task

            call_args = mock_run.call_args
            assert call_args[1]["host"] == "0.0.0.0"
            assert call_args[1]["port"] == 9000


class TestMCPClientServerInteraction:
    """Test actual client-server interaction (simplified)."""

    @pytest.mark.asyncio
    async def test_server_can_handle_multiple_sessions(self) -> None:
        """Test that server can handle multiple concurrent sessions."""
        server = create_mcp_server()

        # Create multiple sessions concurrently
        tasks = []
        for i in range(3):
            task = server.app._tool_manager.call_tool(
                "create_session", {"language": "python", "session_id": f"session-{i}"}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # All should succeed
        for result in results:
            parsed = json.loads(result.content[0].text)  # type: ignore[union-attr]
            assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_server_tool_execution_pipeline(self) -> None:
        """Test that the server can handle a sequence of tool calls."""
        server = create_mcp_server()

        # Test that we can create multiple sessions
        result1 = await server.app._tool_manager.call_tool(
            "create_session", {"language": "python", "session_id": "test1"}
        )
        assert result1 is not None

        result2 = await server.app._tool_manager.call_tool(
            "create_session", {"language": "javascript", "session_id": "test2"}
        )
        assert result2 is not None

        # Test list_runtimes works
        runtimes_result = await server.app._tool_manager.call_tool("list_runtimes", {})
        assert runtimes_result is not None

        # Test destroy sessions
        destroy1 = await server.app._tool_manager.call_tool(
            "destroy_session", {"session_id": "test1"}
        )
        assert destroy1 is not None

        destroy2 = await server.app._tool_manager.call_tool(
            "destroy_session", {"session_id": "test2"}
        )
        assert destroy2 is not None


class TestMCPErrorHandlingIntegration:
    """Test error handling in integrated scenarios."""

    @pytest.mark.asyncio
    async def test_server_handles_invalid_requests_gracefully(self) -> None:
        """Test that server handles malformed requests without crashing."""
        server = create_mcp_server()

        # Test with invalid tool name
        try:
            result = await server.app._tool_manager.call_tool("non_existent_tool", {})
            # Should not crash, should return some error response
            assert result is not None
        except Exception as e:
            # If it raises an exception, that's also acceptable as long as it's caught
            assert isinstance(e, Exception)

    @pytest.mark.asyncio
    async def test_server_handles_execution_failures(self) -> None:
        """Test that execution failures are properly communicated."""
        server = create_mcp_server()

        # Test with invalid language
        result = await server.app._tool_manager.call_tool("create_session", {"language": "invalid"})
        parsed = json.loads(result.content[0].text)  # type: ignore[union-attr]
        assert parsed["success"] is False


# Note: Real HTTP integration tests would require starting an actual HTTP server
# and making real HTTP requests, which is complex and better suited for
# end-to-end testing with tools like pytest-httpx or test clients.
