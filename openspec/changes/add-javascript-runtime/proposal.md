# Change: Add JavaScript Runtime Support

## Why

LLMs frequently generate JavaScript code for web automation, data processing, and scripting tasks. Currently, the sandbox only supports Python execution, forcing users to either run JavaScript in unsafe environments or manually translate code to Python. Adding JavaScript runtime support enables the sandbox to safely execute untrusted JS code with the same security guarantees (no network, filesystem isolation, resource limits) that currently protect Python execution.

This capability is essential for:
- **Multi-language LLM workflows**: Allow LLMs to choose the best language for each task
- **Web automation tasks**: Execute browser automation scripts or DOM manipulation logic
- **Node.js-style scripting**: Run data transformation and file processing code
- **Parity with Python**: Provide equivalent security and monitoring for JavaScript workloads

## What Changes

Add a complete JavaScript runtime implementation using QuickJS compiled to WASM, mirroring the existing Python sandbox architecture:

- **New JavaScriptSandbox class** in `sandbox/runtimes/javascript/sandbox.py`
  - Implements BaseSandbox interface
  - Executes untrusted JS code via QuickJS WASM binary
  - Captures console.log/console.error output to stdout/stderr
  - Enforces fuel budgets, memory limits, and filesystem isolation
  - Detects file changes and populates SandboxResult with metrics

- **QuickJS WASM binary integration** (`bin/quickjs.wasm`)
  - WASI-compatible QuickJS engine (~1-2 MB binary)
  - Download script: `scripts/fetch_quickjs.ps1`
  - Invoked via Wasmtime with same security model as Python

- **Factory function update** in `sandbox/core/factory.py`
  - Remove NotImplementedError for RuntimeType.JAVASCRIPT
  - Instantiate JavaScriptSandbox when runtime == RuntimeType.JAVASCRIPT
  - Pass wasm_binary_path kwarg (default: "bin/quickjs.wasm")

- **ExecutionPolicy defaults for JavaScript**
  - Default argv: `["quickjs", "/app/user_code.js"]`
  - Default env: `{"NODE_ENV": "production"}` (minimal)
  - Reuse fuel_budget, memory_bytes, stdout/stderr caps from existing policy

- **Testing and validation**
  - `tests/test_javascript_sandbox.py`: Unit tests for JS execution
  - `tests/test_javascript_security.py`: Security boundary tests (fuel, memory, filesystem)
  - Coverage targets: >90% for new JavaScriptSandbox code

- **Documentation updates**
  - Update README.md with JavaScript examples
  - Update JAVASCRIPT.md with implementation details
  - Add QuickJS binary download instructions

## Impact

**Affected Specs:**
- `specs/factory-api/spec.md` - MODIFIED: Factory JavaScript stub requirement
- `specs/javascript-runtime/spec.md` - ADDED: New capability spec for JavaScript runtime

**Affected Code:**
- `sandbox/core/factory.py` - Update RuntimeType.JAVASCRIPT branch to instantiate JavaScriptSandbox
- `sandbox/runtimes/javascript/` - New module with sandbox.py, __init__.py
- `bin/` - Add quickjs.wasm binary
- `scripts/` - Add fetch_quickjs.ps1 download script
- `tests/` - Add test_javascript_sandbox.py, test_javascript_security.py

**Backwards Compatibility:**
- ✅ No breaking changes to existing API
- ✅ Python sandbox behavior unchanged
- ✅ ExecutionPolicy model remains compatible
- ✅ SandboxResult schema unchanged
- ✅ Existing tests continue passing

**Non-Goals:**
- No npm/Node.js module ecosystem support (QuickJS is standalone interpreter)
- No async/await or Promise support in initial version (may defer to future iteration)
- No browser DOM APIs (sandbox focuses on pure JavaScript execution)
- No REPL mode in first version (script-only execution like Python)

**Migration Path:**
- Users currently blocked by Python-only limitation can immediately use RuntimeType.JAVASCRIPT
- No code changes required for existing Python workflows
- New users can choose runtime based on LLM-generated code language

**Security Considerations:**
- JavaScript sandbox MUST preserve all existing security boundaries (no network, no subprocess, WASI filesystem isolation)
- QuickJS WASM binary MUST NOT include network capabilities or non-standard syscalls
- Fuel metering MUST apply to JavaScript execution (instruction counting)
- Memory limits MUST be enforced via Wasmtime store configuration
- All security tests from Python sandbox MUST have JavaScript equivalents
