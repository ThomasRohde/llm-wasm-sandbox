# Capability: Python Runtime

## ADDED Requirements

### Requirement: Base Sandbox Abstraction
The sandbox MUST provide a BaseSandbox abstract base class that defines the contract for all runtime implementations.

#### Scenario: Define abstract execute method
Given BaseSandbox is an abstract base class
When a subclass is created
Then it MUST implement execute(code: str) -> SandboxResult
And the method MUST accept untrusted code as a string
And the method MUST return a typed SandboxResult

#### Scenario: Define abstract validate_code method
Given BaseSandbox is an abstract base class
When a subclass is created
Then it MUST implement validate_code(code: str) -> bool
And the method MUST perform syntax-only validation
And the method MUST NOT execute the code

#### Scenario: Provide shared initialization
Given BaseSandbox provides __init__(policy, workspace, logger)
When a subclass calls super().__init__()
Then self.policy MUST be set to the provided ExecutionPolicy
And self.workspace MUST be set to the provided Path
And self.logger MUST be set to the provided SandboxLogger or default

#### Scenario: Provide log helper method
Given BaseSandbox provides _log_execution_metrics(result)
When a subclass calls the method after execution
Then it MUST delegate to self.logger.log_execution_complete(result)

---

### Requirement: Python Sandbox Implementation
The sandbox MUST provide a PythonSandbox class that executes Python code using CPython WASM runtime.

#### Scenario: Execute Python code successfully
Given a PythonSandbox instance with default policy
When execute("print('Hello')") is called
Then it MUST return a SandboxResult with success=True
And result.stdout MUST contain "Hello"
And result.fuel_consumed MUST be a positive integer

#### Scenario: Execute with injected setup code
Given inject_setup=True (default)
When execute("import urllib3; print('OK')") is called
Then the code MUST have sys.path setup prepended
And /app/site-packages MUST be available for imports
And the import MUST succeed

#### Scenario: Execute without injected setup
Given inject_setup=False
When execute("print(sys.path)", inject_setup=False) is called
Then no setup code MUST be prepended
And sys.path MUST be the default WASM Python sys.path

#### Scenario: Handle execution errors gracefully
Given untrusted code raises an exception
When execute("raise ValueError('test')") is called
Then it MUST return a SandboxResult with success=False
And result.stderr MUST contain "ValueError: test"
And the host process MUST NOT crash

#### Scenario: Reuse existing host layer logic
Given PythonSandbox wraps existing host.py functionality
When execute() is called
Then it MUST delegate to run_untrusted_python()
And all WASI configuration MUST match current behavior
And all security boundaries MUST be preserved

---

### Requirement: Python Code Validation
PythonSandbox MUST provide syntax validation without execution.

#### Scenario: Validate syntactically correct code
Given valid Python code "x = 1 + 2"
When validate_code("x = 1 + 2") is called
Then it MUST return True

#### Scenario: Reject syntactically invalid code
Given invalid Python code "x = 1 +"
When validate_code("x = 1 +") is called
Then it MUST return False

#### Scenario: Validation does not execute code
Given code with side effects "import os; os.system('rm -rf /')"
When validate_code(code) is called
Then no code MUST be executed
And no filesystem operations MUST occur

#### Scenario: Use Python compile() for validation
Given PythonSandbox uses compile(code, "<sandbox>", "exec")
When validate_code() is called
Then it MUST catch SyntaxError and return False
And it MUST return True for successful compilation

---

### Requirement: File Delta Detection
PythonSandbox MUST detect filesystem changes made by untrusted code.

#### Scenario: Detect created files
Given workspace is initially empty
When execute("open('/app/output.txt', 'w').write('data')") is called
Then result.files_created MUST include "output.txt"

#### Scenario: Detect modified files
Given /app/input.txt exists before execution
When execute("with open('/app/input.txt', 'a') as f: f.write('more')") is called
Then result.files_modified MUST include "input.txt"

#### Scenario: Exclude user_code.py from delta
Given user_code.py is always created by the sandbox
When execute() returns a result
Then result.files_created MUST NOT include "user_code.py"

#### Scenario: Provide relative paths
Given workspace is "/abs/path/workspace"
And code creates "/app/subdir/file.txt"
When the result is returned
Then files_created MUST include "subdir/file.txt" (relative path)

---

### Requirement: Execution Metrics
PythonSandbox MUST capture detailed execution metrics in SandboxResult.

#### Scenario: Measure execution duration
Given code takes ~100ms to execute
When execute(code) is called
Then result.duration_ms MUST be approximately 100
And duration MUST be measured with time.perf_counter()

#### Scenario: Capture fuel consumption
Given policy.fuel_budget is 2_000_000_000
And code consumes 1_000_000 instructions
When execute(code) returns
Then result.fuel_consumed MUST be approximately 1_000_000

#### Scenario: Capture memory usage
Given code allocates 10 MB
When execute(code) returns
Then result.memory_used_bytes MUST be >= 10_000_000

#### Scenario: Set workspace path
Given execution uses workspace="/tmp/sandbox-123"
When execute(code) returns
Then result.workspace_path MUST be "/tmp/sandbox-123"

---

### Requirement: Security Boundary Preservation
PythonSandbox MUST maintain all existing security guarantees from the current implementation.

#### Scenario: Enforce WASI filesystem isolation
Given policy mounts only /app
When code attempts open("/etc/passwd")
Then it MUST fail with "not-permitted" or equivalent error
And result.success MUST be False

#### Scenario: Enforce fuel limits
Given policy.fuel_budget is 100_000
And code contains an infinite loop
When execute("while True: pass") is called
Then it MUST trap with OutOfFuel within the budget
And result.stderr MUST contain "OutOfFuel" or timeout message

#### Scenario: Enforce memory limits
Given policy.memory_bytes is 64_000_000
And code attempts to allocate 100 MB
When execute("x = 'a' * 100_000_000") is called
Then it MUST fail due to memory limit
And the host process MUST NOT crash

#### Scenario: Enforce output capping
Given policy.stdout_max_bytes is 1000
And code prints 10,000 bytes
When execute(code) returns
Then result.stdout length MUST be <= 1000 bytes
And truncation MUST be indicated

---

### Requirement: Logging Integration
PythonSandbox MUST emit structured log events for execution lifecycle.

#### Scenario: Log execution start
Given a PythonSandbox with configured logger
When execute(code) is called
Then logger.log_execution_start() MUST be called before execution
And the log MUST include runtime="python"
And the log MUST include policy snapshot (fuel, memory)

#### Scenario: Log execution completion
Given execution completes successfully
When the result is returned
Then logger.log_execution_complete(result) MUST be called
And the log MUST include success, duration_ms, fuel_consumed

#### Scenario: Log security violations
Given code exhausts fuel budget
When execution is interrupted
Then logger.log_security_event() MAY be called
And the event type MUST be "fuel_exhaustion"

---

### Requirement: WASM Binary Configuration
PythonSandbox MUST support custom WASM binary paths for different Python versions or distributions.

#### Scenario: Use default WASM binary
Given no wasm_binary_path is specified
When PythonSandbox is instantiated
Then it MUST default to "bin/python.wasm"

#### Scenario: Use custom WASM binary
Given wasm_binary_path="bin/python-3.12.wasm"
When PythonSandbox is instantiated
Then it MUST use the specified binary for execution

#### Scenario: Validate WASM binary exists
Given wasm_binary_path points to non-existent file
When execute() is called
Then it MUST raise FileNotFoundError or equivalent
And provide a clear error message
