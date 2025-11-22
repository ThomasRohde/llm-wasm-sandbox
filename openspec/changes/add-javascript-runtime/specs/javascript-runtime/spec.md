# Capability: JavaScript Runtime

## ADDED Requirements

### Requirement: JavaScript Sandbox Implementation
The sandbox MUST provide a JavaScriptSandbox class that executes JavaScript code using QuickJS WASM runtime.

#### Scenario: Execute JavaScript code successfully
- **WHEN** execute("console.log('Hello from QuickJS')") is called
- **THEN** it MUST return a SandboxResult with success=True
- **AND** result.stdout MUST contain "Hello from QuickJS"
- **AND** result.fuel_consumed MUST be a positive integer

#### Scenario: Execute code with file I/O
- **WHEN** execute("require('fs').writeFileSync('/app/output.txt', 'data')") is called
- **THEN** the file MUST be created in the workspace
- **AND** result.files_created MUST include "output.txt"
- **AND** result.success MUST be True

#### Scenario: Handle execution errors gracefully
- **WHEN** execute("throw new Error('test error')") is called
- **THEN** it MUST return a SandboxResult with success=False
- **AND** result.stderr MUST contain "Error: test error"
- **AND** the host process MUST NOT crash

#### Scenario: Capture console.log output
- **WHEN** execute("console.log('line1'); console.log('line2')") is called
- **THEN** result.stdout MUST contain both "line1" and "line2"
- **AND** output MUST be in execution order

#### Scenario: Capture console.error output
- **WHEN** execute("console.error('error message')") is called
- **THEN** result.stderr MUST contain "error message"
- **AND** result.stdout MUST be empty

#### Scenario: Use QuickJS WASM binary
- **WHEN** JavaScriptSandbox is instantiated
- **THEN** it MUST use QuickJS compiled to WASM/WASI
- **AND** the binary MUST be located at bin/quickjs.wasm by default
- **AND** the binary path MUST be configurable via wasm_binary_path parameter

---

### Requirement: JavaScript Code Execution Policy
JavaScriptSandbox MUST execute code with appropriate argv and environment configuration.

#### Scenario: Use JavaScript-appropriate argv
- **WHEN** execute() prepares execution
- **THEN** argv MUST be ["quickjs", "/app/user_code.js"]
- **AND** user code MUST be written to workspace/session_id/user_code.js

#### Scenario: Use minimal environment variables
- **WHEN** execute() prepares WASI configuration
- **THEN** env MUST contain minimal or empty variable set
- **AND** env MUST NOT include Python-specific variables (PYTHONUTF8, etc.)
- **AND** env MAY include {"NODE_ENV": "production"} if appropriate

#### Scenario: Mount workspace at /app
- **WHEN** execute() configures WASI preopens
- **THEN** workspace directory MUST be mounted at /app
- **AND** JavaScript code MUST see /app as root for file operations
- **AND** no other filesystem paths MUST be accessible

---

### Requirement: JavaScript Code Validation
JavaScriptSandbox MUST provide syntax validation without execution.

#### Scenario: Validate syntactically correct code
- **WHEN** validate_code("const x = 1 + 2;") is called
- **THEN** it MUST return True

#### Scenario: Reject syntactically invalid code
- **WHEN** validate_code("const x = 1 +") is called
- **THEN** it MUST return False

#### Scenario: Validation does not execute code
- **WHEN** validate_code("console.log('side effect')") is called
- **THEN** no code MUST be executed
- **AND** no output MUST be generated
- **AND** no filesystem operations MUST occur

#### Scenario: Return True if no parser available
- **WHEN** no JavaScript parser is available in host Python
- **THEN** validate_code() MAY return True unconditionally
- **AND** syntax errors will be caught during execute() instead

---

### Requirement: File Delta Detection
JavaScriptSandbox MUST detect filesystem changes made by untrusted JavaScript code.

#### Scenario: Detect created files
- **WHEN** workspace is initially empty
- **AND** execute() creates /app/output.json
- **THEN** result.files_created MUST include "output.json"

#### Scenario: Detect modified files
- **WHEN** /app/input.txt exists before execution
- **AND** execute() appends to /app/input.txt
- **THEN** result.files_modified MUST include "input.txt"

#### Scenario: Exclude user_code.js from delta
- **WHEN** user_code.js is created by the sandbox
- **THEN** result.files_created MUST NOT include "user_code.js"

#### Scenario: Provide relative paths
- **WHEN** code creates /app/subdir/file.json
- **THEN** result.files_created MUST include "subdir/file.json" (relative path)

---

### Requirement: Execution Metrics
JavaScriptSandbox MUST capture detailed execution metrics in SandboxResult.

#### Scenario: Measure execution duration
- **WHEN** code takes ~100ms to execute
- **THEN** result.duration_ms MUST be approximately 100
- **AND** duration MUST be measured with time.perf_counter()

#### Scenario: Capture fuel consumption
- **WHEN** policy.fuel_budget is 2_000_000_000
- **AND** code consumes 500_000 instructions
- **THEN** result.fuel_consumed MUST be approximately 500_000

#### Scenario: Capture memory usage
- **WHEN** code allocates 5 MB
- **THEN** result.memory_used_bytes MUST be >= 5_000_000

#### Scenario: Set workspace path
- **WHEN** execution uses workspace="/tmp/sandbox-abc"
- **THEN** result.workspace_path MUST be "/tmp/sandbox-abc"

#### Scenario: Include runtime in metadata
- **WHEN** execute() returns
- **THEN** result.metadata MUST include runtime="javascript"

---

### Requirement: Security Boundary Preservation
JavaScriptSandbox MUST maintain all existing security guarantees from the Python sandbox.

#### Scenario: Enforce WASI filesystem isolation
- **WHEN** policy mounts only /app
- **AND** code attempts to read /etc/passwd
- **THEN** it MUST fail with permission error
- **AND** result.success MUST be False

#### Scenario: Enforce fuel limits
- **WHEN** policy.fuel_budget is 100_000
- **AND** code contains infinite loop: while(true) {}
- **THEN** it MUST trap with OutOfFuel within the budget
- **AND** result.stderr MUST contain "OutOfFuel" or timeout message

#### Scenario: Enforce memory limits
- **WHEN** policy.memory_bytes is 64_000_000
- **AND** code attempts: let x = new Array(100_000_000)
- **THEN** it MUST fail due to memory limit
- **AND** the host process MUST NOT crash

#### Scenario: Enforce output capping
- **WHEN** policy.stdout_max_bytes is 1000
- **AND** code generates 10_000 bytes via console.log
- **THEN** result.stdout length MUST be <= 1000 bytes
- **AND** metadata MUST indicate truncation (stdout_truncated: true)

#### Scenario: Prevent filesystem escapes
- **WHEN** code attempts to access /app/../etc/passwd
- **THEN** it MUST fail with permission error
- **AND** no path traversal MUST succeed

#### Scenario: No network access
- **WHEN** code attempts network operations (if QuickJS provides any)
- **THEN** all network calls MUST fail
- **AND** QuickJS WASM MUST NOT include socket capabilities

---

### Requirement: Logging Integration
JavaScriptSandbox MUST emit structured log events for execution lifecycle.

#### Scenario: Log execution start
- **WHEN** execute(code) is called
- **THEN** logger.log_execution_start() MUST be called before execution
- **AND** the log MUST include runtime="javascript"
- **AND** the log MUST include policy snapshot (fuel, memory)
- **AND** the log MUST include session_id

#### Scenario: Log execution completion
- **WHEN** execution completes successfully
- **THEN** logger.log_execution_complete(result) MUST be called
- **AND** the log MUST include success, duration_ms, fuel_consumed

#### Scenario: Log security violations
- **WHEN** code exhausts fuel budget
- **THEN** logger MAY log security event
- **AND** event type MUST be "fuel_exhaustion" if logged

---

### Requirement: WASM Binary Configuration
JavaScriptSandbox MUST support custom WASM binary paths for different QuickJS versions.

#### Scenario: Use default WASM binary
- **WHEN** no wasm_binary_path is specified
- **THEN** it MUST default to "bin/quickjs.wasm"

#### Scenario: Use custom WASM binary
- **WHEN** wasm_binary_path="bin/quickjs-custom.wasm" is provided
- **THEN** it MUST use the specified binary for execution

#### Scenario: Validate WASM binary exists
- **WHEN** wasm_binary_path points to non-existent file
- **AND** execute() is called
- **THEN** it MUST raise FileNotFoundError
- **AND** error message MUST include the missing file path

---

### Requirement: Session Management Integration
JavaScriptSandbox MUST integrate with session-based workflow like PythonSandbox.

#### Scenario: Accept session_id in constructor
- **WHEN** JavaScriptSandbox is instantiated with session_id="test-session-123"
- **THEN** self.session_id MUST be set to "test-session-123"
- **AND** workspace MUST be workspace_root/test-session-123

#### Scenario: Write code to session workspace
- **WHEN** execute(code) is called
- **THEN** user_code.js MUST be written to workspace_root/session_id/user_code.js

#### Scenario: Update session metadata after execution
- **WHEN** execute() completes
- **THEN** session metadata timestamp MUST be updated
- **AND** .metadata.json MUST have current updated_at value

#### Scenario: Isolate sessions from each other
- **WHEN** two sandboxes with different session_ids are created
- **THEN** each MUST have separate workspace directories
- **AND** executions MUST NOT interfere with each other

---

### Requirement: Error Handling and Result Mapping
JavaScriptSandbox MUST map JavaScript execution errors to SandboxResult fields.

#### Scenario: Map syntax errors to stderr
- **WHEN** code contains syntax error: "const x = "
- **THEN** result.success MUST be False
- **AND** result.stderr MUST contain syntax error message
- **AND** result.exit_code MUST be non-zero

#### Scenario: Map runtime exceptions to stderr
- **WHEN** code throws: throw new TypeError('bad type')
- **THEN** result.success MUST be False
- **AND** result.stderr MUST contain "TypeError: bad type"
- **AND** result.exit_code MUST be non-zero

#### Scenario: Map successful execution to success=True
- **WHEN** code executes without errors
- **THEN** result.success MUST be True
- **AND** result.exit_code MUST be 0
- **AND** result.stderr MUST be empty or contain only warnings

#### Scenario: Populate all SandboxResult fields
- **WHEN** execute() returns
- **THEN** all required SandboxResult fields MUST be populated
- **AND** stdout, stderr, exit_code, fuel_consumed, memory_used_bytes, duration_ms, workspace_path MUST have valid values
- **AND** metadata MUST include at minimum: runtime="javascript"

---

### Requirement: Host Layer Integration
JavaScriptSandbox MUST integrate with low-level host execution layer.

#### Scenario: Use separate host function for JavaScript
- **WHEN** JavaScriptSandbox delegates to host layer
- **THEN** it MAY call run_untrusted_javascript() function
- **OR** it MAY call generalized run_untrusted_wasm() function
- **AND** WASI configuration MUST be equivalent to Python sandbox

#### Scenario: Configure WASI with JavaScript specifics
- **WHEN** host function is called
- **THEN** argv MUST be set to ["quickjs", "/app/user_code.js"]
- **AND** env MUST be set to JavaScript-appropriate variables
- **AND** stdout/stderr capture MUST work with QuickJS output

#### Scenario: Reuse fuel and memory limiting
- **WHEN** host function executes WASM
- **THEN** it MUST configure Wasmtime store with fuel and memory limits from policy
- **AND** fuel consumption MUST be tracked and returned
- **AND** memory usage MUST be tracked and returned

---

### Requirement: BaseSandbox Interface Compliance
JavaScriptSandbox MUST comply with BaseSandbox abstract interface.

#### Scenario: Inherit from BaseSandbox
- **WHEN** JavaScriptSandbox is defined
- **THEN** it MUST inherit from BaseSandbox abstract base class

#### Scenario: Implement execute method
- **WHEN** JavaScriptSandbox is instantiated
- **THEN** it MUST implement execute(code: str, **kwargs) -> SandboxResult
- **AND** the signature MUST match BaseSandbox abstract method

#### Scenario: Implement validate_code method
- **WHEN** JavaScriptSandbox is instantiated
- **THEN** it MUST implement validate_code(code: str) -> bool
- **AND** the signature MUST match BaseSandbox abstract method

#### Scenario: Call parent __init__
- **WHEN** JavaScriptSandbox.__init__() is called
- **THEN** it MUST call super().__init__(policy, session_id, workspace_root, logger)
- **AND** all BaseSandbox attributes MUST be initialized

---

### Requirement: QuickJS Binary Provisioning
The project MUST provide tooling to download and verify QuickJS WASM binary.

#### Scenario: Provide PowerShell download script
- **WHEN** scripts/fetch_quickjs.ps1 is executed
- **THEN** it MUST download QuickJS WASM binary from verified source
- **AND** it MUST place binary in bin/quickjs.wasm
- **AND** it MUST report success or failure clearly

#### Scenario: Exclude binary from version control
- **WHEN** .gitignore is configured
- **THEN** bin/quickjs.wasm MUST be excluded
- **AND** binary MUST NOT be committed to repository

#### Scenario: Document binary source and version
- **WHEN** README.md or JAVASCRIPT.md is read
- **THEN** it MUST document QuickJS version used
- **AND** it MUST link to source repository
- **AND** it MUST provide checksum if available

#### Scenario: Handle missing binary gracefully
- **WHEN** JavaScriptSandbox.execute() is called
- **AND** bin/quickjs.wasm does not exist
- **THEN** it MUST raise FileNotFoundError
- **AND** error message MUST direct user to fetch script
