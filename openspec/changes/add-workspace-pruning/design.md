# Design: Workspace Pruning with Session Metadata

## Overview
This design extends session management to track temporal metadata (creation and update timestamps) and enable automated cleanup of stale workspaces. The implementation balances simplicity, reliability, and backwards compatibility.

## Architecture

### Metadata Model

**Storage Location**: `.metadata.json` within each session workspace
```
workspace/
  <session_id>/
    .metadata.json        # Session metadata (new)
    user_code.py          # Existing session files
    data.txt
    ...
```

**Schema**:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2025-11-22T10:15:30.123456Z",
  "updated_at": "2025-11-22T14:22:18.987654Z",
  "version": 1
}
```

**Field Definitions**:
- `session_id`: UUIDv4 string (redundant with directory name, but useful for validation)
- `created_at`: ISO 8601 UTC timestamp with microsecond precision
- `updated_at`: ISO 8601 UTC timestamp, refreshed on each `execute()` call
- `version`: Schema version (currently 1, enables future migrations)

**Rationale for JSON**:
- Human-readable for debugging
- Trivial to parse with stdlib (`json.load()`)
- Extensible: Can add fields like `execution_count`, `last_error_at` later
- Standard format: Tooling-friendly for scripts/monitoring

### Timestamp Lifecycle

**Creation** (`create_session_sandbox()`):
```python
session_id = str(uuid.uuid4())
workspace_path = workspace_root / session_id
workspace_path.mkdir(parents=True, exist_ok=True)

metadata = {
    "session_id": session_id,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "version": 1
}
(workspace_path / ".metadata.json").write_text(json.dumps(metadata, indent=2))
```

**Update** (`SessionAwareSandbox.execute()`):
```python
def execute(self, code: str, **kwargs: Any) -> Any:
    result = self._sandbox.execute(code, session_id=self.session_id, **kwargs)
    
    # Refresh updated_at timestamp after successful execution
    _update_session_timestamp(self.session_id, workspace_root)
    
    return result
```

**Update Helper** (`_update_session_timestamp()`):
```python
def _update_session_timestamp(session_id: str, workspace_root: Path) -> None:
    metadata_path = workspace_root / session_id / ".metadata.json"
    
    if not metadata_path.exists():
        # Session created before metadata feature - skip silently
        return
    
    try:
        metadata = json.loads(metadata_path.read_text())
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(json.dumps(metadata, indent=2))
    except (json.JSONDecodeError, OSError) as e:
        # Log warning but don't fail execution
        logger.warning(f"Failed to update session metadata: {e}")
```

### Pruning Algorithm

**Signature**:
```python
def prune_sessions(
    older_than_hours: float = 24.0,
    workspace_root: Path | None = None,
    dry_run: bool = False,
    logger: SandboxLogger | None = None
) -> PruneResult:
    """Delete session workspaces inactive for specified duration.
    
    Args:
        older_than_hours: Age threshold in hours (based on updated_at)
        workspace_root: Root directory for sessions (default: Path("workspace"))
        dry_run: If True, list candidates without deleting
        logger: Optional structured logger for audit trail
    
    Returns:
        PruneResult: Named tuple with (deleted_sessions, skipped_sessions, 
                     reclaimed_bytes, errors)
    """
```

**Algorithm**:
```python
1. Enumerate all subdirectories in workspace_root
2. For each directory:
   a. Check if .metadata.json exists
   b. If not: skip (log warning, count as skipped)
   c. Parse metadata and extract updated_at
   d. Calculate age: now - updated_at
   e. If age >= threshold:
      - If dry_run: add to candidates list
      - Else: delete workspace with shutil.rmtree()
      - Log deletion (session_id, age, size)
   f. Handle errors gracefully (permission denied, corrupted metadata)
3. Return PruneResult with counts and reclaimed space
```

**PruneResult Model**:
```python
@dataclass
class PruneResult:
    """Result of workspace pruning operation."""
    deleted_sessions: list[str]          # Session IDs deleted
    skipped_sessions: list[str]          # Sessions without metadata
    reclaimed_bytes: int                 # Disk space freed
    errors: dict[str, str]               # session_id -> error message
    dry_run: bool                        # Was this a dry run?
```

### Edge Cases and Error Handling

**Missing Metadata**:
- **Cause**: Session created before metadata feature, or manual deletion
- **Handling**: Skip session, log warning, count in `skipped_sessions`
- **Rationale**: Conservative approach - don't delete sessions we can't date

**Corrupted Metadata**:
- **Cause**: Partial write, disk error, manual editing
- **Handling**: Catch `json.JSONDecodeError`, log error, count in `skipped_sessions`
- **Future**: Consider `repair_session_metadata()` using filesystem mtimes

**Permission Errors**:
- **Cause**: Insufficient permissions to delete workspace
- **Handling**: Catch `PermissionError`, log error, add to `errors` dict, continue
- **Rationale**: Partial pruning is better than failing entirely

**Concurrent Execution**:
- **Risk**: Session deleted during active `execute()` call
- **Mitigation**: Document that pruning is not concurrency-safe
- **Future**: Consider file locking (`.lock` file) or check for recent activity

**Clock Skew**:
- **Risk**: System clock jumps backwards, timestamps become invalid
- **Mitigation**: Use `datetime.now(timezone.utc)` for consistency
- **Fallback**: Could compare `updated_at < created_at` as sanity check

### Integration Points

**Modified Functions**:
1. `create_session_sandbox()`: Write `.metadata.json` after workspace creation
2. `SessionAwareSandbox.execute()`: Call `_update_session_timestamp()` after execution
3. New `prune_sessions()`: Standalone function in `sandbox/sessions.py`

**Public API Additions**:
```python
# In sandbox/__init__.py
from sandbox.sessions import (
    create_session_sandbox,
    get_session_sandbox,
    # ... existing exports ...
    prune_sessions,           # NEW
    PruneResult,              # NEW
)
```

**Logging Events**:
- `session.metadata.created`: When `.metadata.json` is written
- `session.metadata.updated`: When `updated_at` is refreshed
- `session.prune.started`: Pruning operation begins
- `session.prune.candidate`: Session identified for deletion
- `session.prune.deleted`: Session workspace deleted
- `session.prune.completed`: Pruning operation finished

### Backwards Compatibility

**Existing Sessions**:
- Sessions without `.metadata.json` continue working normally
- `execute()` attempts to update timestamp but skips if metadata missing
- Pruning skips sessions without metadata (logged as `skipped_sessions`)

**Migration Strategy**:
- No automatic migration of existing sessions
- Document that pruning only affects sessions created after feature deployment
- Optional: Provide `repair_session_metadata()` to backfill timestamps from mtimes

### Security Considerations

**Path Traversal**:
- Metadata path constructed as `workspace_root / session_id / ".metadata.json"`
- `_validate_session_path()` already prevents traversal via session_id
- No additional validation needed (session_id is UUIDv4 by design)

**Metadata Tampering**:
- Guest code cannot write to `.metadata.json` (WASI preopen excludes dotfiles)
- Host code is trusted - no need for signing/verification
- Future: Could validate `session_id` field matches directory name

**Privilege Escalation**:
- Pruning runs with host process privileges (same as `delete_session_workspace()`)
- No additional security implications beyond existing deletion APIs

### Testing Strategy

**Unit Tests**:
- `test_metadata_creation()`: Verify `.metadata.json` created on `create_session_sandbox()`
- `test_metadata_update()`: Verify `updated_at` refreshed after `execute()`
- `test_prune_old_sessions()`: Verify sessions older than threshold are deleted
- `test_prune_dry_run()`: Verify dry-run lists candidates without deleting
- `test_prune_skips_missing_metadata()`: Verify sessions without metadata are skipped
- `test_prune_handles_corrupted_metadata()`: Verify error handling for invalid JSON
- `test_backwards_compat_no_metadata()`: Verify sessions without metadata still execute

**Integration Tests**:
- Multi-turn workflow: Create session, execute multiple times, verify `updated_at` changes
- Prune workflow: Create old/new sessions, prune, verify only old sessions deleted

**Security Tests**:
- Verify guest code cannot read/write `.metadata.json`
- Verify pruning respects workspace_root boundaries

### Performance Considerations

**Metadata Write Overhead**:
- Single JSON write per session creation: ~1ms (negligible)
- Timestamp update per execution: ~1ms (amortized across execution time)
- No measurable impact on execution latency

**Pruning Performance**:
- Directory enumeration: O(n) where n = number of sessions
- Metadata parsing: O(n) JSON reads (~1ms each)
- Deletion: O(n) `shutil.rmtree()` calls (~10-100ms each depending on size)
- Expected: 100 sessions/second pruning throughput on typical hardware

**Optimization Opportunities**:
- Parallel pruning: Use `ThreadPoolExecutor` for concurrent deletions
- Lazy metadata updates: Batch timestamp writes (trade freshness for throughput)
- Index file: Maintain `_sessions_index.json` for fast age queries (future)

### Future Extensions

**Configurable Retention Policies**:
```python
prune_sessions(
    policy=RetentionPolicy(
        max_age_hours=24,
        max_sessions=1000,
        min_free_space_gb=10
    )
)
```

**Rich Metadata**:
Add fields like `execution_count`, `total_fuel_consumed`, `last_error` for analytics

**Session Archival**:
```python
archive_sessions(
    older_than_hours=168,  # 1 week
    archive_path=Path("archive/")
)
```

**Incremental Pruning**:
```python
prune_sessions(
    older_than_hours=24,
    max_deletions=100  # Stop after 100 deletions
)
```
