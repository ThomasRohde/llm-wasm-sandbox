"""Tests for MCP server tool functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.server import create_mcp_server


def parse_tool_result(result):
    """Parse FastMCP tool result from JSON content."""
    return json.loads(result.content[0].text)


class TestMCPToolExecuteCode:
    """Test the execute_code tool functionality."""

    @pytest.mark.asyncio
    async def test_execute_code_python_success(self):
        """Test successful Python code execution."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = "Hello World"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.success = True
        mock_result.fuel_consumed = 1000
        mock_result.duration_seconds = 0.1
        mock_result.memory_used_bytes = 0
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": "print('Hello World')", "language": "python"}
        )

        parsed = parse_tool_result(result)
        assert parsed["content"] == "Hello World"
        assert parsed["structured_content"]["stdout"] == "Hello World"
        assert parsed["structured_content"]["success"] is True
        assert parsed["structured_content"]["fuel_consumed"] == 1000
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_execute_code_javascript_success(self):
        """Test successful JavaScript code execution."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = "42"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.success = True
        mock_result.fuel_consumed = 500
        mock_result.duration_seconds = 0.05
        mock_result.memory_used_bytes = 0
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": "console.log(42)", "language": "javascript"}
        )

        parsed = parse_tool_result(result)
        assert parsed["content"] == "42"
        assert parsed["structured_content"]["stdout"] == "42"
        assert parsed["structured_content"]["success"] is True
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_execute_code_invalid_language(self):
        """Test execute_code with invalid language."""
        server = create_mcp_server()

        # Call the tool with invalid language
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": "print('test')", "language": "invalid"}
        )

        parsed = parse_tool_result(result)
        assert "Unsupported language" in parsed["content"]
        assert parsed["success"] is False

    @pytest.mark.asyncio
    async def test_execute_code_execution_failure(self):
        """Test execute_code when execution fails."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "SyntaxError: invalid syntax"
        mock_result.exit_code = 1
        mock_result.success = False
        mock_result.fuel_consumed = 200
        mock_result.duration_seconds = 0.02
        mock_result.memory_used_bytes = 0
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": "invalid syntax", "language": "python"}
        )

        parsed = parse_tool_result(result)
        assert "SyntaxError" in parsed["content"]
        assert parsed["structured_content"]["success"] is False
        assert parsed["success"] is False

    @pytest.mark.asyncio
    async def test_execute_code_with_session_id(self):
        """Test execute_code with explicit session ID."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = "session test"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.success = True
        mock_result.fuel_consumed = 300
        mock_result.duration_seconds = 0.03
        mock_result.memory_used_bytes = 0
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Call the tool with session_id
        result = await server.app._tool_manager.call_tool(
            "execute_code",
            {"code": "print('session test')", "language": "python", "session_id": "test-session"},
        )

        server.session_manager.get_or_create_session.assert_called_with(
            language="python", session_id="test-session"
        )
        parsed = parse_tool_result(result)
        assert parsed["content"] == "session test"
        assert parsed["success"] is True


class TestMCPToolListRuntimes:
    """Test the list_runtimes tool functionality."""

    @pytest.mark.asyncio
    async def test_list_runtimes(self):
        """Test listing available runtimes."""
        server = create_mcp_server()

        # Call the tool
        result = await server.app._tool_manager.call_tool("list_runtimes", {})

        parsed = parse_tool_result(result)
        assert "python" in parsed["content"].lower()
        assert "javascript" in parsed["content"].lower()
        assert parsed["structured_content"] is not None
        assert len(parsed["structured_content"]["runtimes"]) == 2

        runtimes = parsed["structured_content"]["runtimes"]
        python_runtime = next(r for r in runtimes if r["name"] == "python")
        js_runtime = next(r for r in runtimes if r["name"] == "javascript")

        assert python_runtime["version"] == "3.12"
        assert "CPython" in python_runtime["description"]
        assert js_runtime["version"] == "ES2023"
        assert "QuickJS" in js_runtime["description"]
        assert parsed["success"] is True


class TestMCPToolCreateSession:
    """Test the create_session tool functionality."""

    @pytest.mark.asyncio
    async def test_create_session_python(self):
        """Test creating a Python session."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = type(
            "MockSession",
            (),
            {
                "workspace_id": "test-workspace-123",
                "language": "python",
                "sandbox_session_id": "sandbox-456",
                "created_at": 1234567890.0,
                "auto_persist_globals": False,
            },
        )()

        with patch.object(
            server.session_manager, "create_session", new_callable=AsyncMock
        ) as mock_method:
            mock_method.side_effect = lambda *args, **kwargs: mock_session
            # Call the tool
            result = await server.app._tool_manager.call_tool(
                "create_session", {"language": "python"}
            )

            parsed = parse_tool_result(result)
            assert "Created session test-workspace-123" in parsed["content"]
            assert parsed["structured_content"]["session_id"] == "test-workspace-123"
            assert parsed["structured_content"]["language"] == "python"
            assert parsed["structured_content"]["sandbox_session_id"] == "sandbox-456"
            assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_create_session_javascript(self):
        """Test creating a JavaScript session."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = type(
            "MockSession",
            (),
            {
                "workspace_id": "js-session-789",
                "language": "javascript",
                "sandbox_session_id": "js-sandbox-101",
                "created_at": 1234567891.0,
                "auto_persist_globals": False,
            },
        )()

        server.session_manager.create_session = AsyncMock(return_value=mock_session)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "create_session", {"language": "javascript"}
        )

        parsed = parse_tool_result(result)
        assert "Created session js-session-789" in parsed["content"]
        assert parsed["structured_content"]["language"] == "javascript"
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_create_session_invalid_language(self):
        """Test create_session with invalid language."""
        server = create_mcp_server()

        # Call the tool with invalid language
        result = await server.app._tool_manager.call_tool("create_session", {"language": "invalid"})

        parsed = parse_tool_result(result)
        assert "Unsupported language" in parsed["content"]
        assert parsed["success"] is False

    @pytest.mark.asyncio
    async def test_create_session_with_custom_id(self):
        """Test create_session with custom session ID."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = type(
            "MockSession",
            (),
            {
                "workspace_id": "custom-id",
                "language": "python",
                "sandbox_session_id": "sandbox-custom",
                "created_at": 1234567892.0,
                "auto_persist_globals": False,
            },
        )()

        server.session_manager.create_session = AsyncMock(return_value=mock_session)

        # Call the tool with custom session_id
        result = await server.app._tool_manager.call_tool(
            "create_session", {"language": "python", "session_id": "custom-id"}
        )

        server.session_manager.create_session.assert_called_with(
            language="python", session_id="custom-id", auto_persist_globals=False
        )
        parsed = parse_tool_result(result)
        assert parsed["structured_content"]["session_id"] == "custom-id"
        assert parsed["success"] is True


class TestMCPToolDestroySession:
    """Test the destroy_session tool functionality."""

    @pytest.mark.asyncio
    async def test_destroy_session_success(self):
        """Test successful session destruction."""
        server = create_mcp_server()

        server.session_manager.destroy_session = AsyncMock(return_value=True)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "destroy_session", {"session_id": "test-session"}
        )

        parsed = parse_tool_result(result)
        assert "Destroyed session test-session" in parsed["content"]
        assert parsed["structured_content"]["session_id"] == "test-session"
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_destroy_session_not_found(self):
        """Test destroying a non-existent session."""
        server = create_mcp_server()

        server.session_manager.destroy_session = AsyncMock(return_value=False)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "destroy_session", {"session_id": "non-existent"}
        )

        parsed = parse_tool_result(result)
        assert "Session non-existent not found" in parsed["content"]
        assert parsed["success"] is False


class TestMCPToolCancelExecution:
    """Test the cancel_execution tool functionality."""

    @pytest.mark.asyncio
    async def test_cancel_execution_not_supported(self):
        """Test that cancel_execution returns not supported."""
        server = create_mcp_server()

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "cancel_execution", {"session_id": "test-session"}
        )

        parsed = parse_tool_result(result)
        assert "not yet supported" in parsed["content"]
        assert parsed["structured_content"]["supported"] is False
        assert parsed["success"] is False


class TestMCPToolGetWorkspaceInfo:
    """Test the get_workspace_info tool functionality."""

    @pytest.mark.asyncio
    async def test_get_workspace_info_success(self):
        """Test successful workspace info retrieval."""
        server = create_mcp_server()

        mock_info = {
            "workspace_id": "test-workspace",
            "language": "python",
            "sandbox_session_id": "sandbox-123",
            "created_at": 1234567890.0,
            "last_used_at": 1234567900.0,
            "execution_count": 5,
            "variables": ["x", "y"],
            "imports": ["os", "sys"],
            "files": ["/app/main.py", "/app/utils.py"],
            "is_expired": False,
        }

        server.session_manager.get_session_info = AsyncMock(return_value=mock_info)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "get_workspace_info", {"session_id": "test-workspace"}
        )

        parsed = parse_tool_result(result)
        assert "Session test-workspace: python, 5 executions, 2 files" in parsed["content"]
        assert parsed["structured_content"] == mock_info
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_get_workspace_info_not_found(self):
        """Test workspace info for non-existent session."""
        server = create_mcp_server()

        server.session_manager.get_session_info = AsyncMock(return_value=None)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "get_workspace_info", {"session_id": "non-existent"}
        )

        parsed = parse_tool_result(result)
        assert "Session non-existent not found" in parsed["content"]
        assert parsed["success"] is False


class TestMCPToolResetWorkspace:
    """Test the reset_workspace tool functionality."""

    @pytest.mark.asyncio
    async def test_reset_workspace_success(self):
        """Test successful workspace reset."""
        server = create_mcp_server()

        server.session_manager.reset_session = AsyncMock(return_value=True)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "reset_workspace", {"session_id": "test-workspace"}
        )

        parsed = parse_tool_result(result)
        assert "Reset workspace session test-workspace" in parsed["content"]
        assert parsed["structured_content"]["session_id"] == "test-workspace"
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_reset_workspace_failure(self):
        """Test failed workspace reset."""
        server = create_mcp_server()

        server.session_manager.reset_session = AsyncMock(return_value=False)

        # Call the tool
        result = await server.app._tool_manager.call_tool(
            "reset_workspace", {"session_id": "test-workspace"}
        )

        parsed = parse_tool_result(result)
        assert "Failed to reset session test-workspace" in parsed["content"]
        assert parsed["success"] is False
