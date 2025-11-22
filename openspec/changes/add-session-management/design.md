# Design: Session Management

## Architecture Overview

Session management extends the existing three-layer architecture without breaking abstractions:

```
┌─────────────────────────────────────────────────────────┐
│ Application Layer (LLM Integration / API Server)        │
│ - Manages session lifecycles (create, cleanup)          │
│ - Uses session helpers + file operations                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Session Layer (NEW: sandbox/sessions.py)                │
│ - Session ID generation (UUIDv4)                        │
│ - Session-to-workspace mapping                          │
│ - Factory helpers (create_session_sandbox, etc.)        │
│ - File operations (list, read, write, delete)           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Core Layer (UNCHANGED)                                   │
│ - ExecutionPolicy, SandboxResult (extended metadata)    │
│ - BaseSandbox, create_sandbox factory                   │
│ - SandboxLogger (extended with session context)         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Runtime Layer (UNCHANGED)                                │
│ - PythonSandbox.execute() (workspace already isolated)  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ Host Layer (UNCHANGED)                                   │
│ - Wasmtime/WASI configuration with per-workspace mounts │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Decision 1: Stateless Session Helpers
**Choice**: Provide stateless functions (`create_session_sandbox`, `get_session_sandbox`) instead of a stateful `SessionManager` class.

**Rationale**:
- Applications may want different caching strategies (in-memory, Redis, database)
- Stateless design follows factory pattern established by `create_sandbox()`
- Simpler to test and reason about
- Applications can layer their own state management on top

**Trade-off**: Applications must track session IDs themselves, but this is already required for API routing.

### Decision 2: Session ID as Directory Name
**Choice**: Use UUIDv4 string directly as directory name (`workspace/<uuid>/`).

**Rationale**:
- UUIDs are safe filesystem names (alphanumeric + hyphens only)
- No encoding/escaping needed
- Prevents path traversal by design (no `/` or `..` in UUID)
- Opaque to clients - no information leakage

**Trade-off**: Large directory counts in `workspace/` root. Applications needing optimization can implement sharding (e.g., `workspace/<first-2-chars>/<uuid>/`) as a wrapper.

### Decision 3: File Operations as Standalone Functions
**Choice**: Provide module-level functions (`list_session_files()`, `read_session_file()`) rather than methods on sandbox instances.

**Rationale**:
- File operations are independent of code execution
- May want to inspect session files without creating a sandbox instance
- Clearer separation: sandbox executes code, file ops manage artifacts
- Matches pattern of vendored package management (`copy_vendor_to_workspace()`)

**Trade-off**: Slightly more verbose (pass session_id to each call). Could add convenience methods later if needed.

### Decision 4: Metadata Extension vs. Dedicated Field
**Choice**: Use `SandboxResult.metadata["session_id"]` instead of adding `session_id: str | None` to model.

**Rationale**:
- Session usage is optional - dedicated field would be `None` for non-session usage
- Metadata already exists for runtime-specific extensions
- Avoids model schema changes for optional feature
- Consistent with current pattern (e.g., runtime info in metadata)

**Trade-off**: Less type-safe than dedicated field. Can reconsider in future if session usage becomes universal.

## Session Lifecycle

### Create Session
```python
session_id, sandbox = create_session_sandbox(
    runtime=RuntimeType.PYTHON,
    policy=custom_policy,
    workspace_root=Path("workspace")
)
# Creates: workspace/<session_id>/ directory
# Returns: (session_id: str, PythonSandbox instance)
```

**Implementation**:
1. Generate UUIDv4 → `session_id`
2. Construct workspace path: `workspace_root / session_id`
3. Create directory with `mkdir(parents=True, exist_ok=True)`
4. Call `create_sandbox(workspace=workspace_path, ...)`
5. Inject `session_id` into logger context
6. Return `(session_id, sandbox)`

### Use Session
```python
# For subsequent executions in same session
sandbox = get_session_sandbox(
    session_id=session_id,
    runtime=RuntimeType.PYTHON
)
result = sandbox.execute(code)
# Guest code sees files from previous executions in /app
```

**Implementation**:
1. Resolve workspace path from session_id
2. Validate directory exists (create if missing with `exist_ok=True`)
3. Call `create_sandbox(workspace=workspace_path, ...)`
4. Return sandbox instance

**Key insight**: No persistent state needed - workspace directory itself is the source of truth.

### Cleanup Session
```python
delete_session_workspace(session_id, workspace_root=Path("workspace"))
# Removes: workspace/<session_id>/ and all contents
```

**Implementation**:
1. Resolve workspace path
2. Validate path is within workspace_root (prevent traversal)
3. Use `shutil.rmtree()` with `ignore_errors=False`
4. Log deletion event

## File Operations Security Model

All file operations validate paths using this pattern:

```python
def _validate_session_path(
    session_id: str,
    relative_path: str,
    workspace_root: Path
) -> Path:
    """Validate and resolve path within session workspace.
    
    Raises ValueError if path escapes workspace.
    """
    workspace = workspace_root / session_id
    target = workspace / relative_path
    
    # Resolve symlinks and normalize
    resolved = target.resolve()
    
    # Ensure result is within workspace
    if not resolved.is_relative_to(workspace.resolve()):
        raise ValueError(f"Path escapes session workspace: {relative_path}")
    
    return resolved
```

**Attack vectors prevented**:
- `../../../etc/passwd` → ValueError
- Absolute paths: `/etc/passwd` → ValueError (not relative to workspace)
- Symlink attacks: resolved paths checked against workspace

## Integration with Existing Layers

### Core Models (ExecutionPolicy, SandboxResult)
**Changes**: None to model schemas. Usage pattern:
- Session helpers pass custom `workspace` to `create_sandbox()`
- Sandbox execution injects `metadata["session_id"]` into result
- Logger methods accept optional `session_id` kwarg

### Factory API (create_sandbox)
**Changes**: None. Session helpers are thin wrappers:
```python
def create_session_sandbox(...):
    session_id = str(uuid.uuid4())
    workspace = workspace_root / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    
    sandbox = create_sandbox(
        runtime=runtime,
        workspace=workspace,  # ← Key parameter
        policy=policy,
        logger=logger
    )
    return session_id, sandbox
```

### Python Runtime (PythonSandbox)
**Changes**: None to execution logic. Already supports per-instance workspace via `__init__(workspace=...)`.

### Host Layer (WASI Configuration)
**Changes**: None. WASI preopen already uses sandbox instance's workspace path. Session isolation achieved by passing different workspace to each sandbox instance.

## Logging Strategy

Extend `SandboxLogger` events with session context:

```python
# In session helpers
logger.log_execution_start(
    runtime="python",
    policy=policy,
    session_id=session_id  # ← New kwarg
)

# In file operations
logger.log_event(
    "session.file.read",
    session_id=session_id,
    path=relative_path
)
```

**Log events added**:
- `session.created` - session_id, workspace_path
- `session.retrieved` - session_id, workspace_path
- `session.deleted` - session_id
- `session.file.list` - session_id, pattern, count
- `session.file.read` - session_id, path, size_bytes
- `session.file.write` - session_id, path, size_bytes
- `session.file.delete` - session_id, path

## Backwards Compatibility

**Non-session usage (current pattern)**:
```python
sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
result = sandbox.execute(code)
# Works unchanged - uses default workspace/ directory
```

**Session-aware usage (new pattern)**:
```python
session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON)
result = sandbox.execute(code)
# Uses workspace/<session_id>/ directory
```

**Coexistence**: Both patterns work simultaneously. Applications can migrate incrementally.

## Testing Strategy

### Unit Tests
- Session ID generation (UUID format validation)
- Workspace path construction
- Path traversal attack prevention
- File operations (list, read, write, delete)
- Error handling (missing files, permission errors)

### Integration Tests
- Session isolation: Two sessions, files in A not visible to B
- Session persistence: Multiple executions in same session see each other's files
- File operations: Write file from host, read from guest
- Cleanup: Delete session workspace, verify removal

### Security Tests
- Path traversal: `read_session_file(session_id, "../../../etc/passwd")` → ValueError
- Symlink attacks: Create symlink escaping workspace → operations fail
- Absolute paths: Operations with `/tmp/evil` → ValueError

## API Surface Summary

**New module**: `sandbox/sessions.py`

**Exports**:
```python
# Session lifecycle
create_session_sandbox(runtime, policy, workspace_root, logger) -> (str, BaseSandbox)
get_session_sandbox(session_id, runtime, policy, workspace_root, logger) -> BaseSandbox
delete_session_workspace(session_id, workspace_root) -> None

# File operations
list_session_files(session_id, workspace_root, pattern) -> list[str]
read_session_file(session_id, relative_path, workspace_root) -> bytes
write_session_file(session_id, relative_path, data, workspace_root, overwrite) -> None
delete_session_path(session_id, relative_path, workspace_root, recursive) -> None
```

**Public API update**: `sandbox/__init__.py` adds:
```python
__all__ = [
    # ... existing exports ...
    "create_session_sandbox",
    "get_session_sandbox",
    "delete_session_workspace",
    "list_session_files",
    "read_session_file",
    "write_session_file",
    "delete_session_path",
]
```

## Performance Considerations

- **Session creation**: O(1) - mkdir + UUID generation (microseconds)
- **File listing**: O(n) where n = files in session workspace (not entire workspace/)
- **File operations**: Standard filesystem I/O, bounded by policy limits
- **Workspace directory growth**: Linear in number of sessions. Applications should implement cleanup policies.

## Future Extensions

These are explicitly **out of scope** for this change but noted for future consideration:

1. **Session Manager class**: Optional stateful wrapper for applications wanting in-memory session tracking
2. **Session metadata storage**: Persist session creation time, last access, tags
3. **Disk quota enforcement**: Per-session storage limits
4. **Session-aware vendored packages**: Copy different vendored packages per session
5. **Cross-session data sharing**: Explicit API for controlled cross-session file access
