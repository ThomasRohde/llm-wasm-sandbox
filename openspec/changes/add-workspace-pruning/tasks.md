# Tasks: Add Workspace Pruning

Implementation checklist for adding session metadata tracking and workspace pruning capabilities.

## Phase 1: Metadata Model and Persistence

### Task 1.1: Define SessionMetadata model
- [x] Create `SessionMetadata` dataclass in `sandbox/sessions.py`
- [x] Add fields: `session_id`, `created_at`, `updated_at`, `version`
- [x] Implement `to_dict()` and `from_dict()` for JSON serialization
- [x] Add type hints and docstrings
- [x] **Validation**: Unit test `SessionMetadata` creation and serialization

### Task 1.2: Add metadata creation to session initialization
- [x] Modify `create_session_sandbox()` to write `.metadata.json`
- [x] Use `datetime.now(UTC)` for timestamps
- [x] Set `created_at` and `updated_at` to same value at creation
- [x] Handle write failures gracefully (log warning, continue)
- [x] **Validation**: Test that `.metadata.json` exists after session creation
- [x] **Validation**: Test graceful handling of permission errors

### Task 1.3: Add metadata reading helper
- [x] Implement `_read_session_metadata(session_id, workspace_root) -> SessionMetadata | None`
- [x] Parse JSON and construct `SessionMetadata` object
- [x] Return `None` for missing or corrupted metadata (don't raise)
- [x] Log warnings for corrupted metadata
- [x] **Validation**: Test reading valid metadata
- [x] **Validation**: Test handling missing/corrupted metadata files

### Task 1.4: Add metadata update helper
- [x] Implement `_update_session_timestamp(session_id, workspace_root) -> None`
- [x] Read existing metadata, update `updated_at` only
- [x] Handle missing metadata gracefully (silent skip for legacy sessions)
- [x] Handle corrupted metadata gracefully (log warning, skip)
- [x] Minimize I/O overhead (single read + single write)
- [x] **Validation**: Test timestamp update preserves other fields
- [x] **Validation**: Test graceful handling of missing metadata
- [x] **Validation**: Benchmark update overhead (< 10ms target)

## Phase 2: Automatic Timestamp Updates

### Task 2.1: Integrate timestamp update into execute()
- [x] Modify `SessionAwareSandbox.execute()` to call `_update_session_timestamp()`
- [x] Update timestamp **after** successful execution (not before)
- [x] Ensure timestamp update does not affect execution result
- [x] Handle update failures gracefully (log warning, don't fail execution)
- [x] **Validation**: Test `updated_at` changes after each execution
- [x] **Validation**: Test multiple executions update timestamp correctly
- [x] **Validation**: Test execution succeeds even if timestamp update fails

### Task 2.2: Add structured logging for metadata operations
- [x] Emit `session.metadata.created` event on session creation
- [x] Emit `session.metadata.updated` event on timestamp update
- [x] Include fields: `session_id`, `timestamp`, `operation`
- [x] Use existing `SandboxLogger` interface
- [x] **Validation**: Test log events emitted with correct fields

## Phase 3: Pruning Implementation

### Task 3.1: Define PruneResult model
- [x] Create `PruneResult` dataclass in `sandbox/sessions.py`
- [x] Add fields: `deleted_sessions`, `skipped_sessions`, `reclaimed_bytes`, `errors`, `dry_run`
- [x] Implement `__str__()` for human-readable summary
- [x] Format `reclaimed_bytes` as human-readable (e.g., "1.5 MB")
- [x] **Validation**: Test `PruneResult` creation and string formatting

### Task 3.2: Implement workspace enumeration
- [x] Create `_enumerate_sessions(workspace_root) -> list[str]`
- [x] List all subdirectories in workspace_root
- [x] Filter to UUID-formatted directory names only
- [x] Ignore non-UUID directories (don't error)
- [x] **Validation**: Test enumeration with mixed directory types
- [x] **Validation**: Test with empty workspace

### Task 3.3: Implement age filtering logic
- [x] Create `_calculate_session_age(metadata: SessionMetadata) -> float`
- [x] Compute `(now - updated_at).total_seconds() / 3600` (hours)
- [x] Handle timezone-aware datetime arithmetic
- [x] Return age in hours as float
- [x] **Validation**: Test age calculation with various timestamps
- [x] **Validation**: Test handling of timezone-aware/naive datetimes

### Task 3.4: Implement directory size calculation
- [x] Create `_calculate_workspace_size(workspace_path: Path) -> int`
- [x] Recursively sum file sizes in workspace
- [x] Handle symlinks appropriately (count target size or skip)
- [x] Handle permission errors (return 0, log warning)
- [x] **Validation**: Test size calculation for various workspace structures
- [x] **Validation**: Test handling of permission errors

### Task 3.5: Implement prune_sessions() core function
- [x] Create `prune_sessions(older_than_hours, workspace_root, dry_run, logger) -> PruneResult`
- [x] Enumerate sessions with `_enumerate_sessions()`
- [x] For each session:
  - [x] Read metadata with `_read_session_metadata()`
  - [x] Skip if metadata missing/corrupted (add to `skipped_sessions`)
  - [x] Calculate age with `_calculate_session_age()`
  - [x] If age >= threshold:
    - [x] Calculate size with `_calculate_workspace_size()`
    - [x] If not dry_run: delete with `shutil.rmtree()`
    - [x] Add to `deleted_sessions` list
    - [x] Accumulate `reclaimed_bytes`
  - [x] Handle errors (permission, OSError) and add to `errors` dict
- [x] Construct and return `PruneResult`
- [x] **Validation**: Test pruning old sessions
- [x] **Validation**: Test preserving recent sessions
- [x] **Validation**: Test dry-run mode
- [x] **Validation**: Test error handling (permissions)

### Task 3.6: Add structured logging for pruning
- [x] Emit `session.prune.started` event at function start
- [x] Emit `session.prune.candidate` for each candidate session
- [x] Emit `session.prune.deleted` after each deletion
- [x] Emit `session.prune.skipped` for sessions without metadata
- [x] Emit `session.prune.completed` with final counts
- [x] Include relevant context fields in each event
- [x] **Validation**: Test log events emitted during pruning

## Phase 4: Public API and Documentation

### Task 4.1: Export prune_sessions from package
- [x] Add `prune_sessions` to `sandbox/__init__.py` exports
- [x] Add `PruneResult` to `sandbox/__init__.py` exports
- [x] Add `SessionMetadata` to `sandbox/__init__.py` exports (optional)
- [x] **Validation**: Test imports work from `sandbox` package

### Task 4.2: Update docstrings and type hints
- [x] Add comprehensive docstring to `prune_sessions()`
- [x] Include examples for common usage patterns
- [x] Document edge cases (missing metadata, permissions)
- [x] Add type hints to all new functions
- [x] **Validation**: Run `mypy` on modified files

### Task 4.3: Update README.md
- [x] Add "Workspace Pruning" section to README
- [x] Include usage examples for `prune_sessions()`
- [x] Document metadata behavior and backwards compatibility
- [x] Add note about concurrency safety
- [x] **Validation**: Review README for clarity and completeness

### Task 4.4: Update demo scripts
- [x] Add pruning example to `demo_session_workflow.py`
- [x] Show dry-run and actual pruning usage
- [x] Demonstrate `PruneResult` inspection
- [x] **Validation**: Run demo script successfully

## Phase 5: Testing

### Task 5.1: Unit tests for metadata operations
- [x] `test_metadata_creation()`: Verify `.metadata.json` created
- [x] `test_metadata_update()`: Verify `updated_at` changes
- [x] `test_metadata_read()`: Verify metadata parsing
- [x] `test_metadata_missing()`: Verify graceful handling
- [x] `test_metadata_corrupted()`: Verify error handling
- [x] **Validation**: All tests pass, coverage > 90%

### Task 5.2: Unit tests for pruning operations
- [x] `test_prune_old_sessions()`: Verify old sessions deleted
- [x] `test_prune_preserves_recent()`: Verify recent sessions kept
- [x] `test_prune_dry_run()`: Verify no deletion in dry-run mode
- [x] `test_prune_skips_no_metadata()`: Verify legacy sessions skipped
- [x] `test_prune_custom_threshold()`: Verify various age thresholds
- [x] `test_prune_calculates_size()`: Verify reclaimed bytes accuracy
- [x] `test_prune_handles_errors()`: Verify permission error handling
- [x] `test_prune_custom_workspace()`: Verify custom workspace_root
- [x] **Validation**: All tests pass, coverage > 90%

### Task 5.3: Integration tests for timestamp updates
- [x] `test_multi_turn_timestamp_updates()`: Execute multiple times, verify timestamp progression
- [x] `test_execute_without_metadata()`: Legacy session execution works
- [x] `test_execute_updates_timestamp_async()`: Timestamp updates don't block execution
- [x] **Validation**: All tests pass

### Task 5.4: Security tests
- [x] `test_metadata_hidden_from_guest()`: Guest cannot read `.metadata.json`
- [x] `test_prune_respects_workspace_boundary()`: No deletion outside workspace
- [x] `test_prune_validates_session_id()`: UUID validation prevents traversal
- [x] **Validation**: All security tests pass

### Task 5.5: Performance tests
- [x] Benchmark metadata creation overhead (< 1ms)
- [x] Benchmark timestamp update overhead (< 10ms)
- [x] Benchmark pruning throughput (> 10 sessions/second)
- [x] Verify no regression in execution latency
- [x] **Validation**: Performance targets met

## Phase 6: Final Validation

### Task 6.1: End-to-end workflow test
- [x] Create session, execute code, verify metadata
- [x] Execute multiple times, verify timestamp updates
- [x] Prune old sessions, verify correct deletions
- [x] Verify recent sessions preserved
- [x] **Validation**: Complete workflow succeeds

### Task 6.2: Backwards compatibility test
- [x] Create session with current code (no metadata)
- [x] Switch to new code, verify execution still works
- [x] Verify pruning skips legacy session
- [x] **Validation**: Zero breaking changes to existing behavior

### Task 6.3: Documentation review
- [x] Ensure all public functions have docstrings
- [x] Verify README.md examples are accurate
- [x] Check that design.md matches implementation
- [x] Verify spec requirements are met
- [x] **Validation**: Documentation complete and accurate

### Task 6.4: Code quality checks
- [x] Run `ruff check sandbox/` - no new violations
- [x] Run `mypy sandbox/` - all types correct
- [x] Run `pytest --cov=sandbox tests/` - coverage > 90%
- [x] Review code for consistency with project conventions
- [x] **Validation**: All quality checks pass

## Dependencies Between Tasks

- **Phase 1 → Phase 2**: Metadata model must exist before automatic updates
- **Phase 1 → Phase 3**: Metadata reading required for pruning
- **Phase 2 → Phase 5.3**: Timestamp updates must work before integration tests
- **Phase 3 → Phase 5.2**: Pruning implementation must exist before unit tests
- **Phases 1-4 → Phase 6**: All implementation complete before final validation

## Parallelizable Work

- **Task 1.2 + 1.3**: Metadata creation and reading can be developed in parallel
- **Task 3.2 + 3.3 + 3.4**: Enumeration, filtering, and sizing are independent
- **Phase 4 (Documentation) + Phase 5 (Testing)**: Can proceed in parallel once Phase 3 complete

## Success Criteria

All tasks completed when:
- [x] All unit tests pass
- [x] All integration tests pass
- [x] All security tests pass
- [x] Performance benchmarks meet targets
- [x] Code coverage > 90% for new code
- [x] `mypy` reports no type errors
- [x] `ruff` reports no violations
- [x] README.md updated with pruning examples
- [x] Demo script demonstrates pruning workflow
- [x] Backwards compatibility verified (legacy sessions work)
- [ ] `openspec validate add-workspace-pruning --strict` passes
