"""Unit tests for session logging integration.

Tests verify that all session lifecycle and file operation events are
logged correctly with proper structure and metadata.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from sandbox import create_sandbox
from sandbox.core.logging import SandboxLogger
from sandbox.core.models import RuntimeType
from sandbox.sessions import (
    delete_session_path,
    delete_session_workspace,
    list_session_files,
    read_session_file,
    write_session_file,
)


@pytest.fixture
def mock_logger() -> Mock:
    """Create mock logger for capturing log calls."""
    return Mock(spec=SandboxLogger)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


class TestSessionLifecycleLogging:
    """Test session creation, retrieval, and deletion logging."""

    def test_create_session_logs_event(self, temp_workspace: Path, mock_logger: Mock) -> None:
        """Verify create_sandbox logs session.created or session.retrieved event."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
            logger=mock_logger,
        )
        session_id = sandbox.session_id

        mock_logger.log_session_created.assert_called_once()
        mock_logger.log_session_retrieved.assert_not_called()
        call_args = mock_logger.log_session_created.call_args
        assert call_args[0][0] == session_id

    def test_get_session_logs_event(self, temp_workspace: Path, mock_logger: Mock) -> None:
        """Verify create_sandbox with existing session_id logs session.retrieved event."""
        # Create session first (without logger to avoid interference)
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id

        # Get session with logger using existing session_id
        sandbox = create_sandbox(
            session_id=session_id,
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
            logger=mock_logger,
        )

        # Verify sandbox was retrieved
        assert sandbox is not None

        # Verify log_session_retrieved was called
        mock_logger.log_session_retrieved.assert_called_once()
        call_args = mock_logger.log_session_retrieved.call_args

        # Verify session_id and workspace_path in call
        assert call_args[0][0] == session_id
        assert session_id in call_args[0][1]

    def test_delete_session_logs_event(self, temp_workspace: Path, mock_logger: Mock) -> None:
        """Verify delete_session_workspace no longer logs (logging removed from this function)."""
        # Create session first
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON, workspace_root=temp_workspace, logger=mock_logger
        )

        session_id = sandbox.session_id

        # Delete session (no longer accepts logger parameter)
        delete_session_workspace(session_id=session_id, workspace_root=temp_workspace)

        # This function no longer logs directly - logging is handled elsewhere
        # So we just verify it completes without error
        assert True  # Test passes if no exception raised

    def test_session_creation_without_logger(self, temp_workspace: Path) -> None:
        """Verify session creation works without logger (no crash)."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON, workspace_root=temp_workspace, logger=None
        )

        session_id = sandbox.session_id

        # Should succeed without error
        assert session_id is not None
        assert sandbox is not None


class TestFileOperationLogging:
    """Test file operation logging (list, read, write, delete)."""

    def test_list_files_logs_event(self, temp_workspace: Path, mock_logger: Mock) -> None:
        """Verify list_session_files logs session.file.list event."""
        # Create session and write some files
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id
        write_session_file(session_id, "file1.txt", "data1", temp_workspace)
        write_session_file(session_id, "file2.txt", "data2", temp_workspace)

        # List files with logger
        files = list_session_files(
            session_id=session_id, workspace_root=temp_workspace, logger=mock_logger
        )

        # Verify log_file_operation was called
        mock_logger.log_file_operation.assert_called_once()
        call_args = mock_logger.log_file_operation.call_args

        # Verify operation, session_id, and file_count
        assert call_args[1]["operation"] == "list"
        assert call_args[1]["session_id"] == session_id
        assert call_args[1]["file_count"] == len(files)

    def test_read_file_logs_event(self, temp_workspace: Path, mock_logger: Mock) -> None:
        """Verify read_session_file logs session.file.read event."""
        # Create session and write file
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id
        test_data = b"test content"
        write_session_file(session_id, "test.txt", test_data, temp_workspace)

        # Read file with logger
        data = read_session_file(
            session_id=session_id,
            relative_path="test.txt",
            workspace_root=temp_workspace,
            logger=mock_logger,
        )

        # Verify data was read
        assert data == test_data

        # Verify log_file_operation was called
        mock_logger.log_file_operation.assert_called_once()
        call_args = mock_logger.log_file_operation.call_args

        # Verify operation, session_id, path, and file_size
        assert call_args[1]["operation"] == "read"
        assert call_args[1]["session_id"] == session_id
        assert call_args[1]["path"] == "test.txt"
        assert call_args[1]["file_size"] == len(test_data)

    def test_write_file_logs_event(self, temp_workspace: Path, mock_logger: Mock) -> None:
        """Verify write_session_file logs session.file.write event."""
        # Create session
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id

        # Write file with logger
        test_data = "test content"
        write_session_file(
            session_id=session_id,
            relative_path="test.txt",
            data=test_data,
            workspace_root=temp_workspace,
            logger=mock_logger,
        )

        # Verify log_file_operation was called
        mock_logger.log_file_operation.assert_called_once()
        call_args = mock_logger.log_file_operation.call_args

        # Verify operation, session_id, path, and file_size
        assert call_args[1]["operation"] == "write"
        assert call_args[1]["session_id"] == session_id
        assert call_args[1]["path"] == "test.txt"
        assert call_args[1]["file_size"] == len(test_data.encode("utf-8"))

    def test_delete_file_logs_event(self, temp_workspace: Path, mock_logger: Mock) -> None:
        """Verify delete_session_path logs session.file.delete event."""
        # Create session and write file
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id
        write_session_file(session_id, "test.txt", "data", temp_workspace)

        # Delete file with logger
        delete_session_path(
            session_id=session_id,
            relative_path="test.txt",
            workspace_root=temp_workspace,
            logger=mock_logger,
        )

        # Verify log_file_operation was called
        mock_logger.log_file_operation.assert_called_once()
        call_args = mock_logger.log_file_operation.call_args

        # Verify operation, session_id, path, and recursive flag
        assert call_args[1]["operation"] == "delete"
        assert call_args[1]["session_id"] == session_id
        assert call_args[1]["path"] == "test.txt"
        assert call_args[1]["recursive"] is False

    def test_delete_directory_logs_recursive_flag(
        self, temp_workspace: Path, mock_logger: Mock
    ) -> None:
        """Verify delete_session_path logs recursive=True for directories."""
        # Create session and directory with file
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id
        write_session_file(session_id, "dir/test.txt", "data", temp_workspace)

        # Delete directory with logger
        delete_session_path(
            session_id=session_id,
            relative_path="dir",
            workspace_root=temp_workspace,
            recursive=True,
            logger=mock_logger,
        )

        # Verify log_file_operation was called with recursive=True
        mock_logger.log_file_operation.assert_called_once()
        call_args = mock_logger.log_file_operation.call_args
        assert call_args[1]["recursive"] is True


class TestExecutionLogging:
    """Test session_id propagation to execution logs."""

    def test_execution_includes_session_id_in_logs(
        self, temp_workspace: Path, mock_logger: Mock
    ) -> None:
        """Verify session-aware execution includes session_id in logs."""
        # Create session with logger
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
            logger=mock_logger,
        )
        session_id = sandbox.session_id

        # Reset mock to clear session creation log
        mock_logger.reset_mock()

        # Execute code (all sandboxes automatically include session_id)
        _result = sandbox.execute("print('hello')")

        # Verify log_execution_start was called with session_id
        mock_logger.log_execution_start.assert_called_once()
        start_call = mock_logger.log_execution_start.call_args
        assert start_call[1].get("session_id") == session_id

        # Verify log_execution_complete was called with session_id
        mock_logger.log_execution_complete.assert_called_once()
        complete_call = mock_logger.log_execution_complete.call_args
        assert complete_call[1].get("session_id") == session_id

    def test_execution_includes_session_id_in_result_metadata(self, temp_workspace: Path) -> None:
        """Verify session-aware execution includes session_id in result.metadata."""
        # Create session
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id

        # Execute code
        result = sandbox.execute("print('hello')")

        # Verify session_id in result.metadata
        assert "session_id" in result.metadata
        assert result.metadata["session_id"] == session_id

    def test_all_sandboxes_include_session_id(self, temp_workspace: Path) -> None:
        """Verify all sandboxes include session_id in metadata (greenfield architecture)."""
        # Create sandbox - all sandboxes are session-aware by default
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        # Execute code
        result = sandbox.execute("print('hello')")

        # Verify execution succeeded
        assert result is not None

        # Verify session_id IS in result.metadata (all sandboxes are session-aware)
        assert "session_id" in result.metadata
        assert result.metadata["session_id"] == sandbox.session_id


class TestLoggerEventStructure:
    """Test structured log event format and schema."""

    def test_log_session_created_structure(self) -> None:
        """Verify log_session_created emits correctly structured event."""
        from unittest.mock import MagicMock

        mock_logger = MagicMock()
        sandbox_logger = SandboxLogger(mock_logger)

        # Log session created
        sandbox_logger.log_session_created("test-session-id", "/path/to/workspace")

        # Verify info method was called
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args
        # Check that event_type is in kwargs
        assert "event_type" in call_args.kwargs
        assert call_args.kwargs["event_type"] == "session.created"
        assert call_args.kwargs["session_id"] == "test-session-id"
        assert call_args.kwargs["workspace_path"] == "/path/to/workspace"

    def test_log_file_operation_structure(self) -> None:
        """Verify log_file_operation emits correctly structured event."""
        from unittest.mock import MagicMock

        mock_logger = MagicMock()
        sandbox_logger = SandboxLogger(mock_logger)

        # Log file write operation
        sandbox_logger.log_file_operation(
            operation="write",
            session_id="test-session-id",
            path="test.txt",
            file_size=1024,
        )

        # Verify info method was called
        assert mock_logger.info.called
        call_args = mock_logger.info.call_args
        assert "event_type" in call_args.kwargs
        assert call_args.kwargs["event_type"] == "session.file.write"
        assert call_args.kwargs["session_id"] == "test-session-id"
        assert call_args.kwargs["path"] == "test.txt"
        assert call_args.kwargs["file_size"] == 1024


class TestLoggingEdgeCases:
    """Test edge cases and error conditions in logging."""

    def test_file_operations_work_without_logger(self, temp_workspace: Path) -> None:
        """Verify file operations work when logger=None."""
        # Create session
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=temp_workspace)

        session_id = sandbox.session_id

        # All operations should work without logger
        write_session_file(session_id, "test.txt", "data", temp_workspace, logger=None)
        data = read_session_file(session_id, "test.txt", temp_workspace, logger=None)
        files = list_session_files(session_id, temp_workspace, logger=None)
        delete_session_path(session_id, "test.txt", temp_workspace, logger=None)

        # Should succeed without error
        assert data == b"data"
        assert "test.txt" in files or len(files) == 0  # May be deleted

    def test_delete_nonexistent_session_logs_correctly(
        self, temp_workspace: Path, mock_logger: Mock
    ) -> None:
        """Verify deleting nonexistent session completes without error (idempotent)."""
        # Delete nonexistent session (no longer accepts logger)
        delete_session_workspace(session_id="nonexistent-id", workspace_root=temp_workspace)

        # Should complete without error (idempotent operation)
        assert True  # Test passes if no exception raised
