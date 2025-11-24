# JavaScript Runtime Augmentation PRD

**Status**: Draft Proposal  
**Target**: Make JavaScript runtime feature-complete with Python implementation  
**Primary Goal**: Enable auto_persist_globals and provide std-like APIs without QuickJS recompilation  
**Author**: Development Team  
**Date**: 2025-11-24

---

## Executive Summary

This document proposes a **host-managed augmentation layer** for the JavaScript runtime that brings it to feature parity with the Python sandbox while maintaining security boundaries. The core insight is treating JavaScript execution as a **pure function** `next_state = f(code, prev_state)` where the Python host owns all persistence, rather than exposing WASI filesystem APIs to untrusted JavaScript code.

### Key Benefits
- ✅ **Zero QuickJS recompilation** - works with existing qjs-wasi.wasm binary
- ✅ **Stronger security** - no raw filesystem access from untrusted JS
- ✅ **Language-agnostic persistence** - same `.session_state.json` format as Python
- ✅ **std-like API** - familiar developer experience via globalThis extensions
- ✅ **Extensible architecture** - easy to add new host-backed capabilities

---

## Problem Statement

### Current Limitations

1. **No auto_persist_globals**: JavaScript sessions lose state between executions
   - Python: Globals automatically serialized to `.session_state.json`
   - JavaScript: All state lost after each `execute()` call

2. **Missing std module APIs**: QuickJS-WASI doesn't expose file I/O to JavaScript
   - `std.open()`, `std.loadFile()`, `os.open()` not available
   - WASI filesystem syscalls exist but aren't bound to JS APIs
   - Requires C-level glue code in QuickJS build

3. **Inconsistent developer experience**: Python and JavaScript runtimes have different capabilities
   - LLM agents must learn different patterns per runtime
   - Python workflows (data pipelines, multi-turn analysis) don't translate to JS

### Root Cause Analysis

The QuickJS-NG WASI build (`qjs-wasi.wasm`) is a **minimal runtime**:
- Includes WASM linear memory safety ✅
- Has WASI syscall stubs for stdio/preopens ✅
- Does **NOT** expose WASI file descriptors as `std.*` JavaScript APIs ❌

To get `std.open()`, you'd need to:
1. Fork QuickJS-NG and modify `quickjs-libc.c` to bind WASI FDs
2. Rebuild with `wasi-sdk` toolchain
3. Maintain custom binary (security patches, upgrades)

**This violates our security model**: Giving untrusted LLM-generated JavaScript direct filesystem access (even within preopens) creates unnecessary attack surface.

---

## Proposed Solution: Three-Layer Architecture

### Layer 1: Host-Managed State Persistence (MVP)

**Pattern**: Stdout-based state serialization  
**Implementation Time**: 4-6 hours  
**Security Impact**: Zero new capabilities

```
┌─────────────────────────────────────────────────────────────┐
│ Python Host (sandbox/runtimes/javascript/sandbox.py)       │
├─────────────────────────────────────────────────────────────┤
│ 1. Load prev_state from .session_state.json                │
│ 2. Wrap user code: PRELUDE + user_code + EPILOGUE          │
│ 3. Execute wrapped code in QuickJS-WASI                    │
│ 4. Parse stdout for /*__SANDBOX_STATE_BEGIN__*/ markers    │
│ 5. Save extracted state to .session_state.json             │
│ 6. Strip markers from stdout before returning to caller    │
└─────────────────────────────────────────────────────────────┘
                              ▼
                   ┌──────────────────────┐
                   │  QuickJS-WASI        │
                   │  (pure computation)  │
                   │                      │
                   │  globalThis.counter  │
                   │  globalThis.config   │
                   │  console.log()       │
                   └──────────────────────┘
```

#### Implementation Details

**1. Code Wrapping (`_wrap_with_state_prelude_and_epilogue`)**

```python
def _wrap_with_state_prelude_and_epilogue(
    self, 
    code: str, 
    prev_state: dict[str, Any]
) -> str:
    """Inject state restore/persist logic around user code."""
    
    # Safely embed previous state as JSON literal
    state_json_str = json.dumps(prev_state)
    state_json_literal = json.dumps(state_json_str)  # Double-encode for JS string
    
    prelude = f'''
// === SANDBOX STATE PRELUDE (auto-generated) ===
(function() {{
  const __SANDBOX_STATE_JSON = {state_json_literal};
  const __SANDBOX_BLACKLIST = new Set([
    "globalThis", "console", "Object", "Array", "JSON", 
    "Math", "Date", "Error", "Promise",
    "__SANDBOX_STATE_JSON", "__restoreState", 
    "__collectState", "__persistState"
  ]);

  function __restoreState() {{
    if (!__SANDBOX_STATE_JSON) return;
    try {{
      const obj = JSON.parse(__SANDBOX_STATE_JSON);
      if (obj && typeof obj === "object") {{
        for (const [k, v] of Object.entries(obj)) {{
          if (__SANDBOX_BLACKLIST.has(k)) continue;
          globalThis[k] = v;
        }}
      }}
    }} catch (e) {{
      // Ignore corrupt state; don't kill execution
    }}
  }}

  function __collectState() {{
    const state = {{}};
    for (const name of Object.getOwnPropertyNames(globalThis)) {{
      if (__SANDBOX_BLACKLIST.has(name)) continue;
      if (name.startsWith("__SANDBOX_")) continue;
      
      const value = globalThis[name];
      if (value === undefined) continue;
      if (typeof value === "function") continue;
      
      // Only persist JSON-safe values
      try {{
        JSON.stringify(value);
        state[name] = value;
      }} catch {{
        continue;  // Skip non-serializable (circular refs, etc.)
      }}
    }}
    return state;
  }}

  function __persistState() {{
    const state = __collectState();
    console.log("/*__SANDBOX_STATE_BEGIN__*/");
    console.log(JSON.stringify(state));
    console.log("/*__SANDBOX_STATE_END__*/");
  }}

  __restoreState();

// === USER CODE STARTS HERE ===
'''
    
    epilogue = '''
// === USER CODE ENDS HERE ===

  __persistState();
}})();
'''
    
    if self.auto_persist_globals:
        return prelude + code + epilogue
    else:
        # No-op wrapper for non-persistent sessions
        return f'(function() {{\n{code}\n}})();'
```

**2. State Extraction (`_extract_state_from_stdout`)**

```python
def _extract_state_from_stdout(self, stdout: str) -> dict[str, Any] | None:
    """Parse state JSON from stdout markers."""
    begin = "/*__SANDBOX_STATE_BEGIN__*/"
    end = "/*__SANDBOX_STATE_END__*/"
    
    lines = stdout.splitlines()
    start_idx = None
    end_idx = None
    
    for i, line in enumerate(lines):
        if begin in line:
            start_idx = i
        elif end in line and start_idx is not None:
            end_idx = i
            break
    
    if start_idx is None or end_idx is None:
        return None
    
    # State JSON is on line after BEGIN marker
    if end_idx > start_idx + 1:
        json_line = lines[start_idx + 1]
        try:
            return json.loads(json_line)
        except json.JSONDecodeError:
            return None
    
    return None

def _strip_state_markers(self, stdout: str) -> str:
    """Remove internal state markers from user-visible output."""
    lines = stdout.splitlines()
    cleaned = []
    inside_marker = False
    
    for line in lines:
        if "/*__SANDBOX_STATE_BEGIN__*/" in line:
            inside_marker = True
        elif "/*__SANDBOX_STATE_END__*/" in line:
            inside_marker = False
            continue
        elif not inside_marker:
            cleaned.append(line)
    
    return "\n".join(cleaned)
```

**3. Integration with Existing Execute Flow**

```python
def execute(self, code: str, **kwargs: Any) -> SandboxResult:
    """Execute JavaScript with automatic state persistence."""
    
    # Load previous state if auto_persist enabled
    prev_state = {}
    if self.auto_persist_globals:
        state_file = self.workspace / ".session_state.json"
        if state_file.exists():
            try:
                prev_state = json.loads(state_file.read_text())
            except Exception:
                prev_state = {}
    
    # Wrap code with state prelude/epilogue
    wrapped_code = self._wrap_with_state_prelude_and_epilogue(code, prev_state)
    
    # ... existing execution logic (write to workspace, run WASM, etc.)
    raw_result = run_untrusted_javascript(...)
    
    # Extract and save new state
    if self.auto_persist_globals:
        new_state = self._extract_state_from_stdout(raw_result.stdout)
        if new_state is not None:
            state_file.write_text(json.dumps(new_state, indent=2))
    
    # Clean stdout for user
    clean_stdout = self._strip_state_markers(raw_result.stdout)
    
    # Return result with cleaned output
    return SandboxResult(
        stdout=clean_stdout,
        stderr=raw_result.stderr,
        # ... rest of fields
    )
```

#### Security Properties

1. **No new WASM capabilities**: JavaScript still cannot access filesystem directly
2. **JSON-only serialization**: Functions, class instances, circular refs automatically filtered
3. **Size limits**: Can enforce `max_state_bytes` policy (e.g., 1 MB limit)
4. **Name allowlist/denylist**: Can restrict which globals persist (e.g., block `__proto__`)
5. **Identical to Python model**: Same `.session_state.json` format, same security guarantees

---

### Layer 2: std-like API Polyfills (Phase 2)

**Pattern**: GlobalThis injection with host-backed helpers  
**Implementation Time**: 8-12 hours  
**Security Impact**: Controlled, validated file I/O

Once Layer 1 is working, add a **polyfill module** that provides `std.*` APIs backed by Python host:

```javascript
// Injected before user code runs
globalThis.std = {
  // Read-only file access (validates path is in /app)
  loadFile(path) {
    // Via special console.log marker parsed by host
    console.log(`/*__HOST_LOADFILE__*/${path}/*__END__*/`);
    // Host replaces next line of stdout with file contents
    return __HOST_FILE_CONTENT__;  // Injected by host in next execution
  },
  
  // Directory listing
  readdir(path) {
    // Similar marker pattern
  },
  
  // Environment variable access (already supported via policy.env)
  getenv(key) {
    return globalThis.__SANDBOX_ENV__[key] || null;
  }
};

globalThis.os = {
  // Platform info
  platform: "wasi",
  
  // Limited to /app workspace
  getcwd() {
    return "/app";
  }
};
```

**Alternative: Direct WASI bindings** (if you want zero-latency file I/O):
- Use Wasmtime's `Linker.define_func()` to add `env.host_read_file(path_ptr, path_len)`
- Rebuild QuickJS-NG to import this function
- Wrap in JavaScript shim

---

### Layer 3: Advanced Host Functions (Future)

**Pattern**: Wasmtime Linker custom imports  
**Implementation Time**: 2-4 weeks (requires QuickJS rebuild)  
**Security Impact**: Full capability control at host level

For production-grade features requiring tight integration:

```c
// In custom QuickJS-NG build (quickjs-host-api.c)
__attribute__((import_module("env"), import_name("host_read_file")))
extern int host_read_file(const char *path, int len, char *buf, int bufsize);

// Exposed to JavaScript as:
std.readFile = function(path) {
  const buf = new ArrayBuffer(1024 * 1024);  // 1 MB max
  const len = __wasm_host_read_file(path, path.length, buf, buf.byteLength);
  return new TextDecoder().decode(new Uint8Array(buf, 0, len));
};
```

**Python host implementation**:
```python
def _define_js_host_functions(linker: Linker, workspace_path: Path):
    """Add custom WASM imports for JavaScript runtime."""
    
    def host_read_file(
        caller: Caller, 
        path_ptr: int, 
        path_len: int,
        buf_ptr: int,
        buf_size: int
    ) -> int:
        """Read file from workspace and write to WASM memory."""
        memory = caller["memory"]
        
        # Extract path from WASM linear memory
        path_bytes = memory.read(caller, path_ptr, path_len)
        path = path_bytes.decode('utf-8')
        
        # Validate path is within workspace
        full_path = (workspace_path / path.lstrip('/')).resolve()
        if not full_path.is_relative_to(workspace_path):
            return -1  # EPERM
        
        # Read file
        try:
            content = full_path.read_bytes()
            if len(content) > buf_size:
                return -2  # EFBIG
            
            # Write to WASM memory at buf_ptr
            memory.write(caller, buf_ptr, content)
            return len(content)
        except FileNotFoundError:
            return -3  # ENOENT
        except Exception:
            return -4  # EIO
    
    # Register with Wasmtime linker
    from wasmtime import FuncType, ValType
    
    linker.define_func(
        "env", 
        "host_read_file",
        FuncType(
            [ValType.i32(), ValType.i32(), ValType.i32(), ValType.i32()],
            [ValType.i32()]
        ),
        host_read_file
    )
```

---

## Implementation Roadmap

### Phase 1: MVP State Persistence (Target: 1 week)

**Deliverables**:
- [ ] `_wrap_with_state_prelude_and_epilogue()` method
- [ ] `_extract_state_from_stdout()` method
- [ ] `_strip_state_markers()` method
- [ ] Update `JavaScriptSandbox.execute()` to use wrapping
- [ ] Tests: `test_javascript_auto_persist_*.py` unskipped and passing
- [ ] Documentation: Update README.md with JS auto_persist example

**Success Criteria**:
```python
# This should work identically to Python version
sandbox = create_sandbox(
    runtime=RuntimeType.JAVASCRIPT,
    auto_persist_globals=True
)

# Turn 1
result1 = sandbox.execute('let counter = 0; counter++;')

# Turn 2 (same session)
result2 = sandbox.execute('counter++; console.log(counter);')
assert result2.stdout.strip() == '2'  # State persisted!
```

**Risks**:
- Stdout parsing brittleness → Mitigated by unique markers
- JSON serialization edge cases → Comprehensive test suite
- Performance overhead → Negligible (JSON ops are ~1ms)

---

### Phase 2: std Polyfill Library (Target: 2-3 weeks)

**Deliverables**:
- [ ] `sandbox/polyfills/quickjs_std.js` module
- [ ] Host-side marker parsing for `loadFile`, `readdir`
- [ ] Environment variable injection (`__SANDBOX_ENV__`)
- [ ] Tests: File I/O, directory listing, env access
- [ ] Documentation: `docs/JAVASCRIPT_STD_API.md`

**APIs to implement**:
```javascript
// File I/O (read-only)
std.loadFile(path)           // Returns string or null
std.loadBinaryFile(path)     // Returns Uint8Array or null
std.readdir(path)            // Returns array of filenames

// Environment
std.getenv(key)              // Returns string or null
std.setenv(key, val)         // Updates session env (policy-gated)

// Utilities
std.parseJSON(str)           // Wrapper for JSON.parse with error handling
std.formatJSON(obj, indent)  // Wrapper for JSON.stringify

// OS info
os.platform                  // "wasi"
os.getcwd()                  // "/app"
```

**Implementation note**: For Phase 2, use stdout markers for simplicity. Phase 3 can optimize with direct WASM imports if needed.

---

### Phase 3: Native Host Functions (Target: 4-6 weeks)

**Deliverables**:
- [ ] Custom QuickJS-NG build with `quickjs-host-api.c`
- [ ] Wasmtime `Linker.define_func()` implementations in `host.py`
- [ ] Build scripts for reproducible WASI compilation
- [ ] Performance benchmarks (should be 10-100x faster than stdout markers)
- [ ] Security audit of WASM import surface

**Decision point**: Only proceed if:
1. Phase 2 stdout-based approach proves too slow (>10ms overhead)
2. Need binary data transfer (images, PDFs) without base64 bloat
3. Want to support 3rd-party QuickJS modules requiring `std`

---

## Success Metrics

### Functional Parity
- [x] Python: auto_persist_globals works
- [ ] JavaScript: auto_persist_globals works (Phase 1)
- [ ] Both runtimes share `.session_state.json` format
- [ ] LLM agents can use same prompts for Python/JavaScript

### Performance
- Target: <5ms overhead for state serialization (Phase 1)
- Target: <2ms for file I/O via markers (Phase 2)
- Target: <0.5ms for native WASM imports (Phase 3)

### Security
- Zero new WASM capabilities in Phase 1
- Controlled file I/O in Phase 2 (read-only, workspace-scoped)
- Audited import surface in Phase 3

### Developer Experience
- Auto-persist "just works" with `auto_persist_globals=True`
- Error messages guide users when state fails to persist
- Examples cover common patterns (counters, configs, data pipelines)

---

## Alternative Approaches Considered

### 1. Switch to WasmEdge-QuickJS
**Pros**: Already has `fs` module bindings  
**Cons**: Different binary, different security model, community fragmentation  
**Decision**: Rejected - prefer controlling our own stack

### 2. Embed state in WASI environment variables
**Pros**: No stdout parsing  
**Cons**: 32 KB env limit, not designed for structured data  
**Decision**: Rejected - stdout is cleaner for large state

### 3. Use WASI sockets for state channel
**Pros**: Binary-safe, no stdout pollution  
**Cons**: Adds network capability (security risk), overkill for local state  
**Decision**: Rejected - maintain zero-network policy

### 4. Stateless sessions only (no persistence)
**Pros**: Simplest implementation  
**Cons**: Breaks LLM multi-turn workflows, feature gap vs Python  
**Decision**: Rejected - persistence is core feature

---

## Open Questions

1. **State size limits**: Should we enforce max JSON size? (Proposed: 10 MB)
2. **State validation**: Should we reject state with unsafe property names (`__proto__`, `constructor`)?
3. **Cross-runtime state**: Should Python and JavaScript sessions share state if `session_id` is the same?
4. **Error handling**: When state extraction fails, fail execution or log warning?
5. **Versioning**: Should state include schema version for future migrations?

---

## References

### Inspiration
- Colleague's insight: "Treat JS as pure function `f(code, state) -> state`"
- QuickJS CLI: Uses C-level `std` module backed by host libc
- WasmEdge-QuickJS: WASI FS bindings via custom build
- [QuickJS stdlib documentation](https://quickjs-ng.github.io/quickjs/stdlib)

### Related Issues
- [QuickJS-NG #43: Add support of `fs` and `env`](https://github.com/second-state/wasmedge-quickjs/issues/43)
- [WasmEdge: Running JavaScript in WebAssembly](https://www.secondstate.io/articles/run-javascript-in-webassembly-with-wasmedge/)

### Internal Docs
- `WASM_SANDBOX.md` - Security model and architecture
- `MCP_INTEGRATION.md` - Multi-runtime session management
- `tests/test_javascript_auto_persist.py` - Target test cases

---

## Appendix A: Example Usage

### Before (Current State)
```python
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

# Turn 1
result1 = sandbox.execute('''
let config = {theme: 'dark', retries: 3};
console.log(config.theme);
''')
# Output: "dark"

# Turn 2 - config is LOST
result2 = sandbox.execute('''
console.log(typeof config);  // "undefined" - lost!
''')
```

### After (Phase 1)
```python
sandbox = create_sandbox(
    runtime=RuntimeType.JAVASCRIPT,
    auto_persist_globals=True
)

# Turn 1
result1 = sandbox.execute('''
let config = {theme: 'dark', retries: 3};
console.log(config.theme);
''')
# Output: "dark"
# State saved: {"config": {"theme": "dark", "retries": 3}}

# Turn 2 - config PERSISTS
result2 = sandbox.execute('''
config.retries++;  // Modify existing state
console.log(`Retries: ${config.retries}`);
''')
# Output: "Retries: 4"
# State saved: {"config": {"theme": "dark", "retries": 4}}
```

### After (Phase 2 - std polyfill)
```python
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

result = sandbox.execute('''
// Read data file from workspace
const data = std.loadFile('input.json');
const parsed = JSON.parse(data);

// Process data
const summary = {
  count: parsed.items.length,
  total: parsed.items.reduce((sum, x) => sum + x.value, 0)
};

console.log(std.formatJSON(summary, 2));
''')
# Works just like QuickJS CLI!
```

---

## Appendix B: Performance Analysis

### State Serialization Overhead (Phase 1)

**Benchmark scenario**: 100 global variables, 10 KB JSON state

| Operation | Time | Notes |
|-----------|------|-------|
| `JSON.stringify(state)` | ~0.5ms | In QuickJS |
| `console.log()` output | ~0.1ms | WASI stdio |
| Python `json.loads()` | ~0.3ms | Parse extracted state |
| File write | ~1ms | SSD write |
| **Total overhead** | **~2ms** | Negligible vs execution time |

**Conclusion**: Stdout-based approach is production-ready for state <1 MB.

### File I/O via Markers (Phase 2)

**Benchmark scenario**: Read 10 KB file 100 times

| Approach | Time per read | Notes |
|----------|---------------|-------|
| Stdout markers | ~5ms | Parse + reinject |
| Direct WASM import (Phase 3) | ~0.2ms | 25x faster |

**Conclusion**: Markers acceptable for <100 file reads. Optimize with Phase 3 if needed.

---

**END OF PRD**
