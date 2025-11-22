# PRD: Harden Python WASM sandbox correctness and observability

## Overview
Recent code review surfaced gaps between the implementation and the OpenSpec requirements for the Python runtime, logging, and policy handling. The fixes here focus on preserving security boundaries (memory limits, missing binary failures), making logging interoperable with standard loggers and spec-compliant event schemas, and tightening policy validation and configuration defaults.

## Problems to Fix
- Logging API assumes `structlog` and will raise `TypeError` when given a standard `logging.Logger`; emitted event names/fields diverge from spec and omit filesystem delta logging (sandbox/core/logging.py:51-180).
- Memory limits silently disable if `wasmtime.Store.set_limits` is unavailable, leaving the sandbox without a cap (sandbox/host.py:133-139).
- Missing or misconfigured WASM binaries are swallowed and converted into a successful return path instead of raising a clear error (sandbox/runtimes/python/sandbox.py:104-135), violating factory error expectations.
- Invalid `ExecutionPolicy` constructions raise raw `pydantic.ValidationError` instead of `PolicyValidationError`; mount_data_dir lacks default guest path when built programmatically (sandbox/core/models.py:26-142).
- `validate_code` uses `compile(..., "<string>", ...)` instead of the agreed `<sandbox>` marker (sandbox/runtimes/python/sandbox.py:164-179).

## Goals
- Enforce memory caps and binary presence deterministically; never degrade silently.
- Make logging usable with `logging.Logger` and align event names/payloads with spec (execution start/complete, security events, filesystem deltas).
- Ensure policy validation always raises `PolicyValidationError`, with correct defaults for optional data mounts.
- Preserve existing public API surface and backward-compatible test expectations.

## Non-Goals
- No new runtime types or WASI capability expansions.
- No redesign of session management or workspace layout.
- No dependency upgrades beyond what is required to implement the fixes.

## User Stories
- As a platform engineer, I need missing or invalid WASM binaries to fail fast so deployment misconfigurations are caught early.
- As an observability engineer, I need execution and security events to use standard loggers and spec-compliant fields so logs ingest cleanly.
- As a security reviewer, I need memory caps to remain enforced even when wasmtime APIs differ, to prevent memory exhaustion attacks.
- As an API consumer, I need policy validation errors to be predictable and typed (`PolicyValidationError`) regardless of how the policy is constructed.

## Proposed Changes
1) **Logging compatibility and schema**
   - Accept both `structlog` and `logging.Logger` instances without runtime errors; normalize to a common interface internally.
   - Emit execution start/complete/security events with spec message keys (`sandbox.execution.start`, `sandbox.execution.complete`, `sandbox.security.*`) and required fields (`event`, `runtime`, policy snapshot, success, duration_ms, fuel_consumed, memory_used_bytes, exit_code).
   - Add filesystem delta logging (counts and truncated paths) on completion.

2) **Resource enforcement**
   - Enforce memory caps even when `Store.set_limits` is unavailable: detect support at initialization and fail fast or provide a guarded fallback; add explicit tests for cap enforcement.
   - Surface missing `wasm_binary_path` as `FileNotFoundError` from `PythonSandbox.execute`/`create_sandbox` rather than wrapping it into a success=False result.

3) **Policy validation and defaults**
   - Wrap `ExecutionPolicy` validation errors in `PolicyValidationError` for direct instantiation and keep field-level details.
   - Auto-set `guest_data_path="/data"` when `mount_data_dir` is provided programmatically (not only via TOML).

4) **Validation consistency**
   - Update `validate_code` to compile with the `<sandbox>` filename sentinel to match spec wording.

## Acceptance Criteria
- Logging methods accept a plain `logging.Logger` without raising, and emitted records include spec-required keys; filesystem delta counts/paths appear in execution.complete logs with truncation for long paths.
- Memory limit enforcement fails closed: if limits cannot be set, execution raises a clear exception before running guest code; out-of-memory attempts trigger a trap or error that bubbles into `SandboxResult` with `trap_reason="memory_limit"`.
- Calling `create_sandbox(runtime=RuntimeType.PYTHON, wasm_binary_path="missing.wasm").execute("print(1)")` raises `FileNotFoundError` with the missing path in the message.
- `ExecutionPolicy(fuel_budget=-1)` raises `PolicyValidationError`; `ExecutionPolicy(mount_data_dir="datasets")` sets `guest_data_path="/data"` by default.
- `PythonSandbox.validate_code("x=1")` returns True and uses `<sandbox>` in compile(), while invalid code returns False without execution.
- Test coverage updated for the above behaviors (logging acceptance via unit/contract tests, memory cap enforcement, missing binary, policy validation).

## Rollout & Verification
- Add unit tests for logging schema, policy validation errors, data mount defaults, missing WASM binary handling, and memory cap enforcement.
- Run `uv run pytest` locally; ensure logging assertions avoid brittle ordering by asserting structured fields.
- Document behavioral changes in README and docstrings where relevant (logging expectations, policy validation).
