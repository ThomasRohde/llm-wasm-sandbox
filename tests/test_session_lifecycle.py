"""Integration tests for session lifecycle API (Phase 2).

Tests create_session_sandbox, get_session_sandbox, and delete_session_workspace
functions to verify session creation, retrieval, workspace persistence, and cleanup.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from sandbox import (
    RuntimeType,
    create_sandbox,
    delete_session_workspace,
)


def test_create_session_sandbox_generates_uuid(tmp_path: Path) -> None:
    """Test that create_session_sandbox generates valid UUIDv4."""
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id

    # Verify session_id is valid UUID format
    try:
        uuid_obj = uuid.UUID(session_id, version=4)
        assert str(uuid_obj) == session_id
    except ValueError:
        pytest.fail(f"session_id '{session_id}' is not a valid UUIDv4")


def test_create_session_sandbox_creates_workspace(tmp_path: Path) -> None:
    """Test that create_session_sandbox creates workspace directory."""
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id

    workspace = tmp_path / session_id
    assert workspace.exists()
    assert workspace.is_dir()


def test_create_session_sandbox_returns_sandbox_instance(tmp_path: Path) -> None:
    """Test that create_session_sandbox returns working sandbox."""
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id

    # Verify sandbox can execute code
    result = sandbox.execute("print('hello from session')")
    assert result.success
    assert "hello from session" in result.stdout


def test_create_session_sandbox_isolates_workspace(tmp_path: Path) -> None:
    """Test that session workspace is isolated to WASI guest."""
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id

    # Execute code that writes file
    result = sandbox.execute("""
with open('/app/test.txt', 'w') as f:
    f.write('session data')
print('written')
""")
    assert result.success

    # Verify file exists in session workspace on host
    session_workspace = tmp_path / session_id
    test_file = session_workspace / "test.txt"
    assert test_file.exists()
    assert test_file.read_text() == "session data"


def test_get_session_sandbox_reuses_workspace(tmp_path: Path) -> None:
    """Test that create_sandbox with existing session_id accesses existing workspace."""
    # Create session and write file
    sandbox1 = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox1.session_id
    result1 = sandbox1.execute("""
with open('/app/state.json', 'w') as f:
    f.write('{"count": 1}')
""")
    assert result1.success

    # Retrieve session and read file
    sandbox2 = create_sandbox(session_id=session_id,
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    result2 = sandbox2.execute("""
with open('/app/state.json', 'r') as f:
    print(f.read())
""")
    assert result2.success
    assert '{"count": 1}' in result2.stdout


def test_get_session_sandbox_creates_workspace_if_missing(tmp_path: Path) -> None:
    """Test that create_sandbox with explicit session_id creates workspace for new session_id."""
    # Use arbitrary UUID
    session_id = str(uuid.uuid4())
    workspace = tmp_path / session_id
    assert not workspace.exists()

    # Retrieve sandbox (should create workspace)
    sandbox = create_sandbox(session_id=session_id,
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )

    # Verify workspace was created
    assert workspace.exists()
    assert workspace.is_dir()

    # Verify sandbox can execute code
    result = sandbox.execute("print('ok')")
    assert result.success


def test_delete_session_workspace_removes_directory(tmp_path: Path) -> None:
    """Test that delete_session_workspace removes workspace."""
    # Create session
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id
    workspace = tmp_path / session_id
    assert workspace.exists()

    # Delete workspace
    delete_session_workspace(session_id, workspace_root=tmp_path)

    # Verify workspace is gone
    assert not workspace.exists()


def test_delete_session_workspace_removes_all_files(tmp_path: Path) -> None:
    """Test that delete_session_workspace removes workspace contents."""
    # Create session and write files
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id
    result = sandbox.execute("""
import os
os.makedirs('/app/subdir', exist_ok=True)
with open('/app/file1.txt', 'w') as f:
    f.write('data1')
with open('/app/subdir/file2.txt', 'w') as f:
    f.write('data2')
""")
    assert result.success

    workspace = tmp_path / session_id
    assert (workspace / "file1.txt").exists()
    assert (workspace / "subdir" / "file2.txt").exists()

    # Delete workspace
    delete_session_workspace(session_id, workspace_root=tmp_path)

    # Verify all files and subdirectories removed
    assert not workspace.exists()


def test_delete_session_workspace_idempotent(tmp_path: Path) -> None:
    """Test that delete_session_workspace is idempotent."""
    session_id = str(uuid.uuid4())

    # Delete nonexistent workspace (should not raise)
    delete_session_workspace(session_id, workspace_root=tmp_path)

    # Create and delete workspace
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id
    delete_session_workspace(session_id, workspace_root=tmp_path)

    # Delete again (should not raise)
    delete_session_workspace(session_id, workspace_root=tmp_path)


def test_delete_session_workspace_rejects_path_traversal(tmp_path: Path) -> None:
    """Test that delete_session_workspace validates session_id."""
    # Attempt path traversal via session_id
    with pytest.raises(ValueError, match="must not contain path separators"):
        delete_session_workspace("../etc", workspace_root=tmp_path)

    with pytest.raises(ValueError, match="must not contain path separators"):
        delete_session_workspace("foo/bar", workspace_root=tmp_path)

    with pytest.raises(ValueError, match="must not contain path separators"):
        delete_session_workspace("foo\\bar", workspace_root=tmp_path)


def test_session_isolation_between_sessions(tmp_path: Path) -> None:
    """Test that different sessions have isolated workspaces."""
    # Create two sessions
    sandbox_a = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id_a = sandbox_a.session_id

    sandbox_b = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id_b = sandbox_b.session_id

    # Write different files in each session
    result_a = sandbox_a.execute("""
with open('/app/data.txt', 'w') as f:
    f.write('session A data')
""")
    assert result_a.success

    result_b = sandbox_b.execute("""
with open('/app/data.txt', 'w') as f:
    f.write('session B data')
""")
    assert result_b.success

    # Verify each session sees only its own file
    result_read_a = sandbox_a.execute("print(open('/app/data.txt').read())")
    assert "session A data" in result_read_a.stdout
    assert "session B data" not in result_read_a.stdout

    result_read_b = sandbox_b.execute("print(open('/app/data.txt').read())")
    assert "session B data" in result_read_b.stdout
    assert "session A data" not in result_read_b.stdout


def test_session_persistence_across_executions(tmp_path: Path) -> None:
    """Test that session state persists across multiple executions."""
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON,
        workspace_root=tmp_path
    )
    session_id = sandbox.session_id

    # First execution: write counter
    result1 = sandbox.execute("""
with open('/app/counter.txt', 'w') as f:
    f.write('1')
print('wrote 1')
""")
    assert result1.success

    # Second execution: read and increment counter
    result2 = sandbox.execute("""
with open('/app/counter.txt', 'r') as f:
    count = int(f.read())
count += 1
with open('/app/counter.txt', 'w') as f:
    f.write(str(count))
print(f'incremented to {count}')
""")
    assert result2.success
    assert "incremented to 2" in result2.stdout

    # Third execution: verify counter persisted
    result3 = sandbox.execute("""
with open('/app/counter.txt', 'r') as f:
    print(f'counter is {f.read()}')
""")
    assert result3.success
    assert "counter is 2" in result3.stdout
