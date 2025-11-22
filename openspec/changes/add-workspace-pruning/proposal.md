# Proposal: Add Workspace Pruning

## Objective
Enable automated cleanup of stale session workspaces by tracking session timestamps (creation and last update times) and providing a pruning command that removes sessions older than a specified age threshold.

## Problem
The current session management implementation creates isolated workspace directories (`workspace/<session_id>/`) for each session but provides no mechanism to:

1. **Track workspace age**: No record of when a session was created or last modified
2. **Identify stale workspaces**: Cannot determine which sessions are inactive and safe to delete
3. **Automate cleanup**: Must manually inspect directories and use filesystem operations to prune old workspaces

**Real-world scenario**: A production LLM service creates hundreds of session workspaces daily. Without automated pruning, the `workspace/` directory grows unbounded, consuming disk space and degrading filesystem performance. Operators need a simple command like `prune_sessions(older_than_hours=24)` to safely clean up inactive sessions.

**Current workaround**: Host applications must implement their own timestamp tracking, workspace enumeration, and deletion logic - duplicating effort across integrations and risking inconsistent cleanup behavior.

## Solution
Extend session management with two complementary features:

1. **Session metadata tracking**: Record `created_at` and `updated_at` timestamps in a `.metadata.json` file within each session workspace
2. **Workspace pruning API**: Provide `prune_sessions()` function to enumerate and delete sessions meeting age criteria

This approach integrates cleanly with the existing session model:
- **Minimal overhead**: Metadata written only on session creation and execution
- **Filesystem-based**: No external database required - timestamps live alongside session data
- **Backwards compatible**: Existing sessions without metadata continue working; pruning skips sessions without metadata

## Scope

### In Scope
- Session metadata model (`.metadata.json` with `created_at`, `updated_at` fields)
- Automatic metadata creation on `create_session_sandbox()`
- Automatic `updated_at` refresh on `execute()` within session
- Manual metadata update via `touch_session()` helper
- Pruning API: `prune_sessions(older_than_hours=24, workspace_root=Path("workspace"))`
- Pruning criteria: Age-based filtering using `updated_at` timestamp
- Dry-run mode for pruning (list candidates without deleting)
- Structured logging for prune operations (sessions deleted, disk space reclaimed)
- Tests for metadata persistence, update behavior, and prune filtering

### Out of Scope
- Background daemon or scheduler for automated pruning (host application concern)
- Disk quota enforcement per session
- Session archival or backup before deletion
- Metadata encryption or signing
- Cross-session metadata queries (e.g., "list all sessions for user X")
- Alternative pruning criteria (e.g., by size, execution count) - can extend later
- Migration of existing sessions to add metadata retroactively

## Rationale
**Why filesystem-based metadata?**
- Simplicity: No dependency on external databases or state stores
- Reliability: Metadata cannot go out-of-sync with workspace (deleted together)
- Portability: Sessions can be moved between hosts by copying directories

**Why `.metadata.json` filename?**
- Hidden from guest code (WASI preopen doesn't expose dotfiles by default)
- JSON format allows future extension (add fields without breaking schema)
- Standard naming convention (similar to `.gitignore`, `.dockerignore`)

**Why `updated_at` instead of `last_accessed`?**
- Captures meaningful activity (code execution) rather than passive reads
- Simpler to implement reliably (updated on `execute()` only)
- Aligns with cleanup intent (prune inactive sessions, not just unread ones)

## Dependencies
- Existing capability: `session-management` (modified)
- No new external dependencies required

## Risks and Mitigations

### Risk: Clock skew on distributed systems
**Impact**: Timestamps may be inconsistent if sessions span multiple hosts with unsynchronized clocks
**Mitigation**: Document that pruning assumes monotonic time on a single host. For distributed deployments, recommend NTP or rely on filesystem mtimes as fallback.

### Risk: Concurrent access during pruning
**Impact**: Pruning may delete a session workspace while another thread/process is executing within it
**Mitigation**: 
- Document that `prune_sessions()` is not concurrency-safe and should run during maintenance windows
- Consider adding optional file locking in future if concurrent pruning is required

### Risk: Metadata corruption or deletion
**Impact**: If `.metadata.json` is corrupted or missing, session age cannot be determined
**Mitigation**:
- Pruning skips sessions without valid metadata (conservative approach)
- Log warnings for sessions with missing/corrupted metadata
- Provide `repair_session_metadata()` helper to reconstruct from filesystem mtimes

### Risk: Breaking existing sessions
**Impact**: Existing sessions without metadata might behave unexpectedly
**Mitigation**: 
- Metadata is opt-in via creation timestamp - existing sessions continue working
- Pruning explicitly skips sessions without metadata
- Tests validate backwards compatibility

## Alternatives Considered

### Alternative 1: Use filesystem modification times (mtimes)
**Rejected**: Unreliable - mtimes change with file operations, not just meaningful activity. Cannot distinguish "session was active" from "file was touched by backup tool."

### Alternative 2: External database for session registry
**Rejected**: Adds complexity and introduces sync issues. Metadata can drift from actual workspace state. Filesystem-based approach is simpler and more reliable.

### Alternative 3: Implicit pruning on `create_session_sandbox()`
**Rejected**: Unpredictable side effects - session creation shouldn't delete unrelated sessions. Pruning should be explicit and controllable.

### Alternative 4: Add TTL field to ExecutionPolicy
**Rejected**: Mixes execution policy (resource limits) with lifecycle management (cleanup). These are separate concerns - policy is per-execution, pruning is per-deployment.

## Success Criteria
1. Session workspaces have `.metadata.json` tracking `created_at` and `updated_at`
2. `updated_at` refreshes automatically on each `execute()` call
3. `prune_sessions(older_than_hours=24)` deletes sessions inactive for 24+ hours
4. Dry-run mode lists prune candidates without deleting
5. Existing sessions without metadata continue working
6. Tests validate timestamp updates and prune filtering
7. Structured logging provides audit trail for prune operations

## Open Questions
1. Should `touch_session()` be public API or internal helper?
2. Should pruning support custom filter predicates (e.g., `filter_fn: Callable[[SessionMetadata], bool]`)?
3. Should we add a `repair_session_metadata()` function to reconstruct timestamps from filesystem mtimes?
4. Should `.metadata.json` include additional fields like `execution_count` or `last_error`?
