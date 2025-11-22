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

import contextlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sandbox.core.logging import SandboxLogger


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
        # Session created before metadata feature - skip silently
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
    # Validate session_id contains no path separators
    if os.sep in session_id or "/" in session_id or "\\" in session_id:
        raise ValueError(
            f"session_id '{session_id}' must not contain path separators (/, \\)"
        )

    # Resolve workspace path: workspace_root / session_id / relative_path
    workspace = workspace_root / session_id

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
    workspace = workspace_root / session_id
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


def _enumerate_sessions(workspace_root: Path) -> list[str]:
    """List all UUID-formatted session directories in workspace.

    Enumerates subdirectories in workspace_root and filters to those matching
    UUID format (36 characters with hyphens in standard positions). Non-UUID
    directories are ignored (no error).

    Args:
        workspace_root: Root directory containing session workspaces

    Returns:
        list[str]: List of session IDs (directory names) that match UUID format

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

    sessions = []
    for item in workspace_root.iterdir():
        if not item.is_dir():
            continue

        # Check if directory name matches UUID format (loose check)
        name = item.name
        if len(name) == 36 and name.count('-') == 4:
            # Basic UUID format validation (8-4-4-4-12 pattern)
            parts = name.split('-')
            if (len(parts) == 5 and
                len(parts[0]) == 8 and
                len(parts[1]) == 4 and
                len(parts[2]) == 4 and
                len(parts[3]) == 4 and
                len(parts[4]) == 12):
                sessions.append(name)

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


def delete_session_workspace(
    session_id: str,
    workspace_root: Path | None = None
) -> None:
    """Delete session workspace and all contained files.

    Permanently removes the session's workspace directory and all files within it.
    This is the cleanup operation for ending a session. Operation is idempotent -
    deleting a nonexistent workspace succeeds silently.

    Args:
        session_id: UUIDv4 string identifying the session
        workspace_root: Root directory for session workspaces. Default: Path("workspace")

    Raises:
        ValueError: If session_id contains path separators (security validation)
        PermissionError: If filesystem permissions prevent deletion
        OSError: If deletion fails for other filesystem reasons

    Examples:
        >>> # Clean up session after completion
        >>> from sandbox import delete_session_workspace
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> delete_session_workspace(session_id)

        >>> # Idempotent: deleting again is safe
        >>> delete_session_workspace(session_id)  # No error

        >>> # Workspace directory is removed
        >>> from pathlib import Path
        >>> workspace_path = Path("workspace") / session_id
        >>> workspace_path.exists()
        False

    Safety Notes:
        - Path validation prevents traversal attacks (e.g., session_id="../etc")
        - Uses shutil.rmtree with ignore_errors=False to surface permission issues
        - FileNotFoundError is caught for idempotent behavior
        - Applications should delete sessions after use to prevent disk growth
    """
    if workspace_root is None:
        workspace_root = Path("workspace")

    # Validate session_id (prevents path traversal)
    if os.sep in session_id or "/" in session_id or "\\" in session_id:
        raise ValueError(
            f"session_id '{session_id}' must not contain path separators (/, \\)"
        )

    # Resolve workspace path
    workspace = workspace_root / session_id

    # Delete workspace directory recursively
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(workspace, ignore_errors=False)


def prune_sessions(
    older_than_hours: float = 24.0,
    workspace_root: Path | None = None,
    dry_run: bool = False,
    logger: SandboxLogger | None = None
) -> PruneResult:
    """Delete session workspaces inactive for specified duration.

    Enumerates all session workspaces and deletes those whose updated_at
    timestamp exceeds the age threshold. Sessions without metadata are skipped
    (logged as warnings). Provides dry-run mode to preview deletions without
    actually removing files.

    This function is not concurrency-safe - it should run during maintenance
    windows when no other processes are accessing session workspaces.

    Args:
        older_than_hours: Age threshold in hours (based on updated_at). Default: 24.0
        workspace_root: Root directory for sessions. Default: Path("workspace")
        dry_run: If True, list candidates without deleting. Default: False
        logger: Optional structured logger for audit trail

    Returns:
        PruneResult: Statistics about pruning operation (deleted, skipped, reclaimed bytes, errors)

    Examples:
        >>> # Prune sessions older than 24 hours (default)
        >>> from sandbox import prune_sessions
        >>> result = prune_sessions()
        >>> print(result)
        Pruned 5 sessions (2 skipped), reclaimed 12.3 MB

        >>> # Dry-run to preview deletions
        >>> result = prune_sessions(older_than_hours=48.0, dry_run=True)
        >>> print(result.deleted_sessions)
        ['session-1', 'session-2', 'session-3']
        >>> print(result)
        Would prune 3 sessions, reclaimed 0 B

        >>> # Aggressive cleanup (1 hour threshold)
        >>> result = prune_sessions(older_than_hours=1.0)

        >>> # Custom workspace location
        >>> from pathlib import Path
        >>> result = prune_sessions(
        ...     older_than_hours=72.0,
        ...     workspace_root=Path("/var/lib/sandbox/workspaces")
        ... )

    Notes:
        - Sessions without .metadata.json are skipped (not deleted)
        - Corrupted metadata files are logged as warnings and skipped
        - Permission errors during deletion are captured in result.errors
        - In dry-run mode, reclaimed_bytes is always 0
        - Uses updated_at timestamp (not created_at) for age calculation
    """
    if workspace_root is None:
        workspace_root = Path("workspace")

    # Initialize result tracking
    deleted_sessions: list[str] = []
    skipped_sessions: list[str] = []
    reclaimed_bytes = 0
    errors: dict[str, str] = {}

    # Log pruning start
    if logger is not None:
        logger.log_prune_started(
            threshold_hours=older_than_hours,
            workspace_root=str(workspace_root),
            dry_run=dry_run
        )

    # Enumerate all session directories
    session_ids = _enumerate_sessions(workspace_root)

    for session_id in session_ids:
        workspace_path = workspace_root / session_id

        # Read session metadata
        metadata = _read_session_metadata(session_id, workspace_root)

        if metadata is None:
            # Missing or corrupted metadata - skip session
            skipped_sessions.append(session_id)

            if logger is not None:
                logger.log_prune_skipped(
                    session_id=session_id,
                    reason="missing_metadata"
                )
            continue

        # Calculate session age
        try:
            age_hours = _calculate_session_age(metadata)
        except (ValueError, TypeError) as e:
            # Corrupted timestamp - skip session
            skipped_sessions.append(session_id)

            if logger is not None:
                logger.log_prune_skipped(
                    session_id=session_id,
                    reason=f"corrupted_timestamp: {e}"
                )
            continue

        # Check if session meets age threshold
        if age_hours >= older_than_hours:
            # Log candidate
            if logger is not None:
                logger.log_prune_candidate(
                    session_id=session_id,
                    age_hours=age_hours,
                    threshold_hours=older_than_hours
                )

            # Calculate workspace size before deletion
            if not dry_run:
                workspace_size = _calculate_workspace_size(workspace_path)
                reclaimed_bytes += workspace_size

            # Delete workspace (if not dry-run)
            if not dry_run:
                try:
                    shutil.rmtree(workspace_path, ignore_errors=False)
                    deleted_sessions.append(session_id)

                    if logger is not None:
                        logger.log_prune_deleted(
                            session_id=session_id,
                            age_hours=age_hours,
                            reclaimed_bytes=workspace_size
                        )
                except (OSError, PermissionError) as e:
                    # Capture deletion error
                    errors[session_id] = str(e)

                    if logger is not None:
                        logger.log_prune_error(
                            session_id=session_id,
                            error=str(e)
                        )
            else:
                # Dry-run: add to deleted list without actually deleting
                deleted_sessions.append(session_id)

    # Log completion
    if logger is not None:
        logger.log_prune_completed(
            deleted_count=len(deleted_sessions),
            skipped_count=len(skipped_sessions),
            error_count=len(errors),
            reclaimed_bytes=reclaimed_bytes,
            dry_run=dry_run
        )

    # Return result
    return PruneResult(
        deleted_sessions=deleted_sessions,
        skipped_sessions=skipped_sessions,
        reclaimed_bytes=reclaimed_bytes,
        errors=errors,
        dry_run=dry_run
    )


def list_session_files(
    session_id: str,
    workspace_root: Path | None = None,
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
        pattern: Optional glob pattern (e.g., "*.txt", "**/*.py"). Default: "*" (all files)

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
    if workspace_root is None:
        workspace_root = Path("workspace")

    # Resolve and validate workspace path
    workspace = _ensure_session_workspace(session_id, workspace_root)

    # List files matching pattern
    search_pattern = pattern or "*"
    all_paths = workspace.rglob(search_pattern)

    # Filter to files only (exclude directories)
    files = [p for p in all_paths if p.is_file()]

    # Convert to relative paths (POSIX-style)
    relative_paths = [p.relative_to(workspace).as_posix() for p in files]

    # Sort results
    sorted_paths = sorted(relative_paths)

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

    Returns:
        bytes: Raw file contents

    Raises:
        ValueError: If relative_path attempts path traversal or is absolute
        FileNotFoundError: If file does not exist
        IsADirectoryError: If path points to a directory
        PermissionError: If file cannot be read due to permissions

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

        >>> # Path traversal rejected
        >>> try:
        ...     read_session_file(session_id, "../etc/passwd")
        ... except ValueError as e:
        ...     print(f"Blocked: {e}")
        Blocked: Path '../etc/passwd' escapes session workspace boundary

        >>> # Missing file raises error
        >>> try:
        ...     read_session_file(session_id, "nonexistent.txt")
        ... except FileNotFoundError:
        ...     print("File not found")
        File not found

    Security Notes:
        - All paths validated via _validate_session_path()
        - Symlink escapes prevented by path resolution
        - Returns bytes to avoid encoding assumptions
    """
    if workspace_root is None:
        workspace_root = Path("workspace")

    # Resolve and validate path (prevents traversal)
    full_path = _validate_session_path(session_id, relative_path, workspace_root)

    # Read file contents (let FileNotFoundError propagate)
    data = full_path.read_bytes()

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
        overwrite: If False, raises FileExistsError when file exists. Default: True

    Raises:
        ValueError: If relative_path attempts path traversal or is absolute
        FileExistsError: If file exists and overwrite=False
        PermissionError: If file cannot be written due to permissions
        OSError: If write fails for other filesystem reasons

    Examples:
        >>> # Write text file
        >>> from sandbox import write_session_file
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> write_session_file(session_id, "input.txt", "Hello from host")

        >>> # Write binary data
        >>> binary_data = b'\x89PNG\r\n\x1a\n...'
        >>> write_session_file(session_id, "image.png", binary_data)

        >>> # Create nested directory structure
        >>> write_session_file(session_id, "data/config.json", '{"key": "value"}')

        >>> # Prevent overwrite
        >>> try:
        ...     write_session_file(session_id, "input.txt", "new data", overwrite=False)
        ... except FileExistsError:
        ...     print("File already exists")
        File already exists

        >>> # Path traversal rejected
        >>> try:
        ...     write_session_file(session_id, "../etc/evil", "data")
        ... except ValueError as e:
        ...     print(f"Blocked: {e}")
        Blocked: Path '../etc/evil' escapes session workspace boundary

    Notes:
        - Parent directories created automatically (mkdir parents=True)
        - String data is UTF-8 encoded before writing
        - overwrite=True is default for convenience (matches typical usage)
        - Use overwrite=False to ensure files aren't accidentally replaced
    """
    if workspace_root is None:
        workspace_root = Path("workspace")

    # Resolve and validate path (prevents traversal)
    full_path = _validate_session_path(session_id, relative_path, workspace_root)

    # Check overwrite flag
    if not overwrite and full_path.exists():
        raise FileExistsError(
            f"File '{relative_path}' already exists in session '{session_id}'. "
            f"Set overwrite=True to replace."
        )

    # Create parent directories
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert str to bytes if needed
    if isinstance(data, str):
        data = data.encode('utf-8')

    # Write data
    full_path.write_bytes(data)

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
        recursive: If True, delete directories recursively. Default: False (safety)

    Raises:
        ValueError: If relative_path attempts path traversal or is absolute,
                   or if path is a directory and recursive=False
        FileNotFoundError: If path does not exist (explicit errors, not silent)
        PermissionError: If path cannot be deleted due to permissions
        OSError: If deletion fails for other filesystem reasons

    Examples:
        >>> # Delete single file
        >>> from sandbox import delete_session_path
        >>> session_id = "550e8400-e29b-41d4-a716-446655440000"
        >>> delete_session_path(session_id, "temp.txt")

        >>> # Delete directory (requires recursive=True)
        >>> delete_session_path(session_id, "cache", recursive=True)

        >>> # Error if recursive not set for directory
        >>> try:
        ...     delete_session_path(session_id, "data")
        ... except ValueError as e:
        ...     print(f"Error: {e}")
        Error: Cannot delete directory 'data' without recursive=True

        >>> # Missing path raises error (not silent)
        >>> try:
        ...     delete_session_path(session_id, "nonexistent.txt")
        ... except FileNotFoundError:
        ...     print("File not found")
        File not found

        >>> # Path traversal rejected
        >>> try:
        ...     delete_session_path(session_id, "../etc/passwd")
        ... except ValueError as e:
        ...     print(f"Blocked: {e}")
        Blocked: Path '../etc/passwd' escapes session workspace boundary

    Safety Notes:
        - recursive=False by default prevents accidental tree deletion
        - FileNotFoundError is NOT caught - caller must handle missing paths
        - Use delete_session_workspace() to delete entire session
        - Path validation prevents escapes and symlink attacks
    """
    if workspace_root is None:
        workspace_root = Path("workspace")

    # Resolve and validate path (prevents traversal)
    full_path = _validate_session_path(session_id, relative_path, workspace_root)

    # Check if path is directory
    if full_path.is_dir():
        if not recursive:
            raise ValueError(
                f"Cannot delete directory '{relative_path}' without recursive=True. "
                f"Set recursive=True to delete directory and all contents."
            )
        # Delete directory recursively
        shutil.rmtree(full_path)
    else:
        # Delete file (let FileNotFoundError propagate)
        full_path.unlink()

    # Log file operation
    if logger is not None:
        logger.log_file_operation(
            operation="delete",
            session_id=session_id,
            path=relative_path,
            recursive=recursive
        )
