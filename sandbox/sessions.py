"""Session management for stateful multi-turn LLM interactions.

This module provides session file operations and pruning utilities for the
WASM sandbox. All sandboxes are session-aware by default via create_sandbox(),
which auto-generates session IDs and manages workspace isolation.

Session Model
-------------
Each session is identified by a UUIDv4 string (or custom identifier) that maps
to an isolated workspace directory: `workspace/<session_id>/`. This directory
is mounted as `/app` in the WASI guest environment, providing capability-based
isolation between sessions.

Session creation is handled by create_sandbox() factory, which auto-generates
session IDs and creates .metadata.json files for tracking timestamps.

Security Considerations
-----------------------
- **Path traversal prevention**: All file operations validate paths using
  `Path.is_relative_to()` to prevent escapes via `../` or symlinks
- **Session ID validation**: Session IDs must not contain path separators
  to prevent directory traversal attacks
- **Workspace isolation**: Each session workspace is isolated via WASI
  capability-based preopens - guests cannot access other session workspaces
- **No cross-session sharing**: By design, sessions cannot access each
  other's files. Applications wanting shared data should use dedicated
  mount points (ExecutionPolicy.mount_data_dir)

Usage Examples
--------------
Basic Session Lifecycle:
    >>> from sandbox import create_sandbox, RuntimeType
    >>> # Create new session with auto-generated ID
    >>> sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    >>> print(sandbox.session_id)
    '550e8400-e29b-41d4-a716-446655440000'
    >>> result = sandbox.execute("with open('/app/data.txt', 'w') as f: f.write('hello')")

    >>> # Resume existing session
    >>> sandbox = create_sandbox(session_id='550e8400-e29b-41d4-a716-446655440000')
    >>> result = sandbox.execute("print(open('/app/data.txt').read())")
    >>> print(result.stdout)
    hello

File Operations from Host:
    >>> from sandbox import create_sandbox, list_session_files, read_session_file
    >>> sandbox = create_sandbox()
    >>> session_id = sandbox.session_id
    >>>
    >>> # List all files in session
    >>> files = list_session_files(session_id)
    >>> print(files)
    ['data.txt', 'user_code.py']

    >>> # Read file from host side
    >>> data = read_session_file(session_id, 'data.txt')
    >>> print(data.decode('utf-8'))
    hello

    >>> # Write file from host (upload user data)
    >>> from sandbox import write_session_file
    >>> write_session_file(session_id, 'input.csv', b'name,age\\nAlice,30')
    >>>
    >>> # Sandbox can now read host-written file
    >>> code = '''
    ... with open('/app/input.csv', 'r') as f:
    ...     print(f.read())
    ... '''
    >>> result = sandbox.execute(code)

Multi-Turn Workflow with Persistence:
    >>> from sandbox import create_sandbox
    >>> # Turn 1: Generate and save data
    >>> sandbox = create_sandbox()
    >>> session_id = sandbox.session_id
    >>> code1 = '''import json
    ... data = {'results': [1, 2, 3], 'status': 'complete'}
    ... with open('/app/results.json', 'w') as f:
    ...     json.dump(data, f)
    ... '''
    >>> result = sandbox.execute(code1)
    >>>
    >>> # Turn 2: Read and process saved data (reuse session_id)
    >>> sandbox = create_sandbox(session_id=session_id)
    >>> code2 = '''import json
    ... with open('/app/results.json', 'r') as f:
    ...     data = json.load(f)
    ... print(f"Sum: {sum(data['results'])}")
    ... '''
    >>> result = sandbox.execute(code2)
    >>> print(result.stdout)
    Sum: 6

Cleaning Up Sessions:
    >>> from sandbox import delete_session_path, delete_session_workspace
    >>> # Delete specific file or directory
    >>> delete_session_path(session_id, 'data.txt')

    >>> # Delete entire session workspace when done
    >>> delete_session_workspace(session_id)

Custom Policy with Sessions:
    >>> from sandbox import create_sandbox, ExecutionPolicy
    >>> policy = ExecutionPolicy(
    ...     fuel_budget=1_000_000_000,
    ...     memory_bytes=64 * 1024 * 1024
    ... )
    >>> sandbox = create_sandbox(policy=policy)

Session Isolation:
    >>> from sandbox import create_sandbox, read_session_file
    >>> # Each session has completely isolated workspace
    >>> sandbox_a = create_sandbox()
    >>> sandbox_b = create_sandbox()
    >>>
    >>> # Both write to same filename in different workspaces
    >>> sandbox_a.execute("open('/app/data.txt', 'w').write('A')")
    >>> sandbox_b.execute("open('/app/data.txt', 'w').write('B')")
    >>>
    >>> # Each sees only its own file
    >>> print(read_session_file(sandbox_a.session_id, 'data.txt').decode())  # 'A'
    >>> print(read_session_file(sandbox_b.session_id, 'data.txt').decode())  # 'B'
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sandbox.core.logging import SandboxLogger
    from sandbox.core.storage import StorageAdapter


@dataclass
class SessionMetadata:
    """Metadata for session workspace tracking creation and update timestamps.

    This metadata enables automated cleanup of stale session workspaces by
    recording when sessions are created and last accessed. Stored as
    `.metadata.json` within each session workspace directory.

    Attributes:
        session_id: UUIDv4 session identifier (redundant with directory name,
                   useful for validation)
        created_at: ISO 8601 UTC timestamp when session was created
        updated_at: ISO 8601 UTC timestamp when session was last used
                   (refreshed on each execute() call)
        version: Metadata schema version (currently 1, enables future migrations)

    Examples:
        >>> from datetime import UTC, datetime
        >>> metadata = SessionMetadata(
        ...     session_id="550e8400-e29b-41d4-a716-446655440000",
        ...     created_at=datetime.now(UTC).isoformat(),
        ...     updated_at=datetime.now(UTC).isoformat(),
        ...     version=1
        ... )
        >>> metadata_dict = metadata.to_dict()
        >>> print(metadata_dict)
        {'session_id': '550e8400-...', 'created_at': '2025-11-22T...', ...}

        >>> # Reconstruct from dict
        >>> restored = SessionMetadata.from_dict(metadata_dict)
        >>> print(restored.session_id)
        550e8400-e29b-41d4-a716-446655440000
    """

    session_id: str
    created_at: str
    updated_at: str
    version: int

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for JSON serialization.

        Returns:
            dict: Dictionary with session_id, created_at, updated_at, version keys

        Examples:
            >>> metadata = SessionMetadata(
            ...     session_id="abc-123",
            ...     created_at="2025-11-22T10:00:00Z",
            ...     updated_at="2025-11-22T14:00:00Z",
            ...     version=1
            ... )
            >>> data = metadata.to_dict()
            >>> print(data['session_id'])
            abc-123
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMetadata:
        """Construct SessionMetadata from dictionary.

        Args:
            data: Dictionary with session_id, created_at, updated_at, version keys

        Returns:
            SessionMetadata: Reconstructed metadata instance

        Raises:
            KeyError: If required keys are missing from data dict
            TypeError: If data types are incorrect

        Examples:
            >>> data = {
            ...     "session_id": "abc-123",
            ...     "created_at": "2025-11-22T10:00:00Z",
            ...     "updated_at": "2025-11-22T14:00:00Z",
            ...     "version": 1
            ... }
            >>> metadata = SessionMetadata.from_dict(data)
            >>> print(metadata.session_id)
            abc-123
        """
        return cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            version=data["version"]
        )


@dataclass
class PruneResult:
    """Result of workspace pruning operation.

    This model captures comprehensive statistics from pruning operations,
    including which sessions were deleted, which were skipped (due to missing
    metadata), disk space reclaimed, and any errors encountered during deletion.

    Attributes:
        deleted_sessions: List of session IDs that were deleted
        skipped_sessions: List of session IDs skipped (missing/corrupted metadata)
        reclaimed_bytes: Total disk space freed in bytes
        errors: Dictionary mapping session_id to error message for failed deletions
        dry_run: Whether this was a dry-run (no actual deletions)

    Examples:
        >>> result = PruneResult(
        ...     deleted_sessions=["session-1", "session-2"],
        ...     skipped_sessions=["legacy-session"],
        ...     reclaimed_bytes=1_500_000,
        ...     errors={"session-3": "Permission denied"},
        ...     dry_run=False
        ... )
        >>> print(result)
        Pruned 2 sessions (1 skipped, 1 error), reclaimed 1.4 MB
    """

    deleted_sessions: list[str]
    skipped_sessions: list[str]
    reclaimed_bytes: int
    errors: dict[str, str]
    dry_run: bool

    def __str__(self) -> str:
        """Format result as human-readable summary.

        Returns:
            str: Summary like "Pruned 5 sessions (2 skipped, 1 error), reclaimed 12.3 MB"

        Examples:
            >>> result = PruneResult(
            ...     deleted_sessions=["a", "b"],
            ...     skipped_sessions=[],
            ...     reclaimed_bytes=1_048_576,
            ...     errors={},
            ...     dry_run=False
            ... )
            >>> str(result)
            'Pruned 2 sessions, reclaimed 1.0 MB'
        """
        # Format reclaimed bytes as human-readable
        size_str = _format_bytes(self.reclaimed_bytes)

        # Build summary components
        deleted_count = len(self.deleted_sessions)
        skipped_count = len(self.skipped_sessions)
        error_count = len(self.errors)

        # Base message
        if self.dry_run:
            msg = f"Would prune {deleted_count} sessions"
        else:
            msg = f"Pruned {deleted_count} sessions"

        # Add skipped/error counts if present
        details = []
        if skipped_count > 0:
            details.append(f"{skipped_count} skipped")
        if error_count > 0:
            details.append(f"{error_count} error{'s' if error_count > 1 else ''}")

        if details:
            msg += f" ({', '.join(details)})"

        # Add reclaimed space
        msg += f", reclaimed {size_str}"

        return msg


def _read_session_metadata(
    session_id: str,
    workspace_root: Path
) -> SessionMetadata | None:
    """Read session metadata from .metadata.json file.

    Attempts to parse the .metadata.json file in the session workspace and
    construct a SessionMetadata object. Returns None if the metadata file
    doesn't exist or is corrupted, logging warnings for diagnostic purposes.

    This function is used by pruning and timestamp update operations to
    access session temporal information. It handles missing metadata gracefully
    to support backwards compatibility with sessions created before the
    metadata feature was added.

    Args:
        session_id: UUIDv4 session identifier
        workspace_root: Root directory containing all session workspaces

    Returns:
        SessionMetadata | None: Parsed metadata if valid, None if missing or corrupted

    Examples:
        >>> # Read metadata from existing session
        >>> metadata = _read_session_metadata("abc-123", Path("workspace"))
        >>> if metadata:
        ...     print(metadata.created_at)
        2025-11-22T10:00:00Z

        >>> # Missing metadata returns None (legacy session)
        >>> metadata = _read_session_metadata("old-session", Path("workspace"))
        >>> print(metadata)
        None

        >>> # Corrupted JSON returns None with warning logged
        >>> metadata = _read_session_metadata("bad-metadata", Path("workspace"))
        >>> print(metadata)
        None
    """
    metadata_path = workspace_root / session_id / ".metadata.json"

    if not metadata_path.exists():
        # Session created before metadata feature - skip silently
        return None

    try:
        data = json.loads(metadata_path.read_text())
        return SessionMetadata.from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # Log warning but don't fail - corrupted metadata shouldn't break operations
        # Using print to stderr since we may not have a logger here
        import sys
        print(
            f"Warning: Failed to read session metadata for {session_id}: {e}",
            file=sys.stderr
        )
        return None


def _update_session_timestamp(
    session_id: str,
    workspace_root: Path,
    logger: SandboxLogger | None = None
) -> None:
    """Update the updated_at timestamp in session metadata.

    Reads the existing metadata, updates only the updated_at field to the
    current UTC time, and writes back to .metadata.json. This function is
    called after each successful execution to track session activity.

    Handles missing or corrupted metadata gracefully by skipping the update
    silently (for legacy sessions) or logging warnings (for corrupted metadata).
    This ensures timestamp updates never cause execution failures.

    Args:
        session_id: UUIDv4 session identifier
        workspace_root: Root directory containing all session workspaces
        logger: Optional SandboxLogger for structured logging

    Examples:
        >>> # Update timestamp after execution
        >>> _update_session_timestamp("abc-123", Path("workspace"))

        >>> # Legacy session without metadata - silently skipped
        >>> _update_session_timestamp("old-session", Path("workspace"))

        >>> # With logger for structured logging
        >>> from sandbox.core.logging import SandboxLogger
        >>> logger = SandboxLogger()
        >>> _update_session_timestamp("abc-123", Path("workspace"), logger)
    """
    metadata_path = workspace_root / session_id / ".metadata.json"

    if not metadata_path.exists():
        # Session created before metadata feature - skip silently (pruning will handle)
        return

    try:
        data = json.loads(metadata_path.read_text())
        data["updated_at"] = datetime.now(UTC).isoformat()
        metadata_path.write_text(json.dumps(data, indent=2))

        # Log structured event if logger provided
        if logger is not None:
            logger.log_session_metadata_updated(
                session_id=session_id,
                timestamp=data["updated_at"]
            )
    except (json.JSONDecodeError, OSError) as e:
        # Log warning but don't fail execution
        import sys
        print(
            f"Warning: Failed to update session timestamp for {session_id}: {e}",
            file=sys.stderr
        )


def _validate_session_workspace(
    session_id: str,
    workspace_root: Path,
    allow_non_uuid: bool = True
) -> Path:
    """Validate session_id safety and return resolved workspace path.

    Ensures session identifiers cannot perform path traversal (no separators,
    no '..' segments) and optionally enforces UUID formatting. Returns the
    fully resolved workspace path and verifies it remains inside the provided
    workspace_root.

    Args:
        session_id: Caller-provided session identifier
        workspace_root: Root directory containing all session workspaces
        allow_non_uuid: If False, session_id must be a valid UUID string

    Returns:
        Path: Resolved session workspace path under workspace_root

    Raises:
        ValueError: If session_id is empty, contains traversal characters, fails
                    UUID enforcement, or resolves outside workspace_root
    """
    if not session_id:
        raise ValueError("session_id must not be empty")

    separators = {"/", "\\"}
    if os.sep:
        separators.add(os.sep)
    if os.altsep:
        separators.add(os.altsep)

    if any(sep in session_id for sep in separators) or ".." in session_id:
        raise ValueError(
            f"session_id '{session_id}' must not contain path separators or traversal sequences"
        )

    normalized_id = session_id
    if not allow_non_uuid:
        try:
            normalized_id = str(uuid.UUID(session_id))
        except ValueError as exc:
            raise ValueError("session_id must be a valid UUID string") from exc

    root = Path(workspace_root).resolve()
    workspace = (root / normalized_id).resolve()

    try:
        workspace.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"session workspace '{workspace}' escapes workspace_root '{root}'"
        ) from exc

    return workspace


def _validate_session_path(
    session_id: str,
    relative_path: str,
    workspace_root: Path
) -> Path:
    """Validate and resolve a session file path, preventing path traversal.

    This function implements defense-in-depth path validation to prevent
    directory traversal attacks via `../`, absolute paths, or symlink escapes.
    It ensures that resolved paths stay within the session workspace boundary.

    Args:
        session_id: Session UUID (must not contain path separators)
        relative_path: Relative path within session workspace (e.g., "data.txt", "dir/file.txt")
        workspace_root: Root directory containing all session workspaces

    Returns:
        Path: Absolute, resolved path within session workspace

    Raises:
        ValueError: If path validation fails due to:
            - session_id contains path separators (/, \\)
            - relative_path is absolute
            - resolved path escapes session workspace (e.g., via ../ or symlinks)

    Security Notes:
        - Uses Path.resolve() to canonicalize paths and resolve symlinks
        - Uses Path.is_relative_to() (Python 3.9+) to verify containment
        - Validates session_id separately to prevent crafted IDs like "../etc"

    Examples:
        >>> # Valid paths
        >>> _validate_session_path("abc-123", "data.txt", Path("workspace"))
        Path('workspace/abc-123/data.txt')

        >>> # Invalid: path traversal
        >>> _validate_session_path("abc-123", "../etc/passwd", Path("workspace"))
        ValueError: Path '../etc/passwd' escapes session workspace

        >>> # Invalid: absolute path
        >>> _validate_session_path("abc-123", "/etc/passwd", Path("workspace"))
        ValueError: Path '/etc/passwd' must be relative

        >>> # Invalid: session_id with separator
        >>> _validate_session_path("../etc", "passwd", Path("workspace"))
        ValueError: session_id must not contain path separators
    """
    # Resolve workspace path after validating session_id safety
    workspace = _validate_session_workspace(session_id, workspace_root)

    # Check if relative_path is absolute
    path_obj = Path(relative_path)
    if path_obj.is_absolute():
        raise ValueError(
            f"Path '{relative_path}' must be relative to session workspace"
        )

    # Resolve full path and canonicalize (resolves symlinks)
    full_path = (workspace / relative_path).resolve()

    # Verify resolved path is within session workspace
    try:
        full_path.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Path '{relative_path}' escapes session workspace boundary. "
            f"Resolved to '{full_path}', expected within '{workspace.resolve()}'"
        ) from exc

    return full_path


def _ensure_session_workspace(
    session_id: str,
    workspace_root: Path
) -> Path:
    """Create session workspace directory if it doesn't exist.

    Idempotent operation that ensures the workspace directory exists for
    the given session ID. Creates parent directories as needed.

    Args:
        session_id: Session UUID
        workspace_root: Root directory containing all session workspaces

    Returns:
        Path: Absolute path to session workspace directory

    Examples:
        >>> # Create new session workspace
        >>> workspace = _ensure_session_workspace("abc-123", Path("workspace"))
        >>> workspace.exists()
        True

        >>> # Idempotent: calling again returns same path, doesn't error
        >>> workspace2 = _ensure_session_workspace("abc-123", Path("workspace"))
        >>> workspace == workspace2
        True
    """
    workspace = _validate_session_workspace(session_id, workspace_root)
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def _format_bytes(size_bytes: int) -> str:
    """Format byte count as human-readable string (e.g., '1.5 MB').

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Human-readable size string

    Examples:
        >>> _format_bytes(1024)
        '1.0 KB'
        >>> _format_bytes(1_500_000)
        '1.4 MB'
        >>> _format_bytes(500)
        '500 B'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.1f} GB"


def _looks_like_uuid(name: str) -> bool:
    """Lightweight check to see if a string can be parsed as a UUID."""
    try:
        uuid.UUID(name)
        return True
    except ValueError:
        return False


def _enumerate_sessions(workspace_root: Path) -> list[str]:
    """List session directories in workspace, including custom IDs.

    Enumerates subdirectories in workspace_root and includes any directory
    that either contains a .metadata.json file (canonical session marker) or
    is UUID-shaped for backwards compatibility. Hidden directories and known
    non-session folders (e.g., site-packages) are skipped.

    Args:
        workspace_root: Root directory containing session workspaces

    Returns:
        list[str]: List of session IDs (directory names) eligible for pruning

    Examples:
        >>> # Returns only UUID directories
        >>> sessions = _enumerate_sessions(Path("workspace"))
        >>> sessions
        ['550e8400-e29b-41d4-a716-446655440000', '6ba7b810-9dad-11d1-80b4-00c04fd430c8']

        >>> # Ignores non-UUID directories
        >>> # workspace contains: uuid-session/, site-packages/, temp/
        >>> sessions = _enumerate_sessions(Path("workspace"))
        >>> 'site-packages' in sessions
        False
    """
    if not workspace_root.exists():
        return []

    reserved = {"site-packages"}
    root = workspace_root.resolve()
    sessions = []

    for item in root.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith(".") or item.name in reserved:
            continue

        metadata_path = item / ".metadata.json"
        # Include any directory with metadata (UUID or custom session IDs)
        if metadata_path.exists():
            sessions.append(item.name)
            continue

        # For backwards compatibility: include UUID-shaped dirs without metadata
        if _looks_like_uuid(item.name):
            sessions.append(item.name)

    return sessions


def _calculate_session_age(metadata: SessionMetadata) -> float:
    """Calculate session age in hours from updated_at timestamp.

    Computes the time elapsed since the session was last updated, using
    the updated_at field from SessionMetadata. Handles timezone-aware
    datetime arithmetic.

    Args:
        metadata: SessionMetadata with updated_at timestamp

    Returns:
        float: Age in hours since last update

    Examples:
        >>> from datetime import UTC, datetime, timedelta
        >>> # Session updated 25 hours ago
        >>> past_time = datetime.now(UTC) - timedelta(hours=25)
        >>> metadata = SessionMetadata(
        ...     session_id="abc-123",
        ...     created_at=past_time.isoformat(),
        ...     updated_at=past_time.isoformat(),
        ...     version=1
        ... )
        >>> age = _calculate_session_age(metadata)
        >>> age >= 24.0  # At least 24 hours old
        True
    """
    # Parse updated_at timestamp (ISO 8601 format)
    updated_at = datetime.fromisoformat(metadata.updated_at.replace('Z', '+00:00'))

    # Calculate elapsed time
    now = datetime.now(UTC)
    elapsed = now - updated_at

    # Convert to hours
    return elapsed.total_seconds() / 3600


def _calculate_workspace_size(workspace_path: Path) -> int:
    """Calculate total size of files in workspace directory.

    Recursively sums the sizes of all files in the workspace directory.
    Handles errors gracefully (permission errors, missing files) by logging
    warnings and returning 0 for problematic files.

    Args:
        workspace_path: Path to workspace directory

    Returns:
        int: Total size in bytes of all files in workspace

    Examples:
        >>> # Calculate size of session workspace
        >>> size = _calculate_workspace_size(Path("workspace/session-id"))
        >>> size
        1_500_000  # 1.5 MB

        >>> # Empty workspace returns 0
        >>> size = _calculate_workspace_size(Path("workspace/empty-session"))
        >>> size
        0
    """
    total_size = 0

    try:
        for item in workspace_path.rglob("*"):
            if item.is_file():
                try:
                    total_size += item.stat().st_size
                except (OSError, PermissionError) as e:
                    # Log warning but continue
                    import sys
                    print(
                        f"Warning: Failed to stat {item}: {e}",
                        file=sys.stderr
                    )
    except (OSError, PermissionError) as e:
        # Log warning and return 0
        import sys
        print(
            f"Warning: Failed to access workspace {workspace_path}: {e}",
            file=sys.stderr
        )
        return 0

    return total_size


def list_session_files(
    session_id: str,
    workspace_root: Path | None = None,
    storage_adapter: StorageAdapter | None = None,
    pattern: str | None = None,
    logger: SandboxLogger | None = None
) -> list[str]:
    """List all files in session workspace, optionally filtered by glob pattern.

    Returns relative paths of all files in the session workspace. Directories
    are excluded from results. Useful for discovering artifacts created by
    sandbox execution or verifying expected files exist.

    Args:
        session_id: UUIDv4 string identifying the session
        workspace_root: Root directory for session workspaces. Default: Path("workspace")
                       Ignored if storage_adapter is provided.
        storage_adapter: Optional StorageAdapter for workspace operations.
                        If None, creates DiskStorageAdapter with workspace_root.
        pattern: Optional glob pattern (e.g., "*.txt", "**/*.py"). Default: "*" (all files)
        logger: Optional SandboxLogger for structured logging

    Returns:
        list[str]: Sorted list of relative file paths (POSIX-style, no leading slash)

    Examples:
        >>> # List all files in session
        >>> from sandbox import list_session_files
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> files = list_session_files(session_id)
        >>> print(files)
        ['data.txt', 'output.json', 'user_code.py']

        >>> # Filter by pattern
        >>> json_files = list_session_files(session_id, pattern="*.json")
        >>> print(json_files)
        ['output.json']

        >>> # Recursive pattern for nested directories
        >>> py_files = list_session_files(session_id, pattern="**/*.py")
        >>> print(py_files)
        ['user_code.py', 'lib/helper.py']

        >>> # Empty workspace returns empty list
        >>> new_session_files = list_session_files("new-session-id")
        >>> print(new_session_files)
        []

    Notes:
        - Uses rglob() for recursive matching
        - Filters to files only (is_file()) - directories excluded
        - Returns POSIX-style paths with forward slashes on all platforms
        - Empty workspace returns empty list (not an error)
    """
    # Create storage adapter if not provided
    if storage_adapter is None:
        from sandbox.core.storage import DiskStorageAdapter
        if workspace_root is None:
            workspace_root = Path("workspace")
        storage_adapter = DiskStorageAdapter(workspace_root)

    # List files via adapter
    search_pattern = pattern or "*"
    sorted_paths = storage_adapter.list_files(session_id, search_pattern)

    # Log file operation
    if logger is not None:
        logger.log_file_operation(
            operation="list",
            session_id=session_id,
            path=search_pattern,
            file_count=len(sorted_paths)
        )

    return sorted_paths


def read_session_file(
    session_id: str,
    relative_path: str,
    workspace_root: Path | None = None,
    storage_adapter: StorageAdapter | None = None,
    logger: SandboxLogger | None = None
) -> bytes:
    """Read file from session workspace as bytes.

    Reads the contents of a file within the session workspace and returns
    raw bytes. Applications must decode text files using appropriate encoding
    (typically UTF-8). Path traversal attempts are blocked via validation.

    Args:
        session_id: UUIDv4 string identifying the session
        relative_path: Relative path within session workspace (e.g., "data.txt", "dir/output.json")
        workspace_root: Root directory for session workspaces. Default: Path("workspace")
                       Ignored if storage_adapter is provided.
        storage_adapter: Optional StorageAdapter for workspace operations.
                        If None, creates DiskStorageAdapter with workspace_root.
        logger: Optional SandboxLogger for structured logging

    Returns:
        bytes: Raw file contents

    Raises:
        ValueError: If relative_path attempts path traversal or is absolute
        FileNotFoundError: If file does not exist

    Examples:
        >>> # Read text file
        >>> from sandbox import read_session_file
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> data = read_session_file(session_id, "output.txt")
        >>> print(data.decode('utf-8'))
        Hello from sandbox

        >>> # Read binary file
        >>> image_data = read_session_file(session_id, "plot.png")
        >>> print(len(image_data))
        4567

    Security Notes:
        - All paths validated by storage adapter
        - Symlink escapes prevented by path resolution
        - Returns bytes to avoid encoding assumptions
    """
    # Create storage adapter if not provided
    if storage_adapter is None:
        from sandbox.core.storage import DiskStorageAdapter
        if workspace_root is None:
            workspace_root = Path("workspace")
        storage_adapter = DiskStorageAdapter(workspace_root)

    # Read file via adapter
    data = storage_adapter.read_file(session_id, relative_path)

    # Log file operation
    if logger is not None:
        logger.log_file_operation(
            operation="read",
            session_id=session_id,
            path=relative_path,
            file_size=len(data)
        )

    return data


def write_session_file(
    session_id: str,
    relative_path: str,
    data: bytes | str,
    workspace_root: Path | None = None,
    storage_adapter: StorageAdapter | None = None,
    overwrite: bool = True,
    logger: SandboxLogger | None = None
) -> None:
    """Write data to file in session workspace.

    Creates or overwrites a file in the session workspace with the provided
    data. Parent directories are created automatically. Supports both binary
    and text data (text is UTF-8 encoded).

    Args:
        session_id: UUIDv4 string identifying the session
        relative_path: Relative path within session workspace (e.g., "input.txt", "data/config.json")
        data: File content as bytes or str (str is UTF-8 encoded)
        workspace_root: Root directory for session workspaces. Default: Path("workspace")
                       Ignored if storage_adapter is provided.
        storage_adapter: Optional StorageAdapter for workspace operations.
                        If None, creates DiskStorageAdapter with workspace_root.
        overwrite: If False, raises FileExistsError when file exists. Default: True
        logger: Optional SandboxLogger for structured logging

    Raises:
        ValueError: If relative_path attempts path traversal or is absolute
        FileExistsError: If file exists and overwrite=False

    Examples:
        >>> # Write text file
        >>> from sandbox import write_session_file
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> write_session_file(session_id, "input.txt", "Hello from host")

        >>> # Write binary data
        >>> binary_data = b'\\x89PNG\\r\\n\\x1a\\n...'
        >>> write_session_file(session_id, "image.png", binary_data)

    Notes:
        - Parent directories created automatically
        - String data is UTF-8 encoded before writing
        - overwrite=True is default for convenience
    """
    # Create storage adapter if not provided
    if storage_adapter is None:
        from sandbox.core.storage import DiskStorageAdapter
        if workspace_root is None:
            workspace_root = Path("workspace")
        storage_adapter = DiskStorageAdapter(workspace_root)

    # Convert str to bytes if needed
    if isinstance(data, str):
        data = data.encode('utf-8')

    # Check overwrite flag (only for DiskStorageAdapter)
    if not overwrite and hasattr(storage_adapter, '_validate_session_path'):
        try:
            existing_data = storage_adapter.read_file(session_id, relative_path)
            if existing_data:
                raise FileExistsError(
                    f"File '{relative_path}' already exists in session '{session_id}'. "
                    f"Set overwrite=True to replace."
                )
        except FileNotFoundError:
            pass  # File doesn't exist, OK to write

    # Write via adapter
    storage_adapter.write_file(session_id, relative_path, data)

    # Log file operation
    if logger is not None:
        logger.log_file_operation(
            operation="write",
            session_id=session_id,
            path=relative_path,
            file_size=len(data)
        )



def delete_session_path(
    session_id: str,
    relative_path: str,
    workspace_root: Path | None = None,
    storage_adapter: StorageAdapter | None = None,
    recursive: bool = False,
    logger: SandboxLogger | None = None
) -> None:
    """Delete file or directory in session workspace.

    Removes a file or directory from the session workspace. For directories,
    recursive=True must be explicitly set to prevent accidental deletion of
    directory trees. Path traversal attempts are blocked via validation.

    Args:
        session_id: UUIDv4 string identifying the session
        relative_path: Relative path within session workspace (e.g., "temp.txt", "cache/")
        workspace_root: Root directory for session workspaces. Default: Path("workspace")
                       Ignored if storage_adapter is provided.
        storage_adapter: Optional StorageAdapter for workspace operations.
                        If None, creates DiskStorageAdapter with workspace_root.
        recursive: If True, delete directories recursively. Default: False (safety)
        logger: Optional SandboxLogger for structured logging

    Raises:
        ValueError: If relative_path attempts path traversal or is absolute,
                   or if path is a directory and recursive=False
        FileNotFoundError: If path does not exist

    Examples:
        >>> # Delete single file
        >>> from sandbox import delete_session_path
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> delete_session_path(session_id, "temp.txt")

        >>> # Delete directory (requires recursive=True)
        >>> delete_session_path(session_id, "cache", recursive=True)

    Safety Notes:
        - recursive=False by default prevents accidental tree deletion
        - Use delete_session_workspace() to delete entire session
    """
    # Create storage adapter if not provided
    if storage_adapter is None:
        from sandbox.core.storage import DiskStorageAdapter
        if workspace_root is None:
            workspace_root = Path("workspace")
        storage_adapter = DiskStorageAdapter(workspace_root)

    # Delete via adapter (validates paths internally)
    storage_adapter.delete_path(session_id, relative_path, recursive=recursive)

    # Log file operation
    if logger is not None:
        logger.log_file_operation(
            operation="delete",
            session_id=session_id,
            path=relative_path,
            recursive=recursive
        )


def delete_session_workspace(
    session_id: str,
    workspace_root: Path | None = None,
    storage_adapter: StorageAdapter | None = None,
    logger: SandboxLogger | None = None
) -> None:
    """Delete entire session workspace directory.

    Removes the session workspace and all its contents. This is a destructive
    operation that cannot be undone. Commonly used for cleanup after session
    completion or pruning old sessions.

    Args:
        session_id: UUIDv4 string identifying the session
        workspace_root: Root directory for session workspaces. Default: Path("workspace")
                       Ignored if storage_adapter is provided.
        storage_adapter: Optional StorageAdapter for workspace operations.
                        If None, creates DiskStorageAdapter with workspace_root.
        logger: Optional SandboxLogger for structured logging

    Examples:
        >>> from sandbox import delete_session_workspace
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> delete_session_workspace(session_id)

    Safety Notes:
        - This deletes the ENTIRE session workspace
        - Cannot be undone - use with caution
        - Consider using prune_sessions() for automated cleanup
    """
    # Create storage adapter if not provided
    if storage_adapter is None:
        from sandbox.core.storage import DiskStorageAdapter
        if workspace_root is None:
            workspace_root = Path("workspace")
        storage_adapter = DiskStorageAdapter(workspace_root)

    # Delete via adapter
    storage_adapter.delete_session(session_id)

    # Log operation
    if logger is not None:
        logger.log_session_deleted(session_id)


def prune_sessions(
    older_than_hours: float = 24.0,
    workspace_root: Path | None = None,
    storage_adapter: StorageAdapter | None = None,
    dry_run: bool = False,
    logger: SandboxLogger | None = None
) -> PruneResult:
    """Delete session workspaces inactive for specified duration.

    Args:
        older_than_hours: Age threshold in hours
        workspace_root: Root directory. Default: Path("workspace"). Ignored if storage_adapter provided.
        storage_adapter: Optional StorageAdapter. If None, creates DiskStorageAdapter.
        dry_run: If True, report what would be deleted without deleting
        logger: Optional SandboxLogger

    Returns:
        PruneResult with deleted/skipped sessions and metrics
    """
    from datetime import UTC, datetime, timedelta

    # Create storage adapter if not provided
    if storage_adapter is None:
        from sandbox.core.storage import DiskStorageAdapter
        if workspace_root is None:
            workspace_root = Path("workspace")
        storage_adapter = DiskStorageAdapter(workspace_root)

    deleted_sessions = []
    skipped_sessions = []
    reclaimed_bytes = 0
    errors = {}

    # Calculate cutoff timestamp
    cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)

    # Log start of pruning
    if logger is not None:
        logger.log_prune_started(
            older_than_hours=older_than_hours,
            cutoff_time=cutoff.isoformat()
        )

    # Enumerate all sessions
    for session_id in storage_adapter.enumerate_sessions():
        try:
            # Read metadata to check age
            metadata = storage_adapter.read_metadata(session_id)
            updated_at = datetime.fromisoformat(metadata.updated_at)

            if updated_at < cutoff:
                # Session is old enough to prune
                if logger is not None:
                    logger.log_prune_candidate(
                        session_id=session_id,
                        updated_at=metadata.updated_at,
                        age_hours=(datetime.now(UTC) - updated_at).total_seconds() / 3600
                    )

                if not dry_run:
                    session_size = storage_adapter.get_session_size(session_id)
                    storage_adapter.delete_session(session_id)
                    reclaimed_bytes += session_size

                    if logger is not None:
                        logger.log_prune_deleted(
                            session_id=session_id,
                            size_bytes=session_size
                        )

                deleted_sessions.append(session_id)
        except FileNotFoundError:
            # No metadata file - legacy session or incomplete session
            skipped_sessions.append(session_id)
            if logger is not None:
                logger.log_prune_skipped(
                    session_id=session_id,
                    reason="missing_metadata"
                )
        except (json.JSONDecodeError, ValueError) as e:
            # Corrupted metadata or invalid timestamp format
            skipped_sessions.append(session_id)
            reason = "corrupted_metadata"
            if "isoformat" in str(e).lower() or "invalid" in str(e).lower():
                reason = "corrupted_timestamp"
            if logger is not None:
                logger.log_prune_skipped(
                    session_id=session_id,
                    reason=reason
                )
        except Exception as e:
            errors[session_id] = str(e)
            if logger is not None:
                logger.log_prune_error(
                    session_id=session_id,
                    error=str(e)
                )

    # Log pruning operation
    if logger is not None:
        logger.log_prune_completed(
            deleted_count=len(deleted_sessions),
            skipped_count=len(skipped_sessions),
            error_count=len(errors),
            reclaimed_bytes=reclaimed_bytes,
            dry_run=dry_run
        )

    return PruneResult(
        deleted_sessions=deleted_sessions,
        skipped_sessions=skipped_sessions,
        reclaimed_bytes=reclaimed_bytes,
        errors=errors,
        dry_run=dry_run
    )
