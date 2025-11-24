# Runtime Parity Specification

## ADDED Requirements

### Requirement: Feature Parity Across Runtimes
Both Python and JavaScript runtimes SHALL provide equivalent capabilities for core sandbox features including state persistence, vendored packages, helper utilities, and automatic code injection.

#### Scenario: Python has feature X, JavaScript should have equivalent
- **GIVEN** a feature exists in Python runtime (e.g., auto_persist_globals)
- **WHEN** user creates JavaScript sandbox with same feature flag
- **THEN** JavaScript runtime SHALL provide functionally equivalent behavior
- **AND** differences in implementation details (JSON vs Python pickle) are acceptable if semantics match

#### Scenario: Runtime-specific features documented clearly
- **GIVEN** a feature that cannot be made equivalent due to language constraints
- **WHEN** user reads documentation for that runtime
- **THEN** documentation SHALL clearly explain the limitation
- **AND** documentation SHALL provide alternative approaches if available

### Requirement: Symmetric API Surface
Both runtimes SHALL expose the same high-level API for creating sandboxes, executing code, and managing sessions.

#### Scenario: create_sandbox works identically for both runtimes
- **GIVEN** user wants to create a sandbox with custom policy
- **WHEN** user calls `create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)`
- **THEN** same call pattern SHALL work with `RuntimeType.JAVASCRIPT`
- **AND** result objects SHALL have identical structure (SandboxResult)
- **AND** session management SHALL work identically

#### Scenario: Error patterns are consistent
- **GIVEN** an execution error occurs (fuel exhaustion, syntax error, runtime error)
- **WHEN** error happens in Python runtime
- **AND** equivalent error happens in JavaScript runtime  
- **THEN** both SHALL use same error codes and metadata fields
- **AND** both SHALL populate `metadata['trapped']` and `metadata['trap_reason']` identically

### Requirement: Documentation Parity
Each runtime SHALL have comprehensive capability documentation that is equally detailed.

#### Scenario: JavaScript capabilities documented as thoroughly as Python
- **GIVEN** `PYTHON_CAPABILITIES.md` exists with 1260+ lines of reference material
- **WHEN** user reads `JAVASCRIPT_CAPABILITIES.md`
- **THEN** it SHALL provide equivalent depth of coverage for JavaScript
- **AND** it SHALL include standard library reference
- **AND** it SHALL document vendored packages with usage examples
- **AND** it SHALL provide LLM-friendly code patterns
