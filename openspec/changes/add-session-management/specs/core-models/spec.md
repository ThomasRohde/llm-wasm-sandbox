# Capability: Core Models

## MODIFIED Requirements

### Requirement: SandboxResult Metadata Extension
SandboxResult.metadata MUST support session context for session-aware executions.

#### Scenario: Include session ID in metadata
Given a sandbox created via create_session_sandbox() with session_id "abc-123"
When sandbox.execute(code) returns a SandboxResult
Then result.metadata MUST be a dict
And result.metadata MUST include key "session_id" with value "abc-123"

#### Scenario: Metadata remains optional for non-session usage
Given a sandbox created via create_sandbox() without session
When sandbox.execute(code) returns a SandboxResult
Then result.metadata MUST NOT contain "session_id" key
And result MUST validate successfully (session_id is optional)

#### Scenario: Session ID in metadata is string type
Given result.metadata["session_id"] exists
When the value is accessed
Then it MUST be a string (UUID format)
And it MUST NOT be None or other type

---

### Requirement: Workspace Path Reflects Session
SandboxResult.workspace_path MUST reflect the session-specific workspace when applicable.

#### Scenario: Workspace path for session execution
Given a session sandbox with workspace "workspace/abc-123/"
When sandbox.execute(code) returns a SandboxResult
Then result.workspace_path MUST equal "workspace/abc-123/" (or absolute equivalent)
And the path MUST be the actual workspace used during execution

#### Scenario: Workspace path for non-session execution
Given a non-session sandbox with default workspace "workspace/"
When sandbox.execute(code) returns a SandboxResult
Then result.workspace_path MUST equal "workspace/" (or absolute equivalent)
And behavior MUST be unchanged from pre-session implementation

---

## ADDED Requirements

None. Session support extends existing models via metadata field without schema changes.
