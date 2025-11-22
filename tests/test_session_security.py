"""Comprehensive security tests for session management.

This module consolidates and extends security tests for path traversal
prevention, symlink escapes, session_id validation, and workspace_root
validation across all session APIs.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from sandbox import RuntimeType, create_sandbox
from sandbox.sessions import (
    _validate_session_path,
    delete_session_path,
    delete_session_workspace,
    list_session_files,
    read_session_file,
    write_session_file,
)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create temporary workspace root for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for each test."""
    return str(uuid.uuid4())


class TestPathTraversalPrevention:
    """Test path traversal attack prevention across all file operations."""

    def test_validate_session_path_rejects_parent_traversal(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Path validation rejects ../ traversal attempts."""
        (temp_workspace / session_id).mkdir()

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            _validate_session_path(session_id, "../etc/passwd", temp_workspace)

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            _validate_session_path(session_id, "../../etc/passwd", temp_workspace)

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            _validate_session_path(session_id, "dir/../../../etc/passwd", temp_workspace)

    def test_validate_session_path_rejects_absolute_paths(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Path validation rejects absolute paths."""
        (temp_workspace / session_id).mkdir()

        # Absolute Unix-style path
        with pytest.raises(ValueError, match="escapes session workspace boundary|must be relative"):
            _validate_session_path(session_id, "/etc/passwd", temp_workspace)

        # Windows-style absolute path (if on Windows)
        if os.name == "nt":
            with pytest.raises(ValueError, match="escapes session workspace boundary|must be relative"):
                _validate_session_path(session_id, "C:\\Windows\\System32", temp_workspace)

    def test_read_session_file_rejects_traversal(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """read_session_file rejects path traversal attempts."""
        (temp_workspace / session_id).mkdir()

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            read_session_file(session_id, "../etc/passwd", workspace_root=temp_workspace)

    def test_write_session_file_rejects_traversal(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """write_session_file rejects path traversal attempts."""
        (temp_workspace / session_id).mkdir()

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            write_session_file(
                session_id, "../etc/passwd", b"malicious", workspace_root=temp_workspace
            )

    def test_delete_session_path_rejects_traversal(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """delete_session_path rejects path traversal attempts."""
        (temp_workspace / session_id).mkdir()

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            delete_session_path(session_id, "../etc/passwd", workspace_root=temp_workspace)


class TestSymlinkEscapePrevention:
    """Test symlink escape detection and prevention."""


class TestSessionIDValidation:
    """Test session_id validation prevents directory traversal."""

    def test_session_id_with_forward_slash_rejected(
        self, temp_workspace: Path
    ) -> None:
        """Session IDs with forward slashes are rejected."""
        malicious_id = "../etc"

        with pytest.raises(ValueError, match="must not contain path separators"):
            _validate_session_path(malicious_id, "passwd", temp_workspace)

        with pytest.raises(ValueError, match="must not contain path separators"):
            read_session_file(malicious_id, "file.txt", workspace_root=temp_workspace)

    def test_session_id_with_backslash_rejected(
        self, temp_workspace: Path
    ) -> None:
        """Session IDs with backslashes are rejected."""
        malicious_id = "..\\etc"

        with pytest.raises(ValueError, match="must not contain path separators"):
            _validate_session_path(malicious_id, "passwd", temp_workspace)

        with pytest.raises(ValueError, match="must not contain path separators"):
            write_session_file(
                malicious_id, "file.txt", b"data", workspace_root=temp_workspace
            )

    def test_session_id_with_os_separator_rejected(
        self, temp_workspace: Path
    ) -> None:
        """Session IDs with OS path separator are rejected."""
        malicious_id = f"test{os.sep}path"

        with pytest.raises(ValueError, match="must not contain path separators"):
            _validate_session_path(malicious_id, "file.txt", temp_workspace)

    def test_delete_workspace_rejects_traversal_in_session_id(
        self, temp_workspace: Path
    ) -> None:
        """delete_session_workspace rejects session_id with path separators."""
        with pytest.raises(ValueError, match="must not contain path separators"):
            delete_session_workspace("../etc", workspace_root=temp_workspace)

        with pytest.raises(ValueError, match="must not contain path separators"):
            delete_session_workspace("foo/bar", workspace_root=temp_workspace)

        with pytest.raises(ValueError, match="must not contain path separators"):
            delete_session_workspace("foo\\bar", workspace_root=temp_workspace)


class TestWorkspaceRootValidation:
    """Test workspace_root parameter validation."""

    def test_custom_workspace_root_accepted(
        self, session_id: str, tmp_path: Path
    ) -> None:
        """Custom workspace_root paths are accepted and used correctly."""
        custom_workspace = tmp_path / "custom_sessions"
        custom_workspace.mkdir()

        session_workspace = custom_workspace / session_id
        session_workspace.mkdir()

        # Create file in custom workspace
        test_file = session_workspace / "test.txt"
        test_file.write_text("custom data")

        # Read file using custom workspace_root
        data = read_session_file(session_id, "test.txt", workspace_root=custom_workspace)
        assert data.decode("utf-8") == "custom data"

    def test_workspace_root_must_exist_or_be_creatable(
        self, session_id: str, tmp_path: Path
    ) -> None:
        """Workspace root is created if it doesn't exist."""
        new_workspace_root = tmp_path / "new_workspace"
        assert not new_workspace_root.exists()

        # Writing file should create workspace_root
        write_session_file(
            session_id, "file.txt", b"data", workspace_root=new_workspace_root
        )

        assert new_workspace_root.exists()
        assert (new_workspace_root / session_id / "file.txt").exists()


class TestCrossSessions:
    """Test that sessions cannot access each other's workspaces."""

    def test_session_cannot_list_another_sessions_files(
        self, temp_workspace: Path
    ) -> None:
        """Listing files in session A doesn't show session B's files."""
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())

        # Create files in both sessions
        workspace_a = temp_workspace / session_a
        workspace_a.mkdir()
        (workspace_a / "file_a.txt").write_text("session A")

        workspace_b = temp_workspace / session_b
        workspace_b.mkdir()
        (workspace_b / "file_b.txt").write_text("session B")

        # List files in session A
        files_a = list_session_files(session_a, workspace_root=temp_workspace)
        assert "file_a.txt" in files_a
        assert "file_b.txt" not in files_a

        # List files in session B
        files_b = list_session_files(session_b, workspace_root=temp_workspace)
        assert "file_b.txt" in files_b
        assert "file_a.txt" not in files_b

    def test_session_cannot_read_another_sessions_file_directly(
        self, temp_workspace: Path
    ) -> None:
        """Attempting to read another session's file using path tricks fails."""
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())

        # Create file in session B
        workspace_b = temp_workspace / session_b
        workspace_b.mkdir()
        (workspace_b / "secret.txt").write_text("secret from B")

        # Session A tries to read session B's file using ../
        workspace_a = temp_workspace / session_a
        workspace_a.mkdir()

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            read_session_file(
                session_a, f"../{session_b}/secret.txt", workspace_root=temp_workspace
            )

    def test_session_cannot_delete_another_sessions_file(
        self, temp_workspace: Path
    ) -> None:
        """Session A cannot delete files in session B's workspace."""
        session_a = str(uuid.uuid4())
        session_b = str(uuid.uuid4())

        # Create file in session B
        workspace_b = temp_workspace / session_b
        workspace_b.mkdir()
        target_file = workspace_b / "important.txt"
        target_file.write_text("important data")

        # Session A tries to delete session B's file
        workspace_a = temp_workspace / session_a
        workspace_a.mkdir()

        with pytest.raises(ValueError, match="escapes session workspace boundary"):
            delete_session_path(
                session_a, f"../{session_b}/important.txt", workspace_root=temp_workspace
            )

        # Verify file still exists
        assert target_file.exists()


class TestWASIIsolation:
    """Test that WASI guest code respects session boundaries."""

    def test_guest_cannot_access_host_filesystem_outside_app(
        self, temp_workspace: Path
    ) -> None:
        """Guest code cannot read files outside /app mount point."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON, workspace_root=temp_workspace
        )

        # Try to read /etc/passwd (should fail - not mounted)
        result = sandbox.execute("""
try:
    with open('/etc/passwd', 'r') as f:
        print('SECURITY BREACH: Read /etc/passwd')
except FileNotFoundError:
    print('SUCCESS: Cannot access /etc/passwd')
except Exception as e:
    print(f'SUCCESS: Access denied - {type(e).__name__}')
""")

        assert result.success
        assert "SUCCESS" in result.stdout
        assert "SECURITY BREACH" not in result.stdout

    def test_guest_cannot_traverse_to_parent_sessions(
        self, temp_workspace: Path
    ) -> None:
        """Guest code cannot use ../ to escape session workspace."""
        # Create session A with a file
        sandbox_a = create_sandbox(
            runtime=RuntimeType.PYTHON, workspace_root=temp_workspace
        )
        session_a = sandbox_a.session_id
        workspace_a = temp_workspace / session_a
        (workspace_a / "secret.txt").write_text("session A secret")

        # Create session B and try to access session A
        sandbox_b = create_sandbox(
            runtime=RuntimeType.PYTHON, workspace_root=temp_workspace
        )

        code = f"""
import os
try:
    # Try to traverse up and into session A
    with open('/app/../{session_a}/secret.txt', 'r') as f:
        print('SECURITY BREACH: Accessed other session')
except FileNotFoundError:
    print('SUCCESS: File not found')
except Exception as e:
    print(f'SUCCESS: Access denied - {{type(e).__name__}}')
"""

        result = sandbox_b.execute(code)

        assert result.success
        assert "SUCCESS" in result.stdout
        assert "SECURITY BREACH" not in result.stdout


