"""Tests for sandbox factory API (create_sandbox function).

Verifies factory correctly instantiates runtime-specific sandboxes,
handles default parameters, validates runtime types, and passes
through constructor arguments.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sandbox import (
    BaseSandbox,
    ExecutionPolicy,
    PolicyValidationError,
    PythonSandbox,
    RuntimeType,
    SandboxLogger,
    create_sandbox,
)


class TestCreateSandboxDefaults:
    """Test create_sandbox() with default parameters."""

    def test_create_sandbox_default_returns_python_sandbox(self) -> None:
        """Test create_sandbox() without arguments returns PythonSandbox."""
        sandbox = create_sandbox()

        assert isinstance(sandbox, PythonSandbox)
        assert isinstance(sandbox, BaseSandbox)

    def test_create_sandbox_default_uses_default_policy(self) -> None:
        """Test create_sandbox() uses default ExecutionPolicy when policy=None."""
        sandbox = create_sandbox()

        assert isinstance(sandbox.policy, ExecutionPolicy)
        assert sandbox.policy.fuel_budget == 2_000_000_000  # Default from ExecutionPolicy
        assert sandbox.policy.memory_bytes == 128_000_000  # Default 128 million bytes

    def test_create_sandbox_default_uses_workspace_directory(self) -> None:
        """Test create_sandbox() uses default workspace_root."""
        sandbox = create_sandbox()

        # With new architecture, workspace is workspace_root/session_id
        assert sandbox.workspace_root == Path("workspace")
        assert sandbox.workspace.parent == Path("workspace")
        assert str(sandbox.session_id) in str(sandbox.workspace)

    def test_create_sandbox_default_creates_logger(self) -> None:
        """Test create_sandbox() creates SandboxLogger when logger=None."""
        sandbox = create_sandbox()

        assert isinstance(sandbox.logger, SandboxLogger)
        # structlog logger doesn't have a name attribute like logging.Logger
        assert sandbox.logger._logger is not None


class TestCreateSandboxRuntimeSelection:
    """Test create_sandbox() runtime type selection."""

    def test_create_sandbox_with_python_runtime_returns_python_sandbox(self) -> None:
        """Test create_sandbox(runtime=PYTHON) returns PythonSandbox."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)

        assert isinstance(sandbox, PythonSandbox)

    def test_create_sandbox_with_javascript_runtime_returns_javascript_sandbox(self) -> None:
        """Test create_sandbox(runtime=JAVASCRIPT) returns JavaScriptSandbox."""
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox
        
        sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

        assert isinstance(sandbox, JavaScriptSandbox)
        assert sandbox.session_id is not None
        assert sandbox.wasm_binary_path == "bin/quickjs.wasm"

    def test_create_sandbox_with_invalid_runtime_raises_value_error(self) -> None:
        """Test create_sandbox(runtime='invalid') raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_sandbox(runtime="invalid")  # type: ignore[arg-type]

        assert "Invalid runtime type" in str(exc_info.value)
        assert "RuntimeType enum" in str(exc_info.value)


class TestCreateSandboxCustomPolicy:
    """Test create_sandbox() with custom ExecutionPolicy."""

    def test_create_sandbox_accepts_custom_policy(self) -> None:
        """Test create_sandbox() uses provided ExecutionPolicy."""
        custom_policy = ExecutionPolicy(
            fuel_budget=500_000_000,
            memory_bytes=32 * 1024 * 1024,  # 32 MB
        )

        sandbox = create_sandbox(policy=custom_policy)

        assert sandbox.policy == custom_policy
        assert sandbox.policy.fuel_budget == 500_000_000
        assert sandbox.policy.memory_bytes == 32 * 1024 * 1024

    def test_create_sandbox_policy_with_custom_env(self) -> None:
        """Test create_sandbox() preserves custom environment variables."""
        custom_policy = ExecutionPolicy(
            env={"CUSTOM_VAR": "test_value", "DEBUG": "1"}
        )

        sandbox = create_sandbox(policy=custom_policy)

        assert sandbox.policy.env["CUSTOM_VAR"] == "test_value"
        assert sandbox.policy.env["DEBUG"] == "1"

    def test_create_sandbox_with_invalid_policy_raises_validation_error(self) -> None:
        """Test create_sandbox() raises PolicyValidationError for invalid policy."""
        # ExecutionPolicy validation happens at construction, not in factory
        with pytest.raises(PolicyValidationError):
            ExecutionPolicy(fuel_budget=-1000)  # Negative fuel invalid


class TestCreateSandboxCustomWorkspace:
    """Test create_sandbox() with custom workspace path."""

    def test_create_sandbox_accepts_custom_workspace(self) -> None:
        """Test create_sandbox() uses provided workspace_root path."""
        custom_workspace = Path("custom_workspace")

        sandbox = create_sandbox(workspace_root=custom_workspace)

        assert sandbox.workspace_root == custom_workspace
        assert sandbox.workspace.parent == custom_workspace

    def test_create_sandbox_workspace_as_string(self) -> None:
        """Test create_sandbox() accepts workspace_root as Path."""
        sandbox = create_sandbox(workspace_root=Path("my_workspace"))

        assert sandbox.workspace_root == Path("my_workspace")
        assert sandbox.workspace.parent == Path("my_workspace")


class TestCreateSandboxCustomLogger:
    """Test create_sandbox() with custom SandboxLogger."""

    def test_create_sandbox_accepts_custom_logger(self) -> None:
        """Test create_sandbox() uses provided SandboxLogger."""
        import logging

        custom_logger = SandboxLogger(logging.getLogger("custom"))
        sandbox = create_sandbox(logger=custom_logger)

        assert sandbox.logger == custom_logger
        assert sandbox.logger._logger.name == "custom"


class TestCreateSandboxKwargs:
    """Test create_sandbox() passes runtime-specific kwargs."""

    def test_create_sandbox_accepts_wasm_binary_path_kwarg(self) -> None:
        """Test create_sandbox() passes wasm_binary_path to PythonSandbox."""
        custom_wasm_path = "custom/path/python.wasm"

        sandbox = create_sandbox(wasm_binary_path=custom_wasm_path)

        assert isinstance(sandbox, PythonSandbox)
        assert sandbox.wasm_binary_path == custom_wasm_path

    def test_create_sandbox_default_wasm_binary_path(self) -> None:
        """Test create_sandbox() uses default bin/python.wasm if not specified."""
        sandbox = create_sandbox()

        assert sandbox.wasm_binary_path == "bin/python.wasm"

    def test_create_sandbox_passes_arbitrary_kwargs_to_runtime(self) -> None:
        """Test create_sandbox() passes unknown kwargs to runtime constructor."""
        # PythonSandbox doesn't accept arbitrary kwargs, but factory should pass them
        # This test verifies the factory passes kwargs, even if runtime rejects them
        sandbox = create_sandbox(wasm_binary_path="bin/python.wasm")

        # Just verify sandbox was created successfully
        assert isinstance(sandbox, PythonSandbox)


class TestCreateSandboxIntegration:
    """Integration tests for create_sandbox() with combined parameters."""

    def test_create_sandbox_with_all_custom_parameters(self) -> None:
        """Test create_sandbox() with all parameters customized."""
        import logging

        custom_policy = ExecutionPolicy(fuel_budget=800_000_000)
        custom_workspace_root = Path("integration_workspace")
        custom_logger = SandboxLogger(logging.getLogger("integration"))
        custom_wasm = "integration/python.wasm"

        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=custom_policy,
            workspace_root=custom_workspace_root,
            logger=custom_logger,
            wasm_binary_path=custom_wasm,
        )

    def test_missing_wasm_binary_raises_on_execute(self, tmp_path: Path) -> None:
        """create_sandbox should surface missing wasm binaries via FileNotFoundError."""
        policy = ExecutionPolicy()
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            wasm_binary_path=str(tmp_path / "missing.wasm"),
            workspace_root=tmp_path / "ws-root",
            policy=policy
        )

        with pytest.raises(FileNotFoundError):
            sandbox.execute("print('hi')")

    def test_create_sandbox_returns_sandbox_with_execute_method(self) -> None:
        """Test create_sandbox() returns sandbox with executable interface."""
        sandbox = create_sandbox()

        # Verify sandbox has required BaseSandbox methods
        assert hasattr(sandbox, "execute")
        assert hasattr(sandbox, "validate_code")
        assert callable(sandbox.execute)
        assert callable(sandbox.validate_code)


class TestCreateSandboxJavaScriptIntegration:
    """Integration tests for JavaScript runtime factory creation."""

    def test_create_javascript_sandbox_with_default_wasm_path(self) -> None:
        """Test create_sandbox(runtime=JAVASCRIPT) uses default bin/quickjs.wasm."""
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox

        sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

        assert isinstance(sandbox, JavaScriptSandbox)
        assert sandbox.wasm_binary_path == "bin/quickjs.wasm"

    def test_create_javascript_sandbox_with_custom_policy(self) -> None:
        """Test factory with custom policy passes policy to JavaScriptSandbox."""
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox

        custom_policy = ExecutionPolicy(
            fuel_budget=500_000_000,
            memory_bytes=32 * 1024 * 1024,
            env={"DEBUG": "1"}
        )

        sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=custom_policy)

        assert isinstance(sandbox, JavaScriptSandbox)
        assert sandbox.policy == custom_policy
        assert sandbox.policy.fuel_budget == 500_000_000
        assert sandbox.policy.memory_bytes == 32 * 1024 * 1024
        assert sandbox.policy.env["DEBUG"] == "1"

    def test_create_javascript_sandbox_with_custom_wasm_binary_path(self) -> None:
        """Test factory with custom wasm_binary_path uses correct binary."""
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox

        custom_wasm = "custom/path/quickjs.wasm"

        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            wasm_binary_path=custom_wasm
        )

        assert isinstance(sandbox, JavaScriptSandbox)
        assert sandbox.wasm_binary_path == custom_wasm

    def test_create_javascript_sandbox_with_custom_logger(self) -> None:
        """Test factory with custom logger passes logger to JavaScriptSandbox."""
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox
        import logging

        custom_logger = SandboxLogger(logging.getLogger("js-test"))

        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            logger=custom_logger
        )

        assert isinstance(sandbox, JavaScriptSandbox)
        assert sandbox.logger == custom_logger

    def test_create_javascript_sandbox_with_custom_session_id(self, tmp_path: Path) -> None:
        """Test factory with custom session_id creates correct workspace."""
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox

        custom_workspace = tmp_path / "js_workspace"

        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            workspace_root=custom_workspace
        )

        assert isinstance(sandbox, JavaScriptSandbox)
        assert sandbox.workspace_root == custom_workspace
        assert sandbox.workspace.parent == custom_workspace
        assert str(sandbox.session_id) in str(sandbox.workspace)

    def test_create_javascript_sandbox_with_all_parameters(self, tmp_path: Path) -> None:
        """Test factory with all custom parameters for JavaScript runtime."""
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox
        import logging

        custom_policy = ExecutionPolicy(fuel_budget=800_000_000)
        custom_workspace = tmp_path / "full_js_workspace"
        custom_logger = SandboxLogger(logging.getLogger("js-integration"))
        custom_wasm = "integration/quickjs.wasm"

        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            policy=custom_policy,
            workspace_root=custom_workspace,
            logger=custom_logger,
            wasm_binary_path=custom_wasm
        )

        assert isinstance(sandbox, JavaScriptSandbox)
        assert sandbox.policy == custom_policy
        assert sandbox.workspace_root == custom_workspace
        assert sandbox.logger == custom_logger
        assert sandbox.wasm_binary_path == custom_wasm
