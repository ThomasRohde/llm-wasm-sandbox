"""Pluggable storage backend abstraction for workspace management.

Provides adapter pattern for workspace storage, enabling multiple backend
implementations (disk, memory, cloud) while preserving security guarantees
and API compatibility.
"""

from __future__ import annotations

import json
import shutil
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sandbox.sessions import SessionMetadata


class StorageBackend(str, Enum):
    """Supported storage backend types for workspace management.

    DISK: Local filesystem storage (current implementation)
    MEMORY: In-memory storage (for testing and ephemeral sessions)
    S3: AWS S3 cloud storage (future implementation)
    REDIS: Redis key-value store (future implementation)
    """
    DISK = "disk"
    MEMORY = "memory"
    S3 = "s3"
    REDIS = "redis"


class StorageAdapter(ABC):
    """Abstract base class for workspace storage backends.

    Defines the contract that all storage backends must implement, providing
    operations for session management, file I/O, metadata tracking, and
    workspace enumeration. Each adapter is responsible for implementing
    its own change detection strategy for tracking file modifications.

    Adapter-Configurable Constants:
        METADATA_FILENAME: Name of metadata file (default: ".metadata.json")
        SITE_PACKAGES_DIR: Name of vendored packages directory (default: "site-packages")
        PYTHON_CODE_FILENAME: Name of Python code file (default: "user_code.py")
        JAVASCRIPT_CODE_FILENAME: Name of JavaScript code file (default: "user_code.js")

    Attributes:
        workspace_root: Root path or identifier for all session workspaces
    """

    # Adapter-configurable constants - subclasses can override
    METADATA_FILENAME: str = ".metadata.json"
    SITE_PACKAGES_DIR: str = "site-packages"
    PYTHON_CODE_FILENAME: str = "user_code.py"
    JAVASCRIPT_CODE_FILENAME: str = "user_code.js"

    def __init__(self, workspace_root: Any) -> None:
        """Initialize storage adapter with root workspace location.

        Args:
            workspace_root: Root location for all session workspaces.
                          For DiskStorageAdapter: Path object
                          For MemoryStorageAdapter: dict identifier
                          For S3StorageAdapter: bucket name, etc.
        """
        self.workspace_root = workspace_root

    @abstractmethod
    def create_session(self, session_id: str) -> None:
        """Create a new session workspace with metadata.

        Must create session directory/namespace, initialize metadata with
        created_at and updated_at timestamps, and prepare for file operations.

        Args:
            session_id: UUIDv4 session identifier

        Raises:
            Exception: If session creation fails (adapter-specific)
        """
        pass

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """Check if session workspace exists.

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            True if session exists, False otherwise
        """
        pass

    @abstractmethod
    def write_file(self, session_id: str, relative_path: str, data: bytes) -> None:
        """Write file to session workspace.

        Must validate that relative_path doesn't escape session boundary
        (no path traversal via ../ or absolute paths).

        Args:
            session_id: UUIDv4 session identifier
            relative_path: Path relative to session workspace root
            data: File content as bytes

        Raises:
            ValueError: If relative_path contains path traversal
            Exception: If write operation fails (adapter-specific)
        """
        pass

    @abstractmethod
    def read_file(self, session_id: str, relative_path: str) -> bytes:
        """Read file from session workspace.

        Must validate that relative_path doesn't escape session boundary.

        Args:
            session_id: UUIDv4 session identifier
            relative_path: Path relative to session workspace root

        Returns:
            File content as bytes

        Raises:
            ValueError: If relative_path contains path traversal
            FileNotFoundError: If file doesn't exist
            Exception: If read operation fails (adapter-specific)
        """
        pass

    @abstractmethod
    def list_files(self, session_id: str, pattern: str = "*") -> list[str]:
        """List files in session workspace matching glob pattern.

        Args:
            session_id: UUIDv4 session identifier
            pattern: Glob pattern for filtering (default: "*" for all files)

        Returns:
            List of relative paths matching pattern

        Raises:
            Exception: If listing fails (adapter-specific)
        """
        pass

    @abstractmethod
    def delete_path(self, session_id: str, relative_path: str) -> None:
        """Delete file or directory from session workspace.

        Must validate that relative_path doesn't escape session boundary.

        Args:
            session_id: UUIDv4 session identifier
            relative_path: Path relative to session workspace root

        Raises:
            ValueError: If relative_path contains path traversal
            Exception: If deletion fails (adapter-specific)
        """
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete entire session workspace.

        Args:
            session_id: UUIDv4 session identifier

        Raises:
            Exception: If deletion fails (adapter-specific)
        """
        pass

    @abstractmethod
    def enumerate_sessions(self) -> list[str]:
        """Enumerate all session IDs in workspace.

        Returns:
            List of session IDs (UUIDv4 strings)
        """
        pass

    @abstractmethod
    def read_metadata(self, session_id: str) -> SessionMetadata:
        """Read session metadata.

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            SessionMetadata with created_at, updated_at timestamps

        Raises:
            FileNotFoundError: If metadata doesn't exist
            Exception: If metadata parsing fails
        """
        pass

    @abstractmethod
    def write_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        """Write session metadata.

        Args:
            session_id: UUIDv4 session identifier
            metadata: SessionMetadata to persist

        Raises:
            Exception: If write fails (adapter-specific)
        """
        pass

    @abstractmethod
    def update_session_timestamp(self, session_id: str) -> None:
        """Update session's updated_at timestamp to current UTC time.

        Args:
            session_id: UUIDv4 session identifier

        Raises:
            Exception: If update fails (adapter-specific)
        """
        pass

    @abstractmethod
    def copy_vendor_packages(
        self,
        session_id: str,
        vendor_path: Path
    ) -> None:
        """Copy vendored packages to session workspace.

        Adapters can optimize this operation (e.g., memory backend uses
        shared references, cloud backend uses copy-on-write).

        Args:
            session_id: UUIDv4 session identifier
            vendor_path: Host path to vendor directory containing site-packages

        Raises:
            Exception: If copy fails (adapter-specific)
        """
        pass

    @abstractmethod
    def get_workspace_snapshot(self, session_id: str) -> dict[str, float]:
        """Get snapshot of all files with modification times.

        Used for change detection to track files created/modified during
        execution. Each adapter implements its own optimal strategy:
        - Disk: stat() all files
        - Memory: track last-modified dict
        - Cloud: use versioning metadata

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            Dictionary mapping relative paths to modification timestamps (POSIX)

        Raises:
            Exception: If snapshot fails (adapter-specific)
        """
        pass

    @abstractmethod
    def get_session_size(self, session_id: str) -> int:
        """Calculate total size of session workspace in bytes.

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            Total size in bytes

        Raises:
            Exception: If calculation fails (adapter-specific)
        """
        pass

    def detect_file_changes(
        self,
        session_id: str,
        before: dict[str, float],
        after: dict[str, float]
    ) -> tuple[list[str], list[str]]:
        """Detect files created and modified by comparing snapshots.

        Default implementation compares before/after snapshots. Adapters
        can override with more efficient change tracking mechanisms.

        Args:
            session_id: UUIDv4 session identifier
            before: Snapshot before execution (from get_workspace_snapshot)
            after: Snapshot after execution (from get_workspace_snapshot)

        Returns:
            Tuple of (files_created, files_modified) as relative path lists
        """
        files_created = []
        files_modified = []

        for path, mtime in after.items():
            if path not in before:
                files_created.append(path)
            elif before[path] != mtime:
                files_modified.append(path)

        return (sorted(files_created), sorted(files_modified))


class DiskStorageAdapter(StorageAdapter):
    """Disk-based storage adapter using local filesystem.

    Implements workspace storage using traditional filesystem operations
    with Path-based validation for security. This is the default adapter
    providing backward compatibility with the original implementation.

    Attributes:
        workspace_root: Path object pointing to root workspace directory
    """

    def __init__(self, workspace_root: Path | str = Path("workspace")) -> None:
        """Initialize disk storage adapter.

        Args:
            workspace_root: Path to root workspace directory (created if needed)
        """
        if isinstance(workspace_root, str):
            workspace_root = Path(workspace_root)
        super().__init__(workspace_root)
        self.workspace_root: Path = workspace_root
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _validate_session_path(
        self,
        session_id: str,
        relative_path: str | None = None
    ) -> tuple[Path, Path]:
        """Validate session path and prevent traversal attacks.

        Args:
            session_id: UUIDv4 session identifier
            relative_path: Optional relative path within session

        Returns:
            Tuple of (workspace_path, full_path)

        Raises:
            ValueError: If paths contain traversal attempts or are absolute
        """
        # Validate session_id doesn't contain path separators
        if "/" in session_id or "\\" in session_id or session_id in (".", ".."):
            raise ValueError(
                f"Invalid session_id '{session_id}': must not contain path separators"
            )

        workspace = self.workspace_root / session_id

        # If no relative_path, just return workspace
        if relative_path is None:
            return (workspace, workspace)

        # Validate relative_path
        if Path(relative_path).is_absolute():
            raise ValueError(
                f"Invalid path '{relative_path}': must be relative to session workspace"
            )

        # Resolve and validate path is within session workspace
        full_path = (workspace / relative_path).resolve()
        workspace_resolved = workspace.resolve()

        if not full_path.is_relative_to(workspace_resolved):
            raise ValueError(
                f"Path '{relative_path}' escapes session workspace"
            )

        return (workspace, full_path)

    def create_session(self, session_id: str) -> None:
        """Create session workspace directory with metadata.

        Args:
            session_id: UUIDv4 session identifier

        Raises:
            ValueError: If session_id contains path traversal

        Note:
            Metadata write failures are logged but don't prevent session creation
        """
        workspace, _ = self._validate_session_path(session_id)
        workspace.mkdir(parents=True, exist_ok=True)

        # Create metadata (failures don't prevent session creation)
        try:
            from sandbox.sessions import SessionMetadata
            now = datetime.now(UTC).isoformat()
            metadata = SessionMetadata(
                session_id=session_id,
                created_at=now,
                updated_at=now,
                version=1
            )
            self.write_metadata(session_id, metadata)
        except OSError as e:
            # Log warning but don't fail session creation
            import sys
            print(
                f"Warning: Failed to write metadata for session {session_id}: {e}",
                file=sys.stderr
            )

    def session_exists(self, session_id: str) -> bool:
        """Check if session workspace exists.

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            True if session directory exists, False otherwise
        """
        workspace, _ = self._validate_session_path(session_id)
        return workspace.exists()

    def write_file(self, session_id: str, relative_path: str, data: bytes) -> None:
        """Write file to session workspace on disk.

        Args:
            session_id: UUIDv4 session identifier
            relative_path: Path relative to session workspace
            data: File content as bytes

        Raises:
            ValueError: If relative_path contains path traversal
        """
        _, full_path = self._validate_session_path(session_id, relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(data)

    def read_file(self, session_id: str, relative_path: str) -> bytes:
        """Read file from session workspace on disk.

        Args:
            session_id: UUIDv4 session identifier
            relative_path: Path relative to session workspace

        Returns:
            File content as bytes

        Raises:
            ValueError: If relative_path contains path traversal
            FileNotFoundError: If file doesn't exist
        """
        _, full_path = self._validate_session_path(session_id, relative_path)
        return full_path.read_bytes()

    def list_files(self, session_id: str, pattern: str = "*") -> list[str]:
        """List files in session workspace matching glob pattern.

        Args:
            session_id: UUIDv4 session identifier
            pattern: Glob pattern (default: "*")

        Returns:
            List of relative paths
        """
        workspace, _ = self._validate_session_path(session_id)

        if not workspace.exists():
            return []

        files = []
        for file in workspace.rglob(pattern):
            if file.is_file():
                relative = file.relative_to(workspace)
                # Convert to POSIX path (forward slashes) for consistency across platforms
                files.append(relative.as_posix())

        return sorted(files)

    def delete_path(self, session_id: str, relative_path: str, recursive: bool = True) -> None:
        """Delete file or directory from session workspace.

        Args:
            session_id: UUIDv4 session identifier
            relative_path: Path relative to session workspace
            recursive: Allow deletion of directories (default: True for backwards compat)

        Raises:
            ValueError: If relative_path contains path traversal or directory without recursive
            FileNotFoundError: If path does not exist
        """
        _, full_path = self._validate_session_path(session_id, relative_path)

        if not full_path.exists():
            raise FileNotFoundError(f"Path '{relative_path}' not found in session '{session_id}'")

        if full_path.is_file():
            full_path.unlink()
        elif full_path.is_dir():
            if not recursive:
                raise ValueError(f"Cannot delete directory '{relative_path}' without recursive=True")
            shutil.rmtree(full_path)

    def delete_session(self, session_id: str) -> None:
        """Delete entire session workspace directory.

        Args:
            session_id: UUIDv4 session identifier
        """
        workspace, _ = self._validate_session_path(session_id)

        if workspace.exists():
            shutil.rmtree(workspace)

    def enumerate_sessions(self) -> list[str]:
        """Enumerate all session directories.

        Returns all directories in workspace_root to allow pruning logic
        to handle both valid UUID sessions and legacy/custom session IDs.
        Non-session directories (like system files) will be skipped during
        pruning if they lack metadata.

        Returns:
            List of directory names (all subdirectories in workspace_root)
        """
        if not self.workspace_root.exists():
            return []

        sessions = []
        for item in self.workspace_root.iterdir():
            if item.is_dir():
                sessions.append(item.name)

        return sorted(sessions)

    def read_metadata(self, session_id: str) -> SessionMetadata:
        """Read session metadata from .metadata.json file.

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            SessionMetadata instance

        Raises:
            FileNotFoundError: If metadata file doesn't exist
            json.JSONDecodeError: If metadata is corrupted
        """
        from sandbox.sessions import SessionMetadata

        _, metadata_path = self._validate_session_path(
            session_id,
            self.METADATA_FILENAME
        )

        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata not found for session '{session_id}'"
            )

        data = json.loads(metadata_path.read_text())
        return SessionMetadata.from_dict(data)

    def write_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        """Write session metadata to .metadata.json file.

        Args:
            session_id: UUIDv4 session identifier
            metadata: SessionMetadata to persist
        """
        _, metadata_path = self._validate_session_path(
            session_id,
            self.METADATA_FILENAME
        )

        metadata_path.write_text(json.dumps(metadata.to_dict(), indent=2))

    def update_session_timestamp(self, session_id: str) -> None:
        """Update session's updated_at timestamp.

        Args:
            session_id: UUIDv4 session identifier
        """
        _, metadata_path = self._validate_session_path(
            session_id,
            self.METADATA_FILENAME
        )

        if not metadata_path.exists():
            return

        data = json.loads(metadata_path.read_text())
        data["updated_at"] = datetime.now(UTC).isoformat()
        metadata_path.write_text(json.dumps(data, indent=2))

    def copy_vendor_packages(
        self,
        session_id: str,
        vendor_path: Path
    ) -> None:
        """Copy vendored site-packages to session workspace.

        Args:
            session_id: UUIDv4 session identifier
            vendor_path: Host path to vendor directory

        Raises:
            FileNotFoundError: If vendor/site-packages doesn't exist
        """
        src = vendor_path / self.SITE_PACKAGES_DIR
        workspace, _ = self._validate_session_path(session_id)
        dst = workspace / self.SITE_PACKAGES_DIR

        if not src.exists():
            raise FileNotFoundError(
                f"Vendor directory not found: {src}"
            )

        # Remove existing and copy fresh
        if dst.exists():
            shutil.rmtree(dst)

        shutil.copytree(src, dst)

    def get_workspace_snapshot(self, session_id: str) -> dict[str, float]:
        """Get snapshot of all files with modification times.

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            Dictionary mapping relative paths to mtime (POSIX timestamp)
        """
        workspace, _ = self._validate_session_path(session_id)
        snapshot = {}

        if not workspace.exists():
            return snapshot

        for file in workspace.rglob("*"):
            if file.is_file():
                relative = str(file.relative_to(workspace))
                snapshot[relative] = file.stat().st_mtime

        return snapshot

    def get_session_size(self, session_id: str) -> int:
        """Calculate total size of session workspace.

        Args:
            session_id: UUIDv4 session identifier

        Returns:
            Total size in bytes
        """
        workspace, _ = self._validate_session_path(session_id)
        total = 0

        if not workspace.exists():
            return 0

        for file in workspace.rglob("*"):
            if file.is_file():
                total += file.stat().st_size

        return total
