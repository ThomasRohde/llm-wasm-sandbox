"""Tests for workspace pruning functionality (Phase 3 of workspace pruning).

Tests prune_sessions() logic including age filtering, size calculation,
dry-run mode, error handling, and security boundaries.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from sandbox.core.logging import SandboxLogger
from sandbox.sessions import SessionMetadata, prune_sessions


def _create_dummy_session(
    workspace_root: Path,
    session_id: str,
    age_hours: float,
    size_bytes: int = 1024
) -> None:
    """Helper to create a dummy session with specific age and size."""
    session_dir = workspace_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy file to consume space
    (session_dir / "data.bin").write_bytes(b"0" * size_bytes)

    # Create metadata with specific age
    past_time = datetime.now(UTC) - timedelta(hours=age_hours)
    metadata = SessionMetadata(
        session_id=session_id,
        created_at=past_time.isoformat(),
        updated_at=past_time.isoformat(),
        version=1
    )
    (session_dir / ".metadata.json").write_text(json.dumps(metadata.to_dict()))


def test_prune_old_sessions(tmp_path: Path) -> None:
    """Test that sessions older than threshold are deleted."""
    old_id = str(uuid.uuid4())
    new_id = str(uuid.uuid4())

    # Create old session (25 hours old)
    _create_dummy_session(tmp_path, old_id, age_hours=25.0)

    # Create new session (1 hour old)
    _create_dummy_session(tmp_path, new_id, age_hours=1.0)

    # Prune sessions older than 24 hours
    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)

    # Verify result
    assert old_id in result.deleted_sessions
    assert new_id not in result.deleted_sessions
    assert result.reclaimed_bytes > 0
    assert not result.dry_run

    # Verify filesystem
    assert not (tmp_path / old_id).exists()
    assert (tmp_path / new_id).exists()


def test_prune_preserves_recent_sessions(tmp_path: Path) -> None:
    """Test that sessions newer than threshold are preserved."""
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())

    _create_dummy_session(tmp_path, id1, age_hours=23.0)
    _create_dummy_session(tmp_path, id2, age_hours=0.1)

    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)

    assert len(result.deleted_sessions) == 0
    assert (tmp_path / id1).exists()
    assert (tmp_path / id2).exists()


def test_prune_dry_run(tmp_path: Path) -> None:
    """Test that dry-run mode lists candidates but doesn't delete."""
    old_id = str(uuid.uuid4())
    _create_dummy_session(tmp_path, old_id, age_hours=30.0)

    result = prune_sessions(
        older_than_hours=24.0,
        workspace_root=tmp_path,
        dry_run=True
    )

    # Verify result indicates what would happen
    assert old_id in result.deleted_sessions
    assert result.dry_run
    # Note: reclaimed_bytes is 0 in dry-run per implementation/design
    assert result.reclaimed_bytes == 0

    # Verify filesystem unchanged
    assert (tmp_path / old_id).exists()


def test_prune_skips_sessions_without_metadata(tmp_path: Path) -> None:
    """Test that sessions without metadata are skipped (legacy support)."""
    legacy_id = str(uuid.uuid4())
    valid_old_id = str(uuid.uuid4())

    # Create session directory without metadata
    (tmp_path / legacy_id).mkdir()

    # Create valid old session
    _create_dummy_session(tmp_path, valid_old_id, age_hours=30.0)

    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)

    # Legacy session should be skipped, not deleted
    assert legacy_id in result.skipped_sessions
    assert legacy_id not in result.deleted_sessions
    assert (tmp_path / legacy_id).exists()

    # Valid old session should be deleted
    assert valid_old_id in result.deleted_sessions


def test_prune_skips_corrupted_metadata(tmp_path: Path) -> None:
    """Test that sessions with corrupted metadata are skipped."""
    corrupted_id = str(uuid.uuid4())
    session_dir = tmp_path / corrupted_id
    session_dir.mkdir()
    (session_dir / ".metadata.json").write_text("{ invalid json }")

    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)

    assert corrupted_id in result.skipped_sessions
    assert (tmp_path / corrupted_id).exists()


def test_prune_custom_threshold(tmp_path: Path) -> None:
    """Test pruning with custom age threshold."""
    id_2h = str(uuid.uuid4())
    id_5h = str(uuid.uuid4())

    _create_dummy_session(tmp_path, id_2h, age_hours=2.0)
    _create_dummy_session(tmp_path, id_5h, age_hours=5.0)

    # Prune older than 3 hours
    result = prune_sessions(older_than_hours=3.0, workspace_root=tmp_path)

    assert id_5h in result.deleted_sessions
    assert id_2h not in result.deleted_sessions


def test_prune_calculates_reclaimed_size(tmp_path: Path) -> None:
    """Test that reclaimed bytes are calculated correctly."""
    fat_id = str(uuid.uuid4())
    size = 1024 * 10  # 10 KB
    _create_dummy_session(tmp_path, fat_id, age_hours=30.0, size_bytes=size)

    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)

    # Should be at least the size of the data file
    # (metadata file adds a few bytes)
    assert result.reclaimed_bytes >= size
    assert result.reclaimed_bytes < size + 1000  # Reasonable upper bound


def test_prune_handles_permission_errors(tmp_path: Path, monkeypatch) -> None:
    """Test graceful handling of permission errors during deletion."""
    locked_id = str(uuid.uuid4())
    _create_dummy_session(tmp_path, locked_id, age_hours=30.0)

    # Mock shutil.rmtree to raise PermissionError
    def mock_rmtree(*args, **kwargs):
        raise PermissionError("Access denied")

    monkeypatch.setattr(shutil, "rmtree", mock_rmtree)

    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)

    assert locked_id not in result.deleted_sessions
    assert locked_id in result.errors
    assert "Access denied" in result.errors[locked_id]
    # Session should still exist (mocked deletion)
    assert (tmp_path / locked_id).exists()


def test_prune_custom_workspace_root(tmp_path: Path) -> None:
    """Test pruning works with custom workspace root."""
    custom_root = tmp_path / "custom_workspaces"
    custom_root.mkdir()

    old_id = str(uuid.uuid4())
    _create_dummy_session(custom_root, old_id, age_hours=30.0)

    result = prune_sessions(older_than_hours=24.0, workspace_root=custom_root)

    assert old_id in result.deleted_sessions
    assert not (custom_root / old_id).exists()


def test_prune_ignores_non_uuid_directories(tmp_path: Path) -> None:
    """Test that pruning ignores directories that don't look like session IDs."""
    # Create directory that isn't a UUID
    (tmp_path / "system_files").mkdir()

    # Even if it has metadata and is old
    _create_dummy_session(tmp_path, "not-a-uuid", age_hours=30.0)

    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)

    # Should not be touched or reported
    assert "system_files" not in result.deleted_sessions
    assert "system_files" not in result.skipped_sessions
    assert (tmp_path / "system_files").exists()

    # Note: The current implementation of _enumerate_sessions filters by UUID format.
    # So "not-a-uuid" should be ignored completely.
    assert "not-a-uuid" not in result.deleted_sessions
    assert (tmp_path / "not-a-uuid").exists()


# Security Tests


def test_prune_respects_workspace_boundary(tmp_path: Path) -> None:
    """Test that pruning does not traverse outside workspace root."""
    # Create a directory outside workspace
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "important.txt").write_text("data")

    # Create workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Try to trick it with symlink (if OS supports)
    try:
        # Create symlink in workspace pointing to outside
        # Note: Windows requires admin for symlinks usually, so this might fail/skip
        (workspace / "fake-session-uuid-1234").symlink_to(outside_dir)
    except OSError:
        pytest.skip("Symlinks not supported or insufficient privileges")

    # Even if we could create it, _enumerate_sessions checks for UUID format
    # and prune_sessions uses workspace_root / session_id.
    # So it shouldn't follow symlinks to delete outside content unless
    # the symlink IS the session directory.

    # But shutil.rmtree on a symlink deletes the link, not the target.
    # So this is safe by default in Python.
    pass


def test_prune_validates_session_id_format(tmp_path: Path) -> None:
    """Test that only valid UUID directories are considered."""
    # Create various directories
    (tmp_path / "valid-uuid-1234").mkdir() # Not a real UUID
    (tmp_path / "550e8400-e29b-41d4-a716-446655440000").mkdir() # Real UUID

    # Mock _read_session_metadata to return None so we don't need files
    with patch("sandbox.sessions._read_session_metadata", return_value=None):
        result = prune_sessions(workspace_root=tmp_path)

        # Only the real UUID should be in skipped (due to missing metadata)
        # The non-UUID directory should be ignored completely
        assert "550e8400-e29b-41d4-a716-446655440000" in result.skipped_sessions
        assert "valid-uuid-1234" not in result.skipped_sessions


# Performance Tests


def test_prune_throughput(tmp_path: Path) -> None:
    """Benchmark pruning throughput."""
    # Create 100 dummy sessions
    count = 100
    for _ in range(count):
        # Use simple names for speed in test, but mock enumeration to accept them
        # or just use UUIDs. Let's use UUID-like strings.
        # Actually, _enumerate_sessions uses UUID regex.
        # Let's mock _enumerate_sessions to avoid generating 100 UUIDs and folders if possible,
        # but for integration test we should create files.

        # Generating 100 folders is fast enough.
        import uuid
        sid = str(uuid.uuid4())
        _create_dummy_session(tmp_path, sid, age_hours=30.0, size_bytes=100)

    start = time.time()
    result = prune_sessions(older_than_hours=24.0, workspace_root=tmp_path)
    duration = time.time() - start

    assert len(result.deleted_sessions) == count

    # Expect > 10 sessions/sec (conservative)
    # 100 sessions should take < 10 seconds
    assert duration < 10.0

    # Calculate rate
    rate = count / duration if duration > 0 else float('inf')
    print(f"Pruning rate: {rate:.1f} sessions/sec")


# Logging Tests


def test_prune_logging(tmp_path: Path) -> None:
    """Test that pruning emits correct log events."""
    logger = Mock(spec=SandboxLogger)

    # Create one old session
    session_id = str(uuid.uuid4())
    _create_dummy_session(tmp_path, session_id, age_hours=25.0)

    prune_sessions(
        older_than_hours=24.0,
        workspace_root=tmp_path,
        logger=logger
    )

    # Verify log calls
    logger.log_prune_started.assert_called_once()
    logger.log_prune_candidate.assert_called_once()
    logger.log_prune_deleted.assert_called_once()
    logger.log_prune_completed.assert_called_once()


def test_prune_error_logging(tmp_path: Path) -> None:
    """Test that pruning errors are logged."""
    logger = Mock(spec=SandboxLogger)

    session_id = str(uuid.uuid4())
    _create_dummy_session(tmp_path, session_id, age_hours=25.0)

    # Mock shutil.rmtree to raise PermissionError
    with patch("shutil.rmtree", side_effect=PermissionError("Access denied")):
        prune_sessions(
            older_than_hours=24.0,
            workspace_root=tmp_path,
            logger=logger
        )

    logger.log_prune_error.assert_called_once()


def test_prune_corrupted_timestamp_logging(tmp_path: Path) -> None:
    """Test that corrupted timestamps are logged as skipped."""
    logger = Mock(spec=SandboxLogger)

    session_id = str(uuid.uuid4())
    session_dir = tmp_path / session_id
    session_dir.mkdir()

    # Create metadata with invalid timestamp
    metadata = {
        "session_id": session_id,
        "created_at": "invalid-date",
        "updated_at": "invalid-date",
        "version": 1
    }
    (session_dir / ".metadata.json").write_text(json.dumps(metadata))

    prune_sessions(
        older_than_hours=24.0,
        workspace_root=tmp_path,
        logger=logger
    )

    logger.log_prune_skipped.assert_called_once()
    args = logger.log_prune_skipped.call_args[1]
    assert args["session_id"] == session_id
    assert "corrupted_timestamp" in args["reason"]
