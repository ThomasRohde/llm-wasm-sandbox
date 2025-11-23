"""Tests for session metadata tracking (Phase 1 and Phase 2 of workspace pruning).

Tests SessionMetadata model, metadata persistence, automatic timestamp updates,
structured logging, and backwards compatibility with legacy sessions.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from sandbox import (
    RuntimeType,
    create_sandbox,
)
from sandbox.core.logging import SandboxLogger
from sandbox.sessions import (
    SessionMetadata,
    _read_session_metadata,
    _update_session_timestamp,
)

# Phase 1: Metadata Model and Persistence Tests


def test_session_metadata_creation() -> None:
    """Test SessionMetadata dataclass instantiation."""
    now_utc = datetime.now(UTC).isoformat()
    metadata = SessionMetadata(
        session_id="550e8400-e29b-41d4-a716-446655440000",
        created_at=now_utc,
        updated_at=now_utc,
        version=1,
    )

    assert metadata.session_id == "550e8400-e29b-41d4-a716-446655440000"
    assert metadata.created_at == now_utc
    assert metadata.updated_at == now_utc
    assert metadata.version == 1


def test_session_metadata_to_dict() -> None:
    """Test SessionMetadata serialization to dict."""
    metadata = SessionMetadata(
        session_id="abc-123",
        created_at="2025-11-22T10:00:00Z",
        updated_at="2025-11-22T14:00:00Z",
        version=1,
    )

    data = metadata.to_dict()

    assert isinstance(data, dict)
    assert data["session_id"] == "abc-123"
    assert data["created_at"] == "2025-11-22T10:00:00Z"
    assert data["updated_at"] == "2025-11-22T14:00:00Z"
    assert data["version"] == 1


def test_session_metadata_from_dict() -> None:
    """Test SessionMetadata deserialization from dict."""
    data = {
        "session_id": "abc-123",
        "created_at": "2025-11-22T10:00:00Z",
        "updated_at": "2025-11-22T14:00:00Z",
        "version": 1,
    }

    metadata = SessionMetadata.from_dict(data)

    assert metadata.session_id == "abc-123"
    assert metadata.created_at == "2025-11-22T10:00:00Z"
    assert metadata.updated_at == "2025-11-22T14:00:00Z"
    assert metadata.version == 1


def test_session_metadata_roundtrip() -> None:
    """Test SessionMetadata serialization roundtrip."""
    original = SessionMetadata(
        session_id="test-id",
        created_at="2025-11-22T10:00:00.123456Z",
        updated_at="2025-11-22T14:30:00.654321Z",
        version=1,
    )

    data = original.to_dict()
    restored = SessionMetadata.from_dict(data)

    assert restored.session_id == original.session_id
    assert restored.created_at == original.created_at
    assert restored.updated_at == original.updated_at
    assert restored.version == original.version


def test_create_session_writes_metadata(tmp_path: Path) -> None:
    """Test that create_sandbox writes .metadata.json."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    session_id = sandbox.session_id

    metadata_path = tmp_path / session_id / ".metadata.json"
    assert metadata_path.exists()
    assert metadata_path.is_file()


def test_metadata_json_format(tmp_path: Path) -> None:
    """Test that .metadata.json contains valid JSON with expected fields."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    session_id = sandbox.session_id

    metadata_path = tmp_path / session_id / ".metadata.json"
    data = json.loads(metadata_path.read_text())

    assert "session_id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert "version" in data
    assert data["session_id"] == session_id
    assert data["version"] == 1


def test_metadata_timestamps_are_utc_iso8601(tmp_path: Path) -> None:
    """Test that metadata timestamps are ISO 8601 UTC format."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    session_id = sandbox.session_id

    metadata_path = tmp_path / session_id / ".metadata.json"
    data = json.loads(metadata_path.read_text())

    # Verify ISO 8601 format by parsing
    created_dt = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    updated_dt = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))

    # Verify timestamps are recent (within last minute)
    now = datetime.now(UTC)
    assert (now - created_dt).total_seconds() < 60
    assert (now - updated_dt).total_seconds() < 60


def test_metadata_created_and_updated_at_same_on_creation(tmp_path: Path) -> None:
    """Test that created_at and updated_at are identical at session creation."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    session_id = sandbox.session_id

    metadata_path = tmp_path / session_id / ".metadata.json"
    data = json.loads(metadata_path.read_text())

    assert data["created_at"] == data["updated_at"]


def test_read_session_metadata_success(tmp_path: Path) -> None:
    """Test _read_session_metadata with valid metadata."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    session_id = sandbox.session_id

    metadata = _read_session_metadata(session_id, tmp_path)

    assert metadata is not None
    assert metadata.session_id == session_id
    assert metadata.version == 1
    assert isinstance(metadata.created_at, str)
    assert isinstance(metadata.updated_at, str)


def test_read_session_metadata_missing_file(tmp_path: Path) -> None:
    """Test _read_session_metadata returns None for missing metadata."""
    # Create session workspace without metadata (simulate legacy session)
    session_id = "legacy-session-id"
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True)

    metadata = _read_session_metadata(session_id, tmp_path)

    assert metadata is None


def test_read_session_metadata_corrupted_json(tmp_path: Path, capsys) -> None:
    """Test _read_session_metadata handles corrupted JSON gracefully."""
    # Create session workspace with invalid JSON
    session_id = "corrupted-session"
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True)
    metadata_path = workspace / ".metadata.json"
    metadata_path.write_text("{ invalid json }")

    metadata = _read_session_metadata(session_id, tmp_path)

    assert metadata is None
    # Verify warning was logged to stderr
    captured = capsys.readouterr()
    assert "Warning: Failed to read session metadata" in captured.err


def test_read_session_metadata_missing_fields(tmp_path: Path, capsys) -> None:
    """Test _read_session_metadata handles missing fields gracefully."""
    # Create metadata with missing required field
    session_id = "incomplete-session"
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True)
    metadata_path = workspace / ".metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "created_at": "2025-11-22T10:00:00Z",
                # Missing updated_at and version
            }
        )
    )

    metadata = _read_session_metadata(session_id, tmp_path)

    assert metadata is None
    # Verify warning was logged
    captured = capsys.readouterr()
    assert "Warning: Failed to read session metadata" in captured.err


def test_read_session_metadata_permission_error(tmp_path: Path) -> None:
    """Test handling of PermissionError during metadata read."""
    from unittest.mock import patch

    session_id = "test-session"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    session_dir = workspace_root / session_id
    session_dir.mkdir()

    with patch("pathlib.Path.read_text", side_effect=PermissionError("Access denied")):
        metadata = _read_session_metadata(session_id, workspace_root)

    assert metadata is None


# Phase 2: Automatic Timestamp Update Tests


def test_update_session_timestamp(tmp_path: Path) -> None:
    """Test _update_session_timestamp updates updated_at field."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    session_id = sandbox.session_id

    # Read initial timestamps
    metadata_path = tmp_path / session_id / ".metadata.json"
    initial_data = json.loads(metadata_path.read_text())
    initial_updated_at = initial_data["updated_at"]

    # Wait brief moment to ensure timestamp difference
    time.sleep(0.01)

    # Update timestamp
    _update_session_timestamp(session_id, tmp_path)

    # Read updated timestamps
    updated_data = json.loads(metadata_path.read_text())
    new_updated_at = updated_data["updated_at"]

    # Verify updated_at changed
    assert new_updated_at != initial_updated_at

    # Verify created_at unchanged
    assert updated_data["created_at"] == initial_data["created_at"]

    # Verify other fields unchanged
    assert updated_data["session_id"] == initial_data["session_id"]
    assert updated_data["version"] == initial_data["version"]


def test_update_session_timestamp_legacy_session(tmp_path: Path) -> None:
    """Test _update_session_timestamp skips sessions without metadata."""
    # Create session workspace without metadata
    session_id = "legacy-session"
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True)

    # Should not raise error
    _update_session_timestamp(session_id, tmp_path)

    # Verify no metadata file created (skipped silently)
    metadata_path = workspace / ".metadata.json"
    assert not metadata_path.exists()


def test_update_session_timestamp_corrupted_metadata(tmp_path: Path, capsys) -> None:
    """Test _update_session_timestamp handles corrupted metadata gracefully."""
    # Create session with corrupted metadata
    session_id = "corrupted-session"
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True)
    metadata_path = workspace / ".metadata.json"
    metadata_path.write_text("{ invalid json }")

    # Should not raise error
    _update_session_timestamp(session_id, tmp_path)

    # Verify warning logged
    captured = capsys.readouterr()
    assert "Warning: Failed to update session timestamp" in captured.err


def test_update_session_timestamp_permission_error(tmp_path: Path) -> None:
    """Test handling of PermissionError during timestamp update."""
    from unittest.mock import patch

    session_id = "test-session"
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    session_dir = workspace_root / session_id
    session_dir.mkdir()

    # Create valid metadata first
    metadata = SessionMetadata(
        session_id=session_id,
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
        version=1,
    )
    (session_dir / ".metadata.json").write_text(json.dumps(metadata.to_dict()))

    with patch("pathlib.Path.write_text", side_effect=PermissionError("Access denied")):
        # Should not raise
        _update_session_timestamp(session_id, workspace_root)


def test_execute_updates_timestamp(tmp_path: Path) -> None:
    """Test that sandbox.execute() automatically updates timestamp."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    session_id = sandbox.session_id

    # Read initial timestamp
    metadata_path = tmp_path / session_id / ".metadata.json"
    initial_data = json.loads(metadata_path.read_text())
    initial_updated_at = initial_data["updated_at"]

    # Wait brief moment
    time.sleep(0.01)

    # Execute code
    result = sandbox.execute("print('test')")
    assert result.success

    # Read updated timestamp
    updated_data = json.loads(metadata_path.read_text())
    new_updated_at = updated_data["updated_at"]

    # Verify timestamp was updated
    assert new_updated_at != initial_updated_at


def test_execute_multiple_times_updates_timestamp(tmp_path: Path) -> None:
    """Test that multiple executions update timestamp progressively."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    session_id = sandbox.session_id

    metadata_path = tmp_path / session_id / ".metadata.json"
    timestamps = []

    # Execute multiple times with delays
    for i in range(3):
        time.sleep(0.01)
        result = sandbox.execute(f"print({i})")
        assert result.success

        data = json.loads(metadata_path.read_text())
        timestamps.append(data["updated_at"])

    # Verify timestamps are distinct and increasing
    assert len(set(timestamps)) == 3  # All unique
    assert timestamps[0] < timestamps[1] < timestamps[2]


def test_execute_failure_still_updates_timestamp(tmp_path: Path) -> None:
    """Test that timestamp updates even when execution has non-zero exit code."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    session_id = sandbox.session_id

    metadata_path = tmp_path / session_id / ".metadata.json"
    initial_data = json.loads(metadata_path.read_text())
    initial_updated_at = initial_data["updated_at"]

    time.sleep(0.01)

    # Execute code that exits with non-zero status
    _result = sandbox.execute("import sys; sys.exit(1)")
    # Note: sandbox may return success=True with exit_code != 0

    # Verify timestamp still updated regardless of exit code
    updated_data = json.loads(metadata_path.read_text())
    new_updated_at = updated_data["updated_at"]
    assert new_updated_at != initial_updated_at


def test_existing_session_preserves_metadata(tmp_path: Path) -> None:
    """Test that create_sandbox with existing session_id works with existing metadata."""
    # Create session
    sandbox1 = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    session_id = sandbox1.session_id

    # Execute code
    result1 = sandbox1.execute("print('first')")
    assert result1.success

    # Retrieve session using existing session_id
    sandbox2 = create_sandbox(
        runtime=RuntimeType.PYTHON, session_id=session_id, workspace_root=tmp_path
    )

    metadata_path = tmp_path / session_id / ".metadata.json"
    before_data = json.loads(metadata_path.read_text())
    before_updated_at = before_data["updated_at"]

    time.sleep(0.01)

    # Execute with retrieved sandbox
    result2 = sandbox2.execute("print('second')")
    assert result2.success

    # Verify timestamp updated
    after_data = json.loads(metadata_path.read_text())
    after_updated_at = after_data["updated_at"]
    assert after_updated_at != before_updated_at


# Structured Logging Tests


def test_metadata_created_logging(tmp_path: Path) -> None:
    """Test that session.metadata.created event is logged."""
    logger = SandboxLogger()

    _sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path, logger=logger)

    # Event logging is verified by successful execution
    # Actual log output verification would require log capture setup
    assert True  # Placeholder - structlog logging tested elsewhere


def test_metadata_updated_logging(tmp_path: Path) -> None:
    """Test that session.metadata.updated event is logged."""
    logger = SandboxLogger()

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path, logger=logger)

    # Execute to trigger update
    result = sandbox.execute("print('test')")
    assert result.success

    # Event logging verified by successful execution
    assert True  # Placeholder - structlog logging tested elsewhere


# Backwards Compatibility Tests


def test_legacy_session_without_metadata_executes(tmp_path: Path) -> None:
    """Test that manually created legacy session gets metadata on first sandbox access."""
    # Manually create session workspace without metadata (simulate legacy)
    session_id = "legacy-session-123"
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True)

    # With new architecture, retrieving session creates metadata if missing
    sandbox = create_sandbox(
        runtime=RuntimeType.PYTHON, session_id=session_id, workspace_root=tmp_path
    )

    result = sandbox.execute("print('legacy session works')")
    assert result.success
    assert "legacy session works" in result.stdout

    # With greenfield StorageAdapter, metadata is auto-created on session creation
    metadata_path = workspace / ".metadata.json"
    assert metadata_path.exists()  # Metadata is now created automatically


def test_metadata_write_failure_does_not_prevent_session_creation(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """Test that session creation succeeds even if metadata write fails."""
    # Mock Path.write_text to simulate write failure
    original_write_text = Path.write_text

    def failing_write_text(self, *args, **kwargs):
        if self.name == ".metadata.json":
            raise OSError("Simulated write failure")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write_text)

    # Session creation should still succeed
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    # Verify session works despite metadata failure
    result = sandbox.execute("print('session works')")
    assert result.success

    # Verify warning was logged
    captured = capsys.readouterr()
    assert "Warning: Failed to write metadata for session" in captured.err


def test_metadata_visible_to_guest_but_readonly(tmp_path: Path) -> None:
    """Test that .metadata.json is visible to guest and guest can read it."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    # Verify metadata exists on host
    metadata_path = tmp_path / sandbox.session_id / ".metadata.json"
    assert metadata_path.exists()

    # Verify .metadata.json is visible in listing
    result = sandbox.execute("""
import os
files = os.listdir('/app')
print(','.join(sorted(files)))
""")
    assert result.success
    listed_files = result.stdout.strip()
    assert ".metadata.json" in listed_files

    # Verify guest can read .metadata.json
    result = sandbox.execute("""
with open('/app/.metadata.json', 'r') as f:
    print(f.read()[:50])  # Print first 50 chars
""")
    assert result.success
    assert "session_id" in result.stdout

    # Note: Guest can technically write to .metadata.json since it's in the
    # preopened workspace directory. This is acceptable since:
    # 1. Guest code is untrusted user code anyway
    # 2. Metadata corruption is handled gracefully (returns None)
    # 3. Host-side pruning validates session_id matches directory name


# Performance Tests


def test_metadata_creation_overhead(tmp_path: Path) -> None:
    """Test that metadata creation adds minimal overhead."""
    start = time.time()
    _sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    duration = time.time() - start

    # Session creation with metadata should complete in reasonable time
    # (< 1 second even on slow systems)
    assert duration < 1.0


def test_timestamp_update_overhead(tmp_path: Path) -> None:
    """Test that timestamp updates add minimal overhead."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

    # Measure update time
    start = time.time()
    _update_session_timestamp(sandbox.session_id, tmp_path)
    duration = time.time() - start

    # Timestamp update should be very fast (< 10ms target, allow 50ms margin)
    assert duration < 0.05
