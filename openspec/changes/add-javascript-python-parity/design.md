# Design: JavaScript-Python Feature Parity

## Context

The llm-wasm-sandbox project currently supports two WASM runtimes: Python (CPython 3.11+) and JavaScript (QuickJS-NG). However, the runtimes have asymmetric capabilities:

**Python advantages:**
- Full `auto_persist_globals` support via `sandbox.state` module
- 30+ vendored pure-Python packages mounted at `/data/site-packages`
- `sandbox_utils` library with shell-like APIs for LLM code
- Automatic sys.path injection for vendored packages
- Comprehensive 1260-line capability documentation

**JavaScript limitations:**
- `auto_persist_globals` is a non-functional placeholder
- Zero vendored packages
- No helper utilities
- No automatic code injection
- Minimal documentation (PRD-style only)

This asymmetry makes Python the only viable choice for LLM agent workflows requiring state persistence or rich library support.

**Constraints:**
- QuickJS-NG WASI binary is prebuilt (cannot modify runtime)
- QuickJS `std` module **does** support file I/O (`std.open()`, `FILE` APIs) - integration just needs to use it
- Vendored packages must be pure JavaScript (no Node.js APIs)
- Implementation must maintain security model (WASI isolation)

**Stakeholders:**
- LLM agent developers (need feature parity for runtime choice)
- MCP server users (expect consistent capabilities)
- Sandbox maintainers (want symmetric codebase)

## Goals / Non-Goals

### Goals

1. **Working state persistence**: Implement functional `auto_persist_globals` for JavaScript using file-backed JSON storage via QuickJS `std.open()`

2. **Vendored package ecosystem**: Curate 5-10 essential pure-JS packages for common LLM agent tasks (CSV, JSON utilities, string manipulation)

3. **Helper library parity**: Create `sandbox_utils.js` matching Python's `sandbox_utils` API surface (readJson, writeJson, listFiles)

4. **Automatic setup injection**: Mirror Python's automatic sys.path injection with JavaScript prologue (std import, requireVendor helper)

5. **Documentation parity**: Write comprehensive `JAVASCRIPT_CAPABILITIES.md` (800+ lines) matching Python's documentation depth

### Non-Goals

1. **DOM/Browser APIs**: Not implementing browser-specific features (no DOM, fetch, localStorage)

2. **Node.js compatibility**: Not replicating Node.js modules (fs, http, child_process)

3. **npm integration**: Not building a package manager; vendored packages are manually curated

4. **AST-based validation**: Not adding JavaScript parser for pre-execution syntax checking (deferred to runtime)

5. **Cross-runtime interop**: Not enabling Python↔JavaScript calls within same execution (Wasm Component Model out of scope)

## Decisions

### Decision 1: File-Based State Persistence for JavaScript

**Choice**: Use QuickJS `std.open()` to read/write `.session_state.json` file in prologue/epilogue code.

**Alternatives considered:**

1. **Memory-only state** (no persistence)
   - ❌ Doesn't solve the parity problem
   - ❌ Useless for multi-turn LLM workflows

2. **Host-side state management** (Python injects state before execution)
   - ❌ Requires serialization/deserialization on every call
   - ❌ Breaks symmetry with Python's approach
   - ❌ More complex host integration

3. **Custom WASI bindings** (extend QuickJS with native state API)
   - ❌ Violates "prebuilt binary only" constraint
   - ❌ Maintenance burden for custom build pipeline

**Rationale**: QuickJS-NG WASI provides robust file I/O via `std.open()`, `std.loadFile()`, and `FILE` object methods (read, write, seek, close). The runtime includes the full QuickJS `std` and `os` modules from `quickjs-libc.c`. Using the same file-based approach as Python (JSON serialization) maintains consistency and leverages these existing capabilities.

**Trade-offs**:
- ✅ Simple, proven pattern (mirrors Python)
- ✅ No custom runtime modifications
- ✅ QuickJS `std` module support confirmed (std.open, FILE APIs available)
- ❌ JSON-only serialization (no functions/classes)
- ⚠️ Requires proper `import * as std from "std";` in JS code

### Decision 2: CommonJS-Style requireVendor() for Package Loading

**Choice**: Inject `globalThis.requireVendor(name)` helper that reads vendor file, executes with `module.exports` scope, and returns exports.

**Alternatives considered:**

1. **ES6 dynamic imports** (`import()`)
   - ❌ QuickJS-NG WASI likely doesn't support dynamic import with custom paths
   - ❌ More complex to inject and test

2. **Global namespace injection** (pre-load all packages into globalThis)
   - ❌ Bloats startup time
   - ❌ Wastes memory for unused packages
   - ❌ Doesn't scale beyond 5-10 packages

3. **Custom module loader** (full AMD/RequireJS implementation)
   - ❌ Over-engineered for 5-10 packages
   - ❌ Adds complexity without clear benefit

**Rationale**: CommonJS pattern is widely understood, simple to implement (~30 lines), and gives fine-grained control over loading. It mirrors Node.js familiarity without requiring Node.js APIs.

**Implementation sketch**:
```javascript
globalThis.requireVendor = function requireVendor(name) {
    const path = `/data_js/vendor/${name}.js`;
    const f = std.open(path, 'r');
    if (!f) throw new Error(`Vendor package not found: ${name}`);
    const src = f.readAsString();
    f.close();
    
    const module = { exports: {} };
    const func = new Function('module', 'exports', src);
    func(module, module.exports);
    return module.exports;
};
```

**Trade-offs**:
- ✅ Simple, ~30 lines
- ✅ Lazy loading (only load what's used)
- ✅ Familiar pattern
- ❌ No caching (loads fresh each time - acceptable for 5-10 packages)
- ❌ No circular dependency handling (not needed for vendored packages)

### Decision 3: Read-Only Mount for vendor_js at /data_js/vendor

**Choice**: Mount `vendor_js/` directory as `/data_js/vendor` with read-only permissions, mirroring Python's `/data/site-packages` pattern.

**Alternatives considered:**

1. **Copy vendor packages to each session workspace**
   - ❌ Wastes disk space (MB per session)
   - ❌ Slower session creation
   - ❌ Inconsistent with Python's optimized approach

2. **Single global vendor mount at /vendor**
   - ✅ Would work technically
   - ❌ Breaks symmetry with Python's `/data` namespace
   - ❌ Less clear separation of concerns

3. **Embed packages in WASM binary**
   - ❌ Violates "prebuilt binary only" constraint
   - ❌ Makes package updates impossible without rebuilding runtime

**Rationale**: Read-only mount is secure (no cross-session pollution), efficient (zero duplication), and consistent with Python's proven pattern.

**Trade-offs**:
- ✅ Zero disk overhead per session
- ✅ Instant session creation
- ✅ Read-only security
- ❌ Requires WASI preopen configuration in host.py
- ❌ Cannot modify vendored packages at runtime (acceptable - they're immutable by design)

### Decision 4: Start with 5-10 Essential Packages, Expand Gradually

**Choice**: Initial vendor_js library includes:
1. CSV parser (papaparse-lite or minimal CSV.js)
2. JSON utilities (schema validation, path access like jsonpath-lite)
3. String utilities (slugify, inflection, truncate)
4. sandbox_utils.js (LLM-friendly file helpers)
5. (Optional) Date manipulation (date-fns core subset)

**Alternatives considered:**

1. **Start with 30+ packages matching Python exactly**
   - ❌ Many Python packages don't have pure-JS equivalents
   - ❌ Too much upfront work
   - ❌ Unclear which JS packages are actually needed

2. **Start with zero packages, add on demand**
   - ❌ Doesn't achieve parity goal
   - ❌ Delays value delivery

3. **Include entire npm ecosystem (bundler + npm install)**
   - ❌ Massive complexity
   - ❌ Security nightmare (npm supply chain risks)
   - ❌ Violates "pure JS, auditable" requirement

**Rationale**: Start small with high-value packages, validate the pattern works, then expand based on actual LLM agent usage patterns. Python's 30+ packages accumulated over time; JavaScript can follow same path.

**Trade-offs**:
- ✅ Manageable scope for v1
- ✅ Proves the pattern works
- ✅ Low security risk (< 10 auditable packages)
- ❌ Not full parity immediately (acceptable - iterative approach)
- ❌ Requires manual curation (acceptable - ensures quality)

### Decision 5: Prologue Injection with inject_setup Parameter

**Choice**: Add `INJECTED_SETUP` constant to `JavaScriptSandbox` and prepend to user code when `inject_setup=True` (default).

**Alternatives considered:**

1. **Always inject, no flag**
   - ❌ Removes user control
   - ❌ Breaks symmetry with Python's `inject_setup` parameter

2. **Manual import in every execution**
   - ❌ Poor UX for LLM-generated code
   - ❌ Increases token usage in prompts

3. **Custom QuickJS initialization** (modify runtime startup)
   - ❌ Violates "prebuilt binary only" constraint

**Rationale**: Mirrors Python's proven pattern exactly. Provides good defaults (inject by default) while preserving opt-out for edge cases.

**Prologue content**:
```javascript
import * as std from "std";

globalThis.requireVendor = function requireVendor(name) { /* ... */ };

globalThis.readJson = function readJson(path) { /* ... */ };
globalThis.writeJson = function writeJson(path, obj) { /* ... */ };
```

**Trade-offs**:
- ✅ Symmetric with Python
- ✅ Zero manual imports for users
- ✅ Opt-out available
- ❌ Adds ~50 lines to every execution (acceptable - injected setup is small)

## Risks / Trade-offs

### Risk 1: Integration Configuration for QuickJS File I/O

**Risk**: Current WASI integration may not properly expose QuickJS file I/O even though runtime supports it.

**Evidence**: QuickJS-NG `qjs-wasi.wasm` includes full `std` and `os` modules with:
- `std.open(filename, flags)` → FILE object
- `std.loadFile(filename)` → string
- `FILE.read()`, `FILE.write()`, `FILE.close()`, etc.
- `os.stat()`, `os.readdir()`, `os.mkdir()`, etc.

**Mitigation**:
- **Task 1.1** verifies JS code properly imports: `import * as std from "std";`
- Check WASI preopen configuration in `sandbox/host.py` (must mount `/app` with read/write permissions)
- Verify `std` module is accessible (may require specific QuickJS runtime flags)
- If integration issues persist, consult QuickJS-NG documentation and WASI configuration

**Likelihood**: Low (runtime has APIs; just need correct integration setup)

### Risk 2: Vendored JS Packages May Have Incompatibilities

**Risk**: Packages designed for browsers/Node.js may not work in QuickJS environment.

**Mitigation**:
- Only vendor packages explicitly tested in QuickJS
- Prefer minimal, standalone implementations over large frameworks
- **Task 2.2** includes verification step for each package
- Provide alternative implementations if standard packages don't work

**Likelihood**: Medium (QuickJS has good ES2020 support, but edge cases exist)

### Risk 3: Performance Impact of Prologue Injection

**Risk**: Injecting ~50 lines of setup code on every execution may consume significant fuel.

**Mitigation**:
- Profile fuel consumption of prologue vs user code
- Optimize prologue if fuel usage is >5% of typical execution
- Consider caching compiled prologue if QuickJS supports bytecode compilation

**Likelihood**: Low (50 lines is trivial vs typical LLM-generated code)

### Risk 4: Documentation Maintenance Burden

**Risk**: Keeping JavaScript documentation in sync with Python as packages evolve.

**Mitigation**:
- Use consistent documentation templates for both runtimes
- Add CI check to warn if Python doc updates aren't mirrored in JavaScript
- Version documentation with package updates

**Likelihood**: Medium (ongoing maintenance cost)

## Migration Plan

### Phase 1: Core State Persistence (Week 1)

1. Verify QuickJS `std` module import and file I/O (Task 1.1)
   - Confirm `import * as std from "std";` works in current setup
   - Test `std.open('/app/test.txt', 'w')` with WASI preopen config
   - Document any integration quirks
2. Implement `wrap_stateful_code()` (Task 1.2)
3. Update JavaScriptSandbox (Task 1.3)
4. Write state persistence tests (Task 1.4)

**Milestone**: JavaScript `auto_persist_globals=True` works end-to-end

### Phase 2: Vendored Packages (Week 2)

1. Create vendor_js structure (Task 2.1)
2. Select and vendor initial packages (Task 2.2)
3. Implement requireVendor() (Task 2.3)
4. Configure WASI mount (Task 2.4)
5. Write vendor tests (Task 2.5)

**Milestone**: JavaScript can load and use vendored CSV/JSON/string packages

### Phase 3: Helper Utilities and Injection (Week 3)

1. Create sandbox_utils.js (Task 3.1)
2. Test sandbox_utils (Task 3.2)
3. Define prologue template (Task 4.1)
4. Update JavaScriptSandbox.execute() (Task 4.2)
5. Write injection tests (Task 4.3)

**Milestone**: JavaScript has automatic setup and helper libraries

### Phase 4: Documentation and Integration (Week 4)

1. Write JAVASCRIPT_CAPABILITIES.md (Task 5.1)
2. Update existing docs (Task 5.2, 5.3)
3. Integration tests (Task 6.1, 6.2)
4. Migration and cleanup (Task 7.1, 7.2, 7.3)

**Milestone**: JavaScript runtime has full parity and comprehensive docs

### Rollback Plan

If QuickJS `std` module integration fails (Phase 1 failure):
1. Debug WASI preopen configuration (most likely issue)
2. Verify QuickJS runtime flags and module import syntax
3. If truly blocked, implement Alternative #2 (host-side state management)
4. Document integration findings in JAVASCRIPT.md

**Note**: Given evidence that `qjs-wasi.wasm` includes full file I/O APIs, rollback is unlikely needed - more likely a config/integration issue.

If vendored packages are incompatible (Phase 2 failure):
1. Reduce scope to sandbox_utils.js only
2. Document missing packages as "future work"
3. Still achieve partial parity (state + helpers)

## Open Questions

1. **Q**: Should `requireVendor()` cache loaded packages to avoid re-reading files?
   **A**: Deferred to implementation testing. If performance testing shows cache is needed, add it in Task 2.3. Otherwise, keep simple (no cache).

2. **Q**: How strictly should JavaScript package APIs match Python equivalents?
   **A**: Use idiomatic JavaScript naming (camelCase vs snake_case). Match semantics (behavior), not syntax (signatures). Document differences clearly.

3. **Q**: Should we version vendor_js packages separately from sandbox version?
   **A**: No. Vendored packages are part of sandbox release. Update packages via PR + version bump. Reduces complexity.

4. **Q**: What happens if user code manually imports `std` module AND we inject it?
   **A**: QuickJS ES6 module imports are idempotent. Multiple `import * as std from "std"` statements won't cause errors. Injection is safe.

5. **Q**: Should JavaScript support Python's `sandbox_utils` pickle-based state?
   **A**: No. JavaScript uses JSON-only. Cross-runtime state sharing is non-goal. Each runtime has independent state files.

---

**Decision Authority**: Core maintainer approval required before implementation starts.

**Review Checklist**:
- [ ] QuickJS `std` module integration verified (import works, file I/O accessible)
- [ ] WASI preopen configuration confirmed for `/app` read/write access
- [ ] Initial vendor_js package list approved
- [ ] Prologue template reviewed for security
- [ ] Documentation scope agreed (800+ lines target)

**Technical References**:
- QuickJS `std` module docs: https://fuchsia.googlesource.com/third_party/quickjs/+/refs/heads/main/doc/quickjs.html
- QuickJS-NG releases (includes `qjs-wasi.wasm`): https://github.com/quickjs-ng/quickjs/releases
- QuickJS-libc.c (FILE implementation): https://fuchsia.googlesource.com/third_party/quickjs/+/ca272d5b/quickjs-libc.c
