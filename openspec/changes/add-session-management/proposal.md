# Proposal: Add Session Management

## Objective
Enable stateful, multi-turn LLM interactions by providing first-class session management with isolated per-session workspaces, session lifecycle APIs, and file operations for accessing session artifacts.

## Problem
The current sandbox treats the workspace as a shared directory (`workspace/`) per host process. Each `execute()` call writes to `user_code.py` in that shared space. This model has critical limitations for production LLM workflows:

1. **No session identity**: The host cannot track or correlate multiple executions for a single user/conversation
2. **No workspace isolation**: Multiple concurrent users/sessions share the same workspace, creating data leakage risks
3. **No persistence semantics**: While files can persist between runs, there's no API to:
   - Isolate workspaces by session
   - Reuse a specific workspace for follow-up executions
   - List, read, or delete session files from host code

**Real-world scenario**: User asks LLM to generate Python code that creates a CSV file. On the next turn, user asks "download that CSV file." Currently impossible - no API to retrieve session artifacts or correlate executions.

## Solution
Introduce a three-part session management system:

1. **Session lifecycle**: UUIDv4-based session IDs mapping to isolated workspace directories (`workspace/<session_id>/`)
2. **Session-aware sandbox creation**: Factory helpers to create/retrieve sandboxes bound to sessions
3. **Workspace operations API**: Trusted host-side file operations (list, read, write, delete) scoped to session workspaces

## Scope

### In Scope
- Session ID generation and workspace mapping
- Per-session workspace isolation via WASI preopens
- Session-aware factory helpers (`create_session_sandbox`, `get_session_sandbox`)
- File operations API for host access to session workspaces
- Backwards compatibility with existing non-session usage
- Structured logging with session context

### Out of Scope
- HTTP/gRPC endpoints (library-level APIs only)
- Multi-tenant OS isolation (containers/cgroups) - separate layer
- Cross-session file sharing
- Encryption at rest for session workspaces
- Session enumeration or registry (host application concern)
- Disk quota enforcement per session (host application concern)

## Rationale
Session management is foundational for production LLM code execution workflows. Without it, each execution is stateless and isolated from previous turns, preventing:
- Multi-step data analysis tasks
- Iterative code refinement with persistent state
- Artifact retrieval (downloading generated files)
- Debugging via file inspection between executions

The design respects existing security boundaries (WASI capability isolation) while adding essential state management primitives.

## Dependencies
- Existing capabilities: `core-models`, `factory-api`, `python-runtime`
- No new external dependencies required

## Risks and Mitigations

### Risk: Path traversal vulnerabilities
**Mitigation**: All session file operations validate paths with `Path.resolve()` and ensure results stay within `workspace_root / session_id`

### Risk: Workspace directory exhaustion
**Mitigation**: Document that host applications must implement cleanup/TTL policies. Provide helper for safe session deletion.

### Risk: Breaking existing usage patterns
**Mitigation**: Session APIs are purely additive. Default behavior (`create_sandbox()` with no session) remains unchanged.

## Alternatives Considered

### Alternative 1: Let applications manage workspaces themselves
**Rejected**: Requires every integrator to reimplement session-to-workspace mapping, validation, and file operations. Better as library primitive.

### Alternative 2: Single SessionManager class
**Rejected**: Adds unnecessary state management to library. Stateless helpers let applications choose their own caching/lifecycle patterns.

### Alternative 3: Guest-visible session IDs
**Rejected**: Session IDs are host concerns. Guest code should only see `/app` - no knowledge of session structure.

## Success Criteria
1. Users can create isolated session workspaces with stable IDs
2. Multiple executions in same session see each other's files
3. Host code can list/read/write files in session workspaces
4. Existing non-session code continues working unchanged
5. All file operations reject path traversal attempts
6. Tests validate session isolation and persistence

## Open Questions
1. Should we provide a `SessionManager` class for applications that want in-memory session tracking?
2. Should `SandboxResult` have a dedicated `session_id` field or use `metadata["session_id"]`?
3. Should we add convenience methods for common patterns (e.g., `session.list_files()` vs standalone function)?
