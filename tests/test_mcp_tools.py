"""Tests for MCP server tool functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.server import create_mcp_server


def parse_tool_result(result) -> dict[str, object]:
    """Parse FastMCP tool result from JSON content."""
    return json.loads(result.content[0].text)


class TestMCPToolExecuteCode:
    """Test the execute_code tool functionality."""

    @pytest.mark.asyncio
    async def test_execute_code_python_success(self) -> None:
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
    async def test_execute_code_javascript_success(self) -> None:
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
    async def test_execute_code_invalid_language(self) -> None:
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
    async def test_execute_code_execution_failure(self) -> None:
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
    async def test_execute_code_with_session_id(self) -> None:
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
    async def test_list_runtimes(self) -> None:
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
    async def test_create_session_python(self) -> None:
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
    async def test_create_session_javascript(self) -> None:
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
    async def test_create_session_invalid_language(self) -> None:
        """Test create_session with invalid language."""
        server = create_mcp_server()

        # Call the tool with invalid language
        result = await server.app._tool_manager.call_tool("create_session", {"language": "invalid"})

        parsed = parse_tool_result(result)
        assert "Unsupported language" in parsed["content"]
        assert parsed["success"] is False

    @pytest.mark.asyncio
    async def test_create_session_with_custom_id(self) -> None:
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
    async def test_destroy_session_success(self) -> None:
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
    async def test_destroy_session_not_found(self) -> None:
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
    async def test_cancel_execution_not_supported(self) -> None:
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
    async def test_get_workspace_info_success(self) -> None:
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
    async def test_get_workspace_info_not_found(self) -> None:
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
    async def test_reset_workspace_success(self) -> None:
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
    async def test_reset_workspace_failure(self) -> None:
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


class TestMCPToolListAvailablePackages:
    """Test the list_available_packages tool functionality."""

    @pytest.mark.asyncio
    async def test_list_available_packages_returns_correct_path(self) -> None:
        """Test that list_available_packages indicates packages are automatically available."""
        server = create_mcp_server()

        # Call the tool
        result = await server.app._tool_manager.call_tool("list_available_packages", {})

        parsed = parse_tool_result(result)

        # Verify the tool returns success
        assert parsed["success"] is True

        # Verify the usage instructions indicate automatic availability
        assert "/data/site-packages" in parsed["content"]
        assert (
            "automatically available" in parsed["content"]
            or "done automatically" in parsed["content"]
        )

        # Verify the WRONG path is NOT in the response
        assert "/app/site-packages" not in parsed["content"]

        # Verify package categories are listed
        assert "openpyxl" in parsed["content"]
        assert "tabulate" in parsed["content"]
        assert "jinja2" in parsed["content"]

    @pytest.mark.asyncio
    async def test_package_import_workflow_with_correct_path(self) -> None:
        """
        Integration test: Verify the exact workflow from the bug report works.

        This simulates:
        1. LLM calls list_available_packages
        2. LLM parses usage instructions
        3. LLM executes code following those instructions
        4. Package imports succeed
        """
        server = create_mcp_server()

        # Step 1: Get package list and usage instructions
        package_result = await server.app._tool_manager.call_tool("list_available_packages", {})
        parsed_packages = parse_tool_result(package_result)

        # Verify we got the correct path in instructions
        assert "/data/site-packages" in parsed_packages["content"]

        # Step 2: Mock session to test code execution with the documented path
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = "openpyxl successfully imported\nWorkbook: <class 'openpyxl.workbook.workbook.Workbook'>"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.success = True
        mock_result.fuel_consumed = 50000000
        mock_result.duration_seconds = 0.5
        mock_result.memory_used_bytes = 0
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Step 3: Execute code following the documented instructions
        test_code = """import sys
sys.path.insert(0, '/data/site-packages')
from openpyxl import Workbook
print("openpyxl successfully imported")
print(f"Workbook: {Workbook}")
"""

        execute_result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": test_code, "language": "python"}
        )

        parsed_exec = parse_tool_result(execute_result)

        # Step 4: Verify the execution succeeded
        assert parsed_exec["success"] is True
        assert "openpyxl successfully imported" in parsed_exec["content"]
        assert "Workbook" in parsed_exec["content"]

        # Verify the session was called with our code
        mock_session.execute_code.assert_called_once()
        call_args = mock_session.execute_code.call_args
        assert test_code in call_args.kwargs.get(
            "code", call_args.args[0] if call_args.args else ""
        )


class TestMCPToolJavaScriptStatePersistence:
    """Test JavaScript state persistence through MCP tools."""

    @pytest.mark.asyncio
    async def test_javascript_state_persistence_workflow(self) -> None:
        """Test JavaScript state persistence across executions via MCP."""
        server = create_mcp_server()

        # Create mock session with state persistence enabled
        mock_session = AsyncMock()
        mock_session.language = "javascript"
        mock_session.auto_persist_globals = True

        # Mock first execution - set state
        mock_result1 = MagicMock()
        mock_result1.stdout = "Counter: 1"
        mock_result1.stderr = ""
        mock_result1.exit_code = 0
        mock_result1.success = True
        mock_result1.fuel_consumed = 1000
        mock_result1.duration_seconds = 0.05
        mock_result1.memory_used_bytes = 0

        # Mock second execution - increment state
        mock_result2 = MagicMock()
        mock_result2.stdout = "Counter: 2"
        mock_result2.stderr = ""
        mock_result2.exit_code = 0
        mock_result2.success = True
        mock_result2.fuel_consumed = 1200
        mock_result2.duration_seconds = 0.06
        mock_result2.memory_used_bytes = 0

        mock_session.execute_code = AsyncMock(side_effect=[mock_result1, mock_result2])
        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Execution 1: Initialize counter
        code1 = "_state.counter = 1; console.log('Counter:', _state.counter);"
        result1 = await server.app._tool_manager.call_tool(
            "execute_code", {"code": code1, "language": "javascript", "session_id": "test-js"}
        )

        parsed1 = parse_tool_result(result1)
        assert parsed1["success"] is True
        assert "Counter: 1" in parsed1["content"]

        # Execution 2: Increment counter
        code2 = "_state.counter = _state.counter + 1; console.log('Counter:', _state.counter);"
        result2 = await server.app._tool_manager.call_tool(
            "execute_code", {"code": code2, "language": "javascript", "session_id": "test-js"}
        )

        parsed2 = parse_tool_result(result2)
        assert parsed2["success"] is True
        assert "Counter: 2" in parsed2["content"]

        # Verify execute_code was called twice
        assert mock_session.execute_code.call_count == 2

    @pytest.mark.asyncio
    async def test_create_javascript_session_with_auto_persist(self) -> None:
        """Test creating JavaScript session with auto_persist_globals enabled."""
        server = create_mcp_server()

        # Mock the session manager
        mock_session = type(
            "MockSession",
            (),
            {
                "workspace_id": "js-stateful-session",
                "language": "javascript",
                "sandbox_session_id": "js-sandbox-789",
                "created_at": 1234567893.0,
                "auto_persist_globals": True,
            },
        )()

        server.session_manager.create_session = AsyncMock(return_value=mock_session)

        # Call the tool with auto_persist_globals=True
        result = await server.app._tool_manager.call_tool(
            "create_session",
            {"language": "javascript", "auto_persist_globals": True},
        )

        parsed = parse_tool_result(result)
        assert parsed["success"] is True
        assert parsed["structured_content"]["language"] == "javascript"
        assert "js-stateful-session" in parsed["content"]

        # Verify create_session was called with correct parameters
        server.session_manager.create_session.assert_called_with(
            language="javascript", session_id=None, auto_persist_globals=True
        )

    @pytest.mark.asyncio
    async def test_javascript_vendored_package_execution(self) -> None:
        """Test JavaScript execution using vendored packages via MCP."""
        server = create_mcp_server()

        # Mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = "Parsed: 2 rows\nFirst: Alice"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.success = True
        mock_result.fuel_consumed = 2000
        mock_result.duration_seconds = 0.08
        mock_result.memory_used_bytes = 0
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Execute code using vendored CSV package
        code = """
const csv = requireVendor('csv-simple');
const data = csv.parse('name,age\\nAlice,30\\nBob,25');
console.log('Parsed:', data.length, 'rows');
console.log('First:', data[0].name);
"""
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": code, "language": "javascript"}
        )

        parsed = parse_tool_result(result)
        assert parsed["success"] is True
        assert "Parsed: 2 rows" in parsed["content"]
        assert "First: Alice" in parsed["content"]

    @pytest.mark.asyncio
    async def test_javascript_helper_utilities_execution(self) -> None:
        """Test JavaScript execution using helper utilities via MCP."""
        server = create_mcp_server()

        # Mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.stdout = "Message: Hello\nCount: 42"
        mock_result.stderr = ""
        mock_result.exit_code = 0
        mock_result.success = True
        mock_result.fuel_consumed = 1500
        mock_result.duration_seconds = 0.07
        mock_result.memory_used_bytes = 0
        mock_session.execute_code = AsyncMock(return_value=mock_result)

        server.session_manager.get_or_create_session = AsyncMock(return_value=mock_session)

        # Execute code using helper utilities
        code = """
writeJson('/app/test.json', {message: 'Hello', count: 42});
const data = readJson('/app/test.json');
console.log('Message:', data.message);
console.log('Count:', data.count);
"""
        result = await server.app._tool_manager.call_tool(
            "execute_code", {"code": code, "language": "javascript"}
        )

        parsed = parse_tool_result(result)
        assert parsed["success"] is True
        assert "Message: Hello" in parsed["content"]
        assert "Count: 42" in parsed["content"]
