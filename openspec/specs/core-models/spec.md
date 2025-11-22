# Capability: Core Models

## ADDED Requirements

### Requirement: Execution Policy Model
The sandbox MUST provide a validated ExecutionPolicy model that defines resource limits, WASI mounts, and guest environment configuration.

#### Scenario: Create policy with default values
Given no custom configuration is provided
When an ExecutionPolicy is instantiated with defaults
Then it MUST set fuel_budget to 2_000_000_000 instructions
And it MUST set memory_bytes to 128_000_000 bytes
And it MUST set stdout_max_bytes to 2_000_000 bytes
And it MUST set stderr_max_bytes to 1_000_000 bytes
And it MUST set mount_host_dir to "workspace"
And it MUST set guest_mount_path to "/app"
And it MUST include Python UTF-8 environment variables

#### Scenario: Validate positive resource limits
Given a user provides an ExecutionPolicy with fuel_budget = -1000
When the policy is validated
Then it MUST raise a ValidationError indicating fuel_budget must be > 0

#### Scenario: Support optional data mount
Given a user provides mount_data_dir = "datasets"
When the policy is created
Then it MUST set guest_data_path to "/data" by default
And both mount_data_dir and guest_data_path MUST be available for WASI preopen

#### Scenario: Merge environment variables
Given DEFAULT_POLICY includes PYTHONUTF8="1"
And a user provides env={"CUSTOM_VAR": "value"}
When policies are merged
Then the result MUST contain both PYTHONUTF8="1" and CUSTOM_VAR="value"

---

### Requirement: Sandbox Result Model
The sandbox MUST provide a typed SandboxResult model that captures execution outcomes, metrics, and filesystem changes.

#### Scenario: Capture successful execution result
Given untrusted code executes without errors
When the sandbox returns a SandboxResult
Then success MUST be True
And stdout MUST contain captured standard output
And stderr MUST be empty or contain warnings only
And exit_code MUST be 0
And fuel_consumed MUST be a positive integer
And memory_used_bytes MUST be > 0
And duration_ms MUST be > 0

#### Scenario: Capture failed execution result
Given untrusted code exhausts fuel budget
When the sandbox returns a SandboxResult
Then success MUST be False
And stderr MUST contain "OutOfFuel" or equivalent error message
And fuel_consumed MUST equal or exceed the configured fuel_budget

#### Scenario: Track filesystem changes
Given untrusted code creates "output.csv" and modifies "input.txt"
When the sandbox returns a SandboxResult
Then files_created MUST include "output.csv"
And files_modified MUST include "input.txt"
And both paths MUST be relative to workspace root

#### Scenario: Include workspace path
Given execution uses workspace="/tmp/sandbox-abc123"
When the sandbox returns a SandboxResult
Then workspace_path MUST be "/tmp/sandbox-abc123"

---

### Requirement: Runtime Type Enum
The sandbox MUST provide a RuntimeType enum for selecting WASM runtime engines.

#### Scenario: Support Python runtime
Given a user requests RuntimeType.PYTHON
When the runtime type is used
Then it MUST resolve to the string value "python"

#### Scenario: Support JavaScript runtime (future)
Given a user requests RuntimeType.JAVASCRIPT
When the runtime type is used
Then it MUST resolve to the string value "javascript"

#### Scenario: Enum values are strings
Given RuntimeType inherits from str and Enum
When a RuntimeType value is serialized
Then it MUST be JSON-serializable as a string

---

### Requirement: Policy Validation Error
The sandbox MUST provide a PolicyValidationError exception for invalid policy configurations.

#### Scenario: Raise validation error for invalid policy
Given a policy has invalid field values (e.g., negative limits)
When load_policy() or ExecutionPolicy() is called
Then it MUST raise PolicyValidationError
And the error message MUST include field-level validation details

#### Scenario: Distinguish from execution errors
Given PolicyValidationError is a distinct exception type
When error handling code catches PolicyValidationError
Then it MUST be distinguishable from SandboxExecutionError

---

### Requirement: Policy Loading with Validation
The load_policy() function MUST return a validated ExecutionPolicy instance instead of a raw dict.

#### Scenario: Load policy from TOML file
Given config/policy.toml exists with fuel_budget=1000000000
When load_policy("config/policy.toml") is called
Then it MUST return an ExecutionPolicy instance
And policy.fuel_budget MUST equal 1000000000

#### Scenario: Load default policy when file missing
Given config/policy.toml does not exist
When load_policy("config/policy.toml") is called
Then it MUST return an ExecutionPolicy with default values
And no exception MUST be raised

#### Scenario: Validate TOML fields at load time
Given config/policy.toml contains memory_bytes=-1000
When load_policy("config/policy.toml") is called
Then it MUST raise PolicyValidationError
And the error MUST indicate memory_bytes validation failure

#### Scenario: Deep merge environment variables
Given DEFAULT_POLICY env has {"PYTHONUTF8": "1", "LC_ALL": "C.UTF-8"}
And policy.toml env has {"CUSTOM": "value"}
When load_policy() merges configurations
Then the result MUST contain all three environment variables

---

### Requirement: SandboxResult JSON Serialization
SandboxResult MUST be serializable to JSON for artifact storage and logging.

#### Scenario: Serialize result to JSON
Given a SandboxResult with stdout="Hello", fuel_consumed=1000000
When result.model_dump_json() is called
Then it MUST return valid JSON
And the JSON MUST contain all fields (stdout, stderr, fuel_consumed, etc.)

#### Scenario: Deserialize result from JSON
Given JSON string representing a SandboxResult
When SandboxResult.model_validate_json(json_str) is called
Then it MUST reconstruct the original SandboxResult instance
And all field values MUST match
