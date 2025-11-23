# PRD: Sandbox Security & Reliability Hardening

## Background
The WASM sandbox currently allows untrusted user code to run under session isolation. A code review uncovered several gaps that risk host file exposure, cross-session tampering, and uncontrolled disk growth. This PRD defines the fixes needed to close those holes and make session lifecycle predictable.

## Goals
- Enforce safe, canonical session workspaces (no traversal, no off-root mounts).
- Prevent cross-session package tampering and keep optional data mounts read-only.
- Ensure session cleanup works for all session IDs and does not leak temp artifacts.
- Preserve existing public APIs while tightening safety guarantees.

## Non-Goals
- Adding new runtimes or changing resource limit defaults.
- Shipping network/socket capabilities inside the sandbox.
- Building a full policy management UI.

## Problems to Fix
1) **Session path traversal**: `create_sandbox` accepts arbitrary `session_id` strings and concatenates them into `workspace_root` before preopening the directory (sandbox/core/factory.py:90-118). A crafted `session_id="../host"` mounts host paths into `/app`, defeating isolation.  
2) **Shared site-packages writable by guests**: Python runtime preopens `workspace/site-packages` as `/app/site-packages` (sandbox/host.py:115-118) with default WASI rights (read/write). Any session can poison packages for all other sessions.  
3) **Data mount not actually read-only**: Optional `mount_data_dir` is also preopened without reduced rights (sandbox/host.py:119-123, 302-305), so “read-only data” is writable by guest code.  
4) **Pruning misses custom session IDs**: `create_sandbox` documents custom `session_id`s, but pruning only enumerates UUID-shaped directories (sandbox/sessions.py:565-611). Non-UUID sessions never get pruned, causing unbounded disk use.  
5) **Temp log directories accumulate**: Each execution creates `tempfile.mkdtemp` logs (sandbox/host.py:101-104, 289-292) and never deletes them. Heavy use leaks disk and may expose artifacts outside the workspace model.

## Requirements
- Reject or normalize any `session_id` containing path separators or traversal sequences before workspace creation and WASI preopen.
- Ensure guest-visible package paths cannot be modified across sessions; either mount read-only or copy per-session.
- Enforce read-only semantics for `mount_data_dir` or drop the mount if that cannot be guaranteed.
- Pruning must cover all session directories that were allowed at creation; no orphaned workspaces.
- Log retention must be bounded and opt-in; defaults should not leak temp files.
- Keep API compatibility (constructors, return types) where possible; raise explicit errors on invalid inputs instead of silently proceeding.

## Proposed Approach
1) **Session validation guardrail**  
   - Add a validation helper reused by `create_sandbox` to reject session IDs with `/`, `\\`, or `..` components and optionally require UUID format unless explicitly overridden by a `allow_non_uuid` flag.  
   - Resolve the workspace path and ensure it remains under `workspace_root` (similar to `_validate_session_path`).  
   - Update tests to cover traversal attempts and legacy valid IDs.

2) **Package mount hardening**  
   - Stop preopening shared `workspace/site-packages` as read/write. Options:  
     a) Copy vendored packages into each session workspace before execution (isolated, simplest).  
     b) If wasmtime Python supports rights, preopen with read-only caps; otherwise, mark mount as read-only via filesystem permissions and verify writes fail in tests.  
   - Document that `/app/site-packages` is immutable per execution and add regression tests for cross-session tamper attempts.

3) **Read-only data mount**  
   - Apply the same rights strategy to `mount_data_dir`: enforce read-only or refuse to mount.  
   - Add tests that guest writes to `/data` fail when `mount_data_dir` is configured.

4) **Pruning correctness**  
   - Align session creation and pruning: either enforce UUID session IDs or change `_enumerate_sessions` to include all non-hidden directories while still rejecting traversal.  
   - Add coverage for pruning non-UUID sessions and ensure metrics/logging remain accurate.

5) **Temp log lifecycle**  
   - Add a retention policy: default to cleanup after execution unless `preserve_logs=True` is requested.  
   - Expose the preserved path in metadata only when kept.  
   - Add tests to verify cleanup and opt-in retention.

## Deliverables
- Code changes implementing the above requirements.
- Updated tests (security, pruning, lifecycle) with coverage for each fix.
- Documentation updates (README/AGENTS/policy) describing new safeguards and any new flags.

## Success Metrics
- Creating a sandbox with a traversal `session_id` raises immediately; no host directories are created or mounted.
- Guest writes to `/app/site-packages` and `/data` are blocked or isolated per session.
- Pruning removes old sessions regardless of ID format (or disallows non-UUID IDs up front).
- No orphaned temp log directories after default executions; preserved logs only when explicitly requested.
