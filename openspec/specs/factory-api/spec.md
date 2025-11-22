# Capability: Factory API

## ADDED Requirements

### Requirement: Sandbox Factory Function
The sandbox MUST provide a create_sandbox() factory function for runtime-agnostic sandbox creation.

#### Scenario: Create Python sandbox with defaults
Given no runtime is specified
When create_sandbox() is called
Then it MUST return a PythonSandbox instance
And the sandbox MUST use default ExecutionPolicy
And the sandbox MUST use default workspace location

#### Scenario: Create Python sandbox explicitly
Given runtime=RuntimeType.PYTHON
When create_sandbox(runtime=RuntimeType.PYTHON) is called
Then it MUST return a PythonSandbox instance

#### Scenario: Create sandbox with custom policy
Given a custom ExecutionPolicy with fuel_budget=500000000
When create_sandbox(policy=custom_policy) is called
Then the returned sandbox MUST use the custom policy
And policy.fuel_budget MUST equal 500000000

#### Scenario: Create sandbox with custom workspace
Given workspace=Path("/tmp/custom-workspace")
When create_sandbox(workspace=workspace) is called
Then the returned sandbox MUST use /tmp/custom-workspace

#### Scenario: Create sandbox with custom logger
Given a configured SandboxLogger instance
When create_sandbox(logger=custom_logger) is called
Then the returned sandbox MUST use the custom logger

#### Scenario: Pass additional kwargs to runtime
Given wasm_binary_path="bin/python-3.12.wasm"
When create_sandbox(runtime=RuntimeType.PYTHON, wasm_binary_path=wasm_binary_path) is called
Then the PythonSandbox MUST receive the wasm_binary_path parameter

---

### Requirement: JavaScript Runtime Support (Stub)
The factory MUST support JavaScript runtime type with clear not-implemented error.

#### Scenario: Request JavaScript sandbox
Given runtime=RuntimeType.JAVASCRIPT
When create_sandbox(runtime=RuntimeType.JAVASCRIPT) is called
Then it MUST raise NotImplementedError
And the error message MUST indicate "JavaScript runtime will be implemented in a future phase"

---

### Requirement: Unsupported Runtime Validation
The factory MUST reject invalid runtime types.

#### Scenario: Reject invalid runtime string
Given an invalid runtime value "ruby"
When create_sandbox(runtime="ruby") is called
Then it MUST raise ValueError
And the error message MUST indicate "Unsupported runtime: ruby"

#### Scenario: Accept only RuntimeType enum values
Given the factory expects RuntimeType enum
When non-enum values are passed
Then type checkers MUST flag the error
And runtime validation MUST occur

---

### Requirement: Public API Exports
The sandbox package MUST export a stable public API surface.

#### Scenario: Export core models
Given sandbox/__init__.py defines __all__
When a user imports from sandbox
Then ExecutionPolicy MUST be importable
And SandboxResult MUST be importable
And RuntimeType MUST be importable

#### Scenario: Export sandbox classes
Given sandbox/__init__.py defines __all__
When a user imports from sandbox
Then BaseSandbox MUST be importable
And PythonSandbox MUST be importable

#### Scenario: Export factory function
Given sandbox/__init__.py defines __all__
When a user imports from sandbox
Then create_sandbox MUST be importable

#### Scenario: Export exception types
Given sandbox/__init__.py defines __all__
When a user imports from sandbox
Then PolicyValidationError MUST be importable
And SandboxExecutionError MUST be importable (if defined)

#### Scenario: Import convenience
Given the public API is exported in __all__
When a user imports `from sandbox import create_sandbox, RuntimeType`
Then the import MUST succeed without accessing internal modules

---

### Requirement: Type Hints and IDE Support
The public API MUST provide complete type hints for IDE autocomplete and type checking.

#### Scenario: create_sandbox has full type hints
Given create_sandbox function signature
When a user inspects the function in an IDE
Then all parameters MUST have type hints
And the return type MUST be BaseSandbox

#### Scenario: Pydantic models have type hints
Given ExecutionPolicy and SandboxResult are Pydantic models
When a user accesses model fields
Then IDEs MUST provide autocomplete for all fields
And type checkers MUST validate field types

#### Scenario: BaseSandbox abstract methods typed
Given BaseSandbox.execute() signature
When a user implements a subclass
Then type checkers MUST validate the signature matches
And return type SandboxResult MUST be enforced

---

### Requirement: Factory Error Messages
The factory MUST provide clear, actionable error messages.

#### Scenario: Missing WASM binary error
Given wasm_binary_path="bin/missing.wasm"
When create_sandbox(runtime=RuntimeType.PYTHON, wasm_binary_path=wasm_binary_path) is called
Then it SHOULD raise FileNotFoundError on first execute()
And the error message MUST include the missing file path

#### Scenario: Invalid policy error
Given a policy with invalid field values
When create_sandbox(policy=invalid_policy) is called
Then it MUST raise PolicyValidationError
And the error MUST include field-level validation details

#### Scenario: Workspace creation error
Given workspace="/root/forbidden"
When create_sandbox(workspace=Path("/root/forbidden")) is called
And execute() is called
Then it SHOULD raise PermissionError
And the error message MUST indicate workspace permission issue

---

### Requirement: Documentation and Examples
The factory API MUST be documented with usage examples.

#### Scenario: Docstring includes basic example
Given create_sandbox() docstring
When a user reads the docstring
Then it MUST include a minimal usage example
And the example MUST show creating a sandbox and executing code

#### Scenario: README includes factory usage
Given README.md is updated for new API
When a user reads the README
Then it MUST show create_sandbox() usage
And it MUST explain RuntimeType selection
And it MUST show custom policy example

#### Scenario: Type stubs or py.typed marker
Given the package includes type hints
When a user installs the package
Then type checkers MUST recognize the types
And py.typed marker SHOULD be present in the package
