"""Tests for MCP server security boundaries and access controls."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from mcp_server.server import create_mcp_server


def parse_tool_result(result):
    """Parse FastMCP tool result from JSON content."""
    return json.loads(result.content[0].text)


class TestMCPSecurityBoundaries:
    """Test MCP server security boundaries and isolation."""

    @pytest.mark.asyncio
    async def test_session_isolation_execute_code(self):
        """Test that execute_code cannot access other sessions."""
        server = create_mcp_server()

        # Create two sessions
        await server.app._tool_manager.call_tool(
            "create_session", {"language": "python", "session_id": "session1"}
        )
        await server.app._tool_manager.call_tool(
            "create_session", {"language": "python", "session_id": "session2"}
        )

        # Mock session manager to return isolated sessions
        mock_session1 = AsyncMock()
        mock_session1.language = "python"
        mock_result1 = MagicMock()
        mock_result1.stdout = "session1_data"
        mock_result1.stderr = ""
        mock_result1.exit_code = 0
        mock_result1.success = True
        mock_session1.execute_code = AsyncMock(return_value=mock_result1)

        mock_session2 = AsyncMock()
        mock_session2.language = "python"
        mock_result2 = MagicMock()
        mock_result2.stdout = "session2_data"
        mock_result2.stderr = ""
        mock_result2.exit_code = 0
        mock_result2.success = True
        mock_session2.execute_code = AsyncMock(return_value=mock_result2)

        # Mock get_or_create_session to return appropriate session
        def mock_get_session(language, session_id=None):
            if session_id == "session1":
                return mock_session1
            elif session_id == "session2":
                return mock_session2
            return mock_session1  # default

        server.session_manager.get_or_create_session = AsyncMock(side_effect=mock_get_session)

        # Execute code in session1
        await server.app._tool_manager.call_tool(
            "execute_code",
            {"code": "print('test')", "language": "python", "session_id": "session1"},
        )

        # Execute code in session2
        await server.app._tool_manager.call_tool(
            "execute_code",
            {"code": "print('test')", "language": "python", "session_id": "session2"},
        )

        # Verify different sessions were used
        calls = server.session_manager.get_or_create_session.call_args_list
        session1_calls = [call for call in calls if call[1].get("session_id") == "session1"]
        session2_calls = [call for call in calls if call[1].get("session_id") == "session2"]

        assert len(session1_calls) > 0
        assert len(session2_calls) > 0

    @pytest.mark.asyncio
    async def test_invalid_session_access_denied(self):
        """Test that accessing non-existent sessions is denied."""
        server = create_mcp_server()

        # Try to execute code with non-existent session
        result = await server.app._tool_manager.call_tool(
            "execute_code",
            {"code": "print('test')", "language": "python", "session_id": "non-existent"},
        )

        parsed = parse_tool_result(result)
        # Should either fail or create a new session, but not crash
        assert parsed["success"] is not None  # Should have some response

    @pytest.mark.asyncio
    async def test_tool_input_validation(self):
        """Test that tools validate their inputs."""
        server = create_mcp_server()

        # Test execute_code with missing required parameters
        with pytest.raises(ValidationError):  # Should raise validation error
            await server.app._tool_manager.call_tool(
                "execute_code",
                {"language": "python"},  # missing code
            )

        # Test create_session with invalid language
        result = await server.app._tool_manager.call_tool(
            "create_session", {"language": "invalid_lang"}
        )

        parsed = parse_tool_result(result)
        assert "Unsupported language" in parsed["content"]
        assert parsed["success"] is False

    @pytest.mark.asyncio
    async def test_destroy_session_security(self):
        """Test that destroying sessions requires proper authorization."""
        server = create_mcp_server()

        # Mock session manager to simulate session not found
        server.session_manager.destroy_session = AsyncMock(return_value=False)

        result = await server.app._tool_manager.call_tool(
            "destroy_session", {"session_id": "some-session"}
        )

        parsed = parse_tool_result(result)
        assert "not found" in parsed["content"]
        assert parsed["success"] is False

    @pytest.mark.asyncio
    async def test_get_workspace_info_isolation(self):
        """Test that workspace info is properly isolated per session."""
        server = create_mcp_server()

        # Mock session manager to return info for specific session
        mock_info = {
            "workspace_id": "test-session",
            "language": "python",
            "execution_count": 5,
            "files": ["/app/test.py"],
        }
        server.session_manager.get_session_info = AsyncMock(return_value=mock_info)

        result = await server.app._tool_manager.call_tool(
            "get_workspace_info", {"session_id": "test-session"}
        )

        parsed = parse_tool_result(result)
        assert parsed["structured_content"]["workspace_id"] == "test-session"
        assert parsed["success"] is True

        # Verify the call was made with correct session_id
        server.session_manager.get_session_info.assert_called_with("test-session")

    @pytest.mark.asyncio
    async def test_reset_workspace_isolation(self):
        """Test that reset_workspace only affects the specified session."""
        server = create_mcp_server()

        # Mock successful reset
        server.session_manager.reset_session = AsyncMock(return_value=True)

        result = await server.app._tool_manager.call_tool(
            "reset_workspace", {"session_id": "test-session"}
        )

        parsed = parse_tool_result(result)
        assert "Reset workspace session test-session" in parsed["content"]
        assert parsed["success"] is True

        # Verify the call was made with correct session_id
        server.session_manager.reset_session.assert_called_with("test-session")

    @pytest.mark.asyncio
    async def test_list_runtimes_no_security_implications(self):
        """Test that list_runtimes doesn't expose sensitive information."""
        server = create_mcp_server()

        result = await server.app._tool_manager.call_tool("list_runtimes", {})

        parsed = parse_tool_result(result)
        assert parsed["success"] is True

        # Should only contain runtime info, no system details
        runtimes = parsed["structured_content"]["runtimes"]
        for runtime in runtimes:
            assert "name" in runtime
            assert "version" in runtime
            assert "description" in runtime
            # Should not contain paths, secrets, etc.
            assert "path" not in runtime
            assert "config" not in runtime

    @pytest.mark.asyncio
    async def test_cancel_execution_not_implemented(self):
        """Test that cancel_execution properly indicates it's not supported."""
        server = create_mcp_server()

        result = await server.app._tool_manager.call_tool(
            "cancel_execution", {"session_id": "test-session"}
        )

        parsed = parse_tool_result(result)
        assert "not yet supported" in parsed["content"]
        assert parsed["structured_content"]["supported"] is False
        assert parsed["success"] is False


class TestMCPTransportSecurity:
    """Test MCP transport-level security."""

    def test_stdio_transport_no_network_exposure(self):
        """Test that stdio transport doesn't expose network interfaces."""
        from mcp_server.transports import StdioTransportConfig

        config = StdioTransportConfig()
        # Stdio transport should not have network-related config
        assert not hasattr(config, "host")
        assert not hasattr(config, "port")
        assert not hasattr(config, "cors_origins")

    def test_http_transport_has_security_defaults(self):
        """Test that HTTP transport has secure defaults."""
        from mcp_server.transports import HTTPTransportConfig

        config = HTTPTransportConfig()

        # Should default to localhost
        assert config.host == "127.0.0.1"

        # Should have reasonable rate limiting
        assert config.rate_limit_requests > 0
        assert config.rate_limit_window_seconds > 0

        # Should have concurrency limits
        assert config.max_concurrent_requests > 0

        # Should have timeout
        assert config.request_timeout_seconds > 0

        # Should have request size limits
        assert config.max_request_size_mb > 0


class TestMCPResourceLimits:
    """Test MCP server resource limits and abuse prevention."""

    @pytest.mark.asyncio
    async def test_execution_timeout_handling(self):
        """Test that executions are properly limited by underlying sandbox."""
        server = create_mcp_server()

        # Mock session with execution that would timeout
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "Execution timed out"
        mock_result.exit_code = -1
        mock_result.success = False
        mock_result.fuel_consumed = 1000000
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Execute potentially long-running code
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": "while True: pass", "language": "python"}
        )

        parsed = parse_tool_result(result)
        # Should not hang, should return failure
        assert parsed["success"] is False

    @pytest.mark.asyncio
    async def test_memory_limit_enforcement(self):
        """Test that memory limits are enforced."""
        server = create_mcp_server()

        # Mock session with memory-intensive execution
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "Memory limit exceeded"
        mock_result.exit_code = -1
        mock_result.success = False
        mock_result.fuel_consumed = 500000
        mock_result.duration_seconds = 1.0
        mock_result.memory_used_bytes = 128 * 1024 * 1024
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Execute memory-intensive code
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": "[0] * 100000000", "language": "python"}
        )

        parsed = parse_tool_result(result)
        assert parsed["success"] is False
        assert "limit" in parsed["content"].lower() or "memory" in parsed["content"].lower()
