"""Unit tests for session file operation functions.

Tests verify list_session_files, read_session_file, write_session_file,
and delete_session_path functionality including security validation.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from sandbox.sessions import (
    delete_session_path,
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


class TestListSessionFiles:
    """Tests for list_session_files function."""

    def test_empty_workspace(self, session_id: str, temp_workspace: Path) -> None:
        """Empty workspace returns empty list."""
        # Create empty session workspace
        (temp_workspace / session_id).mkdir()

        files = list_session_files(session_id, workspace_root=temp_workspace)

        assert files == []

    def test_list_files_flat(self, session_id: str, temp_workspace: Path) -> None:
        """Lists files in flat directory structure."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        # Create test files
        (workspace / "file1.txt").write_text("data1")
        (workspace / "file2.txt").write_text("data2")
        (workspace / "data.json").write_text("{}")

        files = list_session_files(session_id, workspace_root=temp_workspace)

        assert sorted(files) == ["data.json", "file1.txt", "file2.txt"]

    def test_list_files_nested(self, session_id: str, temp_workspace: Path) -> None:
        """Lists files in nested directory structure."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        # Create nested structure
        (workspace / "root.txt").write_text("root")
        subdir = workspace / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")
        deep = subdir / "deep"
        deep.mkdir()
        (deep / "deep.txt").write_text("deep")

        files = list_session_files(session_id, workspace_root=temp_workspace)

        assert sorted(files) == ["root.txt", "subdir/deep/deep.txt", "subdir/nested.txt"]

    def test_list_excludes_directories(self, session_id: str, temp_workspace: Path) -> None:
        """Directory paths excluded from results."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        # Create directories and files
        (workspace / "file.txt").write_text("data")
        (workspace / "dir1").mkdir()
        (workspace / "dir2").mkdir()
        (workspace / "dir2" / "file2.txt").write_text("data2")

        files = list_session_files(session_id, workspace_root=temp_workspace)

        # Only files returned, not directory names
        assert sorted(files) == ["dir2/file2.txt", "file.txt"]

    def test_pattern_filter_extension(self, session_id: str, temp_workspace: Path) -> None:
        """Pattern filter matches by extension."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        # Create files with different extensions
        (workspace / "data.json").write_text("{}")
        (workspace / "text.txt").write_text("text")
        (workspace / "code.py").write_text("print('hello')")
        (workspace / "more.json").write_text("[]")

        json_files = list_session_files(session_id, workspace_root=temp_workspace, pattern="*.json")

        assert sorted(json_files) == ["data.json", "more.json"]

    def test_pattern_filter_recursive(self, session_id: str, temp_workspace: Path) -> None:
        """Recursive pattern matches nested files."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        # Create nested Python files
        (workspace / "main.py").write_text("import lib")
        lib = workspace / "lib"
        lib.mkdir()
        (lib / "helper.py").write_text("def help(): pass")
        tests = lib / "tests"
        tests.mkdir()
        (tests / "test_helper.py").write_text("def test(): pass")

        py_files = list_session_files(
            session_id, workspace_root=temp_workspace, pattern="**/*.py"
        )

        assert sorted(py_files) == ["lib/helper.py", "lib/tests/test_helper.py", "main.py"]

    def test_pattern_no_matches(self, session_id: str, temp_workspace: Path) -> None:
        """Pattern with no matches returns empty list."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        (workspace / "data.txt").write_text("data")

        files = list_session_files(session_id, workspace_root=temp_workspace, pattern="*.json")

        assert files == []

    def test_returns_posix_paths(self, session_id: str, temp_workspace: Path) -> None:
        """Returned paths use forward slashes on all platforms."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        subdir = workspace / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("data")

        files = list_session_files(session_id, workspace_root=temp_workspace)

        # Should be forward slash even on Windows
        assert files == ["subdir/file.txt"]
        assert "/" in files[0]
        assert "\\" not in files[0]


class TestReadSessionFile:
    """Tests for read_session_file function."""

    def test_read_text_file(self, session_id: str, temp_workspace: Path) -> None:
        """Reads text file as bytes."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        (workspace / "data.txt").write_text("Hello World", encoding="utf-8")

        data = read_session_file(session_id, "data.txt", workspace_root=temp_workspace)

        assert data == b"Hello World"
        assert data.decode("utf-8") == "Hello World"

    def test_read_binary_file(self, session_id: str, temp_workspace: Path) -> None:
        """Reads binary file as bytes."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        binary_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        (workspace / "image.png").write_bytes(binary_data)

        data = read_session_file(session_id, "image.png", workspace_root=temp_workspace)

        assert data == binary_data

    def test_read_nested_file(self, session_id: str, temp_workspace: Path) -> None:
        """Reads file from nested directory."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        subdir = workspace / "data" / "output"
        subdir.mkdir(parents=True)
        (subdir / "result.json").write_text('{"result": 42}')

        data = read_session_file(
            session_id, "data/output/result.json", workspace_root=temp_workspace
        )

        assert data == b'{"result": 42}'

    def test_read_missing_file_raises_error(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """FileNotFoundError raised for missing file."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        with pytest.raises(FileNotFoundError):
            read_session_file(session_id, "nonexistent.txt", workspace_root=temp_workspace)

    def test_read_directory_raises_error(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Error raised when path is directory (IsADirectoryError or PermissionError on Windows)."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        (workspace / "dir").mkdir()

        with pytest.raises((IsADirectoryError, PermissionError)):
            read_session_file(session_id, "dir", workspace_root=temp_workspace)

    def test_path_traversal_rejected(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Path traversal attempts blocked."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        with pytest.raises(ValueError, match="escapes session workspace"):
            read_session_file(session_id, "../etc/passwd", workspace_root=temp_workspace)

    def test_absolute_path_rejected(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Absolute paths rejected."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        with pytest.raises(ValueError, match="escapes session workspace"):
            read_session_file(session_id, "/etc/passwd", workspace_root=temp_workspace)


class TestWriteSessionFile:
    """Tests for write_session_file function."""

    def test_write_text_file(self, session_id: str, temp_workspace: Path) -> None:
        """Writes text data to file."""
        write_session_file(
            session_id, "output.txt", "Hello from host", workspace_root=temp_workspace
        )

        file_path = temp_workspace / session_id / "output.txt"
        assert file_path.exists()
        assert file_path.read_text(encoding="utf-8") == "Hello from host"

    def test_write_binary_file(self, session_id: str, temp_workspace: Path) -> None:
        """Writes binary data to file."""
        binary_data = b"\x89PNG\r\n\x1a\n"
        write_session_file(
            session_id, "image.png", binary_data, workspace_root=temp_workspace
        )

        file_path = temp_workspace / session_id / "image.png"
        assert file_path.exists()
        assert file_path.read_bytes() == binary_data

    def test_write_creates_nested_directories(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Parent directories created automatically."""
        write_session_file(
            session_id,
            "data/config/settings.json",
            '{"key": "value"}',
            workspace_root=temp_workspace,
        )

        file_path = temp_workspace / session_id / "data" / "config" / "settings.json"
        assert file_path.exists()
        assert file_path.read_text() == '{"key": "value"}'

    def test_write_overwrites_by_default(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Existing file overwritten by default."""
        # Write initial content
        write_session_file(
            session_id, "data.txt", "original", workspace_root=temp_workspace
        )

        # Overwrite
        write_session_file(
            session_id, "data.txt", "updated", workspace_root=temp_workspace
        )

        file_path = temp_workspace / session_id / "data.txt"
        assert file_path.read_text() == "updated"

    def test_write_respects_overwrite_false(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """FileExistsError raised when overwrite=False."""
        # Write initial file
        write_session_file(
            session_id, "data.txt", "original", workspace_root=temp_workspace
        )

        # Attempt to overwrite with flag set to False
        with pytest.raises(FileExistsError, match="already exists"):
            write_session_file(
                session_id,
                "data.txt",
                "new",
                workspace_root=temp_workspace,
                overwrite=False,
            )

        # Original content preserved
        file_path = temp_workspace / session_id / "data.txt"
        assert file_path.read_text() == "original"

    def test_write_overwrite_false_creates_new_file(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """overwrite=False succeeds for new files."""
        write_session_file(
            session_id,
            "new.txt",
            "data",
            workspace_root=temp_workspace,
            overwrite=False,
        )

        file_path = temp_workspace / session_id / "new.txt"
        assert file_path.exists()
        assert file_path.read_text() == "data"

    def test_path_traversal_rejected(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Path traversal attempts blocked."""
        with pytest.raises(ValueError, match="escapes session workspace"):
            write_session_file(
                session_id, "../etc/evil", "data", workspace_root=temp_workspace
            )

    def test_absolute_path_rejected(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Absolute paths rejected."""
        with pytest.raises(ValueError, match="escapes session workspace"):
            write_session_file(
                session_id, "/etc/evil", "data", workspace_root=temp_workspace
            )

    def test_string_auto_encoded_utf8(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """String data automatically UTF-8 encoded."""
        write_session_file(
            session_id, "text.txt", "Hello 世界", workspace_root=temp_workspace
        )

        file_path = temp_workspace / session_id / "text.txt"
        assert file_path.read_bytes() == "Hello 世界".encode()


class TestDeleteSessionPath:
    """Tests for delete_session_path function."""

    def test_delete_file(self, session_id: str, temp_workspace: Path) -> None:
        """Deletes single file."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        file_path = workspace / "temp.txt"
        file_path.write_text("temporary")

        delete_session_path(session_id, "temp.txt", workspace_root=temp_workspace)

        assert not file_path.exists()

    def test_delete_nested_file(self, session_id: str, temp_workspace: Path) -> None:
        """Deletes file in nested directory."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        subdir = workspace / "data"
        subdir.mkdir()
        file_path = subdir / "temp.txt"
        file_path.write_text("temporary")

        delete_session_path(session_id, "data/temp.txt", workspace_root=temp_workspace)

        assert not file_path.exists()
        assert subdir.exists()  # Parent directory remains

    def test_delete_directory_requires_recursive(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Raises ValueError if directory deleted without recursive=True."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        dir_path = workspace / "cache"
        dir_path.mkdir()
        (dir_path / "file.txt").write_text("data")

        with pytest.raises(ValueError, match="without recursive=True"):
            delete_session_path(session_id, "cache", workspace_root=temp_workspace)

        # Directory still exists
        assert dir_path.exists()

    def test_delete_directory_recursive(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Deletes directory recursively when recursive=True."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        dir_path = workspace / "cache"
        dir_path.mkdir()
        (dir_path / "file1.txt").write_text("data1")
        subdir = dir_path / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("data2")

        delete_session_path(
            session_id, "cache", workspace_root=temp_workspace, recursive=True
        )

        assert not dir_path.exists()

    def test_delete_empty_directory_recursive(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Deletes empty directory when recursive=True."""
        workspace = temp_workspace / session_id
        workspace.mkdir()
        dir_path = workspace / "empty"
        dir_path.mkdir()

        delete_session_path(
            session_id, "empty", workspace_root=temp_workspace, recursive=True
        )

        assert not dir_path.exists()

    def test_delete_missing_file_raises_error(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """FileNotFoundError raised for missing file."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        with pytest.raises(FileNotFoundError):
            delete_session_path(
                session_id, "nonexistent.txt", workspace_root=temp_workspace
            )

    def test_path_traversal_rejected(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Path traversal attempts blocked."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        with pytest.raises(ValueError, match="escapes session workspace"):
            delete_session_path(
                session_id, "../etc/passwd", workspace_root=temp_workspace
            )

    def test_absolute_path_rejected(
        self, session_id: str, temp_workspace: Path
    ) -> None:
        """Absolute paths rejected."""
        workspace = temp_workspace / session_id
        workspace.mkdir()

        with pytest.raises(ValueError, match="escapes session workspace"):
            delete_session_path(session_id, "/etc/passwd", workspace_root=temp_workspace)
