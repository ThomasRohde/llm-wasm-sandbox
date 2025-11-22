# Proposal: Mature Enterprise API

## Summary
Refactor llm-wasm-sandbox into an enterprise-grade API with typed models, multi-runtime support, structured logging, and clear integration points for Strands CLI and other agentic frameworks.

## Background
The current sandbox implementation (host.py, policies.py, runner.py) provides strong security guarantees but lacks:
- Type-safe, validated configuration and result models (using dict returns)
- A stable abstraction layer for supporting multiple WASM runtimes (currently Python-only)
- Structured, observable logging for telemetry integration
- Clear API boundaries for embedding in host applications

This refactor addresses these gaps while preserving existing security boundaries and maintaining backwards compatibility for current consumers.

## Goals
1. **Type Safety**: Replace dict-based returns with Pydantic models (`ExecutionPolicy`, `SandboxResult`)
2. **Multi-Runtime Design**: Create `BaseSandbox` abstraction supporting Python (v1) and JavaScript (future)
3. **Structured Logging**: Implement `SandboxLogger` with event-based logging (execution.start, execution.complete, security.violation)
4. **Clean Integration**: Provide `create_sandbox()` factory for embedding in Strands CLI with minimal coupling
5. **Clean API Surface**: Simple, typed interface with no legacy dict-based returns

## Non-Goals
- Multi-tenant process/container isolation (cgroups, namespaces)
- Network access or remote execution service
- Full OpenTelemetry integration (host application's responsibility)
- OS-level timeout wrappers (host application's responsibility)

## Target Personas
- **Agent Framework Authors** (Strands CLI): Need safe execution substrate for LLM-generated tools
- **Application Developers**: Embed sandbox to run untrusted code with clear limits
- **Security Engineers**: Audit and tune policies with explicit controls

## Success Criteria
- [ ] Pydantic models validate policy configurations at runtime
- [ ] `PythonSandbox` matches current security guarantees (fuel, memory, filesystem isolation)
- [ ] Structured logs emit at execution.start and execution.complete
- [ ] `create_sandbox()` factory supports RuntimeType enum (PYTHON implemented, JAVASCRIPT raises NotImplementedError)
- [ ] All security boundary tests pass (fuel exhaustion, FS isolation, memory limits)
- [ ] Clean typed API with SandboxResult returns (no dict-based interfaces)

## Dependencies
- Pydantic v2.x for model validation
- Existing wasmtime==38.* dependency unchanged
- Python 3.11+ for tomllib (or tomli backport)

## Implementation Phases
1. **Phase 1: Core Models** - Pydantic models (ExecutionPolicy, SandboxResult, RuntimeType)
2. **Phase 2: Python Runtime** - BaseSandbox ABC, PythonSandbox implementation
3. **Phase 3: Logging** - SandboxLogger with structured events
4. **Phase 4: Factory API** - create_sandbox() with public exports, update README/DEMO
5. **Phase 5: Validation** - Comprehensive tests for new APIs, policy validation, security boundaries

## Affected Capabilities
- `core-models` (NEW) - Pydantic models for type-safe configuration and results
- `python-runtime` (NEW) - BaseSandbox abstraction and PythonSandbox implementation
- `logging` (NEW) - Structured logging for observability
- `factory-api` (NEW) - Public API factory and exports

## Open Questions
1. **Exit Code Semantics**: Should we standardize exit codes (0=success, 1=policy violation, 2=guest error)?
2. **Timeout Enforcement**: Include OS-level timeout wrapper in library, or expect host to provide?
3. **Network Extensions**: When network support is needed, what minimal capability set should we expose?

## Related Work
- MATURE.md - Full enterprise maturation PRD
- Current implementation: sandbox/host.py, sandbox/policies.py, sandbox/runner.py
- Existing tests: tests/test_sandbox.py (security boundary validation)
