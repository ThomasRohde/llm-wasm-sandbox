# Tests

Consolidated pytest-based test suite for the LLM WASM Sandbox with **80% code coverage**.

## Running Tests

```powershell
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_sandbox.py

# Run specific test class
uv run pytest tests/test_sandbox.py::TestBasicExecution

# Run specific test
uv run pytest tests/test_sandbox.py::TestBasicExecution::test_basic_smoke

# Run with coverage
uv run pytest --cov=sandbox --cov-report=term-missing

# Generate HTML coverage report
uv run pytest --cov=sandbox --cov-report=html
# Opens in htmlcov/index.html
```

## Test Structure

Tests are organized into logical classes covering all major components:

### Security Tests
- **TestBasicExecution**: Basic smoke tests for sandbox functionality
- **TestFilesystemIsolation**: WASI capability-based filesystem access controls
- **TestFuelExhaustion**: Fuel-based execution limits for runaway code
- **TestMemoryLimits**: Memory cap enforcement

### Component Tests
- **TestPolicyManagement**: Policy loading, defaults, and TOML configuration
- **TestUtilities**: Logging, directory management, custom exceptions
- **TestVendorManagement**: Package vendoring and workspace setup
- **TestHostDirect**: Direct host.py functionality and result structures

### Integration Tests
- **TestSandboxMetrics**: Verification of returned metrics and result structure
- **TestEdgeCases**: Empty code, syntax errors, imports, unicode, large output
- **TestVendorBootstrap**: Vendor bootstrapping and package copying
- **TestPolicyEdgeCases**: Custom policies, data mounts, environment merging

## Coverage Summary

Current coverage: **80%** (183 statements, 36 missed)

### By Module:
- `sandbox/__init__.py`: **100%** ✓
- `sandbox/runner.py`: **100%** ✓
- `sandbox/utils.py`: **100%** ✓
- `sandbox/host.py`: **86%** (9 lines uncovered - mostly error paths)
- `sandbox/policies.py`: **81%** (4 lines uncovered - edge cases)
- `sandbox/vendor.py`: **63%** (23 lines uncovered - package installation logic)

### Uncovered Areas:
- **host.py**: Error handling for optional data directory preopen and memory limit exceptions
- **policies.py**: Import error handling for Python < 3.11 (tomli)
- **vendor.py**: Package installation subprocess calls (requires external dependencies)

## What's Tested

### Security Boundaries
- ✓ Absolute path escapes blocked (e.g., `/etc/passwd`)
- ✓ Parent directory traversal blocked (e.g., `../README.md`)
- ✓ Preopen directory access allowed (e.g., `/app/input.txt`)
- ✓ Infinite loops caught by fuel exhaustion
- ✓ Memory bombs caught by memory limits

### Functional Correctness
- ✓ Basic Python code execution
- ✓ Environment variable access
- ✓ File I/O within preopen
- ✓ Metrics collection (fuel, memory, logs)
- ✓ Policy loading and merging
- ✓ Vendor directory management
- ✓ Unicode handling
- ✓ Empty/syntax error handling

### Edge Cases
- ✓ Empty code execution
- ✓ Syntax errors (trap handling)
- ✓ Import errors
- ✓ Large output capping
- ✓ Custom policy values
- ✓ Directory creation
- ✓ Exception hierarchy

## Configuration

pytest configuration is in `pytest.ini` and `pyproject.toml`:
- Test discovery: `tests/test_*.py`
- Verbose output enabled by default
- Short traceback format for readability
- 33 tests total across 10 test classes

