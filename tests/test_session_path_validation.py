"""Unit tests for session path validation and workspace creation (Phase 1).

Tests core security boundaries and edge cases for session management
infrastructure, including path traversal prevention and workspace isolation.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sandbox.sessions import _ensure_session_workspace, _validate_session_path


class TestValidateSessionPath:
    """Test _validate_session_path helper function."""

    def test_valid_relative_path(self, tmp_path: Path) -> None:
        """Valid relative paths should resolve correctly."""
        session_id = "test-session-123"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        # Create session workspace
        session_workspace = workspace_root / session_id
        session_workspace.mkdir()

        # Valid relative path
        result = _validate_session_path(session_id, "data.txt", workspace_root)
        assert result == session_workspace / "data.txt"
        assert result.is_absolute()

    def test_valid_nested_path(self, tmp_path: Path) -> None:
        """Valid nested relative paths should resolve correctly."""
        session_id = "test-session-456"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        session_workspace = workspace_root / session_id
        session_workspace.mkdir()

        result = _validate_session_path(session_id, "dir/subdir/file.txt", workspace_root)
        assert result == session_workspace / "dir/subdir/file.txt"

    def test_reject_parent_traversal(self, tmp_path: Path) -> None:
        """Paths with ../ should be rejected."""
        session_id = "test-session-789"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        session_workspace = workspace_root / session_id
        session_workspace.mkdir()

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            _validate_session_path(session_id, "../etc/passwd", workspace_root)

    def test_reject_absolute_path(self, tmp_path: Path) -> None:
        """Absolute paths should be rejected."""
        session_id = "test-session-abc"
        workspace_root = tmp_path / "workspace"

        # On Windows, absolute Unix paths like /etc/passwd get interpreted as C:\etc\passwd
        # which still escapes the workspace, so we check for "escapes" rather than "must be relative"
        with pytest.raises(
            ValueError, match=r"escapes session workspace boundary|must be relative"
        ):
            _validate_session_path(session_id, "/etc/passwd", workspace_root)

    def test_reject_session_id_with_separator(self, tmp_path: Path) -> None:
        """Session IDs with path separators should be rejected."""
        workspace_root = tmp_path / "workspace"

        # Test forward slash
        with pytest.raises(ValueError, match="must not contain path separators"):
            _validate_session_path("../etc", "passwd", workspace_root)

        # Test backslash
        with pytest.raises(ValueError, match="must not contain path separators"):
            _validate_session_path("..\\etc", "passwd", workspace_root)

        # Test os.sep
        with pytest.raises(ValueError, match="must not contain path separators"):
            _validate_session_path(f"test{os.sep}path", "file.txt", workspace_root)

    def test_custom_workspace_root(self, tmp_path: Path) -> None:
        """Custom workspace_root locations should work correctly."""
        session_id = "test-session-custom"
        custom_root = tmp_path / "custom_workspace"
        custom_root.mkdir()

        session_workspace = custom_root / session_id
        session_workspace.mkdir()

        result = _validate_session_path(session_id, "file.txt", custom_root)
        assert result == session_workspace / "file.txt"
        assert str(custom_root) in str(result)

    def test_empty_relative_path(self, tmp_path: Path) -> None:
        """Empty relative path should resolve to session workspace root."""
        session_id = "test-session-empty"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        session_workspace = workspace_root / session_id
        session_workspace.mkdir()

        result = _validate_session_path(session_id, ".", workspace_root)
        assert result.resolve() == session_workspace.resolve()

    def test_current_dir_reference(self, tmp_path: Path) -> None:
        """Current directory references (./) should work."""
        session_id = "test-session-current"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        session_workspace = workspace_root / session_id
        session_workspace.mkdir()

        result = _validate_session_path(session_id, "./data.txt", workspace_root)
        assert result == session_workspace / "data.txt"


class TestEnsureSessionWorkspace:
    """Test _ensure_session_workspace helper function."""

    def test_create_new_workspace(self, tmp_path: Path) -> None:
        """Should create new session workspace directory."""
        session_id = "new-session-123"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        result = _ensure_session_workspace(session_id, workspace_root)

        assert result.exists()
        assert result.is_dir()
        assert result == (workspace_root / session_id).resolve()

    def test_idempotent_on_existing_workspace(self, tmp_path: Path) -> None:
        """Should not error if workspace already exists."""
        session_id = "existing-session-456"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        # Create workspace first time
        result1 = _ensure_session_workspace(session_id, workspace_root)

        # Create workspace second time (should be idempotent)
        result2 = _ensure_session_workspace(session_id, workspace_root)

        assert result1 == result2
        assert result2.exists()

    def test_create_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories if workspace_root doesn't exist."""
        session_id = "test-session-nested"
        workspace_root = tmp_path / "deep" / "nested" / "workspace"

        result = _ensure_session_workspace(session_id, workspace_root)

        assert result.exists()
        assert workspace_root.exists()
        assert result == (workspace_root / session_id).resolve()

    def test_custom_workspace_root(self, tmp_path: Path) -> None:
        """Should work with custom workspace_root locations."""
        session_id = "custom-session-789"
        custom_root = tmp_path / "my_custom_workspaces"

        result = _ensure_session_workspace(session_id, custom_root)

        assert result.exists()
        assert result == (custom_root / session_id).resolve()
        assert str(custom_root) in str(result)

    def test_workspace_with_uuid_session_id(self, tmp_path: Path) -> None:
        """Should work with realistic UUIDv4 session IDs."""
        session_id = "550e8400-e29b-41d4-a716-446655440000"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        result = _ensure_session_workspace(session_id, workspace_root)

        assert result.exists()
        assert result.name == session_id

    def test_preserves_existing_files(self, tmp_path: Path) -> None:
        """Should not delete existing files in workspace."""
        session_id = "test-session-preserve"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        # Create workspace with a file
        session_workspace = workspace_root / session_id
        session_workspace.mkdir()
        test_file = session_workspace / "important.txt"
        test_file.write_text("important data")

        # Call ensure_session_workspace
        result = _ensure_session_workspace(session_id, workspace_root)

        # File should still exist
        assert test_file.exists()
        assert test_file.read_text() == "important data"
        assert result == session_workspace.resolve()


class TestPhase1Integration:
    """Integration tests for Phase 1 helpers working together."""

    def test_create_and_validate_path(self, tmp_path: Path) -> None:
        """Workspace creation should allow subsequent path validation."""
        session_id = "integration-test-001"
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        # Create workspace
        workspace = _ensure_session_workspace(session_id, workspace_root)
        assert workspace.exists()

        # Validate paths within workspace
        file_path = _validate_session_path(session_id, "data.txt", workspace_root)
        assert file_path.parent == workspace

    def test_multiple_sessions_isolated(self, tmp_path: Path) -> None:
        """Multiple sessions should have isolated workspaces."""
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()

        session1 = "session-aaa"
        session2 = "session-bbb"

        workspace1 = _ensure_session_workspace(session1, workspace_root)
        workspace2 = _ensure_session_workspace(session2, workspace_root)

        assert workspace1 != workspace2
        assert workspace1.exists() and workspace2.exists()

        # Paths should be isolated
        path1 = _validate_session_path(session1, "file.txt", workspace_root)
        path2 = _validate_session_path(session2, "file.txt", workspace_root)

        assert path1 != path2
        assert path1.parent == workspace1
        assert path2.parent == workspace2
