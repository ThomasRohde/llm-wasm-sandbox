# Design: JavaScript Runtime Implementation

## Context

The llm-wasm-sandbox currently supports only Python code execution via CPython compiled to WebAssembly. LLM workflows frequently generate JavaScript code for scripting, data processing, and automation tasks. Users are forced to either run JavaScript in unsafe environments or manually translate code to Python.

This design extends the sandbox to support JavaScript execution using QuickJS, a lightweight JavaScript engine that compiles to WASM/WASI. The implementation must maintain feature parity with the Python runtime in terms of security, resource limits, monitoring, and API surface.

**Stakeholders:**
- LLM application developers needing multi-language execution
- Security teams requiring consistent isolation across runtimes
- Platform maintainers supporting diverse code generation scenarios

**Constraints:**
- Must preserve all existing security boundaries (no network, no subprocess, filesystem isolation)
- Must reuse ExecutionPolicy, SandboxResult, and BaseSandbox abstractions
- Must maintain backwards compatibility with existing Python workflows
- Should minimize binary size (<10 MB total for bin/ directory)

## Goals / Non-Goals

**Goals:**
- Execute untrusted JavaScript code with same security guarantees as Python
- Provide typed API with create_sandbox(runtime=RuntimeType.JAVASCRIPT)
- Enforce resource limits (fuel, memory) equivalent to Python sandbox
- Capture console.log/console.error output to stdout/stderr
- Detect file changes in workspace (files_created, files_modified)
- Support session-based workflows with isolated workspaces

**Non-Goals:**
- npm package ecosystem support (QuickJS is standalone interpreter)
- Browser DOM APIs or Web APIs (pure JavaScript execution only)
- async/await or Promise support in initial version (defer to future)
- REPL mode in v1 (script-only execution, same as current Python)
- Performance parity with Node.js (acceptable tradeoff for security)
- Support for Node.js-specific globals (process, Buffer, require() with npm modules)

## Decisions

### Decision 1: QuickJS vs. Other JavaScript Engines

**Choice:** Use QuickJS compiled to WASM/WASI

**Alternatives Considered:**
1. **Duktape** - Another embeddable JS engine, but smaller community and fewer WASM builds
2. **SpiderMonkey (Firefox engine)** - Too large (~50 MB WASM binary), complex build process
3. **V8 (Chrome engine)** - Even larger, requires significant memory, not designed for embedding
4. **JavaScriptCore (Safari engine)** - Limited WASI support, Apple-centric ecosystem

**Rationale:**
- QuickJS has proven WASI builds (<2 MB binary size) available via quickjs-build-wasm project
- Lightweight and designed for embedding scenarios
- ES2020 feature support sufficient for most LLM-generated code
- Active community with documented WASM compilation process
- Similar security model to CPython (can run under Wasmtime with same isolation)
- Mature project with stable API

**Trade-offs:**
- ➖ Slower than V8/SpiderMonkey (acceptable for sandboxed untrusted code)
- ➖ No built-in async/await (can add in future if needed)
- ➕ Small binary footprint
- ➕ Deterministic execution (easier to reason about fuel consumption)

### Decision 2: Host Layer Generalization vs. Duplication

**Choice:** Create separate `run_untrusted_javascript()` function in `sandbox/host.py` rather than generalizing existing `run_untrusted_python()`

**Alternatives Considered:**
1. **Generalize to `run_untrusted_wasm(runtime_type, ...)`** - Single unified function for all runtimes
2. **Keep runtime-specific functions** - run_untrusted_python(), run_untrusted_javascript()
3. **Abstract host layer entirely** - Create BaseHost class with Python/JS subclasses

**Rationale:**
- Python and JavaScript have different argv conventions (python -I vs. quickjs)
- Different output patterns (Python traceback vs. JS error stack)
- Different vendored package injection needs (Python sys.path vs. none for JS in v1)
- Generalization would add complexity without clear benefit at 2-runtime scale
- If adding 3+ runtimes in future, refactor to unified approach then

**Trade-offs:**
- ➖ Some code duplication between Python and JS host functions (~50 lines)
- ➕ Each runtime can evolve independently without breaking the other
- ➕ Easier to debug runtime-specific issues
- ➕ Explicit rather than implicit (clear what differs between runtimes)

**Implementation Notes:**
- Extract shared WASI config logic to helper function: `_create_wasi_config(policy, workspace_path)`
- Runtime-specific functions call helper then customize argv/env
- If future runtimes (Ruby, Lua) are added, revisit generalization at 3+ runtime threshold

### Decision 3: JavaScript Package/Module Support

**Choice:** No module system support in v1 (defer to future iteration)

**Alternatives Considered:**
1. **Support ES6 modules with `import`/`export`** - Requires module loader in QuickJS WASM
2. **Support CommonJS `require()`** - Would need Node.js compatibility layer
3. **Pre-bundle vendored libraries** - Ship popular JS libraries in workspace (like Python site-packages)
4. **No module support** - Scripts must be self-contained

**Rationale:**
- QuickJS WASM builds vary in module loader support (some have ES6, some don't)
- CommonJS requires Node.js runtime features (module.exports, require.resolve)
- Pre-bundling adds binary size and security review burden
- Self-contained scripts cover 80% of LLM-generated JavaScript use cases
- Can add module support in v2 after validating demand

**Trade-offs:**
- ➖ Users cannot split code across multiple JS files initially
- ➖ No reusable utility libraries within sandbox
- ➕ Simpler security model (no module resolution path traversal risks)
- ➕ Faster initial implementation
- ➕ Smaller WASM binary

**Migration Path for v2:**
- If module support added, use WASI preopen to mount /app/modules/
- Allow relative imports: `import {foo} from './lib.js'`
- Restrict imports to /app namespace (no filesystem escapes)

### Decision 4: Console.log Output Mapping

**Choice:** Map `console.log()` to stdout, `console.error()` to stderr, exceptions to stderr

**Alternatives Considered:**
1. **All output to stdout** - Simpler, but loses error vs. normal output distinction
2. **Use custom output functions** - Require users to call `print()` instead of console.log
3. **Structured JSON output** - Wrap all output in JSON with type indicators

**Rationale:**
- Matches user expectations (console.log = stdout in Node.js, browsers)
- Preserves error signal in stderr for LLM feedback loops
- Consistent with Python sandbox (print() → stdout, exceptions → stderr)
- No code changes needed in LLM-generated JavaScript

**Trade-offs:**
- ➕ Intuitive mapping for JavaScript developers
- ➕ LLMs can use standard console API without special instructions
- ➖ May need to configure QuickJS to redirect console methods (verify during implementation)

### Decision 5: Fuel Budget Calibration

**Choice:** Use same default fuel budget (2B instructions) for JavaScript as Python, but document that equivalence is approximate

**Alternatives Considered:**
1. **Different fuel budgets per runtime** - JS gets 1B, Python gets 2B (based on profiling)
2. **Time-based limits instead of fuel** - Use timeout_seconds policy field
3. **Adaptive fuel budgeting** - Measure calibration run and adjust

**Rationale:**
- WASM instruction counting is runtime-agnostic (measures actual WASM ops, not language semantics)
- Different languages will have different instruction/line-of-code ratios, but that's expected
- Users can tune policy.fuel_budget for specific workloads
- Starting with same default avoids implicit bias toward one language
- Time-based limits are OS-level safety net (fuel is deterministic limit)

**Trade-offs:**
- ➖ JavaScript loop may take different wall-clock time than Python loop with same fuel
- ➕ Consistent security boundary across runtimes (instructions executed, not time)
- ➕ Deterministic and testable

**Implementation Notes:**
- Add benchmarking script: `benchmark_javascript_vs_python.py` to compare fuel consumption
- Document in README that fuel budget is instruction-based, not time-based
- If disparity is >10x, consider runtime-specific defaults in future

## Risks / Trade-offs

### Risk 1: QuickJS Binary Availability and Trust

**Risk:** QuickJS WASM binaries are community-built, not official releases from quickjs.org

**Impact:** HIGH - Security vulnerability in binary could compromise sandbox isolation

**Mitigation:**
- Use binaries from reputable sources (e.g., github.com/lynzrand/quickjs-build-wasm)
- Verify checksums if provided by source repository
- Document build process so users can compile their own QuickJS WASM if desired
- Consider building our own QuickJS WASM in future for full supply chain control
- Include binary provenance in documentation (commit hash, build date)

**Likelihood:** MEDIUM (community binaries are generally trustworthy, but not audited)

### Risk 2: Stdout/Stderr Capture Differences

**Risk:** QuickJS may handle console.log differently than expected (buffering, formatting)

**Impact:** MEDIUM - Output may be truncated or missing in SandboxResult

**Mitigation:**
- Test early with various output patterns (small, large, mixed stdout/stderr)
- Verify WASI stdout/stderr file descriptors are correctly mapped
- Add flush() calls if buffering issues found
- Fall back to custom print functions if console API unreliable

**Likelihood:** LOW (WASI stdout redirect is standard, QuickJS should honor it)

### Risk 3: Fuel Metering Granularity

**Risk:** QuickJS instruction patterns may differ from CPython, causing fuel exhaustion at unexpected times

**Impact:** MEDIUM - Legitimate code may hit fuel limits, or malicious code may evade limits

**Mitigation:**
- Benchmark common JavaScript patterns (loops, recursion, array operations)
- Adjust default fuel budget if testing shows consistent over/under consumption
- Document fuel consumption characteristics in JAVASCRIPT.md
- Provide tuning guidance for users with specific workloads

**Likelihood:** MEDIUM (instruction counting is reliable, but granularity varies)

### Risk 4: Error Message Quality

**Risk:** JavaScript error messages may be less detailed than Python tracebacks

**Impact:** LOW - Debugging LLM-generated code may be harder

**Mitigation:**
- Capture full error stack if available in QuickJS
- Include line numbers and error types in stderr
- Document error message format differences
- Consider enhancing error messages in future if user feedback indicates issues

**Likelihood:** HIGH (JS errors are generally less verbose than Python)

**Acceptance:** This is acceptable for v1; can improve in future iterations

## Migration Plan

**Phase 1: Implementation (Current Proposal)**
1. Add JavaScriptSandbox class and QuickJS binary integration
2. Update factory to support RuntimeType.JAVASCRIPT
3. Comprehensive testing (unit, integration, security)
4. Documentation updates

**Phase 2: Validation (Post-Implementation)**
1. Deploy to staging environment
2. Run real-world LLM-generated JavaScript code samples
3. Collect metrics on fuel consumption, execution time, error rates
4. Gather user feedback on API ergonomics

**Phase 3: Enhancements (Future Iterations)**
1. Add ES6 module support (`import`/`export`) - if user demand warrants
2. Add async/await support (requires QuickJS async WASM build)
3. Add REPL mode for multi-turn interactive sessions
4. Add vendored JavaScript libraries (lodash, date-fns, etc.)

**Rollback Plan:**
- If critical issues found post-deployment, revert factory to raise NotImplementedError for RuntimeType.JAVASCRIPT
- No impact on existing Python workflows (change is additive only)
- Users attempting JavaScript will get clear error message directing them to file issue

**Backwards Compatibility:**
- Existing API unchanged (create_sandbox() default remains RuntimeType.PYTHON)
- ExecutionPolicy, SandboxResult models unchanged
- Python sandbox behavior unchanged
- All existing tests continue passing

## Open Questions

1. **Q:** Should JavaScriptSandbox support `inject_setup` parameter like PythonSandbox?
   - **A (tentative):** No, defer to v2. JavaScript has no vendored packages in v1, so no setup needed.
   - **Decision point:** During implementation, assess if any global config is needed (e.g., setting timezone, locale).

2. **Q:** How should we handle JavaScript's looser typing for LLM feedback?
   - **A (tentative):** No runtime type checking in v1. LLMs handle JavaScript's dynamic typing already.
   - **Decision point:** If users request TypeScript support, consider adding tsc validation in validate_code().

3. **Q:** Should timeout_seconds be mandatory for JavaScript (vs. optional for Python)?
   - **A (tentative):** Keep optional. Fuel is primary limit; timeout is OS-level safety net for both.
   - **Decision point:** If JavaScript blocking calls bypass fuel (like Python sleep), document timeout as recommended.

4. **Q:** What ES version should we target (ES5, ES6, ES2020)?
   - **A (tentative):** Use whatever QuickJS binary supports (likely ES2020). Document in JAVASCRIPT.md.
   - **Decision point:** Verify during binary selection in task 1.1.

---

**Review Checklist:**
- [x] Architectural decisions documented with rationale
- [x] Alternatives considered and compared
- [x] Risks identified with mitigation strategies
- [x] Trade-offs explicitly stated
- [x] Migration plan with rollback strategy
- [x] Open questions captured for resolution during implementation
