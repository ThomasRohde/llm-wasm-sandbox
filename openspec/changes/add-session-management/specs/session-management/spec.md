# Capability: Session Management

## ADDED Requirements

### Requirement: Session ID Generation
The sandbox MUST provide UUIDv4-based session identifiers for workspace isolation.

#### Scenario: Generate unique session ID
Given a user requests a new session
When create_session_sandbox() is called
Then it MUST generate a UUIDv4 string
And the session_id MUST be globally unique
And the session_id MUST be filesystem-safe (no path separators or special characters)

#### Scenario: Session ID format validation
Given a generated session_id
When the session_id is used as a directory name
Then it MUST contain only alphanumeric characters and hyphens
And it MUST match the UUID format (8-4-4-4-12 hex digits)

---

### Requirement: Session Workspace Mapping
The sandbox MUST map each session ID to an isolated workspace directory.

#### Scenario: Create session workspace
Given a new session_id "abc-123"
When create_session_sandbox() is called with workspace_root="workspace"
Then it MUST create directory "workspace/abc-123/"
And the directory MUST be created with parents=True, exist_ok=True
And the directory permissions MUST allow host read/write access

#### Scenario: Resolve existing session workspace
Given session_id "abc-123" has existing workspace "workspace/abc-123/"
When get_session_sandbox(session_id="abc-123") is called
Then it MUST resolve to "workspace/abc-123/"
And it MUST NOT create a new session ID
And the workspace MUST be reusable across multiple sandbox instances

#### Scenario: Custom workspace root
Given workspace_root=Path("/tmp/custom")
When create_session_sandbox(workspace_root=workspace_root) is called
Then session workspaces MUST be created under "/tmp/custom/<session_id>/"

---

### Requirement: Session-Aware Sandbox Creation
The sandbox MUST provide helpers to create sandboxes bound to sessions.

#### Scenario: Create new session with sandbox
Given runtime=RuntimeType.PYTHON
When create_session_sandbox(runtime=RuntimeType.PYTHON) is called
Then it MUST return a tuple (session_id: str, sandbox: BaseSandbox)
And the sandbox.workspace MUST equal "workspace/<session_id>/"
And the session_id MUST be valid UUID format

#### Scenario: Create session with custom policy
Given a custom ExecutionPolicy with fuel_budget=500000000
When create_session_sandbox(policy=custom_policy) is called
Then the returned sandbox MUST use the custom policy
And policy.fuel_budget MUST equal 500000000

#### Scenario: Create session with custom logger
Given a configured SandboxLogger instance
When create_session_sandbox(logger=custom_logger) is called
Then the returned sandbox MUST use the custom logger
And the logger MUST receive session context (session_id) in events

#### Scenario: Retrieve sandbox for existing session
Given an existing session_id "abc-123"
When get_session_sandbox(session_id="abc-123") is called
Then it MUST return a BaseSandbox instance
And sandbox.workspace MUST equal "workspace/abc-123/"
And the sandbox MUST see files from previous executions in that session

---

### Requirement: Session Isolation
Sandboxes from different sessions MUST NOT access each other's workspaces.

#### Scenario: Files isolated between sessions
Given session A with session_id "aaa-111"
And session B with session_id "bbb-222"
When sandbox A writes "data.txt" with content "Session A data"
And sandbox B writes "data.txt" with content "Session B data"
Then sandbox A reading "data.txt" MUST see "Session A data"
And sandbox B reading "data.txt" MUST see "Session B data"
And neither sandbox can access the other's workspace via WASI

#### Scenario: WASI preopen scoped to session
Given a session workspace at "workspace/abc-123/"
When the sandbox is created for that session
Then WASI preopen MUST mount only "workspace/abc-123/" to guest "/app"
And the guest MUST NOT be able to access "workspace/" root
And the guest MUST NOT be able to access other session directories

---

### Requirement: Session Persistence
Multiple executions within the same session MUST see each other's filesystem changes.

#### Scenario: Persist files across executions
Given a session_id "abc-123"
When sandbox.execute("with open('/app/state.json', 'w') as f: f.write('{\"count\": 1}')") completes
And the same session sandbox executes "with open('/app/state.json', 'r') as f: print(f.read())"
Then the second execution stdout MUST contain '{"count": 1}'
And files_modified in first result MUST include "state.json"

#### Scenario: Track file changes per execution
Given a session with existing file "data.csv"
When sandbox.execute() modifies "data.csv" and creates "output.txt"
Then result.files_modified MUST include "data.csv"
And result.files_created MUST include "output.txt"
And result.files_created MUST NOT include "data.csv" (already existed)

---

### Requirement: Session Deletion
The sandbox MUST provide safe session workspace cleanup.

#### Scenario: Delete session workspace
Given a session workspace at "workspace/abc-123/" with files
When delete_session_workspace(session_id="abc-123") is called
Then "workspace/abc-123/" MUST be removed recursively
And all files within the workspace MUST be deleted
And subsequent get_session_sandbox("abc-123") MUST create fresh empty workspace

#### Scenario: Prevent path traversal in deletion
Given a malicious session_id "../../../tmp"
When delete_session_workspace(session_id="../../../tmp") is called
Then it MUST raise ValueError
And no files outside workspace_root MUST be deleted

#### Scenario: Safe deletion when workspace missing
Given session_id "nonexistent-123"
When delete_session_workspace(session_id="nonexistent-123") is called
Then it MUST complete without errors (idempotent)
And no exception MUST be raised

---

### Requirement: Session Context in Logging
Session operations MUST emit structured log events with session context.

#### Scenario: Log session creation
Given create_session_sandbox() is called
When the session is created
Then logger MUST emit "session.created" event
And event MUST include session_id field
And event MUST include workspace_path field

#### Scenario: Log session retrieval
Given get_session_sandbox(session_id="abc-123") is called
When the session workspace is resolved
Then logger MUST emit "session.retrieved" event
And event MUST include session_id "abc-123"

#### Scenario: Log session deletion
Given delete_session_workspace(session_id="abc-123") is called
When the workspace is deleted
Then logger MUST emit "session.deleted" event
And event MUST include session_id "abc-123"

#### Scenario: Include session ID in execution logs
Given a sandbox created via create_session_sandbox()
When sandbox.execute() is called
Then "execution.start" event MUST include session_id
And "execution.complete" event MUST include session_id

---

### Requirement: Session Metadata in Results
Execution results from session-aware sandboxes MUST include session context.

#### Scenario: Include session ID in result metadata
Given a sandbox created with create_session_sandbox() returning session_id "abc-123"
When sandbox.execute(code) returns a SandboxResult
Then result.metadata["session_id"] MUST equal "abc-123"

#### Scenario: Workspace path reflects session
Given a session sandbox with session_id "abc-123"
When sandbox.execute(code) returns a SandboxResult
Then result.workspace_path MUST equal "workspace/abc-123/" (or absolute equivalent)

---

### Requirement: Backwards Compatibility
Session features MUST NOT break existing non-session usage patterns.

#### Scenario: Non-session sandbox usage unchanged
Given existing code: sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
When sandbox.execute(code) is called
Then it MUST work exactly as before
And default workspace MUST be "workspace/"
And no session_id MUST be present in result.metadata

#### Scenario: Explicit workspace parameter still works
Given existing code: sandbox = create_sandbox(workspace=Path("custom_workspace"))
When sandbox.execute(code) is called
Then it MUST use "custom_workspace/" as workspace
And behavior MUST be identical to pre-session implementation

#### Scenario: Public API surface extended additively
Given sandbox/__init__.py exports
When session functions are added
Then existing exports MUST remain unchanged
And new exports MUST be added to __all__ without removing old ones
