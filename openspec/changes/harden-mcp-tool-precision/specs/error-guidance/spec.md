# Spec: Error Guidance

## ADDED Requirements

### Requirement: Structured Error Analysis

The sandbox SHALL provide structured error analysis in execution results containing error classification, actionable guidance, related documentation links, and optional code examples for common error patterns.

#### Scenario: OutOfFuel Error Guidance

- **WHEN** code execution fails with OutOfFuel trap
- **THEN** the `SandboxResult.metadata` SHALL contain:
  ```json
  {
    "error_guidance": {
      "error_type": "OutOfFuel",
      "error_message": "Execution trapped: OutOfFuel",
      "actionable_guidance": [
        "Code exceeded 10B instruction budget",
        "Likely cause: Heavy package imports (openpyxl 5-7B, PyPDF2 5-6B, jinja2 4-5B)",
        "Solution 1: Simplify code or use lighter alternatives",
        "Solution 2: Create session with higher fuel budget",
        "Example: create_session(language='python', fuel_budget=20_000_000_000)"
      ],
      "related_docs": [
        "docs/PYTHON_CAPABILITIES.md#fuel-budget-guidelines"
      ]
    }
  }
  ```

#### Scenario: Path Restriction Error Guidance

- **WHEN** code execution fails accessing files outside /app
- **THEN** the `SandboxResult.metadata` SHALL contain:
  ```json
  {
    "error_guidance": {
      "error_type": "PathRestriction",
      "error_message": "FileNotFoundError: /etc/passwd",
      "actionable_guidance": [
        "Security error: Cannot access '/etc/passwd' - all file operations restricted to /app directory",
        "Use absolute paths like '/app/data.txt' or relative paths 'data.txt' (auto-prefixed with /app)",
        "WASI capability isolation prevents access outside preopened directories"
      ],
      "related_docs": [
        "docs/MCP_INTEGRATION.md#security-considerations"
      ]
    }
  }
  ```

#### Scenario: QuickJS Tuple Destructuring Error Guidance

- **WHEN** JavaScript execution fails with TypeError on tuple destructuring
- **THEN** the `SandboxResult.metadata` SHALL contain:
  ```json
  {
    "error_guidance": {
      "error_type": "QuickJSTupleDestructuring",
      "error_message": "TypeError: value is not iterable",
      "actionable_guidance": [
        "QuickJS functions return [result, error] tuples - use destructuring",
        "Incorrect: const files = os.readdir('/app')",
        "Correct: const [files, err] = os.readdir('/app')",
        "Check for errors: if (err) { console.error(err); }"
      ],
      "related_docs": [
        "docs/JAVASCRIPT_CAPABILITIES.md#quickjs-api-patterns"
      ],
      "code_examples": [
        "const [files, err] = os.readdir('/app');",
        "if (err) { console.error('Failed to read directory:', err); }",
        "else { console.log('Files:', files); }"
      ]
    }
  }
  ```

#### Scenario: Missing Vendored Package Import Error Guidance

- **WHEN** Python execution fails with ModuleNotFoundError for vendored package
- **THEN** the `SandboxResult.metadata` SHALL contain:
  ```json
  {
    "error_guidance": {
      "error_type": "MissingVendoredPackage",
      "error_message": "ModuleNotFoundError: No module named 'openpyxl'",
      "actionable_guidance": [
        "Package 'openpyxl' is pre-installed but requires sys.path configuration",
        "Add at start of code: import sys; sys.path.insert(0, '/data/site-packages')",
        "Then import normally: import openpyxl",
        "Note: In MCP server, sys.path is auto-configured - this error should not occur"
      ],
      "related_docs": [
        "docs/PYTHON_CAPABILITIES.md#using-vendored-packages"
      ]
    }
  }
  ```

### Requirement: Error Classification Logic

The sandbox SHALL classify errors based on stderr content, trap messages, and exit codes to populate appropriate error guidance.

#### Scenario: Trap-Based Classification

- **WHEN** execution ends with WASM trap
- **THEN** error classification SHALL:
  - Detect "out_of_fuel" trap reason → `OutOfFuel` error type
  - Detect "unreachable" trap → `WASMUnreachable` error type
  - Detect memory limit violations → `MemoryExhausted` error type
  - Include trap message in error guidance context

#### Scenario: Stderr-Based Classification

- **WHEN** execution completes with non-zero exit code
- **THEN** error classification SHALL analyze stderr for patterns:
  - `FileNotFoundError` with path outside `/app` → `PathRestriction`
  - `TypeError: value is not iterable` in JavaScript → `QuickJSTupleDestructuring`
  - `ModuleNotFoundError` for known vendored packages → `MissingVendoredPackage`
  - `SyntaxError` → `SyntaxError` (generic, no special guidance)

#### Scenario: No Error Detected

- **WHEN** execution succeeds (exit_code == 0, no trap)
- **THEN** `SandboxResult.metadata.error_guidance` SHALL be absent or null

### Requirement: Backward Compatibility

Error guidance SHALL be added to existing `SandboxResult.metadata` field to preserve API compatibility with existing clients.

#### Scenario: Existing Clients Ignore New Fields

- **WHEN** an existing client receives `SandboxResult` with `metadata.error_guidance`
- **THEN** the client SHALL:
  - Continue to work without changes (metadata is optional dict)
  - Ignore `error_guidance` field if not explicitly accessed
  - Not experience breaking changes in API contract

#### Scenario: New Clients Consume Error Guidance

- **WHEN** a new client accesses `result.metadata.get('error_guidance')`
- **THEN** the client SHALL:
  - Receive structured error guidance when available
  - Receive `None` when no error occurred
  - Be able to display actionable_guidance to users
  - Optionally link to related_docs for deeper context

### Requirement: Documentation Link Consistency

Error guidance documentation links SHALL reference actual files in the repository and section anchors that exist.

#### Scenario: Valid Documentation References

- **WHEN** error guidance includes `related_docs`
- **THEN** each link SHALL:
  - Reference an existing documentation file (e.g., `docs/PYTHON_CAPABILITIES.md`)
  - Use valid markdown section anchors (e.g., `#fuel-budget-guidelines`)
  - Be maintained when documentation structure changes
  - Be validated during testing (link checker)
