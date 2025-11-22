# Tasks: Mature Enterprise API

## Implementation Checklist

### Phase 1: Core Models (Foundational)
- [x] Add pydantic dependency to pyproject.toml (pydantic~=2.0)
- [x] Create sandbox/core/__init__.py
- [x] Create sandbox/core/models.py with:
  - [x] RuntimeType enum (PYTHON, JAVASCRIPT)
  - [x] ExecutionPolicy Pydantic model with field validators
  - [x] SandboxResult Pydantic model with all fields from MATURE.md
- [x] Create sandbox/core/errors.py with:
  - [x] PolicyValidationError exception class
  - [x] SandboxExecutionError exception class (optional)
- [x] Update sandbox/policies.py:
  - [x] Modify load_policy() to return ExecutionPolicy instead of dict
  - [x] Preserve deep merge logic for env dict
  - [x] Add try/except for Pydantic ValidationError → PolicyValidationError
- [x] Write tests in tests/test_core_models.py:
  - [x] Test ExecutionPolicy default values
  - [x] Test ExecutionPolicy validation (negative fuel, invalid fields)
  - [x] Test ExecutionPolicy JSON serialization
  - [x] Test SandboxResult creation and serialization
  - [x] Test RuntimeType enum values
  - [x] Test load_policy() with valid/invalid TOML
  - [x] Test policy env dict deep merge
- [x] Run pytest tests/test_core_models.py and fix failures

### Phase 2: Logging Infrastructure
- [x] Create sandbox/core/logging.py with:
  - [x] SandboxLogger class wrapping logging.Logger
  - [x] log_execution_start(runtime, policy, **extra) method
  - [x] log_execution_complete(result) method
  - [x] log_security_event(event_type, details) method
  - [x] Ensure no global logging config modification
- [x] Write tests in tests/test_logging.py:
  - [x] Test SandboxLogger wraps provided logger
  - [x] Test default logger creation
  - [x] Test execution.start log structure (capture extra dict)
  - [x] Test execution.complete log structure
  - [x] Test security event log structure (WARNING level)
  - [x] Test no handlers/formatters installed
- [x] Run pytest tests/test_logging.py and fix failures

### Phase 3: Base Sandbox Abstraction
- [x] Create sandbox/core/base.py with:
  - [x] BaseSandbox ABC with __init__(policy, workspace, logger)
  - [x] Abstract execute(code: str, **kwargs) -> SandboxResult method
  - [x] Abstract validate_code(code: str) -> bool method
  - [x] _log_execution_metrics(result) helper method
- [x] Write tests in tests/test_base_sandbox.py:
  - [x] Test BaseSandbox cannot be instantiated directly
  - [x] Test subclass must implement execute() and validate_code()
  - [x] Test __init__ sets policy, workspace, logger attributes
- [x] Run pytest tests/test_base_sandbox.py and fix failures

### Phase 4: Python Runtime Implementation
- [x] Create sandbox/runtimes/python/__init__.py
- [x] Create sandbox/runtimes/python/sandbox.py with:
  - [x] PythonSandbox(BaseSandbox) class
  - [x] __init__(wasm_binary_path, policy, workspace, logger)
  - [x] execute(code, inject_setup) implementation:
    - [x] Call logger.log_execution_start()
    - [x] Use write_untrusted_code() to write code to workspace
    - [x] Snapshot workspace files before execution
    - [x] Call host.run_untrusted_python()
    - [x] Measure duration with time.perf_counter()
    - [x] Detect file delta (created/modified files)
    - [x] Map raw result to SandboxResult
    - [x] Call logger.log_execution_complete()
  - [x] validate_code(code) implementation using compile()
  - [x] _detect_file_delta() helper method (refactor from runner.py)
  - [x] _map_to_sandbox_result() helper method
- [x] Write tests in tests/test_python_sandbox.py:
  - [x] Test successful execution returns SandboxResult
  - [x] Test execute with inject_setup=True adds sys.path
  - [x] Test execute with inject_setup=False skips setup
  - [x] Test validate_code returns True for valid syntax
  - [x] Test validate_code returns False for syntax errors
  - [x] Test validate_code does not execute code
  - [x] Test file delta detection (created/modified files)
  - [x] Test execution metrics (duration, fuel, memory)
  - [x] Test security boundaries (fuel exhaustion, FS escape, memory)
  - [x] Test logging integration (start/complete events emitted)
- [x] Run pytest tests/test_python_sandbox.py and fix failures

### Phase 5: Factory API and Public Exports
- [x] Create sandbox/core/factory.py with:
  - [x] create_sandbox(runtime, policy, workspace, logger, **kwargs) function
  - [x] RuntimeType.PYTHON → PythonSandbox
  - [x] RuntimeType.JAVASCRIPT → NotImplementedError with message
  - [x] Invalid runtime → ValueError
- [x] Update sandbox/__init__.py:
  - [x] Import and expose in __all__: ExecutionPolicy, SandboxResult, RuntimeType
  - [x] Import and expose in __all__: BaseSandbox, PythonSandbox
  - [x] Import and expose in __all__: create_sandbox
  - [x] Import and expose in __all__: PolicyValidationError, SandboxExecutionError
  - [x] Import and expose in __all__: SandboxLogger
- [x] Add py.typed marker file (for type checker support)
- [x] Write tests in tests/test_factory.py:
  - [x] Test create_sandbox() default returns PythonSandbox
  - [x] Test create_sandbox(runtime=PYTHON) returns PythonSandbox
  - [x] Test create_sandbox(runtime=JAVASCRIPT) raises NotImplementedError
  - [x] Test create_sandbox(runtime="invalid") raises ValueError
  - [x] Test create_sandbox with custom policy
  - [x] Test create_sandbox with custom workspace
  - [x] Test create_sandbox with custom logger
  - [x] Test create_sandbox passes kwargs to runtime constructor
- [x] Write tests in tests/test_public_api.py:
  - [x] Test `from sandbox import ExecutionPolicy` works
  - [x] Test `from sandbox import SandboxResult` works
  - [x] Test `from sandbox import RuntimeType` works
  - [x] Test `from sandbox import BaseSandbox` works
  - [x] Test `from sandbox import PythonSandbox` works
  - [x] Test `from sandbox import create_sandbox` works
  - [x] Test `from sandbox import PolicyValidationError` works

---

### Phase 6: Documentation Updates
- [x] Update README.md:
  - [x] Add "Quick Start" section showing create_sandbox()
  - [x] Add example of custom policy with ExecutionPolicy
  - [x] Add example of RuntimeType.PYTHON selection
  - [x] Document SandboxResult return type and field access
- [x] Update DEMO.md:
  - [x] Add demo showing new API usage
  - [x] Show SandboxResult usage and field access
  - [x] Show structured logging integration example
- [x] Update .github/copilot-instructions.md:
  - [x] Document new sandbox/core/ structure
  - [x] Document create_sandbox() factory pattern
  - [x] Update examples to use new API

---

### Phase 7: Integration Testing
- [x] Run full test suite: pytest tests/ --cov=sandbox --cov-report=html
- [x] Verify new tests pass (test_*_models, test_*_sandbox, etc.)
- [x] Check code coverage ≥ 90% for new modules
- [x] Run demo_comprehensive.py with new API
- [x] Verify no performance regression (baseline vs new implementation)

---

### Phase 8: Type Checking and Linting
- [x] Run mypy sandbox/ (fix all type errors)
- [x] Run ruff check sandbox/ (fix linting issues)
- [x] Verify IDE autocomplete works for new API (manual check)
- [x] Verify type checkers recognize py.typed marker

---

### Phase 9: Final Validation
- [x] Run all security boundary tests (fuel, FS, memory attacks)
- [x] Verify WASI filesystem isolation unchanged
- [x] Verify fuel budget enforcement unchanged
- [x] Verify memory cap enforcement unchanged
- [x] Verify stdout/stderr capping unchanged
- [x] Manual smoke test with Strands CLI integration (if available)
- [x] Create PR with all changes and comprehensive description

## Task Dependencies

### Parallel Tracks
- **Track 1 (Models)**: Phase 1 → Phase 4 (Python sandbox needs models)
- **Track 2 (Logging)**: Phase 2 → Phase 4 (Python sandbox needs logger)
- **Track 3 (Base)**: Phase 3 → Phase 4 (Python sandbox extends BaseSandbox)

### Sequential Requirements
- Phase 4 depends on Phases 1, 2, 3 (foundational layers)
- Phase 5 depends on Phase 4 (factory creates PythonSandbox)
- Phase 6 depends on Phases 1-5 (document completed API)
- Phase 7 depends on Phases 1-6 (test complete implementation)
- Phases 8-9 depend on Phase 7 (validate after testing)

## Verification Criteria

Each phase is complete when:
1. All code is written and type-checked
2. All tests for that phase pass
3. No existing tests are broken
4. Code coverage for new modules ≥ 90%
5. Manual smoke test confirms expected behavior

## Rollback Plan

If issues arise during implementation:
1. All new code is in sandbox/core/ and sandbox/runtimes/ (isolated modules)
2. Existing sandbox/*.py files are replaced with clean implementations
3. No legacy compatibility layer to maintain
4. Clean rollback by reverting to previous commit
