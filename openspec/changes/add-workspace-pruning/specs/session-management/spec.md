# Spec Delta: Session Management (Modified)

This spec delta extends the existing `session-management` capability to support temporal metadata tracking and automated workspace pruning.

## MODIFIED Requirements

### Requirement: Session Workspace Creation

Session creation MUST write a `.metadata.json` file containing creation and update timestamps. The system SHALL ensure metadata is created atomically with workspace initialization and SHALL handle write failures gracefully without blocking session creation.

#### Scenario: Create session with metadata
**Given** a request to create a new session sandbox  
**When** `create_session_sandbox()` is called  
**Then** the session workspace is created with a `.metadata.json` file  
**And** the metadata contains `session_id`, `created_at`, `updated_at`, and `version` fields  
**And** `created_at` equals `updated_at` at creation time  
**And** timestamps are ISO 8601 UTC format with microsecond precision

**Acceptance**:
- `.metadata.json` exists in session workspace after creation
- Metadata is valid JSON with required fields
- Timestamps are parseable as ISO 8601 datetimes
- `created_at` and `updated_at` are within 1 second of current time

#### Scenario: Session creation fails gracefully if metadata write fails
**Given** a session workspace is being created  
**When** `.metadata.json` write fails due to permissions or disk error  
**Then** session creation succeeds anyway (metadata is not critical)  
**And** a warning is logged about missing metadata  
**And** the session workspace is usable for executions

**Acceptance**:
- Session creation does not raise exception due to metadata write failure
- Warning logged with session_id and error details
- Session can execute code despite missing metadata

### Requirement: Session Metadata Updates

The system MUST automatically refresh the `updated_at` timestamp in `.metadata.json` after each successful code execution. Updates SHALL preserve the `created_at` timestamp and other metadata fields unchanged. The system SHALL handle missing or corrupted metadata gracefully without failing execution.

#### Scenario: Update timestamp on successful execution
**Given** a session with existing metadata  
**When** `sandbox.execute(code)` completes successfully  
**Then** the `updated_at` timestamp in `.metadata.json` is refreshed  
**And** `updated_at` reflects the current UTC time  
**And** `created_at` remains unchanged  
**And** other metadata fields remain unchanged

**Acceptance**:
- `.metadata.json` updated after each `execute()` call
- `updated_at` increases monotonically with each execution
- Timestamp update completes within 10ms (minimal overhead)
- Execution succeeds even if timestamp update fails

#### Scenario: Skip timestamp update for sessions without metadata
**Given** a session workspace without `.metadata.json` (legacy session)  
**When** `sandbox.execute(code)` is called  
**Then** execution proceeds normally  
**And** no `.metadata.json` is created automatically  
**And** no error or warning is logged (silent skip)

**Acceptance**:
- Legacy sessions (no metadata) execute successfully
- No metadata file created during execution
- No performance impact for legacy sessions

#### Scenario: Handle corrupted metadata gracefully
**Given** a session with corrupted `.metadata.json` (invalid JSON)  
**When** `sandbox.execute(code)` attempts to update timestamp  
**Then** execution proceeds normally  
**And** a warning is logged about corrupted metadata  
**And** the corrupted metadata file is not modified

**Acceptance**:
- Execution does not fail due to corrupted metadata
- Warning logged with session_id and parse error details
- Corrupted file preserved (no overwrite with partial data)

## ADDED Requirements

### Requirement: Session Metadata Model

Session metadata MUST follow a structured JSON schema stored in `.metadata.json` within each session workspace. The schema MUST include `session_id`, `created_at`, `updated_at`, and `version` fields with ISO 8601 UTC timestamps. The metadata file SHALL be hidden from guest code via WASI preopen restrictions.

#### Scenario: Metadata schema validation
**Given** a session workspace with `.metadata.json`  
**When** the metadata is read and parsed  
**Then** it contains the following fields:
- `session_id`: string (UUIDv4 format)
- `created_at`: string (ISO 8601 UTC timestamp)
- `updated_at`: string (ISO 8601 UTC timestamp)
- `version`: integer (currently 1)

**Acceptance**:
- All required fields present in metadata
- `session_id` matches workspace directory name
- Timestamps are valid ISO 8601 format
- `version` is 1 (current schema version)

#### Scenario: Metadata is hidden from guest code
**Given** a session with `.metadata.json`  
**When** guest code attempts to read/write `.metadata.json`  
**Then** the file is not visible in WASI preopen (dotfile excluded)  
**And** guest code cannot access metadata via any path

**Acceptance**:
- `os.listdir('/app')` in guest does not show `.metadata.json`
- `open('/app/.metadata.json')` in guest raises FileNotFoundError
- Path traversal attempts blocked by existing WASI isolation

### Requirement: Workspace Pruning API

The system MUST provide a `prune_sessions()` function that deletes session workspaces older than a specified age threshold. Pruning SHALL be age-based using the `updated_at` timestamp and MUST support dry-run mode for previewing deletions. Sessions without metadata SHALL be skipped and preserved.

#### Scenario: Prune sessions older than threshold
**Given** multiple session workspaces with varying ages  
**When** `prune_sessions(older_than_hours=24)` is called  
**Then** sessions with `updated_at` > 24 hours ago are deleted  
**And** sessions with `updated_at` <= 24 hours ago are preserved  
**And** sessions without metadata are skipped (not deleted)  
**And** a `PruneResult` is returned with deletion counts

**Acceptance**:
- Old sessions deleted completely (workspace directory removed)
- Recent sessions preserved
- Legacy sessions (no metadata) skipped
- `PruneResult.deleted_sessions` lists deleted session IDs
- `PruneResult.skipped_sessions` lists sessions without metadata

#### Scenario: Dry-run mode lists candidates without deleting
**Given** multiple session workspaces with varying ages  
**When** `prune_sessions(older_than_hours=24, dry_run=True)` is called  
**Then** candidate sessions are identified but not deleted  
**And** `PruneResult.deleted_sessions` contains candidate IDs  
**And** `PruneResult.dry_run` is True  
**And** workspace directories still exist after call

**Acceptance**:
- No directories deleted in dry-run mode
- Candidate list matches actual prune behavior (without dry_run)
- `PruneResult.dry_run` flag correctly set

#### Scenario: Calculate disk space reclaimed
**Given** session workspaces to be pruned  
**When** `prune_sessions(older_than_hours=24)` is called  
**Then** `PruneResult.reclaimed_bytes` contains total size of deleted workspaces  
**And** size calculation includes all files in session directories

**Acceptance**:
- `reclaimed_bytes` matches sum of workspace sizes
- Size calculated before deletion (for accurate reporting)
- Dry-run mode also reports would-be reclaimed bytes

#### Scenario: Handle permission errors gracefully
**Given** a session workspace without delete permissions  
**When** `prune_sessions(older_than_hours=24)` attempts to delete it  
**Then** the deletion fails for that session  
**And** other sessions continue to be processed  
**And** the failed session is recorded in `PruneResult.errors`  
**And** pruning completes without raising exception

**Acceptance**:
- Partial pruning succeeds (some sessions deleted)
- Permission errors captured in `errors` dict
- No exception raised from pruning operation

#### Scenario: Custom workspace root
**Given** a non-default workspace root directory  
**When** `prune_sessions(older_than_hours=24, workspace_root=Path("custom/"))` is called  
**Then** pruning enumerates sessions in `custom/` directory  
**And** default `workspace/` directory is not affected

**Acceptance**:
- Pruning operates on specified workspace_root
- Default workspace unaffected
- workspace_root must exist (raises error if missing)

### Requirement: Pruning Result Model

Pruning operations MUST return a structured `PruneResult` object containing lists of deleted and skipped sessions, total disk space reclaimed, error details, and dry-run status. The result MUST support human-readable string representation for logging and display.

#### Scenario: PruneResult contains operation details
**Given** a completed prune operation  
**When** the `PruneResult` is inspected  
**Then** it contains:
- `deleted_sessions`: list of deleted session IDs
- `skipped_sessions`: list of sessions without metadata
- `reclaimed_bytes`: total disk space freed
- `errors`: dict mapping session IDs to error messages
- `dry_run`: boolean indicating if this was a dry run

**Acceptance**:
- All fields populated with accurate data
- Lists contain session IDs as strings
- `reclaimed_bytes` is non-negative integer
- `errors` dict keys are session IDs, values are error strings

#### Scenario: PruneResult supports string representation
**Given** a `PruneResult` instance  
**When** `str(result)` is called  
**Then** a human-readable summary is returned  
**And** summary includes counts and reclaimed space

**Acceptance**:
- String contains deleted/skipped counts
- Reclaimed bytes formatted as human-readable (e.g., "1.5 MB")
- Dry-run status indicated in output

### Requirement: Structured Logging for Pruning

Pruning operations MUST emit structured log events for lifecycle stages (started, candidate, deleted, completed) using the existing `SandboxLogger` interface. Each event SHALL include relevant context fields such as session IDs, age, size, and error details. Warnings MUST be logged for skipped sessions with missing or corrupted metadata.

#### Scenario: Log pruning lifecycle events
**Given** a pruning operation with logger configured  
**When** `prune_sessions()` executes  
**Then** the following events are logged:
- `session.prune.started`: threshold, workspace_root, dry_run
- `session.prune.candidate`: session_id, age_hours, size_bytes (for each candidate)
- `session.prune.deleted`: session_id (for each deletion)
- `session.prune.completed`: deleted_count, skipped_count, reclaimed_bytes, duration

**Acceptance**:
- All lifecycle events emitted with correct event names
- Events include relevant context fields
- Timestamps included (via structlog)
- Log level appropriate (info for normal, warning for errors)

#### Scenario: Log warnings for skipped sessions
**Given** sessions without metadata or with corrupted metadata  
**When** `prune_sessions()` encounters them  
**Then** warnings are logged with:
- `session.prune.skipped`: session_id, reason (e.g., "no_metadata", "corrupted_metadata")

**Acceptance**:
- One warning per skipped session
- Reason field distinguishes no metadata vs corrupted
- Session ID included for debugging

### Requirement: Path Safety for Pruning

Pruning operations MUST validate and respect workspace root boundaries to prevent deletion of files outside the session workspace hierarchy. The system SHALL only enumerate and delete UUID-formatted subdirectories within the workspace root. Non-UUID directories MUST be ignored without error.

#### Scenario: Validate workspace root before pruning
**Given** a pruning request with workspace_root parameter  
**When** `prune_sessions()` is called  
**Then** workspace_root is validated as existing directory  
**And** only subdirectories of workspace_root are enumerated  
**And** no paths outside workspace_root are accessed

**Acceptance**:
- Non-existent workspace_root raises clear error
- No directory traversal outside workspace_root
- Symlinks followed but resolved paths validated

#### Scenario: Prevent deletion of non-session directories
**Given** workspace root contains non-UUID subdirectories  
**When** `prune_sessions()` enumerates workspaces  
**Then** only UUID-formatted directories are considered  
**And** other directories are ignored (not deleted, not counted)

**Acceptance**:
- Non-UUID directories preserved
- No errors logged for non-UUID directories
- Only UUID directories checked for metadata

### Requirement: Backwards Compatibility for Metadata

The system MUST preserve existing behavior for legacy sessions created before the metadata feature. Sessions without `.metadata.json` SHALL execute code successfully without automatic metadata creation. Pruning operations MUST skip sessions without metadata and SHALL NOT delete them under any circumstances.

#### Scenario: Execute legacy session without metadata
**Given** a session workspace created before metadata feature  
**When** `get_session_sandbox(session_id)` retrieves the session  
**And** `sandbox.execute(code)` is called  
**Then** execution proceeds normally  
**And** no metadata is created automatically  
**And** no errors or warnings are logged

**Acceptance**:
- Legacy sessions execute successfully
- Identical behavior to pre-metadata implementation
- No metadata file created during execution
- No performance regression

#### Scenario: Prune skips legacy sessions
**Given** a mix of sessions with and without metadata  
**When** `prune_sessions(older_than_hours=0)` is called (prune all)  
**Then** sessions with metadata are deleted  
**And** sessions without metadata are preserved  
**And** skipped sessions listed in `PruneResult.skipped_sessions`

**Acceptance**:
- Only sessions with metadata eligible for pruning
- Legacy sessions never deleted by prune operation
- Skipped count matches number of legacy sessions
