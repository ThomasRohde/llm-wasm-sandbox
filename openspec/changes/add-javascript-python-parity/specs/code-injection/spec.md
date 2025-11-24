# Code Injection Specification

## ADDED Requirements

### Requirement: Automatic JavaScript Prologue Injection
JavaScript runtime SHALL automatically inject setup code before user code to provide helper functions and import necessary modules.

#### Scenario: Inject std module import automatically
- **GIVEN** JavaScript sandbox executes user code
- **WHEN** user code does NOT explicitly import `std` module
- **THEN** runtime SHALL prepend `import * as std from "std";`
- **AND** injection SHALL happen before any user code
- **AND** injection SHALL be transparent to user

#### Scenario: Inject requireVendor helper function
- **GIVEN** JavaScript sandbox executes user code
- **WHEN** prologue is injected
- **THEN** runtime SHALL define `globalThis.requireVendor()` function
- **AND** function SHALL be available to user code immediately
- **AND** implementation SHALL use `std.open()` for file reading

#### Scenario: Conditional injection based on inject_setup flag
- **GIVEN** user creates JavaScript sandbox
- **WHEN** user calls `sandbox.execute(code, inject_setup=False)`
- **THEN** runtime SHALL NOT inject prologue code
- **AND** user code SHALL run exactly as written
- **AND** pattern mirrors Python's `inject_setup` parameter

### Requirement: Injection Implementation in JavaScriptSandbox
The `JavaScriptSandbox.execute()` method SHALL handle code injection similarly to `PythonSandbox.execute()`.

#### Scenario: Default injection enabled
- **GIVEN** JavaScriptSandbox instance
- **WHEN** `execute(code)` is called without `inject_setup` parameter
- **THEN** `inject_setup` SHALL default to `True`
- **AND** prologue SHALL be prepended to user code
- **AND** behavior mirrors Python's default

#### Scenario: Injected code is written to workspace file
- **GIVEN** user code with auto-injection enabled
- **WHEN** `JavaScriptSandbox._write_untrusted_code()` is called
- **THEN** method SHALL combine prologue + user code
- **AND** combined code SHALL be written to `user_code.js`
- **AND** pattern mirrors Python's code writing

#### Scenario: Prologue content is consistent
- **GIVEN** multiple executions in same session
- **WHEN** each execution has `inject_setup=True`
- **THEN** prologue SHALL be identical across executions
- **AND** prologue SHALL not accumulate or duplicate
- **AND** user code file SHALL contain only one copy of prologue

### Requirement: Prologue Code Template
The injected prologue SHALL be defined as a constant string in `sandbox/runtimes/javascript/sandbox.py`.

#### Scenario: Prologue defined as module constant
- **GIVEN** JavaScript sandbox module loads
- **WHEN** code defines prologue template
- **THEN** template SHALL be defined as `INJECTED_SETUP` constant
- **AND** constant SHALL be at module level (like Python's `INJECTED_SETUP`)
- **AND** constant SHALL include:
  - std module import
  - requireVendor function definition
  - Helper function definitions (readJson, writeJson)

#### Scenario: Prologue is tested independently
- **GIVEN** prologue template exists
- **WHEN** tests validate injection behavior
- **THEN** tests SHALL verify prologue syntax is valid JavaScript
- **AND** tests SHALL verify std module is imported
- **AND** tests SHALL verify requireVendor is defined
- **AND** tests SHALL verify injected code doesn't break user code
