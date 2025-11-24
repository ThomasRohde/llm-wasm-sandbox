# PRD: QuickJS-NG WASI JavaScript Runtime for `llm-wasm-sandbox`

The new WASI QuickJS-NG runtime is downloaded and availble in .\bin\qjs-wasi.wasm.

## 1. Overview

The `llm-wasm-sandbox` provides a **production-ready JavaScript runtime** with capabilities comparable to the existing Python runtime:

- ✅ Runs inside Wasmtime as `wasm32-wasi`
- ✅ Has real filesystem access scoped to the sandbox workspace (`/app`)
- ✅ Shares the same execution policy (fuel, memory, stdout limits)
- ✅ Supports persistent, file-backed state across executions in a session
- ✅ Includes vendored pure-JS packages (CSV, JSON utilities, string manipulation)
- ✅ Provides LLM-friendly helper utilities via `sandbox-utils.js`

**Implementation Status**: ✅ **COMPLETE** - All Phase 1-3 features are implemented and tested.

**Runtime**: Official **QuickJS-NG WASI** binary (`qjs-wasi.wasm`) from QuickJS-NG releases.

**Quick Links**:
- 📚 [Full JavaScript Capabilities Reference](docs/JAVASCRIPT_CAPABILITIES.md) - Comprehensive API documentation
- 🚀 [Usage Examples](examples/demo_javascript.py) - Working code samples
- 🧪 [Test Suite](tests/test_javascript_state.py) - Security and functionality tests

---

## 2. Goals & Non-Goals

### 2.1 Goals ✅ ACHIEVED

1. **✅ JS runtime parity with Python for core sandbox semantics**
   - ✅ Same `/app` workspace mounting
   - ✅ Same resource limits (fuel, memory, stdout)
   - ✅ Full file I/O via QuickJS `std` and `os` modules

2. **✅ Minimal operational overhead**
   - ✅ Uses prebuilt, versioned `qjs-wasi.wasm`
   - ✅ No C toolchain or build pipeline required

3. **✅ LLM-friendly UX**
   - ✅ Simple file helpers: `readJson()`, `writeJson()`, `readText()`, etc.
   - ✅ Vendored packages: CSV parsing, JSON utilities, string manipulation
   - ✅ Auto-persisted state via `auto_persist_globals` flag
   - ✅ Comprehensive [API documentation](docs/JAVASCRIPT_CAPABILITIES.md)

4. **✅ Safe by default**
   - ✅ Same security model as Python runtime
   - ✅ No network access
   - ✅ No host filesystem escape
   - ✅ WASI capability-based isolation

### 2.2 Non-goals

- DOM or browser APIs (use server-side patterns)
- Node.js `fs` / `http` modules (use QuickJS `std`/`os` instead)
- Cross-runtime Python↔JS calls (not yet supported)
- npm package ecosystem (use vendored pure-JS packages)

---

## 3. Implementation Status

**Phase 1 – Basic JS WASI runtime**: ✅ **COMPLETE**
- ✅ `qjs-wasi.wasm` integrated via scripted download
- ✅ Wasmtime integration with `/app` preopen
- ✅ JavaScript runtime exposed in public API
- ✅ Documented examples in `examples/demo_javascript.py`

**Phase 2 – Auto-persisted JS state**: ✅ **COMPLETE**
- ✅ `auto_persist_globals` flag implemented
- ✅ File-based state persistence using `std` module
- ✅ Comprehensive test suite in `tests/test_javascript_state.py`
- ✅ State isolation and corruption handling

**Phase 3 – Vendored packages**: ✅ **COMPLETE**
- ✅ `vendor_js/` directory with curated packages
- ✅ Mounted as read-only `/data_js` in WASI
- ✅ `requireVendor()` helper function
- ✅ Initial package set:
  - `csv-simple.js` - CSV parsing/stringification
  - `json-utils.js` - JSON path access and validation
  - `string-utils.js` - String manipulation helpers
  - `sandbox-utils.js` - File I/O helpers (auto-injected)

**Documentation**: ✅ **COMPLETE**
- ✅ [JAVASCRIPT_CAPABILITIES.md](docs/JAVASCRIPT_CAPABILITIES.md) - Comprehensive API reference (800+ lines)
- ✅ [JAVASCRIPT.md](JAVASCRIPT.md) - Runtime design and architecture
- ✅ [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) - MCP server integration
- ✅ Working examples in `examples/`

---

## 4. Quick Start

### Basic Usage

```python
from sandbox import create_sandbox, RuntimeType

# Create JavaScript sandbox
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

# Execute code
result = sandbox.execute("""
console.log('Hello from JavaScript!');

// File I/O with QuickJS std module
const f = std.open('/app/data.txt', 'w');
f.puts('Sample data');
f.close();

// Read it back
const f2 = std.open('/app/data.txt', 'r');
const content = f2.readAsString();
f2.close();

console.log('Read:', content);
""")

print(result.stdout)
```

### Using Helper Utilities

```python
sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

result = sandbox.execute("""
// Helper functions are automatically available
writeJson('/app/config.json', {
    mode: 'production',
    debug: false
});

const config = readJson('/app/config.json');
console.log('Mode:', config.mode);

// String utilities
const str = requireVendor('string-utils');
console.log(str.slugify('Hello World!'));  // 'hello-world'
""")
```

### State Persistence

```python
# Enable state persistence
sandbox = create_sandbox(
    runtime=RuntimeType.JAVASCRIPT,
    auto_persist_globals=True
)

# First execution
result1 = sandbox.execute("""
_state.counter = (_state.counter || 0) + 1;
console.log('Counter:', _state.counter);
""")
# Output: Counter: 1

# Second execution (same session)
result2 = sandbox.execute("""
_state.counter = (_state.counter || 0) + 1;
console.log('Counter:', _state.counter);
""")
# Output: Counter: 2
```

For comprehensive API documentation, see [**JAVASCRIPT_CAPABILITIES.md**](docs/JAVASCRIPT_CAPABILITIES.md).

---

## 5. Original Design Documentation

The sections below contain the original PRD and design decisions. **For current API documentation and usage, see [JAVASCRIPT_CAPABILITIES.md](docs/JAVASCRIPT_CAPABILITIES.md).**

### 3. Current State (Pre-Implementation)

- **Python runtime**
  - Uses a WASI-enabled `python.wasm` under Wasmtime.
  - Exposes `/app` as a per-session workspace.
  - Optionally supports automatic persistence of Python globals to files in `/app`.
  - Shares a common `ExecutionPolicy` (fuel, memory, stdout constraints).

- **JavaScript runtime**
  - Based on QuickJS (or QuickJS-NG) without a reliable WASI FS story.
  - No stable file I/O story that maps cleanly to `/app`.
  - No `auto_persist_globals` equivalent.

This asymmetry makes Python the “only” serious runtime for stateful agent workflows.

---

## 4. Proposed Design

### 4.1 Runtime Artifact (Decision)

**Runtime:**  
Use the **official QuickJS-NG WASI binary** from QuickJS-NG releases:

- Artifact name: `qjs-wasi.wasm` (WASI-enabled QuickJS-NG)
- Example pinned URL:

  ```text
  https://github.com/quickjs-ng/quickjs/releases/download/v0.11.0/qjs-wasi.wasm
````

**Integration:**

* Download as part of setup/CI and store in repo as:

  ```text
  runtimes/
    javascript/
      qjs-wasi.wasm
  ```

**Constraints:**

* We treat `qjs-wasi.wasm` as an opaque runtime:

  * No rebuilding.
  * No patching.
* Upgrades = replace the binary with a newer release and re-run tests.

---

### 4.2 Host Integration (Wasmtime)

For each JavaScript execution:

1. **Locate the runtime**

   * Load `runtimes/javascript/qjs-wasi.wasm` (configurable via env/setting if needed).

2. **Create Wasmtime `Engine` and `Store`**

   * Use the same engine configuration as Python (fuel enabled).
   * For each execution:

     * Create a new `Store`.
     * Add fuel according to `ExecutionPolicy`.

3. **Configure WASI**

   * Construct a `WasiConfig` per execution:

     * `argv`:

       * Either:

         * Pass `-e "<script>"` if we inject code via inline eval, **or**
         * Pass `-m /app/script.js` and write the user/prologue/epilogue bundle into `/app/script.js`.
     * `env`:

       * Minimal environment, optionally include `SANDBOX_RUNTIME=javascript` for diagnostics.
     * `preopen_dir(session_workspace, "/app")`:

       * Mount the per-session host directory as `/app`.
     * `stdout` / `stderr`:

       * Pipe to in-memory buffers that are capped by `ExecutionPolicy` (same as Python).

4. **Instantiate and run**

   * Instantiate `qjs-wasi.wasm` with the configured store and WASI.
   * Invoke its entrypoint (QuickJS main) with the configured argv.
   * Capture:

     * Exit status.
     * Stdout/stderr.
     * Any Wasmtime errors (out-of-fuel, traps, etc.).

5. **Map result into the sandbox API**

   * `stdout` → `ExecutionResult.stdout`.
   * `stderr` → `ExecutionResult.stderr`.
   * Exit code → success/failure.
   * Resource limit breaches → standardized error (`ResourceLimitExceeded`).

---

### 4.3 Execution Model for JavaScript

We standardize on a “wrapped script” model:

1. **Prologue** (optional)

   * Injected by the host before user code.
   * Responsibilities:

     * Import QuickJS `std` module.
     * Optionally restore persisted JS state (if enabled).
     * Optionally define helper functions (e.g. `readJson`, `writeJson`).

2. **User code**

   * Comes from the LLM / user input.
   * Treated as plain JavaScript (ES2020-ish).

3. **Epilogue** (optional)

   * Injected by the host after user code.
   * Responsibilities:

     * Optionally capture and serialize selected globals for persistence.
     * Write state to `/app/.globals_js.json` (if enabled).

The host either:

* Writes the whole combined script (prologue + user code + epilogue) to `/app/script.js` and runs:

  ```sh
  qjs-wasi.wasm -m /app/script.js
  ```

* Or passes it via `-e` in argv (implementation choice; PRD doesn’t mandate).

---

### 4.4 Filesystem Semantics (`/app`)

**FR-JS-FS-1 – Shared `/app` workspace**

* For each session:

  * The host creates a workspace directory (e.g. `workspaces/{session_id}/app`).
  * JavaScript and Python **share** this directory:

    * Python sees it as `/app`.
    * JavaScript sees it as `/app`.

**FR-JS-FS-2 – JS file I/O**

* JavaScript accesses files in `/app` via QuickJS NG’s `std` module, e.g.:

  ```js
  import * as std from "std";

  const f = std.open("/app/data.json", "w+");
  f.puts(JSON.stringify({ counter: 1 }));
  f.close();

  const f2 = std.open("/app/data.json", "r");
  const txt = f2.readAsString();
  f2.close();
  ```

* This must:

  * Work when run directly under Wasmtime (sanity check).
  * Behave identically when invoked through the sandbox host APIs.

**FR-JS-FS-3 – JSON convenience helpers**

* The JS prologue may inject simple helpers for agents:

  ```js
  globalThis.readJson = function readJson(path) {
    const f = std.open(path, "r");
    if (!f) throw new Error(`Cannot open file for reading: ${path}`);
    const txt = f.readAsString();
    f.close();
    return JSON.parse(txt);
  };

  globalThis.writeJson = function writeJson(path, value) {
    const f = std.open(path, "w+");
    if (!f) throw new Error(`Cannot open file for writing: ${path}`);
    f.puts(JSON.stringify(value));
    f.close();
  };
  ```

* These helpers mirror the Python pattern (`json.load`, `json.dump`) to make prompt recipes symmetric between runtimes.

---

### 4.5 Optional: `auto_persist_globals` for JS

This is **Phase 2**, but included for completeness.

**Requirement:**

* A flag on sandbox creation:

  ```python
  create_sandbox(
      runtime=RuntimeType.JAVASCRIPT,
      auto_persist_globals=True,
  )
  ```

**Behaviour (high level):**

1. Before each execution:

   * Host reads `/app/.globals_js.json` (if present).
   * Injects the parsed JSON object into the JS prologue.
   * Prologue walks the object and assigns keys to `globalThis`.

2. After each execution:

   * Epilogue scans `globalThis` for:

     * Non-private keys (no leading `_`).
     * Values that are JSON-serializable (primitive, arrays, plain objects).
   * Writes them back as JSON into `/app/.globals_js.json`.

**Deliberate limitations:**

* Functions, class instances, and non-JSON types are not persisted.
* State failures (e.g. JSON parse error) should not crash the sandbox:

  * Log to stderr.
  * Continue executing user code.

---

### 4.6 Optional: `vendor_js` (Phase 3)

To mirror Python’s vendored pure-Python packages:

1. **Directory layout**

   ```text
   vendor_js/
     csv.js
     xlsx-lite.js
     string_utils.js
   ```

2. **Mount as `/vendor_js` in WASI**

   * Host preopens `vendor_js/` as `/vendor_js`.

3. **Prologue helper**

   ```js
   import * as std from "std";

   globalThis.requireVendor = function requireVendor(name) {
     const path = `/vendor_js/${name}.js`;
     const f = std.open(path, "r");
     if (!f) throw new Error(`Vendor module not found: ${path}`);
     const src = f.readAsString();
     f.close();

     const module = { exports: {} };
     const func = new Function("module", "exports", src);
     func(module, module.exports);
     return module.exports;
   };
   ```

4. **Usage for agents**

   ```js
   const csv = requireVendor("csv");
   ```

Vendor JS must be:

* Pure JS.
* No network dependencies.
* Reasonably small and auditable.

---

## 5. API & Configuration Changes

### 5.1 Runtime registration

* Add `RuntimeType.JAVASCRIPT` (if not already present).
* Map it to:

  ```python
  runtime_config["javascript"] = {
      "wasm_path": "runtimes/javascript/qjs-wasi.wasm",
      "kind": "wasi",
      # future: feature flags like "supports_auto_persist": True
  }
  ```

### 5.2 Sandbox construction

* Extend the sandbox factory to accept:

  * `runtime=RuntimeType.JAVASCRIPT`
  * `auto_persist_globals` (applies to both Python and JS; semantics per runtime).

### 5.3 CI / Setup

* Add a small script (e.g. `scripts/fetch_js_runtime.py` or shell equivalent) that:

  * Downloads `qjs-wasi.wasm` from a specific QuickJS-NG tag.
  * Validates checksum (optional).
  * Places it under `runtimes/javascript/`.

* CI should:

  * Ensure `qjs-wasi.wasm` exists.
  * Run a minimal smoke test (see next section).

---

## 6. Testing & Validation

### 6.1 Unit / Integration tests

1. **Smoke: hello world**

   * Run a JS snippet that prints “hello” to stdout.
   * Assert exit code = 0 and output contains “hello”.

2. **Filesystem round-trip**

   * JS code writes `/app/test.txt`, then reads it back and prints the content.

3. **Cross-runtime file visibility**

   * Python writes `/app/data.json`.
   * JS reads it and asserts contents.
   * JS modifies `/app/data.json`.
   * Python reads and asserts changes.

4. **Resource limits**

   * JS infinite loop → out-of-fuel error.
   * Giant stdout write → truncated at configured max and flagged.

5. **(Phase 2) `auto_persist_globals`**

   * Run JS script that sets `counter = 1` with `auto_persist_globals=True`.
   * Next run increments `counter` and prints it.
   * Assert `counter` persists across multiple executions in the same session.

---

## 7. Risks & Mitigations

* **Risk:** QuickJS-NG changes WASI behaviour or breaks compatibility.

  * *Mitigation:* Pin to a specific tag. Only bump with explicit testing.

* **Risk:** LLMs confuse QuickJS + Node APIs.

  * *Mitigation:* Clear docs and examples:

    * “Use `import * as std from "std"` and `std.open`.”
    * Provide helper functions (`readJson`, `writeJson`).

* **Risk:** Persisted JS global state grows unbounded.

  * *Mitigation:* Limit persisted keys and size:

    * Ignore large objects / arrays above a threshold.
    * Optionally track approximate size and emit warnings.

---

## 8. Phases & Deliverables

### Phase 1 – Basic JS WASI runtime ✅ COMPLETE

* [x] Add `qjs-wasi.wasm` to repo via scripted download
* [x] Integrate with Wasmtime using `/app` preopen
* [x] Expose JavaScript runtime in the public API
* [x] Provide documented examples:
  * `examples/demo_javascript.py`
  * `examples/demo_javascript_session.py`

### Phase 2 – Auto-persisted JS state ✅ COMPLETE

* [x] Implement `auto_persist_globals` for JS
* [x] Add tests mirroring Python's behaviour
* [x] Document limitations (JSON-only types, etc.)
* [x] File-based state persistence using QuickJS `std` module

### Phase 3 – `vendor_js` ✅ COMPLETE

* [x] Add `vendor_js/` tree and mount as `/data_js`
* [x] Implement `requireVendor()` helper function
* [x] Ship curated library set:
  * `csv-simple.js` - CSV parsing and stringification
  * `json-utils.js` - JSON path access and validation
  * `string-utils.js` - String manipulation helpers
  * `sandbox-utils.js` - File I/O helpers

**All phases complete!** See [JAVASCRIPT_CAPABILITIES.md](docs/JAVASCRIPT_CAPABILITIES.md) for full API reference.
* [ ] Implement `requireVendor()`.
* [ ] Ship a small curated library set.

---

## 9. Questions & Decisions

**Q: Do we want a single `auto_persist_globals` flag for all runtimes, or per-runtime config?**
**A:** ✅ Single flag - Implemented consistently across Python and JavaScript runtimes

**Q: Do we need a "JS standard library" beyond QuickJS `std`?**
**A:** ✅ MINIMAL - Shipped curated vendored packages for common needs (CSV, JSON utils, strings)

**Q: How strict should we be on persisted state size?**
**A:** ✅ SOFT WARNING - No hard caps implemented; relies on JSON serialization limits

---

## 10. See Also

- **[JAVASCRIPT_CAPABILITIES.md](docs/JAVASCRIPT_CAPABILITIES.md)** - Complete API reference (800+ lines)
- [README.md](README.md) - Main project documentation
- [MCP_INTEGRATION.md](docs/MCP_INTEGRATION.md) - Model Context Protocol integration
- [PYTHON_CAPABILITIES.md](docs/PYTHON_CAPABILITIES.md) - Python runtime capabilities
- [examples/demo_javascript.py](examples/demo_javascript.py) - Comprehensive usage examples
