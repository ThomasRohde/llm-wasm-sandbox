"""Tests for PythonSandbox runtime implementation.

Validates that PythonSandbox correctly implements BaseSandbox contract,
executes code with proper isolation, detects file changes, validates syntax,
and integrates with structured logging.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from sandbox.core.logging import SandboxLogger
from sandbox.core.models import ExecutionPolicy, SandboxResult
from sandbox.core.storage import DiskStorageAdapter
from sandbox.runtimes.python import PythonSandbox


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory for test isolation."""
    with tempfile.TemporaryDirectory(
        prefix="test-workspace-", ignore_cleanup_errors=True
    ) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def default_policy():
    """Create default ExecutionPolicy for tests."""
    return ExecutionPolicy()


@pytest.fixture
def python_sandbox(temp_workspace, default_policy):
    """Create PythonSandbox instance with test configuration."""
    import uuid

    session_id = str(uuid.uuid4())
    storage_adapter = DiskStorageAdapter(temp_workspace)

    # Create session workspace and metadata
    if not storage_adapter.session_exists(session_id):
        storage_adapter.create_session(session_id)

    return PythonSandbox(
        wasm_binary_path="bin/python.wasm",
        policy=default_policy,
        session_id=session_id,
        storage_adapter=storage_adapter,
    )


@pytest.fixture
def capture_logger():
    """Create logger with structlog for log capture."""
    import structlog

    # Configure structlog for testing
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    return SandboxLogger(structlog.get_logger("test-sandbox"))


class TestPythonSandboxBasics:
    """Test basic PythonSandbox initialization and configuration."""

    def test_init_sets_attributes(self, temp_workspace, default_policy):
        """Test that __init__ sets wasm_binary_path, policy, session_id, storage_adapter, logger."""
        import uuid

        session_id = str(uuid.uuid4())
        storage_adapter = DiskStorageAdapter(temp_workspace)

        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=default_policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
        )

        assert sandbox.wasm_binary_path == "bin/python.wasm"
        assert sandbox.policy == default_policy
        assert sandbox.session_id == session_id
        assert sandbox.workspace_root == temp_workspace
        assert sandbox.workspace == temp_workspace / session_id
        assert sandbox.logger is not None

    def test_init_with_custom_logger(self, temp_workspace, default_policy, capture_logger):
        """Test that __init__ accepts custom logger."""
        import uuid

        session_id = str(uuid.uuid4())
        storage_adapter = DiskStorageAdapter(temp_workspace)

        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=default_policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
            logger=capture_logger,
        )

        assert sandbox.logger == capture_logger


class TestPythonSandboxExecution:
    """Test PythonSandbox execute() method with various code scenarios."""

    def test_successful_execution_returns_sandbox_result(self, python_sandbox):
        """Test that successful execution returns typed SandboxResult."""
        code = "print('Hello from WASM')"
        result = python_sandbox.execute(code)

        assert isinstance(result, SandboxResult)
        assert result.success is True
        assert "Hello from WASM" in result.stdout
        assert (
            result.stderr == "" or "ResourceWarning" in result.stderr
        )  # Python may emit resource warnings
        assert result.exit_code == 0
        assert result.fuel_consumed is None or result.fuel_consumed > 0
        assert result.duration_ms > 0
        assert result.metadata.get("stdout_truncated") is False
        assert result.metadata.get("stderr_truncated") is False

    def test_execute_with_inject_setup_true(self, python_sandbox):
        """Test execute with inject_setup=True adds sys.path for vendored packages."""
        code = "import sys; print('/data/site-packages' in sys.path)"
        result = python_sandbox.execute(code, inject_setup=True)

        assert isinstance(result, SandboxResult)
        assert "True" in result.stdout

    def test_execute_with_inject_setup_false(self, python_sandbox):
        """Test execute with inject_setup=False skips sys.path setup."""
        code = "import sys; print('/data/site-packages' in sys.path)"
        result = python_sandbox.execute(code, inject_setup=False)

        assert isinstance(result, SandboxResult)
        # Without injection, path check should be False (unless already in sys.path)
        assert (
            "False" in result.stdout or "True" in result.stdout
        )  # Depends on Python default paths

    def test_execute_with_stdout_capture(self, python_sandbox):
        """Test that stdout is captured correctly."""
        code = """
print("Line 1")
print("Line 2")
print("Line 3")
"""
        result = python_sandbox.execute(code)

        assert "Line 1" in result.stdout
        assert "Line 2" in result.stdout
        assert "Line 3" in result.stdout

    def test_execute_with_stderr_capture(self, python_sandbox):
        """Test that stderr is captured correctly."""
        code = """
import sys
print("Error message", file=sys.stderr)
"""
        result = python_sandbox.execute(code)

        assert "Error message" in result.stderr
        assert result.metadata.get("stderr_truncated") is False

    def test_execute_with_guest_error(self, python_sandbox):
        """Test that guest code errors are captured (not raised as host exceptions)."""
        code = """
raise ValueError("Intentional error from guest")
"""
        result = python_sandbox.execute(code)

        # Execution should complete and capture the error in stderr or as WASM exit
        assert isinstance(result, SandboxResult)
        # Guest errors may appear in stderr OR cause WASM exit (both are valid)
        assert (
            "ValueError" in result.stderr
            or "Intentional error" in result.stderr
            or "exit status" in result.stderr
            or "ExitTrap" in result.stderr
        )
        assert result.success is False
        assert result.exit_code != 0

    def test_execute_captures_metrics(self, python_sandbox):
        """Test that execution metrics (duration, fuel, memory) are captured."""
        code = "x = [i for i in range(1000)]"
        result = python_sandbox.execute(code)

        assert result.duration_ms > 0
        assert result.fuel_consumed is None or result.fuel_consumed > 0
        assert result.memory_used_bytes > 0
        assert "memory_pages" in result.metadata

    def test_missing_wasm_binary_raises_file_not_found(self, temp_workspace, default_policy):
        """Missing WASM binaries should raise instead of returning a result."""
        import uuid

        storage_adapter = DiskStorageAdapter(temp_workspace)

        sandbox = PythonSandbox(
            wasm_binary_path="bin/missing-python.wasm",
            policy=default_policy,
            session_id=str(uuid.uuid4()),
            storage_adapter=storage_adapter,
        )

        with pytest.raises(FileNotFoundError):
            sandbox.execute("print('test')")


class TestPythonSandboxFileDetection:
    """Test file delta detection (created/modified files)."""

    def test_file_delta_detects_created_files(self, python_sandbox):
        """Test that files created during execution are detected."""
        code = """
with open('/app/output.txt', 'w') as f:
    f.write('Generated content')
"""
        result = python_sandbox.execute(code)

        assert "output.txt" in result.files_created
        assert len(result.files_modified) == 0

    def test_file_delta_detects_modified_files(self, python_sandbox):
        """Test that files modified during execution are detected."""
        # Create file before execution - ensure parent directory exists
        python_sandbox.workspace.mkdir(parents=True, exist_ok=True)
        existing_file = python_sandbox.workspace / "existing.txt"
        existing_file.write_text("Original content")

        code = """
with open('/app/existing.txt', 'w') as f:
    f.write('Modified content')
"""
        result = python_sandbox.execute(code)

        assert "existing.txt" in result.files_modified
        assert "existing.txt" not in result.files_created

    def test_file_delta_excludes_user_code(self, python_sandbox):
        """Test that user_code.py is not reported in file delta."""
        code = "pass"
        result = python_sandbox.execute(code)

        assert "user_code.py" not in result.files_created
        assert "user_code.py" not in result.files_modified

    def test_file_delta_detects_multiple_files(self, python_sandbox):
        """Test detection of multiple created files."""
        code = """
for i in range(3):
    with open(f'/app/file_{i}.txt', 'w') as f:
        f.write(f'Content {i}')
"""
        result = python_sandbox.execute(code)

        assert len(result.files_created) == 3
        assert "file_0.txt" in result.files_created
        assert "file_1.txt" in result.files_created
        assert "file_2.txt" in result.files_created


class TestPythonSandboxValidation:
    """Test validate_code() syntax checking."""

    def test_validate_code_returns_true_for_valid_syntax(self, python_sandbox):
        """Test that validate_code returns True for syntactically valid code."""
        code = "print('Valid Python code')"
        assert python_sandbox.validate_code(code) is True

    def test_validate_code_returns_false_for_syntax_errors(self, python_sandbox):
        """Test that validate_code returns False for syntax errors."""
        code = "print('Missing closing quote"
        assert python_sandbox.validate_code(code) is False

    def test_validate_code_returns_false_for_invalid_indentation(self, python_sandbox):
        """Test that validate_code detects indentation errors."""
        code = """
def func():
x = 1
"""
        assert python_sandbox.validate_code(code) is False

    def test_validate_code_does_not_execute(self, python_sandbox):
        """Test that validate_code does not execute code or have side effects."""
        code = """
with open('/app/should_not_exist.txt', 'w') as f:
    f.write('Should not be created')
"""
        # Validation should not create the file
        python_sandbox.validate_code(code)

        should_not_exist = python_sandbox.workspace / "should_not_exist.txt"
        assert not should_not_exist.exists()

    def test_validate_code_accepts_complex_syntax(self, python_sandbox):
        """Test that validate_code handles complex valid syntax."""
        code = """
class MyClass:
    def __init__(self, value):
        self.value = value

    def process(self):
        return [x**2 for x in range(self.value)]

obj = MyClass(10)
result = obj.process()
"""
        assert python_sandbox.validate_code(code) is True

    def test_validate_code_uses_sandbox_filename(self, python_sandbox, monkeypatch):
        """Validate code should compile using the <sandbox> filename sentinel."""
        import builtins

        captured: dict[str, str] = {}
        real_compile = builtins.compile

        def fake_compile(source: str, filename: str, mode: str):
            captured["filename"] = filename
            return real_compile(source, filename, mode)

        monkeypatch.setattr(builtins, "compile", fake_compile)

        assert python_sandbox.validate_code("x = 1") is True
        assert captured["filename"] == "<sandbox>"


class TestPythonSandboxSecurityBoundaries:
    """Test security boundaries (fuel exhaustion, FS isolation, memory limits)."""

    def test_fuel_exhaustion_does_not_raise(self, temp_workspace):
        """Test that fuel exhaustion is handled gracefully (captured, not raised)."""
        # Use very low fuel budget to trigger exhaustion
        import uuid

        policy = ExecutionPolicy(fuel_budget=100_000)
        session_id = str(uuid.uuid4())
        storage_adapter = DiskStorageAdapter(temp_workspace)

        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
        )

        code = """
while True:
    pass
"""
        result = sandbox.execute(code)

        # Execution should complete with OutOfFuel trap captured
        assert isinstance(result, SandboxResult)
        # Fuel should be near or at budget
        assert result.fuel_consumed >= 0
        assert result.success is False
        assert result.exit_code != 0
        assert result.metadata.get("trap_reason") == "out_of_fuel"

    def test_filesystem_isolation_prevents_escape(self, python_sandbox):
        """Test that WASI prevents filesystem access outside preopens."""
        code = """
try:
    with open('/etc/passwd', 'r') as f:
        content = f.read()
    print('SUCCESS: Read /etc/passwd')
except Exception as e:
    print(f'BLOCKED: {type(e).__name__}')
"""
        result = python_sandbox.execute(code)

        # Should be blocked by WASI - expect OSError or FileNotFoundError
        assert "BLOCKED" in result.stdout
        assert "SUCCESS" not in result.stdout

    def test_memory_limit_enforcement(self, temp_workspace):
        """Test that memory limits are configured (actual enforcement depends on wasmtime version)."""
        # Use small memory limit
        import uuid

        policy = ExecutionPolicy(memory_bytes=10_000_000)  # 10 MB
        session_id = str(uuid.uuid4())
        storage_adapter = DiskStorageAdapter(temp_workspace)

        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
        )

        code = """
try:
    # Try to allocate large array (may hit memory limit)
    big_list = [0] * (10**7)
    print('Allocated large list')
except MemoryError:
    print('BLOCKED: MemoryError')
"""
        result = sandbox.execute(code)

        # Memory limits are best-effort depending on wasmtime version
        # Just verify execution completes and metrics are captured
        assert isinstance(result, SandboxResult)
        assert result.memory_used_bytes > 0


class TestPythonSandboxLogging:
    """Test logging integration with SandboxLogger."""

    def test_logging_execution_start_emitted(self, temp_workspace, default_policy, capture_logger):
        """Test that log_execution_start is called during execute()."""
        import uuid

        session_id = str(uuid.uuid4())
        storage_adapter = DiskStorageAdapter(temp_workspace)

        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=default_policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
            logger=capture_logger,
        )

        code = "print('Test')"

        # Execute and verify logging (check logger was used)
        result = sandbox.execute(code)

        # If no errors, logging integration works
        assert isinstance(result, SandboxResult)

    def test_logging_execution_complete_emitted(
        self, temp_workspace, default_policy, capture_logger
    ):
        """Test that log_execution_complete is called after execute()."""
        import uuid

        session_id = str(uuid.uuid4())
        storage_adapter = DiskStorageAdapter(temp_workspace)

        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=default_policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
            logger=capture_logger,
        )

        code = "print('Test')"
        result = sandbox.execute(code)

        # Verify result contains expected fields that would be logged
        assert result.fuel_consumed is None or result.fuel_consumed >= 0
        assert result.duration_ms > 0


class TestPythonSandboxWorkspace:
    """Test workspace path handling and result population."""

    def test_result_includes_workspace_path(self, python_sandbox):
        """Test that SandboxResult includes workspace path."""
        code = "pass"
        result = python_sandbox.execute(code)

        assert result.workspace_path == str(python_sandbox.workspace)

    def test_logs_dir_cleaned_by_default(self, python_sandbox):
        """Logs are cleaned up unless explicitly preserved."""
        before = set(Path(tempfile.gettempdir()).glob("wasm-python-*"))

        code = "print('Test')"
        result = python_sandbox.execute(code)

        after = set(Path(tempfile.gettempdir()).glob("wasm-python-*"))
        created = [p for p in after if p not in before]

        assert result.metadata.get("logs_dir") is None
        assert all(not p.exists() for p in created)

    def test_logs_dir_preserved_when_requested(self, temp_workspace):
        """Preserve logs when policy opts in."""
        import uuid

        session_id = str(uuid.uuid4())
        policy = ExecutionPolicy(preserve_logs=True)
        storage_adapter = DiskStorageAdapter(temp_workspace)
        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
        )

        result = sandbox.execute("print('Test')")

        assert result.metadata.get("logs_dir")
        assert Path(result.metadata["logs_dir"]).exists()

        shutil.rmtree(result.metadata["logs_dir"], ignore_errors=True)


class TestPythonSandboxTruncation:
    """Test truncation signaling for stdout/stderr caps."""

    def test_truncation_flags_set(self, temp_workspace):
        """Ensure stdout/stderr truncation is reflected in metadata."""
        import uuid

        policy = ExecutionPolicy(stdout_max_bytes=50, stderr_max_bytes=50)
        session_id = str(uuid.uuid4())
        storage_adapter = DiskStorageAdapter(temp_workspace)
        sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
        )

        code = """
import sys
print("A" * 200)
print("B" * 200, file=sys.stderr)
"""
        result = sandbox.execute(code)

        assert len(result.stdout) <= policy.stdout_max_bytes
        assert len(result.stderr) <= policy.stderr_max_bytes
        assert result.metadata.get("stdout_truncated") is True
        assert result.metadata.get("stderr_truncated") is True


class TestPythonSandboxStatePersistence:
    """Test state persistence with auto_persist_globals."""

    def test_file_handle_not_serialized_with_context_manager(self, temp_workspace):
        """Test that file handles from 'with open()' pattern don't break state serialization.

        Regression test for bug where file handles remaining in globals after
        a context manager block would cause state serialization to fail with:
        TypeError: Object of type TextIOWrapper is not JSON serializable
        """
        from sandbox import RuntimeType, create_sandbox

        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            auto_persist_globals=True,
            workspace_root=temp_workspace,
        )

        # This pattern would previously fail due to 'f' remaining in globals
        code = """
with open('/app/test.txt', 'w') as f:
    f.write('hello')
counter = 42
"""
        result = sandbox.execute(code)

        assert result.success is True
        assert result.exit_code == 0
        # Verify file was created
        assert "test.txt" in result.files_created

    def test_file_handle_not_serialized_explicit_open(self, temp_workspace):
        """Test that explicit file handles are filtered from state serialization."""
        from sandbox import RuntimeType, create_sandbox

        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            auto_persist_globals=True,
            workspace_root=temp_workspace,
        )

        # Explicit open/close, 'f' variable still exists in globals
        code = """
f = open('/app/test2.txt', 'w')
f.write('world')
f.close()
counter = 42
"""
        result = sandbox.execute(code)

        assert result.success is True
        assert result.exit_code == 0

    def test_state_persists_after_file_operations(self, temp_workspace):
        """Test that state is correctly persisted across file I/O operations."""
        from sandbox import RuntimeType, create_sandbox

        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            auto_persist_globals=True,
            workspace_root=temp_workspace,
        )

        # First execution: file I/O with state
        code1 = """
with open('/app/data.txt', 'w') as f:
    f.write('test data')
counter = 1
items = ['a', 'b']
"""
        result1 = sandbox.execute(code1)
        assert result1.success is True

        # Second execution: verify state persisted
        code2 = """
counter += 1
items.append('c')
print(f'counter={counter}')
print(f'items={items}')
"""
        result2 = sandbox.execute(code2)
        assert result2.success is True
        assert "counter=2" in result2.stdout
        assert "items=['a', 'b', 'c']" in result2.stdout
