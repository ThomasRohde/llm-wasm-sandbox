# PRD: Improve Policy Enforcement and Execution Fidelity in the Python WASM Sandbox

## Summary
Fix critical gaps in how the Python sandbox applies execution policy, reports execution outcomes, and emits lifecycle telemetry. The current flow ignores caller-provided `ExecutionPolicy` settings when running code, always reports `success=True`, and mislabels new sessions as “retrieved,” making resource and security controls unenforceable and observability noisy.

## Problems to Solve
- **Policy bypass:** `PythonSandbox.execute` calls `host.run_untrusted_python` which reloads policy from disk, so caller-supplied limits/env/argv/mounts are ignored. Custom fuel/memory caps and env whitelists are not applied to executions.  
- **Incorrect result status:** `_map_to_sandbox_result` sets `success=True` and `exit_code=0` even when execution traps or guest stderr contains errors. Failures (syntax errors, OutOfFuel, runtime errors) are reported as successes.  
- **No truncation signal:** Stdout/stderr are capped, but callers are never told when truncation occurred, violating the spec requirement to indicate capped output.  
- **Session telemetry drift:** New sessions are logged as `session.retrieved` because logging checks metadata existence after creating it, reducing the value of lifecycle logs.

## Goals / Success Criteria
- Executions honor the `ExecutionPolicy` instance passed to `create_sandbox` (fuel, memory, stdout/stderr caps, argv, env, data mounts) without reloading config from disk.  
- `SandboxResult.success` and `exit_code` reflect real execution state: failures/traps set `success=False`, and traps/out-of-fuel are surfaced in stderr/metadata.  
- Stdout/stderr truncation is detectable by callers (explicit flags or markers) while keeping capped payloads.  
- Session lifecycle logs correctly distinguish created vs retrieved sessions.  
- Regression tests cover the above behaviors.

## Non-Goals
- Adding new runtimes or redesigning the logging stack.  
- Changing policy defaults or the public `ExecutionPolicy` schema.  
- Implementing OS-level timeouts beyond existing policy fields.

## Approach
1. **Policy plumbing:** Thread the provided `ExecutionPolicy` into `run_untrusted_python` (accept a policy arg, remove internal `load_policy` call, and default to `ExecutionPolicy()` when none is passed). Ensure all limits/env/mounts use the passed policy.  
2. **Result correctness:** Capture trap/exit outcomes from the WASM run. Set `success` based on trap/exit code and stderr; surface trap reasons (OutOfFuel, memory, other) in stderr/metadata; map exit codes when available instead of forcing `0`.  
3. **Truncation signaling:** When stdout/stderr exceed caps, annotate results (e.g., boolean flags in metadata or “[truncated]” markers) while preserving capped payloads.  
4. **Session logging fix:** Track prior existence before writing metadata so new sessions emit `log_session_created` and existing ones emit `log_session_retrieved`.  
5. **Tests:** Add/extend tests to cover custom policy enforcement (fuel/memory/env), failure status propagation, truncation signaling, and correct session logging.

## Work Items
- [ ] Update host layer to accept `ExecutionPolicy` input and remove implicit `load_policy` usage.  
- [ ] Wire `PythonSandbox` to pass its policy through to the host and ensure mounts/env/argv honor it.  
- [ ] Derive `success`/`exit_code` from trap/exit outcomes; propagate trap reasons into stderr/metadata.  
- [ ] Implement stdout/stderr truncation indicators and document behavior.  
- [ ] Fix session creation logging to distinguish new vs existing sessions.  
- [ ] Add regression tests for policy enforcement, failure signaling, truncation flags, and session logging.  
- [ ] Update docs/README snippets if behavior changes (e.g., new truncation markers).

## Risks & Mitigations
- **Wasmtime API variance:** `Store` limit APIs differ by version; guard with feature detection and add tests that accept best-effort enforcement.  
- **Backwards compatibility:** New truncation indicators may affect downstream parsing; add release notes and keep payload format stable.  
- **Performance:** Extra trap/exit handling should stay lightweight; measure with existing benchmarks if changes touch hot paths.

## Validation
- Unit/integration tests for custom policy adherence, failure reporting, truncation signaling, and session logging.  
- Manual smoke: run code with small fuel/memory to confirm enforcement and accurate `success`/stderr; verify truncation flags with large output.  
- Optional: rerun benchmark scripts to ensure no regressions after host plumbing changes.
