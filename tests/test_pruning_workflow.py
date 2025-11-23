import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

from sandbox import (
    RuntimeType,
    create_sandbox,
    prune_sessions,
)
from sandbox.sessions import SessionMetadata


class TestPruningE2E:
    """End-to-end tests for session pruning and metadata management."""

    @pytest.fixture
    def workspace_root(self, tmp_path):
        """Create a temporary workspace root."""
        ws = tmp_path / "workspace"
        ws.mkdir()
        return ws

    def test_e2e_workflow(self, workspace_root):
        """
        Test the complete lifecycle:
        1. Create session -> verify metadata
        2. Execute code -> verify timestamp update
        3. Prune (recent) -> verify preservation
        4. Prune (old) -> verify deletion
        """
        # 1. Create session
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=workspace_root)

        session_id = sandbox.session_id

        session_dir = workspace_root / session_id
        metadata_file = session_dir / ".metadata.json"

        assert session_dir.exists()
        assert metadata_file.exists()

        # Verify initial metadata
        with open(metadata_file) as f:
            data = json.load(f)
            created_at = datetime.fromisoformat(data["created_at"])
            updated_at = datetime.fromisoformat(data["updated_at"])
            assert data["session_id"] == session_id
            assert created_at == updated_at

        # 2. Execute code and verify timestamp update
        # Sleep briefly to ensure timestamp difference is measurable if FS resolution is low
        time.sleep(0.1)

        sandbox.execute("print('hello')")

        with open(metadata_file) as f:
            data = json.load(f)
            new_updated_at = datetime.fromisoformat(data["updated_at"])
            assert new_updated_at > updated_at
            assert data["created_at"] == created_at.isoformat()

        # 3. Prune recent sessions (should not delete)
        # Set threshold to 1 hour, session is seconds old
        result = prune_sessions(older_than_hours=1.0, workspace_root=workspace_root, dry_run=False)

        assert session_id not in result.deleted_sessions
        assert session_dir.exists()
        assert result.reclaimed_bytes == 0

        # 4. Prune old sessions (make session appear old by modifying metadata)
        # Manually update the metadata to have old timestamps
        metadata_file = session_dir / ".metadata.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        # Set timestamps to 2 hours in the past
        old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        metadata["updated_at"] = old_time
        metadata["created_at"] = old_time

        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        result = prune_sessions(older_than_hours=1.0, workspace_root=workspace_root, dry_run=False)

        assert session_id in result.deleted_sessions
        assert not session_dir.exists()
        assert result.reclaimed_bytes > 0

    def test_backwards_compatibility(self, workspace_root):
        """
        Test compatibility with legacy sessions (no metadata):
        1. Manually create legacy session
        2. Execute code (should work, might add metadata or skip update)
        3. Prune (should skip legacy session)
        """
        # 1. Create legacy session manually
        legacy_id = str(uuid.uuid4())
        legacy_dir = workspace_root / legacy_id
        legacy_dir.mkdir()
        (legacy_dir / "user_code.py").write_text("print('legacy')")

        assert legacy_dir.exists()
        assert not (legacy_dir / ".metadata.json").exists()

        # 2. Execute code in legacy session
        # create_sandbox with existing session_id should work even without metadata
        sandbox = create_sandbox(
            session_id=legacy_id, runtime=RuntimeType.PYTHON, workspace_root=workspace_root
        )

        # Execution should succeed
        # Note: The current implementation of execute() attempts to update timestamp.
        # If metadata is missing, it should handle it gracefully (log warning and continue).
        result = sandbox.execute("print('still working')")
        assert result.success
        assert result.stdout.strip() == "still working"

        # Verify metadata file was created by create_sandbox (greenfield auto-creates metadata)
        # In the greenfield refactor, metadata is always created when sandbox is instantiated via StorageAdapter
        assert (legacy_dir / ".metadata.json").exists()

        # 3. Prune should delete the session (make it appear old)
        # Manually update metadata to have old timestamps
        metadata_file = legacy_dir / ".metadata.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        # Set timestamps to 25 hours in the past
        old_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
        metadata["updated_at"] = old_time
        metadata["created_at"] = old_time

        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        result = prune_sessions(older_than_hours=24.0, workspace_root=workspace_root, dry_run=False)

        # In greenfield refactor, metadata was auto-created, so session is eligible for deletion
        assert legacy_id in result.deleted_sessions
        assert legacy_id not in result.skipped_sessions
        assert not legacy_dir.exists()  # Should be deleted

    def test_prune_mixed_sessions(self, workspace_root):
        """Test pruning with a mix of valid, old, and legacy sessions."""
        # 1. Old valid session (should be deleted)
        old_id = str(uuid.uuid4())
        old_dir = workspace_root / old_id
        old_dir.mkdir()

        old_time = datetime.now(UTC) - timedelta(hours=5)
        old_meta = SessionMetadata(
            session_id=old_id,
            created_at=old_time.isoformat(),
            updated_at=old_time.isoformat(),
            version=1,
        )
        with open(old_dir / ".metadata.json", "w") as f:
            json.dump(old_meta.to_dict(), f)

        # 2. New valid session (should be kept)
        new_id = str(uuid.uuid4())
        new_dir = workspace_root / new_id
        new_dir.mkdir()

        new_time = datetime.now(UTC)
        new_meta = SessionMetadata(
            session_id=new_id,
            created_at=new_time.isoformat(),
            updated_at=new_time.isoformat(),
            version=1,
        )
        with open(new_dir / ".metadata.json", "w") as f:
            json.dump(new_meta.to_dict(), f)

        # 3. Legacy session (should be skipped)
        legacy_id = str(uuid.uuid4())
        legacy_dir = workspace_root / legacy_id
        legacy_dir.mkdir()

        # Prune sessions older than 2 hours
        result = prune_sessions(older_than_hours=2.0, workspace_root=workspace_root, dry_run=False)

        assert old_id in result.deleted_sessions
        assert not old_dir.exists()

        assert new_id not in result.deleted_sessions
        assert new_dir.exists()

        assert legacy_id in result.skipped_sessions
        assert legacy_dir.exists()

    def test_prune_non_uuid_session_ids(self, workspace_root):
        """Pruning should include custom (non-UUID) session IDs."""
        session_id = "custom-session-id"
        session_dir = workspace_root / session_id
        session_dir.mkdir()

        stale_time = datetime.now(UTC) - timedelta(hours=2)
        meta = SessionMetadata(
            session_id=session_id,
            created_at=stale_time.isoformat(),
            updated_at=stale_time.isoformat(),
            version=1,
        )
        (session_dir / ".metadata.json").write_text(json.dumps(meta.to_dict()))

        result = prune_sessions(older_than_hours=0, workspace_root=workspace_root, dry_run=False)

        assert session_id in result.deleted_sessions
        assert not session_dir.exists()
