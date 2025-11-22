# Capability: Factory API

## MODIFIED Requirements

### Requirement: JavaScript Runtime Support (Stub)
The factory MUST support JavaScript runtime type with functional implementation.

**Note:** This requirement replaces the previous stub that raised NotImplementedError. The complete requirement text including all scenarios is provided below.

#### Scenario: Create JavaScript sandbox with defaults
- **WHEN** create_sandbox(runtime=RuntimeType.JAVASCRIPT) is called
- **THEN** it MUST return a JavaScriptSandbox instance
- **AND** the sandbox MUST use default ExecutionPolicy
- **AND** the sandbox MUST use default workspace location
- **AND** the sandbox MUST use bin/quickjs.wasm as WASM binary

#### Scenario: Create JavaScript sandbox with custom policy
- **WHEN** custom policy with fuel_budget=500_000_000 is provided
- **AND** create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=custom_policy) is called
- **THEN** the returned JavaScriptSandbox MUST use the custom policy
- **AND** policy.fuel_budget MUST equal 500_000_000

#### Scenario: Create JavaScript sandbox with custom workspace
- **WHEN** workspace=Path("/tmp/js-workspace") is provided
- **AND** create_sandbox(runtime=RuntimeType.JAVASCRIPT, workspace_root=workspace) is called
- **THEN** the returned JavaScriptSandbox MUST use /tmp/js-workspace as workspace_root

#### Scenario: Create JavaScript sandbox with custom logger
- **WHEN** a configured SandboxLogger instance is provided
- **AND** create_sandbox(runtime=RuntimeType.JAVASCRIPT, logger=custom_logger) is called
- **THEN** the returned JavaScriptSandbox MUST use the custom logger

#### Scenario: Pass wasm_binary_path to JavaScript sandbox
- **WHEN** wasm_binary_path="bin/quickjs-custom.wasm" is provided
- **AND** create_sandbox(runtime=RuntimeType.JAVASCRIPT, wasm_binary_path=wasm_binary_path) is called
- **THEN** the JavaScriptSandbox MUST receive the wasm_binary_path parameter
- **AND** execution MUST use the custom QuickJS binary

#### Scenario: Create JavaScript sandbox with session_id
- **WHEN** session_id="js-session-abc" is provided
- **AND** create_sandbox(runtime=RuntimeType.JAVASCRIPT, session_id=session_id) is called
- **THEN** the JavaScriptSandbox MUST have session_id="js-session-abc"
- **AND** workspace MUST be workspace_root/js-session-abc

#### Scenario: Auto-generate session_id for JavaScript sandbox
- **WHEN** no session_id is provided
- **AND** create_sandbox(runtime=RuntimeType.JAVASCRIPT) is called
- **THEN** the JavaScriptSandbox MUST have a UUIDv4 session_id
- **AND** session workspace MUST be created automatically

#### Scenario: Import JavaScriptSandbox dynamically
- **WHEN** factory dispatches to RuntimeType.JAVASCRIPT
- **THEN** it MUST import from sandbox.runtimes.javascript.sandbox
- **AND** it MUST instantiate JavaScriptSandbox class
- **AND** import MUST NOT fail if JavaScript runtime is not used (lazy import)
