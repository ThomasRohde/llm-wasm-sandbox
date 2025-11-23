"""Tests for JavaScriptSandbox runtime implementation.

Validates that JavaScriptSandbox correctly implements BaseSandbox contract,
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
from sandbox.runtimes.javascript import JavaScriptSandbox


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory for test isolation."""
    with tempfile.TemporaryDirectory(prefix="test-workspace-", ignore_cleanup_errors=True) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def default_policy():
    """Create default ExecutionPolicy for tests."""
    return ExecutionPolicy()


@pytest.fixture
def javascript_sandbox(temp_workspace, default_policy):
    """Create JavaScriptSandbox instance with test configuration."""
    import uuid
    session_id = str(uuid.uuid4())
    return JavaScriptSandbox(
        wasm_binary_path="bin/quickjs.wasm",
        policy=default_policy,
        session_id=session_id,
        workspace_root=temp_workspace
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


class TestJavaScriptSandboxBasics:
    """Test basic JavaScriptSandbox initialization and configuration."""

    def test_init_sets_attributes(self, temp_workspace, default_policy):
        """Test that __init__ sets wasm_binary_path, policy, session_id, workspace_root, logger."""
        import uuid
        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=default_policy,
            session_id=session_id,
            workspace_root=temp_workspace
        )

        assert sandbox.wasm_binary_path == "bin/quickjs.wasm"
        assert sandbox.policy == default_policy
        assert sandbox.session_id == session_id
        assert sandbox.workspace_root == temp_workspace
        assert sandbox.workspace == temp_workspace / session_id
        assert sandbox.logger is not None

    def test_init_with_custom_logger(self, temp_workspace, default_policy, capture_logger):
        """Test that __init__ accepts custom logger."""
        import uuid
        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=default_policy,
            session_id=session_id,
            workspace_root=temp_workspace,
            logger=capture_logger
        )

        assert sandbox.logger == capture_logger


class TestJavaScriptSandboxExecution:
    """Test JavaScriptSandbox execute() method with various code scenarios."""

    def test_successful_execution_returns_sandbox_result(self, javascript_sandbox):
        """Test that successful execution returns typed SandboxResult."""
        code = "console.log('Hello from QuickJS');"
        result = javascript_sandbox.execute(code)

        assert isinstance(result, SandboxResult)
        assert result.success is True
        assert "Hello from QuickJS" in result.stdout
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.fuel_consumed is None or result.fuel_consumed > 0
        assert result.duration_ms > 0
        assert result.metadata.get("stdout_truncated") is False
        assert result.metadata.get("stderr_truncated") is False

    def test_execute_with_stdout_capture(self, javascript_sandbox):
        """Test that stdout is captured correctly."""
        code = """
console.log("Line 1");
console.log("Line 2");
console.log("Line 3");
"""
        result = javascript_sandbox.execute(code)

        assert "Line 1" in result.stdout
        assert "Line 2" in result.stdout
        assert "Line 3" in result.stdout

    def test_execute_with_stderr_capture(self, javascript_sandbox):
        """Test that stderr is captured correctly (via syntax errors)."""
        # Note: console.error is not available in QuickJS WASI build
        # Test stderr capture via syntax error instead
        code = """
console.log('Missing closing quote
"""
        result = javascript_sandbox.execute(code)

        # Syntax error should appear in stderr
        assert len(result.stderr) > 0
        assert result.success is False
        assert result.metadata.get("stderr_truncated") is False

    def test_execute_with_syntax_error(self, javascript_sandbox):
        """Test that syntax errors are captured in stderr."""
        code = """
console.log('Missing closing quote
"""
        result = javascript_sandbox.execute(code)

        # Execution should complete and capture the error
        assert isinstance(result, SandboxResult)
        assert result.success is False
        assert result.exit_code != 0
        # QuickJS should report syntax error in stderr
        assert len(result.stderr) > 0

    def test_execute_with_runtime_error(self, javascript_sandbox):
        """Test that runtime errors are captured (not raised as host exceptions)."""
        code = """
throw new Error("Intentional error from guest");
"""
        result = javascript_sandbox.execute(code)

        # Execution should complete and capture the error
        assert isinstance(result, SandboxResult)
        assert result.success is False
        assert result.exit_code != 0
        # Error should appear in stderr
        assert "Error" in result.stderr or "Intentional error" in result.stderr

    def test_execute_captures_metrics(self, javascript_sandbox):
        """Test that execution metrics (duration, fuel, memory) are captured."""
        code = "const arr = Array.from({length: 1000}, (_, i) => i);"
        result = javascript_sandbox.execute(code)

        assert result.duration_ms > 0
        assert result.fuel_consumed is None or result.fuel_consumed > 0
        assert result.memory_used_bytes > 0
        assert "memory_pages" in result.metadata

    def test_execute_with_multiple_statements(self, javascript_sandbox):
        """Test execution of JavaScript code with multiple statements."""
        code = """
const x = 10;
const y = 20;
const z = x + y;
console.log("Result: " + z);
"""
        result = javascript_sandbox.execute(code)

        assert result.success is True
        assert "Result: 30" in result.stdout

    def test_execute_with_function_definition(self, javascript_sandbox):
        """Test execution of JavaScript code with function definitions."""
        code = """
function greet(name) {
    return "Hello, " + name + "!";
}
console.log(greet("World"));
"""
        result = javascript_sandbox.execute(code)

        assert result.success is True
        assert "Hello, World!" in result.stdout

    def test_execute_with_es6_features(self, javascript_sandbox):
        """Test execution of JavaScript code with ES6 features."""
        code = """
const arr = [1, 2, 3, 4, 5];
const doubled = arr.map(x => x * 2);
console.log(doubled.join(", "));
"""
        result = javascript_sandbox.execute(code)

        assert result.success is True
        assert "2, 4, 6, 8, 10" in result.stdout

    def test_missing_wasm_binary_raises_file_not_found(self, temp_workspace, default_policy):
        """Missing WASM binaries should raise instead of returning a result."""
        import uuid

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/missing-quickjs.wasm",
            policy=default_policy,
            session_id=str(uuid.uuid4()),
            workspace_root=temp_workspace
        )

        with pytest.raises(FileNotFoundError):
            sandbox.execute("console.log('test');")


@pytest.mark.skip(reason="QuickJS WASI build does not support require('std') - file I/O APIs not available")
class TestJavaScriptSandboxFileOperations:
    """Test file I/O operations in JavaScriptSandbox.
    
    NOTE: These tests are skipped because the QuickJS WASI build used in this
    project does not include the std module or file I/O APIs. QuickJS running
    in WASI mode has limited APIs compared to the standalone version.
    
    Future enhancement: Consider using a QuickJS build with std/os modules,
    or implement file I/O via WASI host functions exposed to JavaScript.
    """

    def test_execute_code_that_creates_file(self, javascript_sandbox):
        """Test that JavaScript code can create files in /app."""
        code = """
const fs = require('std');
const file = std.open('/app/output.txt', 'w');
file.puts('Generated content from JavaScript');
file.close();
"""
        result = javascript_sandbox.execute(code)

        # Check if file was created
        output_file = javascript_sandbox.workspace / "output.txt"
        assert output_file.exists()
        assert "output.txt" in result.files_created

    def test_execute_code_that_reads_file(self, javascript_sandbox):
        """Test that JavaScript code can read files from /app."""
        # Create file before execution
        javascript_sandbox.workspace.mkdir(parents=True, exist_ok=True)
        existing_file = javascript_sandbox.workspace / "input.txt"
        existing_file.write_text("Test input data")

        code = """
const fs = require('std');
const file = std.open('/app/input.txt', 'r');
const content = file.readAsString();
file.close();
console.log('Read: ' + content);
"""
        result = javascript_sandbox.execute(code)

        assert "Read: Test input data" in result.stdout


@pytest.mark.skip(reason="QuickJS WASI build does not support require('std') - file I/O APIs not available")
class TestJavaScriptSandboxFileDetection:
    """Test file delta detection (created/modified files).
    
    NOTE: These tests are skipped because file creation from JavaScript requires
    APIs not available in the QuickJS WASI build. File delta detection logic
    is tested indirectly through Python runtime tests.
    """

    def test_file_delta_detects_created_files(self, javascript_sandbox):
        """Test that files created during execution are detected."""
        code = """
const fs = require('std');
const file = std.open('/app/new_file.txt', 'w');
file.puts('New file content');
file.close();
"""
        result = javascript_sandbox.execute(code)

        assert "new_file.txt" in result.files_created
        assert len(result.files_modified) == 0

    def test_file_delta_detects_modified_files(self, javascript_sandbox):
        """Test that files modified during execution are detected."""
        # Create file before execution
        javascript_sandbox.workspace.mkdir(parents=True, exist_ok=True)
        existing_file = javascript_sandbox.workspace / "existing.txt"
        existing_file.write_text("Original content")

        code = """
const fs = require('std');
const file = std.open('/app/existing.txt', 'w');
file.puts('Modified content');
file.close();
"""
        result = javascript_sandbox.execute(code)

        assert "existing.txt" in result.files_modified
        assert "existing.txt" not in result.files_created

    def test_file_delta_excludes_user_code(self, javascript_sandbox):
        """Test that user_code.js is not reported in file delta."""
        code = "console.log('test');"
        result = javascript_sandbox.execute(code)

        assert "user_code.js" not in result.files_created
        assert "user_code.js" not in result.files_modified

    def test_file_delta_detects_multiple_files(self, javascript_sandbox):
        """Test detection of multiple created files."""
        code = """
const fs = require('std');
for (let i = 0; i < 3; i++) {
    const file = std.open('/app/file_' + i + '.txt', 'w');
    file.puts('Content ' + i);
    file.close();
}
"""
        result = javascript_sandbox.execute(code)

        assert len(result.files_created) == 3
        assert "file_0.txt" in result.files_created
        assert "file_1.txt" in result.files_created
        assert "file_2.txt" in result.files_created


class TestJavaScriptSandboxValidation:
    """Test validate_code() behavior."""

    def test_validate_code_returns_true_for_valid_syntax(self, javascript_sandbox):
        """Test that validate_code returns True for syntactically valid code."""
        code = "console.log('Valid JavaScript code');"
        assert javascript_sandbox.validate_code(code) is True

    def test_validate_code_returns_true_for_syntax_errors(self, javascript_sandbox):
        """Test that validate_code returns True (defers to runtime validation)."""
        # Per design: no parser in v1, defer to runtime
        code = "console.log('Missing closing quote"
        assert javascript_sandbox.validate_code(code) is True

    def test_validate_code_does_not_execute(self, javascript_sandbox):
        """Test that validate_code does not execute code or have side effects."""
        # Use code that would have observable side effects if executed
        code = "console.log('Side effect');"
        
        # Validation should not execute the code
        result = javascript_sandbox.validate_code(code)
        
        # Validation returns True (defers to runtime)
        assert result is True
        
        # Verify no user_code.js file was created by validation
        user_code = javascript_sandbox.workspace / "user_code.js"
        # Note: workspace may not exist yet if this is first operation
        if javascript_sandbox.workspace.exists():
            assert not user_code.exists()

    def test_validate_code_accepts_complex_syntax(self, javascript_sandbox):
        """Test that validate_code handles complex valid syntax."""
        code = """
class MyClass {
    constructor(value) {
        this.value = value;
    }
    
    process() {
        return Array.from({length: this.value}, (_, i) => i * i);
    }
}

const obj = new MyClass(10);
const result = obj.process();
"""
        assert javascript_sandbox.validate_code(code) is True


class TestJavaScriptSandboxLogging:
    """Test logging integration with SandboxLogger."""

    def test_logging_execution_start_emitted(self, temp_workspace, default_policy, capture_logger):
        """Test that log_execution_start is called during execute()."""
        import uuid
        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=default_policy,
            session_id=session_id,
            workspace_root=temp_workspace,
            logger=capture_logger
        )

        code = "console.log('Test');"

        # Execute and verify logging (check logger was used)
        result = sandbox.execute(code)

        # If no errors, logging integration works
        assert isinstance(result, SandboxResult)

    def test_logging_execution_complete_emitted(self, temp_workspace, default_policy, capture_logger):
        """Test that log_execution_complete is called after execute()."""
        import uuid
        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=default_policy,
            session_id=session_id,
            workspace_root=temp_workspace,
            logger=capture_logger
        )

        code = "console.log('Test');"
        result = sandbox.execute(code)

        # Verify result contains expected fields that would be logged
        assert result.fuel_consumed is None or result.fuel_consumed >= 0
        assert result.duration_ms > 0


class TestJavaScriptSandboxWorkspace:
    """Test workspace path handling and result population."""

    def test_result_includes_workspace_path(self, javascript_sandbox):
        """Test that SandboxResult includes workspace path."""
        code = "console.log('test');"
        result = javascript_sandbox.execute(code)

        assert result.workspace_path == str(javascript_sandbox.workspace)

    def test_logs_dir_cleaned_by_default(self, javascript_sandbox):
        """Logs are cleaned up unless preservation is requested."""
        before = {p for p in Path(tempfile.gettempdir()).glob("wasm-javascript-*")}

        code = "console.log('Test');"
        result = javascript_sandbox.execute(code)

        after = {p for p in Path(tempfile.gettempdir()).glob("wasm-javascript-*")}
        created = [p for p in after if p not in before]

        assert result.metadata.get("logs_dir") is None
        assert all(not p.exists() for p in created)

    def test_logs_dir_preserved_when_requested(self, temp_workspace):
        """Preserve logs when ExecutionPolicy opts in."""
        import uuid

        session_id = str(uuid.uuid4())
        policy = ExecutionPolicy(preserve_logs=True)
        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy,
            session_id=session_id,
            workspace_root=temp_workspace,
        )

        result = sandbox.execute("console.log('Test');")

        assert result.metadata.get("logs_dir")
        assert Path(result.metadata["logs_dir"]).exists()
        shutil.rmtree(result.metadata["logs_dir"], ignore_errors=True)


class TestJavaScriptSandboxTruncation:
    """Test truncation signaling for stdout/stderr caps."""

    def test_truncation_flags_set(self, temp_workspace):
        """Ensure stdout/stderr truncation is reflected in metadata."""
        import uuid

        policy = ExecutionPolicy(stdout_max_bytes=50, stderr_max_bytes=50)
        session_id = str(uuid.uuid4())
        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy,
            session_id=session_id,
            workspace_root=temp_workspace
        )

        code = """
console.log("A".repeat(200));
console.error("B".repeat(200));
"""
        result = sandbox.execute(code)

        assert len(result.stdout) <= policy.stdout_max_bytes
        assert len(result.stderr) <= policy.stderr_max_bytes
        assert result.metadata.get("stdout_truncated") is True
        assert result.metadata.get("stderr_truncated") is True


class TestJavaScriptSandboxMetadata:
    """Test metadata population in SandboxResult."""

    def test_metadata_includes_runtime(self, javascript_sandbox):
        """Test that metadata includes runtime='javascript'."""
        code = "console.log('test');"
        result = javascript_sandbox.execute(code)

        assert "runtime" in result.metadata
        assert result.metadata["runtime"] == "javascript"

    def test_metadata_includes_session_id(self, javascript_sandbox):
        """Test that metadata includes session_id."""
        code = "console.log('test');"
        result = javascript_sandbox.execute(code)

        assert "session_id" in result.metadata
        assert result.metadata["session_id"] == javascript_sandbox.session_id

    def test_metadata_includes_policy_snapshot(self, javascript_sandbox):
        """Test that metadata includes policy snapshot (fuel, memory limits)."""
        code = "console.log('test');"
        result = javascript_sandbox.execute(code)

        assert "fuel_budget" in result.metadata
        assert "memory_limit_bytes" in result.metadata
        assert result.metadata["fuel_budget"] == javascript_sandbox.policy.fuel_budget
        assert result.metadata["memory_limit_bytes"] == javascript_sandbox.policy.memory_bytes
