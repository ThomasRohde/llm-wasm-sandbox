# JavaScript State Persistence Implementation

## Overview

This document describes the implementation of state persistence for the JavaScript runtime, achieving feature parity with the Python runtime's `auto_persist_globals` functionality.

## Key Findings

### QuickJS WASI Module Integration

The QuickJS-NG WASI binary (`qjs-wasi.wasm`) includes full support for the `std` and `os` modules, which provide file I/O capabilities. However, these modules are **not** accessible via ES6 module imports (`import * as std from "std"`) due to the module loader not resolving builtin module names.

**Solution**: Use the `--std` CLI flag to make `std` and `os` available as **global objects** instead of ES6 modules.

### Correct CLI Configuration

The QuickJS CLI must be invoked with the following argv:

```python
js_argv = ["qjs", "--std", "/app/user_code.js"]
```

- `qjs`: The CLI executable name
- `--std`: Initialize `std` and `os` modules as global objects
- `/app/user_code.js`: Path to the user script (in WASI guest filesystem)

**DO NOT USE** the `-m` flag for ES6 module mode, as it causes module resolution issues with builtin modules.

### File I/O API

QuickJS's `std` module provides the following file I/O APIs:

```javascript
// Open file for writing
const f = std.open('/app/filename.txt', 'w');
f.puts("content");  // Write string
f.close();

// Open file for reading
const f = std.open('/app/filename.txt', 'r');
const content = f.readAsString();  // Read entire file as string
f.close();

// Check if file was opened successfully
if (!f) {
    console.log("Failed to open file");
}
```

## Implementation Details

### State Persistence Pattern

State is persisted using a `_state` global object that is serialized to JSON and written to a file:

```javascript
// Load state (prologue)
var _state = {};
try {
    const f = std.open('/app/.session_state.json', 'r');
    if (f) {
        const content = f.readAsString();
        f.close();
        _state = JSON.parse(content);
    }
} catch (e) {
    // State file doesn't exist yet (first execution)
}

// User code can modify _state
_state.counter = (_state.counter || 0) + 1;
_state.items = _state.items || [];
_state.items.push("new item");

// Save state (epilogue)
if (typeof _state !== 'undefined') {
    const f = std.open('/app/.session_state.json', 'w');
    if (f) {
        f.puts(JSON.stringify(_state));
        f.close();
    }
}
```

### Usage Patterns

#### Pattern 1: Auto-persist with Sandbox

```python
from sandbox import create_sandbox, RuntimeType

sandbox = create_sandbox(
    runtime=RuntimeType.JAVASCRIPT,
    auto_persist_globals=True
)

# Execution 1
result1 = sandbox.execute("""
_state.counter = (_state.counter || 0) + 1;
console.log("Counter:", _state.counter);
""")
# Output: Counter: 1

# Execution 2 (state persists)
result2 = sandbox.execute("""
_state.counter = (_state.counter || 0) + 1;
console.log("Counter:", _state.counter);
""")
# Output: Counter: 2
```

#### Pattern 2: Manual State Wrapping

```python
from sandbox import create_sandbox, RuntimeType
from sandbox.state_js import wrap_stateful_code

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

user_code = """
_state.data = _state.data || [];
_state.data.push("item");
console.log("Items:", _state.data.length);
"""

wrapped = wrap_stateful_code(user_code)
result = sandbox.execute(wrapped)
```

### Limitations

1. **JSON Serialization Only**: Only JSON-serializable types are persisted:
   - ✅ Primitives: `number`, `string`, `boolean`, `null`
   - ✅ Objects: `{}` (plain objects)
   - ✅ Arrays: `[]`
   - ❌ Functions: Filtered out by `JSON.stringify`
   - ❌ Symbols: Not serializable
   - ❌ undefined: Filtered out
   - ❌ Complex objects: `Map`, `Set`, `Date`, custom classes

2. **Explicit State Object**: Unlike Python, JavaScript variables declared with `let` or `const` do **not** automatically become global properties. Users must explicitly use the `_state` object:

   ```javascript
   // ❌ WRONG - Won't persist
   let counter = 0;
   
   // ✅ CORRECT - Will persist
   _state.counter = (_state.counter || 0) + 1;
   ```

3. **No Circular References**: JSON serialization does not handle circular references.

4. **Fuel Consumption**: State load/save operations consume fuel (WASM instructions). Large state objects may impact execution limits.

## Testing

Comprehensive tests are provided in `tests/test_javascript_state.py`:

- Basic state persistence across executions
- Session isolation (different sessions have independent state)
- Complex objects (arrays, nested objects)
- Error handling (corrupted JSON, missing files)
- State filtering (functions excluded)
- Boolean and null values
- Empty objects and arrays
- Session resumption

Run tests with:

```bash
uv run pytest tests/test_javascript_state.py -v
```

## Migration from Python

### Differences from Python State Persistence

| Feature | Python | JavaScript |
|---------|--------|------------|
| State object | `globals()` | `_state` object |
| Variable declaration | `x = 1` persists | Must use `_state.x = 1` |
| Serialization | Pickle (Python-specific) | JSON (cross-language) |
| Module imports | ES6 imports unsupported | Global `std`/`os` |
| Complex types | Classes supported | JSON-only |

### Porting Python Code to JavaScript

**Python:**
```python
counter = 0

def increment():
    global counter
    counter += 1
    return counter
```

**JavaScript:**
```javascript
_state.counter = _state.counter || 0;

function increment() {
    _state.counter += 1;
    return _state.counter;
}
```

## References

- QuickJS documentation: https://bellard.org/quickjs/quickjs.html
- QuickJS-NG releases: https://github.com/quickjs-ng/quickjs/releases
- WASI specification: https://github.com/WebAssembly/WASI
- Wasmtime Python bindings: https://github.com/bytecodealliance/wasmtime-py

## Future Enhancements

1. **Module Support**: Investigate alternative QuickJS builds or module loaders that support ES6 imports for builtin modules.

2. **Custom Serialization**: Implement custom serializers for `Map`, `Set`, `Date`, and other complex types.

3. **State Compression**: Add optional compression for large state objects to reduce file I/O overhead.

4. **State Encryption**: Add optional encryption for sensitive state data.

5. **State Versioning**: Implement schema versioning for backward compatibility during state format changes.
