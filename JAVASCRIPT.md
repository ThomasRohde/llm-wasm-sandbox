# JavaScript (QuickJS) Sandbox - Implementation Guide

This document describes the JavaScript runtime support in `llm-wasm-sandbox` using QuickJS compiled to WebAssembly. The JavaScript sandbox provides the same security guarantees as the Python sandbox while allowing safe execution of untrusted JavaScript code.

---

## Overview

The JavaScript sandbox uses **QuickJS-NG v0.11.0** compiled to WASM/WASI, providing a lightweight JavaScript engine that runs under Wasmtime with the same isolation guarantees as the Python runtime.

### QuickJS Version and Source

- **Engine:** QuickJS-NG (Next Generation)
- **Version:** v0.11.0
- **Binary:** `qjs-wasi.wasm` (~1.36 MB)
- **Source:** [https://github.com/quickjs-ng/quickjs](https://github.com/quickjs-ng/quickjs)
- **Build:** Official WASI build with standard `_start` entry point
- **JavaScript Support:** ES2020 features
- **Maintenance:** Actively maintained fork of original QuickJS

### Why QuickJS?

| Feature | Benefit |
|---------|---------|
| 🪶 **Lightweight** | Small binary size (~1.36 MB) suitable for embedding |
| 🔒 **WASI Compatible** | Runs under Wasmtime with capability-based isolation |
| ⚡ **Fast Startup** | Quick initialization for short-lived LLM-generated scripts |
| 📦 **Self-Contained** | No external dependencies or npm ecosystem required |
| 🛡️ **Security** | Same WASM isolation as Python runtime |

---

## Installation

### Download QuickJS Binary

```powershell
# Windows (PowerShell)
.\scripts\fetch_quickjs.ps1
```

This downloads `qjs-wasi.wasm` from the QuickJS-NG releases and saves it to `bin/quickjs.wasm`.

### Verify Installation

```powershell
# Test the JavaScript sandbox
uv run python -c "from sandbox import create_sandbox, RuntimeType; sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT); result = sandbox.execute('console.log(42)'); print(result.stdout)"
```

Expected output: `42`

---

## Basic Usage

### Simple Execution

```python
from sandbox import create_sandbox, RuntimeType

# Create JavaScript sandbox
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

# Execute JavaScript code
result = sandbox.execute("""
console.log("Hello from QuickJS!");
const x = 2 + 2;
console.log(`2 + 2 = ${x}`);
""")

print(result.stdout)
# Output:
# Hello from QuickJS!
# 2 + 2 = 4
```

### Custom Resource Limits

```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

# Configure conservative limits
policy = ExecutionPolicy(
    fuel_budget=500_000_000,        # 500M instructions
    memory_bytes=32 * 1024 * 1024,  # 32 MB
    stdout_max_bytes=100_000,       # 100 KB output
    env={"NODE_ENV": "production"}
)

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=policy)

result = sandbox.execute("""
const factorial = n => n <= 1 ? 1 : n * factorial(n - 1);
console.log(`10! = ${factorial(10)}`);
""")

print(result.stdout)  # 10! = 3628800
print(f"Fuel consumed: {result.fuel_consumed:,}")
```

---

## JavaScript Features and Limitations

### ✅ Supported JavaScript Features

QuickJS-NG provides broad ES2020 support:

- ✅ **ES6+ Syntax:** Arrow functions, template literals, destructuring, spread operators
- ✅ **Modern Features:** `let`/`const`, classes, modules (ES6 modules)
- ✅ **Standard Objects:** `Array`, `Object`, `String`, `Number`, `Math`, `Date`, `RegExp`
- ✅ **Collections:** `Map`, `Set`, `WeakMap`, `WeakSet`
- ✅ **Promises:** `Promise`, `async`/`await` (limited - see async note below)
- ✅ **JSON:** `JSON.parse()`, `JSON.stringify()`
- ✅ **Console:** `console.log()` (maps to stdout)
- ✅ **Typed Arrays:** `Uint8Array`, `Int32Array`, etc.
- ✅ **Error Handling:** `try`/`catch`/`finally`, custom error types

### ❌ Known Limitations

Differences from Node.js and browser environments:

| Feature | Status | Notes |
|---------|--------|-------|
| **npm Packages** | ❌ Not Available | No package manager or `node_modules` |
| **File I/O** | ⚠️ Limited | QuickJS WASI has minimal file APIs (see File I/O section) |
| **Networking** | ❌ Not Available | No sockets by design (security requirement) |
| **Timers** | ❌ Not Available | No `setTimeout`/`setInterval` in WASI build |
| **DOM/BOM** | ❌ Not Available | Not a browser environment |
| **Node.js APIs** | ❌ Not Available | No `require('fs')`, `require('http')`, etc. |
| **Async I/O** | ⚠️ Limited | Promises work but no event loop for timers |
| **Subprocesses** | ❌ Not Available | No `child_process` or OS command execution |
| **`console.error()`** | ❌ Not Available | QuickJS WASI doesn't expose this function |

---

## Console Output Mapping

### stdout and stderr

QuickJS maps console output to standard streams:

```javascript
// Maps to stdout
console.log("Normal output");
console.log("Multiple", "arguments", 42);

// stderr mapping not available in QuickJS WASI
// Use throw to generate stderr output
throw new Error("This appears in stderr");
```

**Important:** `console.error()` is **not available** in the QuickJS WASI build. To generate stderr output, use:
- Syntax errors (detected at parse time)
- Runtime exceptions (`throw new Error(...)`)
- Uncaught errors in execution

### Output Examples

```python
from sandbox import create_sandbox, RuntimeType

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

# stdout output
result = sandbox.execute('console.log("test");')
print(result.stdout)  # "test\n"

# stderr output via exception
result = sandbox.execute('throw new Error("fail");')
print(result.stderr)  # Contains error message
print(result.success)  # False
```

---

## File I/O Support

### Current Limitations

The QuickJS WASI build has **minimal file I/O APIs**. Standard JavaScript file operations are not available:

```javascript
// ❌ Not available in QuickJS WASI:
// - No require('std') module
// - No require('os') module
// - No File API
// - No fs module (not Node.js)
```

### Workaround: Pre-populate Files

For workflows requiring file input/output, use the session API to pre-populate files:

```python
from sandbox import create_sandbox, RuntimeType
from pathlib import Path

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
session_id = sandbox.session_id

# Write input file via host
workspace = Path("workspace") / session_id
workspace.mkdir(parents=True, exist_ok=True)
(workspace / "input.json").write_text('{"data": [1, 2, 3]}')

# JavaScript can read via QuickJS native APIs (if available)
# or process data passed as code
result = sandbox.execute("""
const inputData = {"data": [1, 2, 3]};  // Embed data in code
const sum = inputData.data.reduce((a, b) => a + b, 0);
console.log(`Sum: ${sum}`);
""")

print(result.stdout)  # Sum: 6
```

### Future Enhancements

File I/O support may be expanded in future versions by:
- Adding QuickJS native file APIs to the WASI build
- Providing a custom JavaScript module for file operations
- Implementing a message-passing interface for file requests

---

## Differences from Node.js

QuickJS is **not Node.js**. It's a lightweight JavaScript engine without the Node.js ecosystem:

| Feature | Node.js | QuickJS WASI |
|---------|---------|--------------|
| **Package Manager** | npm, yarn, pnpm | None |
| **Module System** | CommonJS + ES6 | ES6 modules only |
| **Standard Library** | Extensive (`fs`, `http`, `path`, etc.) | Minimal (core JS only) |
| **Async I/O** | Event loop with libuv | Limited (no timers) |
| **Global Objects** | `process`, `Buffer`, `__dirname` | None of these |
| **Performance** | V8 JIT compiler | Interpreter (slower but smaller) |

### Migration Example

**Node.js code:**
```javascript
const fs = require('fs');
const data = fs.readFileSync('file.txt', 'utf8');
console.log(data);
```

**QuickJS equivalent:**
```javascript
// Option 1: Embed data in code (generated by host)
const data = "file contents here";
console.log(data);

// Option 2: Use session API to pre-populate data
// (data injected via code generation)
```

---

## Security Model

The JavaScript sandbox provides the **same security guarantees** as the Python sandbox:

### WASM Isolation

- ✅ **Memory Safety:** Bounds-checked linear memory
- ✅ **Control Flow Validation:** No arbitrary jumps
- ✅ **Type Safety:** WebAssembly type system enforced

### WASI Capabilities

- ✅ **Filesystem Isolation:** Only `/app` directory accessible via preopens
- ✅ **No Network Access:** No socket capabilities by design
- ✅ **No Subprocess Execution:** Cannot spawn child processes
- ✅ **Environment Isolation:** Only whitelisted environment variables

### Resource Limits

```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

policy = ExecutionPolicy(
    fuel_budget=1_000_000_000,      # Instruction limit (stops infinite loops)
    memory_bytes=64 * 1024 * 1024,  # 64 MB memory cap
    stdout_max_bytes=1_000_000,     # 1 MB stdout limit
    stderr_max_bytes=500_000        # 500 KB stderr limit
)

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=policy)
```

### Security Boundaries Tested

The JavaScript sandbox includes comprehensive security tests:

```python
# Test: Infinite loop detection
result = sandbox.execute("while(true) {}")
assert not result.success  # Trapped by fuel exhaustion

# Test: Memory limit
result = sandbox.execute("const arr = new Array(100_000_000);")
assert not result.success  # Trapped by memory limit

# Test: Output capping
result = sandbox.execute('for(let i=0; i<1000000; i++) console.log("x".repeat(1000));')
assert result.metadata["stdout_truncated"]  # Output truncated
```

---

## Error Handling

### Syntax Errors

Syntax errors are detected at parse time and appear in stderr:

```python
result = sandbox.execute("const x = ;")  # Syntax error
print(result.success)  # False
print(result.stderr)   # Contains parse error message
```

### Runtime Errors

Runtime exceptions appear in stderr:

```python
result = sandbox.execute("""
function divide(a, b) {
    if (b === 0) throw new Error("Division by zero");
    return a / b;
}
console.log(divide(10, 0));
""")

print(result.success)  # False
print(result.stderr)   # Contains "Division by zero" error
```

### Fuel Exhaustion

Infinite loops trigger fuel exhaustion:

```python
result = sandbox.execute("while(true) {}")
print(result.success)  # False
print(result.metadata["trapped"])  # True
print(result.metadata["trap_reason"])  # "out_of_fuel"
```

---

## Performance Characteristics

### Startup Time

QuickJS has **fast startup** compared to V8/Node.js:
- Binary size: ~1.36 MB (vs. ~20+ MB for V8)
- Initialization: <10ms typical
- Ideal for: Short-lived LLM-generated scripts

### Execution Speed

QuickJS is an **interpreter** (not JIT compiler):
- Slower than V8 for compute-heavy workloads
- Acceptable for typical LLM code generation tasks
- Fuel metering adds ~5-10% overhead

### Benchmark Example

```python
import time
from sandbox import create_sandbox, RuntimeType

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

start = time.perf_counter()
result = sandbox.execute("""
const factorial = n => n <= 1 ? 1 : n * factorial(n - 1);
console.log(factorial(10));
""")
duration = time.perf_counter() - start

print(f"Execution time: {duration*1000:.2f}ms")
print(f"Fuel consumed: {result.fuel_consumed:,}")
```

---

## LLM Integration Patterns

### Code Generation Workflow

```python
from sandbox import create_sandbox, RuntimeType

def execute_llm_javascript(code: str) -> dict:
    """Execute LLM-generated JavaScript with safety boundaries."""
    
    from sandbox import ExecutionPolicy
    
    policy = ExecutionPolicy(
        fuel_budget=500_000_000,
        memory_bytes=32 * 1024 * 1024
    )
    
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=policy)
    result = sandbox.execute(code)
    
    if not result.success:
        return {
            "status": "error",
            "feedback": f"Execution failed: {result.stderr}",
            "suggestion": "Check syntax and simplify logic"
        }
    
    return {
        "status": "success",
        "output": result.stdout,
        "metrics": {
            "fuel": result.fuel_consumed,
            "duration_ms": result.duration_ms
        }
    }

# Example usage
llm_code = """
const fibonacci = n => n <= 1 ? n : fibonacci(n-1) + fibonacci(n-2);
console.log(fibonacci(10));
"""

feedback = execute_llm_javascript(llm_code)
print(feedback)
```

### Multi-Turn Sessions

```python
from sandbox import create_sandbox, RuntimeType

# Turn 1: Generate data
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
session_id = sandbox.session_id

result1 = sandbox.execute("""
const users = ["Alice", "Bob", "Charlie"];
console.log(JSON.stringify({users, count: users.length}));
""")

print(result1.stdout)
# {"users":["Alice","Bob","Charlie"],"count":3}

# Turn 2: Process data (same session, fresh execution)
sandbox = create_sandbox(session_id=session_id, runtime=RuntimeType.JAVASCRIPT)

result2 = sandbox.execute("""
const data = {"users":["Alice","Bob","Charlie"],"count":3};
data.users.push("Dave");
data.count = data.users.length;
console.log(JSON.stringify(data));
""")

print(result2.stdout)
# {"users":["Alice","Bob","Charlie","Dave"],"count":4}
```

---

## Testing

### Running JavaScript Tests

```powershell
# Run all JavaScript sandbox tests
uv run pytest tests/test_javascript_sandbox.py -v

# Run security tests
uv run pytest tests/test_javascript_security.py -v

# Run with coverage
uv run pytest tests/test_javascript*.py -v --cov=sandbox.runtimes.javascript
```

### Test Coverage

The JavaScript sandbox has comprehensive test coverage:

- ✅ Basic execution (console.log, expressions, functions)
- ✅ Syntax error handling
- ✅ Runtime error handling
- ✅ Fuel exhaustion (infinite loops)
- ✅ Memory limits (large allocations)
- ✅ Output capping (stdout/stderr limits)
- ✅ Environment variable isolation
- ✅ Factory integration
- ✅ Session management

**Current Test Status:**
- 49 test cases created
- 38 tests passing
- 11 tests skipped (file I/O requires APIs not available in QuickJS WASI)

---

## Troubleshooting

### Common Issues

#### ❌ `quickjs.wasm not found`

**Solution:** Download the binary
```powershell
.\scripts\fetch_quickjs.ps1
```

#### ❌ Syntax errors in working code

**Cause:** QuickJS may have stricter parsing than V8

**Solution:** Check for:
- Missing semicolons in edge cases
- Invalid ES6 syntax
- Browser-specific APIs

#### ❌ `ReferenceError: require is not defined`

**Cause:** QuickJS doesn't support CommonJS `require()`

**Solution:** Use ES6 import syntax or embed dependencies in code

#### ❌ File I/O not working

**Cause:** QuickJS WASI has minimal file APIs

**Solution:** Use session API to pre-populate data or embed in code

---

## Future Enhancements

Potential improvements for future versions:

- [ ] **File I/O APIs:** Add QuickJS native file operations
- [ ] **Timer Support:** Implement `setTimeout`/`setInterval` with fuel tracking
- [ ] **Module System:** Support for custom JavaScript modules
- [ ] **Debugger:** Interactive debugging for LLM-generated code
- [ ] **Performance Profiling:** Detailed fuel consumption by function
- [ ] **Standard Library:** Minimal Node.js-compatible APIs

---

## References

- **QuickJS-NG Repository:** [https://github.com/quickjs-ng/quickjs](https://github.com/quickjs-ng/quickjs)
- **QuickJS Documentation:** [https://bellard.org/quickjs/](https://bellard.org/quickjs/)
- **WASI Specification:** [https://github.com/WebAssembly/WASI](https://github.com/WebAssembly/WASI)
- **Wasmtime Documentation:** [https://docs.wasmtime.dev/](https://docs.wasmtime.dev/)

---

## Summary

The JavaScript sandbox provides:

✅ **Secure Execution** - Same WASM/WASI isolation as Python  
✅ **Resource Limits** - Fuel metering and memory caps  
✅ **Fast Startup** - Lightweight engine ideal for LLM workflows  
✅ **ES2020 Support** - Modern JavaScript features  
✅ **Type-Safe API** - Pydantic models and structured logging  

⚠️ **Limitations** - No npm, limited file I/O, no Node.js APIs  
⚠️ **Use Case** - Best for short-lived, self-contained scripts  

For production LLM code execution, the JavaScript sandbox offers a secure, performant alternative to the Python runtime with broad compatibility for modern JavaScript code.
