# Change: JavaScript-Python Feature Parity

## Why

The JavaScript runtime currently lacks several features that are available in the Python runtime, creating an asymmetric developer experience and limiting JavaScript's viability for stateful agent workflows. Specifically:

1. **No auto-persist globals**: Python has fully functional `auto_persist_globals` support; JavaScript has only placeholder code that doesn't work (QuickJS-NG WASI **does** provide file I/O via `std.open()`, but our integration doesn't utilize it yet)
2. **No vendored packages**: Python has 30+ pre-installed packages for document/data processing; JavaScript has zero
3. **No helper utilities**: Python has `sandbox_utils` library with shell-like APIs; JavaScript has nothing
4. **Limited documentation**: Python has comprehensive capability docs; JavaScript only has a PRD-style planning doc

This asymmetry makes Python the "only serious choice" for LLM agent workflows that require state persistence or rich library support.

## What Changes

- **BREAKING**: Implement working `auto_persist_globals` for JavaScript using file-backed state (leveraging QuickJS-NG's `std.open()` and `FILE` APIs)
- Add vendored JavaScript libraries (pure-JS equivalents of Python packages: CSV, JSON utilities, string helpers)
- Create `sandbox_utils.js` helper library matching Python's `sandbox_utils` API surface
- Write comprehensive `JAVASCRIPT_CAPABILITIES.md` documentation
- Implement automatic code injection for JavaScript (analogous to Python's sys.path setup)
- Add tests for JavaScript state persistence and vendored package usage
- Update examples to demonstrate JavaScript parity features

## Impact

- **Affected specs**:
  - `runtime-parity` (new): Cross-runtime feature consistency
  - `state-persistence` (new): Auto-persist globals for both runtimes
  - `vendored-packages` (new): Package availability and mounting
  - `helper-utilities` (new): LLM-friendly convenience APIs
  - `code-injection` (new): Automatic runtime setup

- **Affected code**:
  - `sandbox/state_js.py`: Make `wrap_stateful_code()` actually work
  - `sandbox/runtimes/javascript/sandbox.py`: Add auto code injection
  - `vendor_js/` (new directory): Pure-JS vendored packages
  - `sandbox/host.py`: Add `/data_js` preopen for vendored JS packages
  - `docs/JAVASCRIPT_CAPABILITIES.md` (new): Comprehensive reference
  - `tests/test_javascript_state.py` (new): State persistence tests
  - `examples/demo_javascript_session.py`: Update to showcase parity

- **Breaking changes**:
  - Existing `auto_persist_globals=True` for JavaScript will now actually work (was silently ignored before)
  - JavaScript code will have automatic access to `std` module imports (may affect code that manually imports)
  
- **Migration path**:
  - Existing JavaScript code continues to work (injection is additive)
  - Users can opt-in to `auto_persist_globals` via flag
  - No code changes required for vendored packages (automatically available)
