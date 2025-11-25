"""Tests for MCP server session management."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.server import create_mcp_server
from mcp_server.sessions import WorkspaceSession, WorkspaceSessionManager
from sandbox import RuntimeType


class TestWorkspaceSession:
    """Test WorkspaceSession class functionality."""

    def test_workspace_session_creation(self) -> None:
        """Test creating a workspace session."""
        session = WorkspaceSession(
            workspace_id="test-123", language="python", sandbox_session_id="sandbox-456"
        )

        assert session.workspace_id == "test-123"
        assert session.language == "python"
        assert session.sandbox_session_id == "sandbox-456"
        assert session.execution_count == 0
        assert session.variables == []
        assert session.imports == []
        assert not session.is_expired

    def test_workspace_session_expiration(self) -> None:
        """Test session expiration logic."""
        # Create session in the past
        past_time = time.time() - 700  # 700 seconds ago
        session = WorkspaceSession(
            workspace_id="test-123", language="python", sandbox_session_id="sandbox-456"
        )
        session.created_at = past_time
        session.last_used_at = past_time

        # Default timeout is 600 seconds, so this should be expired
        assert session.is_expired

        # Test with custom timeout - create a method to check
        assert (
            time.time() - session.last_used_at <= 800
        )  # Should not be expired with longer timeout

    @patch("mcp_server.sessions.create_sandbox")
    def test_get_sandbox(self, mock_create_sandbox) -> None:
        """Test getting sandbox instance."""
        mock_sandbox = MagicMock()
        mock_create_sandbox.return_value = mock_sandbox

        session = WorkspaceSession(
            workspace_id="test-123", language="python", sandbox_session_id="sandbox-456"
        )

        sandbox = session.get_sandbox()

        # Verify create_sandbox was called with expected runtime and session_id
        # (policy parameter is passed but we don't need to check exact values)
        assert mock_create_sandbox.called
        call_args = mock_create_sandbox.call_args
        assert call_args.kwargs["runtime"] == RuntimeType.PYTHON
        assert call_args.kwargs["session_id"] == "sandbox-456"
        assert not call_args.kwargs["auto_persist_globals"]
        assert sandbox == mock_sandbox

    @patch("mcp_server.sessions.create_sandbox")
    @pytest.mark.asyncio
    async def test_execute_code(self, mock_create_sandbox) -> None:
        """Test executing code in session."""
        mock_sandbox = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.fuel_consumed = 100
        mock_sandbox.execute = MagicMock(return_value=mock_result)  # Synchronous, not async
        mock_create_sandbox.return_value = mock_sandbox

        session = WorkspaceSession(
            workspace_id="test-123", language="python", sandbox_session_id="sandbox-456"
        )

        result = await session.execute_code("print('hello')")

        mock_sandbox.execute.assert_called_once_with("print('hello')", timeout=None)
        assert result.success == mock_result.success
        assert result.fuel_consumed == mock_result.fuel_consumed
        assert session.execution_count == 1
        assert session.last_used_at > session.created_at


class TestWorkspaceSessionManager:
    """Test WorkspaceSessionManager functionality."""

    def test_session_manager_creation(self) -> None:
        """Test creating a session manager."""
        manager = WorkspaceSessionManager()

        assert manager._sessions == {}
        assert manager._cleanup_task is None

    @patch("mcp_server.sessions.create_sandbox")
    @pytest.mark.asyncio
    async def test_get_or_create_session_new(self, mock_create_sandbox) -> None:
        """Test getting or creating a new session."""
        mock_sandbox = MagicMock()
        mock_sandbox.session_id = "new-sandbox-id"
        mock_create_sandbox.return_value = mock_sandbox

        manager = WorkspaceSessionManager()

        session = await manager.get_or_create_session("python")

        assert session.language == "python"
        assert session.sandbox_session_id == "new-sandbox-id"
        assert session.workspace_id in manager._sessions
        # Verify create_sandbox was called with expected runtime
        assert mock_create_sandbox.called
        call_args = mock_create_sandbox.call_args
        assert call_args.kwargs["runtime"] == RuntimeType.PYTHON
        assert not call_args.kwargs["auto_persist_globals"]

    @pytest.mark.asyncio
    async def test_get_or_create_session_existing(self) -> None:
        """Test getting an existing session."""
        manager = WorkspaceSessionManager()

        # Create a session manually
        existing_session = WorkspaceSession(
            workspace_id="existing-123", language="python", sandbox_session_id="sandbox-456"
        )
        manager._sessions["existing-123"] = existing_session

        session = await manager.get_or_create_session("python", "existing-123")

        assert session == existing_session

    @pytest.mark.asyncio
    async def test_get_or_create_session_expired(self) -> None:
        """Test getting an expired session creates a new one."""
        manager = WorkspaceSessionManager()

        # Create an expired session
        expired_session = WorkspaceSession(
            workspace_id="expired-123", language="python", sandbox_session_id="sandbox-old"
        )
        expired_session.created_at = time.time() - 700  # Expired
        expired_session.last_used_at = time.time() - 700
        manager._sessions["expired-123"] = expired_session

        with patch("mcp_server.sessions.create_sandbox") as mock_create:
            mock_sandbox = MagicMock()
            mock_sandbox.session_id = "new-sandbox-id"
            mock_create.return_value = mock_sandbox

            session = await manager.get_or_create_session("python", "expired-123")

            # Should create new session with same ID
            assert session.workspace_id == "expired-123"
            assert session.sandbox_session_id == "new-sandbox-id"
            # Verify create_sandbox was called with expected runtime
            assert mock_create.called
            call_args = mock_create.call_args
            assert call_args.kwargs["runtime"] == RuntimeType.PYTHON
            assert not call_args.kwargs["auto_persist_globals"]

    @patch("mcp_server.sessions.create_sandbox")
    @pytest.mark.asyncio
    async def test_create_session_explicit(self, mock_create_sandbox) -> None:
        """Test creating a session explicitly."""
        mock_sandbox = MagicMock()
        mock_sandbox.session_id = "explicit-sandbox-id"
        mock_create_sandbox.return_value = mock_sandbox

        manager = WorkspaceSessionManager()

        session = await manager.create_session("javascript", "custom-id")

        assert session.language == "javascript"
        assert session.workspace_id == "custom-id"
        assert session.sandbox_session_id == "explicit-sandbox-id"
        assert "custom-id" in manager._sessions
        # Verify create_sandbox was called with expected runtime
        assert mock_create_sandbox.called
        call_args = mock_create_sandbox.call_args
        assert call_args.kwargs["runtime"] == RuntimeType.JAVASCRIPT
        assert not call_args.kwargs["auto_persist_globals"]

    @pytest.mark.asyncio
    async def test_destroy_session_success(self) -> None:
        """Test destroying an existing session."""
        manager = WorkspaceSessionManager()

        # Create a session
        session = WorkspaceSession(
            workspace_id="destroy-test", language="python", sandbox_session_id="sandbox-destroy"
        )
        manager._sessions["destroy-test"] = session

        with patch("sandbox.delete_session_workspace") as mock_delete:
            result = await manager.destroy_session("destroy-test")

            assert result is True
            assert "destroy-test" not in manager._sessions
            mock_delete.assert_called_once_with("sandbox-destroy")

    @pytest.mark.asyncio
    async def test_destroy_session_not_found(self) -> None:
        """Test destroying a non-existent session."""
        manager = WorkspaceSessionManager()

        result = await manager.destroy_session("non-existent")

        assert result is False

    @pytest.mark.asyncio
    async def test_reset_session_success(self) -> None:
        """Test resetting a session successfully."""
        manager = WorkspaceSessionManager()

        # Create a session with some state
        session = WorkspaceSession(
            workspace_id="reset-test", language="python", sandbox_session_id="sandbox-reset"
        )
        session.execution_count = 5
        session.variables = ["x", "y"]
        session.imports = ["os"]
        manager._sessions["reset-test"] = session

        with patch("pathlib.Path") as mock_path:
            mock_workspace_path = MagicMock()
            mock_workspace_path.exists.return_value = True
            mock_workspace_path.iterdir.return_value = [
                MagicMock(is_file=MagicMock(return_value=True)),  # file
                MagicMock(
                    is_file=MagicMock(return_value=False), is_dir=MagicMock(return_value=True)
                ),  # dir
            ]
            mock_path.return_value = mock_workspace_path

            result = await manager.reset_session("reset-test")

            assert result is True
            assert session.execution_count == 0
            assert session.variables == []
            assert session.imports == []

    @pytest.mark.asyncio
    async def test_reset_session_not_found(self) -> None:
        """Test resetting a non-existent session."""
        manager = WorkspaceSessionManager()

        result = await manager.reset_session("non-existent")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_session_info_success(self) -> None:
        """Test getting session info successfully."""
        manager = WorkspaceSessionManager()

        # Create a session
        session = WorkspaceSession(
            workspace_id="info-test", language="python", sandbox_session_id="sandbox-info"
        )
        session.execution_count = 3
        session.variables = ["a", "b"]
        session.imports = ["sys"]
        manager._sessions["info-test"] = session

        with patch("sandbox.list_session_files") as mock_list_files:
            mock_list_files.return_value = ["/app/file1.py", "/app/file2.py"]

            info = await manager.get_session_info("info-test")

            assert info is not None
            assert info["workspace_id"] == "info-test"
            assert info["language"] == "python"
            assert info["execution_count"] == 3
            assert info["variables"] == ["a", "b"]
            assert info["imports"] == ["sys"]
            assert info["files"] == ["/app/file1.py", "/app/file2.py"]
            mock_list_files.assert_called_once_with("sandbox-info")

    @pytest.mark.asyncio
    async def test_get_session_info_not_found(self) -> None:
        """Test getting info for non-existent session."""
        manager = WorkspaceSessionManager()

        info = await manager.get_session_info("non-existent")

        assert info is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self) -> None:
        """Test cleaning up expired sessions."""
        manager = WorkspaceSessionManager()

        # Create expired and active sessions
        expired_session = WorkspaceSession(
            workspace_id="expired", language="python", sandbox_session_id="sandbox-expired"
        )
        expired_session.created_at = time.time() - 700
        expired_session.last_used_at = time.time() - 700

        active_session = WorkspaceSession(
            workspace_id="active", language="python", sandbox_session_id="sandbox-active"
        )

        manager._sessions["expired"] = expired_session
        manager._sessions["active"] = active_session

        await manager.cleanup()

        assert "expired" not in manager._sessions
        assert "active" in manager._sessions

    @pytest.mark.asyncio
    async def test_start_stop_cleanup_task(self) -> None:
        """Test starting and stopping cleanup task."""
        manager = WorkspaceSessionManager()

        # Start cleanup task
        await manager.start_cleanup_task()
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        # Stop cleanup task
        await manager.stop_cleanup_task()
        assert manager._cleanup_task is None


class TestSessionManagerIntegration:
    """Test session manager integration with MCP server."""

    @pytest.mark.asyncio
    async def test_server_uses_session_manager(self) -> None:
        """Test that MCP server properly integrates with session manager."""
        server = create_mcp_server()

        # Verify server has session manager
        assert hasattr(server, "session_manager")
        assert isinstance(server.session_manager, WorkspaceSessionManager)

    @pytest.mark.asyncio
    async def test_server_cleanup_on_shutdown(self) -> None:
        """Test that server cleans up sessions on shutdown."""
        server = create_mcp_server()

        # Mock cleanup
        server.session_manager.cleanup = AsyncMock()

        await server.shutdown()

        server.session_manager.cleanup.assert_called_once()
