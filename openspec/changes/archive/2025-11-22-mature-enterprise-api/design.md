# Design: Mature Enterprise API

## Architecture Overview

This design refactors the existing three-layer sandbox into a formalized, type-safe architecture suitable for enterprise integration while preserving all current security guarantees.

### Current Architecture (Informal)
```
runner.py (LLM glue) → host.py (Wasmtime/WASI) → policies.py (config)
     ↓
  dict results, no types, tightly coupled
```

### Target Architecture (Formal)
```
sandbox/
  core/
    __init__.py
    base.py         # BaseSandbox ABC
    models.py       # Pydantic: ExecutionPolicy, SandboxResult, RuntimeType
    errors.py       # PolicyValidationError, SandboxExecutionError
    logging.py      # SandboxLogger (structured events)
  
  runtimes/
    python/
      __init__.py
      sandbox.py    # PythonSandbox(BaseSandbox)
    javascript/     # Future
      __init__.py
      sandbox.py
  
  # Legacy modules (refactored but maintained)
  host.py           # Low-level Wasmtime wrapper (used by PythonSandbox)
  policies.py       # load_policy() now returns ExecutionPolicy
  runner.py         # Backwards-compat adapters for execute/execute_isolated
  utils.py          # Unchanged
  vendor.py         # Unchanged
```

## Key Design Decisions

### 1. Pydantic for Type Safety and Validation

**Rationale**: Current `DEFAULT_POLICY` dict and `SandboxResult` class lack runtime validation. Invalid policies (negative limits, missing fields) can cause runtime errors deep in execution.

**Approach**:
- `ExecutionPolicy(BaseModel)`: Validates fuel_budget > 0, memory_bytes > 0, paths exist
- `SandboxResult(BaseModel)`: Typed output with explicit fields (stdout, stderr, fuel_consumed, etc.)
- Field validators enforce constraints (e.g., `Field(gt=0)` for budgets)
- Pydantic serialization enables JSON export for Strands artifact storage

**Trade-offs**:
- (+) Early validation catches config errors before WASM execution
- (+) IDE autocomplete and type checking improve developer experience
- (-) Small performance overhead from validation (~microseconds per execution)
- (-) Adds Pydantic dependency (acceptable for enterprise use)

### 2. BaseSandbox Abstraction for Multi-Runtime Support

**Rationale**: Current implementation is Python-specific. Future JavaScript support requires shared interface.

**Approach**:
```python
class BaseSandbox(ABC):
    def __init__(self, policy: ExecutionPolicy, workspace: Path, logger: SandboxLogger):
        ...
    
    @abstractmethod
    def execute(self, code: str, **kwargs) -> SandboxResult:
        """Execute untrusted code in sandbox."""
    
    @abstractmethod
    def validate_code(self, code: str) -> bool:
        """Syntax-only validation without execution."""
```

Each runtime (`PythonSandbox`, future `JavascriptSandbox`) implements:
- Runtime-specific WASM binary loading
- Code validation (Python: `compile()`, JS: parser)
- Result mapping from runtime-specific outputs to `SandboxResult`

**Trade-offs**:
- (+) Clear contract for adding runtimes
- (+) Shared policy, workspace, logging behavior
- (-) Slight indirection vs direct function calls
- (-) Abstract methods require implementation for each runtime

### 3. PythonSandbox as Orchestration Layer

**Rationale**: Existing `host.py` is low-level Wasmtime wrapper. New `PythonSandbox` adds type safety and structured results.

**Approach**:
```python
class PythonSandbox(BaseSandbox):
    def execute(self, code: str, inject_setup: bool = True) -> SandboxResult:
        # 1. Log execution start
        self.logger.log_execution_start("python", self.policy)
        
        # 2. Write code to workspace
        write_untrusted_code(code, self.workspace, inject_setup)
        
        # 3. Delegate to host.run_untrusted_python()
        raw_result = run_untrusted_python(self.wasm_binary_path, str(self.workspace))
        
        # 4. Map to SandboxResult (add duration, file delta)
        result = self._map_to_sandbox_result(raw_result)
        
        # 5. Log completion
        self.logger.log_execution_complete(result)
        
        return result
```

**Trade-offs**:
- (+) Reuses existing `host.py` WASM execution logic (no security changes)
- (+) Adds observability hooks (logging, metrics)
- (+) Type-safe inputs/outputs via Pydantic
- (-) Additional layer increases call depth (negligible perf impact)

### 4. Structured Logging without OTEL Coupling

**Rationale**: Strands CLI uses OpenTelemetry for tracing. Sandbox should emit structured logs that can be converted to OTEL spans by the host, but not depend on OTEL libraries.

**Approach**:
```python
class SandboxLogger:
    def log_execution_start(self, runtime: str, policy: ExecutionPolicy, **extra):
        self._logger.info("sandbox.execution.start", extra={
            "event": "execution.start",
            "runtime": runtime,
            "fuel_budget": policy.fuel_budget,
            ...
        })
```

Host application (Strands) can:
1. Configure logger handler to capture structured `extra` dict
2. Create OTEL spans from `execution.start`/`execution.complete` events
3. Add correlation IDs (trace_id, span_id) via logger context

**Trade-offs**:
- (+) No OTEL dependency in sandbox library
- (+) Works with any logging backend (structlog, Python logging, etc.)
- (+) Host controls span creation and sampling
- (-) Host must implement OTEL integration (expected for enterprise frameworks)

### 6. Policy Validation at Construction

**Rationale**: Current `load_policy()` returns unvalidated dict. Errors surface during WASM execution (e.g., negative fuel budget crashes Wasmtime).

**Approach**:
```python
# In policies.py
def load_policy(path: str = "config/policy.toml") -> ExecutionPolicy:
    """Load and validate policy, raising PolicyValidationError on invalid config."""
    if not os.path.exists(path):
        return ExecutionPolicy()  # Default policy
    
    with open(path, "rb") as f:
        data = tomllib.load(f)
    
    try:
        # Pydantic validates and merges with defaults
        return ExecutionPolicy(**data)
    except ValidationError as e:
        raise PolicyValidationError(f"Invalid policy: {e}")
```

**Trade-offs**:
- (+) Fail-fast at configuration time, not during execution
- (+) Clear error messages with field-level details
- (-) Requires Pydantic dependency

## Security Boundary Preservation

**Critical**: This refactor MUST NOT weaken existing security guarantees.

### Unchanged Security Properties
1. **WASI Filesystem Isolation**: `host.py` preopen logic unchanged (guest sees only /app)
2. **Fuel Budgeting**: Wasmtime fuel configuration unchanged (deterministic instruction limits)
3. **Memory Caps**: Wasmtime memory limits unchanged (prevent memory bombs)
4. **Stdio Capping**: Output size limits unchanged (prevent log flooding)
5. **Environment Isolation**: Whitelist-only env vars unchanged

### New Security-Relevant Changes
1. **Policy Validation**: More rigorous validation prevents misconfigurations
2. **Structured Logging**: Security events (fuel exhaustion, FS denial) explicitly logged
3. **Type Safety**: Pydantic prevents type confusion bugs (e.g., passing string where int expected)

## Performance Considerations

### Expected Overhead
- **Pydantic validation**: ~10-50 microseconds per execution (negligible vs WASM startup)
- **Logging calls**: ~1-5 microseconds per event (structured dict creation)
- **Abstraction layers**: 1-2 additional function calls (negligible)

### Mitigation Strategies
- Use Pydantic `model_validate()` only once at policy load time
- Avoid creating new Policy objects per execution (reuse)
- Logger lazy-evaluates extra dicts (no overhead if log level disabled)

Benchmarking with `demo_comprehensive.py` before/after will validate no regression >1%.

## Implementation Strategy

### Phase 1: Core Infrastructure
- Create `sandbox/core/` modules (models, base, errors, logging)
- Implement Pydantic models with validation
- Implement SandboxLogger with structured events

### Phase 2: Python Runtime
- Create `sandbox/runtimes/python/` with `PythonSandbox`
- Implement BaseSandbox abstraction
- Integrate with existing `host.py` for WASM execution

### Phase 3: Public API
- Expose `create_sandbox()` factory in `sandbox/__init__.py`
- Define clean public API exports
- Update README/DEMO with usage examples

### Phase 4: Migration from Legacy Code
- Replace existing `runner.py` with simple wrapper using new API (for any existing demos)
- Update all examples to use typed API
- Remove or archive legacy dict-based implementations

## Testing Strategy

### New Test Coverage
1. **Policy Validation**: Test invalid configs (negative fuel, missing fields)
2. **BaseSandbox Contract**: Ensure `PythonSandbox` implements all abstract methods
3. **Result Mapping**: Verify `SandboxResult` fields are correctly populated
4. **Logging Events**: Capture and validate structured log output
5. **API Integration**: Test `create_sandbox()` factory with different configurations

### Security Regression Tests
- Run all existing security tests (`test_infinite_loop`, `test_fs_escape`, `test_memory_blowup`)
- Verify fuel exhaustion still raises `wasmtime.Trap`
- Verify filesystem escapes still fail with "not-permitted"

## Open Questions

1. **Exit Code Standardization**: Should we define exit codes in `SandboxResult`?
   - 0 = success
   - 1 = policy violation (fuel, memory)
   - 2 = guest error (unhandled exception)
   - Current: Exit codes not exposed by Wasmtime Python bindings

2. **Timeout Enforcement**: Should sandbox include OS-level timeout wrapper?
   - Pro: Handles blocking WASI calls (sleep, stdin read)
   - Con: Platform-specific (signal.alarm on Unix, threading.Timer on Windows)
   - Recommendation: Defer to host application (Strands can wrap with subprocess timeout)

3. **Network Support**: When networking needed, what's the minimal capability set?
   - WASI sockets (wasi-sockets proposal) not yet stable
   - Recommendation: Block until WASI sockets stabilize, then add as explicit opt-in

## Related Documents
- MATURE.md - Full enterprise maturation PRD (source requirements)
- openspec/project.md - Project conventions and security model
- tests/test_sandbox.py - Existing security boundary tests
