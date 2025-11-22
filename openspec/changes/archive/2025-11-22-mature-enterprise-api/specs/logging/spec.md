# Capability: Logging

## ADDED Requirements

### Requirement: Structured Logger
The sandbox MUST provide a SandboxLogger class that emits structured, event-based logs.

#### Scenario: Wrap standard Python logger
Given a user provides a logging.Logger instance
When SandboxLogger is instantiated with that logger
Then it MUST use the provided logger for all log calls

#### Scenario: Use default logger
Given no logger is provided to SandboxLogger
When SandboxLogger is instantiated
Then it MUST create a default logger named "sandbox"

#### Scenario: Expose underlying logger
Given a SandboxLogger instance
When the .logger property is accessed
Then it MUST return the underlying logging.Logger instance

---

### Requirement: Execution Start Event
The sandbox MUST log structured events when execution begins.

#### Scenario: Log execution start with runtime
Given a sandbox is about to execute code
When log_execution_start("python", policy) is called
Then it MUST emit an INFO level log
And the message MUST be "sandbox.execution.start"
And the extra dict MUST include event="execution.start"
And the extra dict MUST include runtime="python"

#### Scenario: Log execution start with policy snapshot
Given a policy with fuel_budget=1000000 and memory_bytes=64000000
When log_execution_start("python", policy) is called
Then the extra dict MUST include fuel_budget=1000000
And the extra dict MUST include memory_bytes=64000000

#### Scenario: Log execution start with workspace
Given execution uses workspace="/tmp/sandbox-abc"
When log_execution_start("python", policy, workspace="/tmp/sandbox-abc") is called
Then the extra dict MUST include workspace="/tmp/sandbox-abc"

#### Scenario: Support additional metadata
Given extra keyword arguments are passed
When log_execution_start("python", policy, session_id="123", user="alice") is called
Then the extra dict MUST include session_id="123"
And the extra dict MUST include user="alice"

---

### Requirement: Execution Complete Event
The sandbox MUST log structured events when execution finishes.

#### Scenario: Log successful execution completion
Given execution completed successfully
When log_execution_complete(result) is called
Then it MUST emit an INFO level log
And the message MUST be "sandbox.execution.complete"
And the extra dict MUST include event="execution.complete"
And the extra dict MUST include success=True

#### Scenario: Log execution metrics
Given result.duration_ms=150.5 and result.fuel_consumed=1000000
When log_execution_complete(result) is called
Then the extra dict MUST include duration_ms=150.5
And the extra dict MUST include fuel_consumed=1000000

#### Scenario: Log memory usage
Given result.memory_used_bytes=10485760
When log_execution_complete(result) is called
Then the extra dict MUST include memory_used_bytes=10485760

#### Scenario: Log exit code
Given result.exit_code=0
When log_execution_complete(result) is called
Then the extra dict MUST include exit_code=0

#### Scenario: Log failed execution completion
Given result.success=False
When log_execution_complete(result) is called
Then the extra dict MUST include success=False
And the log level MUST still be INFO (failures are expected)

---

### Requirement: Security Event Logging
The sandbox MUST log security violations and boundary events.

#### Scenario: Log fuel exhaustion
Given code exhausts fuel budget
When log_security_event("fuel_exhaustion", details) is called
Then it MUST emit a WARNING level log
And the message MUST be "sandbox.security.fuel_exhaustion"
And the extra dict MUST include event="security.fuel_exhaustion"

#### Scenario: Log filesystem denial
Given code attempts to access forbidden path
When log_security_event("filesystem_denial", {"path": "/etc/passwd"}) is called
Then it MUST emit a WARNING level log
And the message MUST be "sandbox.security.filesystem_denial"
And the extra dict MUST include path="/etc/passwd"

#### Scenario: Log memory limit violation
Given code hits memory cap
When log_security_event("memory_limit", {"requested": 100000000, "limit": 64000000}) is called
Then it MUST emit a WARNING level log
And the extra dict MUST include requested and limit values

#### Scenario: Support custom event types
Given a new security event type "network_attempt"
When log_security_event("network_attempt", {"destination": "1.1.1.1"}) is called
Then the message MUST be "sandbox.security.network_attempt"
And all provided details MUST be included in extra dict

---

### Requirement: No Global Logger Configuration
The sandbox MUST NOT modify global logging configuration.

#### Scenario: No handler installation
Given SandboxLogger is instantiated
When any log method is called
Then it MUST NOT call logging.basicConfig()
And it MUST NOT add handlers to the logger

#### Scenario: No formatter configuration
Given SandboxLogger is instantiated
When any log method is called
Then it MUST NOT set formatters on the logger
And formatting MUST be the host application's responsibility

#### Scenario: No log level changes
Given the underlying logger has level=WARNING
When SandboxLogger is instantiated
Then it MUST NOT change the logger's level
And logs below WARNING MUST NOT be emitted

---

### Requirement: Host Application Integration
The sandbox logging MUST support integration with host application telemetry systems.

#### Scenario: Support correlation IDs
Given host application provides trace_id="abc-123"
When logs are emitted with correlation context
Then the host MAY extract trace_id from logger context
And correlate sandbox logs with distributed traces

#### Scenario: Structured extra dict format
Given all log methods use structured extra dicts
When logs are processed by structured logging backends (structlog, JSON formatter)
Then all fields MUST be machine-readable
And no unstructured string concatenation MUST occur

#### Scenario: OTEL span creation by host
Given host application uses OpenTelemetry
When execution.start and execution.complete events are emitted
Then the host MAY create OTEL spans from these events
And the sandbox MUST NOT depend on or import opentelemetry libraries

---

### Requirement: Filesystem Delta Logging
The sandbox MUST support logging filesystem changes as structured events.

#### Scenario: Log file creation count
Given execution created 5 files
When filesystem delta is logged
Then the event MUST include files_created_count=5

#### Scenario: Log file paths with truncation
Given execution created files with very long paths
When filesystem delta is logged
Then paths MUST be truncated to prevent log flooding if they exceed reasonable length
And truncation MUST be indicated (e.g., "...[truncated]")

#### Scenario: Log modified file count
Given execution modified 3 existing files
When filesystem delta is logged
Then the event MUST include files_modified_count=3

---

### Requirement: Error Context Logging
The sandbox MUST provide context in logs when errors occur.

#### Scenario: Log execution failure context
Given code raises an exception
When the error is logged
Then it MUST include error message or type
And it MAY include stack trace snippet

#### Scenario: Log policy violation context
Given code violates a policy constraint
When the violation is logged
Then it MUST include the violated constraint name
And the configured limit and attempted value

#### Scenario: Log WASM trap context
Given WASM execution traps (e.g., OutOfFuel)
When the trap is logged
Then it MUST include trap type
And it MAY include instruction count at trap
