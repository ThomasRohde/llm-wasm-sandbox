"""Tests for public API exports from sandbox package.

Verifies all components are correctly exported and accessible
via 'from sandbox import ...' statements. Ensures __all__ is
complete and import statements work as documented.
"""

from __future__ import annotations


class TestPublicAPIImports:
    """Test that all public API components can be imported."""

    def test_import_execution_policy(self) -> None:
        """Test 'from sandbox import ExecutionPolicy' works."""
        from sandbox import ExecutionPolicy

        # Verify it's the correct class
        assert ExecutionPolicy.__name__ == "ExecutionPolicy"

        # Verify it's a Pydantic model
        policy = ExecutionPolicy()
        assert hasattr(policy, "model_dump")
        assert hasattr(policy, "model_validate")

    def test_import_sandbox_result(self) -> None:
        """Test 'from sandbox import SandboxResult' works."""
        from sandbox import SandboxResult

        # Verify it's the correct class
        assert SandboxResult.__name__ == "SandboxResult"

        # Verify it's a Pydantic model
        assert hasattr(SandboxResult, "model_validate")

    def test_import_runtime_type(self) -> None:
        """Test 'from sandbox import RuntimeType' works."""
        from sandbox import RuntimeType

        # Verify it's the correct enum
        assert RuntimeType.__name__ == "RuntimeType"
        assert hasattr(RuntimeType, "PYTHON")
        assert hasattr(RuntimeType, "JAVASCRIPT")

        # Verify enum values
        assert RuntimeType.PYTHON.value == "python"
        assert RuntimeType.JAVASCRIPT.value == "javascript"

    def test_import_base_sandbox(self) -> None:
        """Test 'from sandbox import BaseSandbox' works."""
        from sandbox import BaseSandbox

        # Verify it's the correct ABC
        assert BaseSandbox.__name__ == "BaseSandbox"

        # Verify it has abstract methods
        assert hasattr(BaseSandbox, "execute")
        assert hasattr(BaseSandbox, "validate_code")

    def test_import_python_sandbox(self) -> None:
        """Test 'from sandbox import PythonSandbox' works."""
        from sandbox import PythonSandbox

        # Verify it's the correct class
        assert PythonSandbox.__name__ == "PythonSandbox"

        # Verify it extends BaseSandbox
        from sandbox import BaseSandbox

        assert issubclass(PythonSandbox, BaseSandbox)

    def test_import_create_sandbox(self) -> None:
        """Test 'from sandbox import create_sandbox' works."""
        from sandbox import create_sandbox

        # Verify it's callable
        assert callable(create_sandbox)

        # Verify function name
        assert create_sandbox.__name__ == "create_sandbox"

    def test_import_policy_validation_error(self) -> None:
        """Test 'from sandbox import PolicyValidationError' works."""
        from sandbox import PolicyValidationError

        # Verify it's an exception class
        assert issubclass(PolicyValidationError, Exception)
        assert PolicyValidationError.__name__ == "PolicyValidationError"

    def test_import_sandbox_execution_error(self) -> None:
        """Test 'from sandbox import SandboxExecutionError' works."""
        from sandbox import SandboxExecutionError

        # Verify it's an exception class
        assert issubclass(SandboxExecutionError, Exception)
        assert SandboxExecutionError.__name__ == "SandboxExecutionError"

    def test_import_sandbox_logger(self) -> None:
        """Test 'from sandbox import SandboxLogger' works."""
        from sandbox import SandboxLogger

        # Verify it's the correct class
        assert SandboxLogger.__name__ == "SandboxLogger"

        # Verify it has logging methods
        assert hasattr(SandboxLogger, "log_execution_start")
        assert hasattr(SandboxLogger, "log_execution_complete")
        assert hasattr(SandboxLogger, "log_security_event")

    def test_import_session_functions(self) -> None:
        """Test 'from sandbox import ...' works for session management functions."""
        from sandbox import (
            delete_session_path,
            delete_session_workspace,
            list_session_files,
            read_session_file,
            write_session_file,
        )

        # Verify all are callable
        assert callable(delete_session_workspace)
        assert callable(list_session_files)
        assert callable(read_session_file)
        assert callable(write_session_file)
        assert callable(delete_session_path)

        # Verify function names
        assert delete_session_workspace.__name__ == "delete_session_workspace"
        assert list_session_files.__name__ == "list_session_files"
        assert read_session_file.__name__ == "read_session_file"
        assert write_session_file.__name__ == "write_session_file"
        assert delete_session_path.__name__ == "delete_session_path"


class TestPublicAPIAll:
    """Test __all__ contains expected exports."""

    def test_all_contains_factory_and_base(self) -> None:
        """Test __all__ includes factory and base classes."""
        from sandbox import __all__

        assert "create_sandbox" in __all__
        assert "BaseSandbox" in __all__
        assert "PythonSandbox" in __all__

    def test_all_contains_models_and_types(self) -> None:
        """Test __all__ includes models and type enums."""
        from sandbox import __all__

        assert "ExecutionPolicy" in __all__
        assert "SandboxResult" in __all__
        assert "RuntimeType" in __all__

    def test_all_contains_exceptions(self) -> None:
        """Test __all__ includes exception classes."""
        from sandbox import __all__

        assert "PolicyValidationError" in __all__
        assert "SandboxExecutionError" in __all__

    def test_all_contains_logging(self) -> None:
        """Test __all__ includes logging components."""
        from sandbox import __all__

        assert "SandboxLogger" in __all__

    def test_all_contains_session_management(self) -> None:
        """Test __all__ includes session management functions."""
        from sandbox import __all__

        assert "delete_session_workspace" in __all__
        assert "list_session_files" in __all__
        assert "read_session_file" in __all__
        assert "write_session_file" in __all__
        assert "delete_session_path" in __all__


class TestImportStarBehavior:
    """Test 'from sandbox import *' behavior."""

    def test_import_star_includes_all_exports(self) -> None:
        """Test 'from sandbox import *' imports all __all__ items."""
        # Create a fresh namespace
        namespace = {}

        # Execute import * in that namespace
        exec("from sandbox import *", namespace)

        # Verify key exports are present
        assert "create_sandbox" in namespace
        assert "ExecutionPolicy" in namespace
        assert "SandboxResult" in namespace
        assert "RuntimeType" in namespace
        assert "BaseSandbox" in namespace
        assert "PythonSandbox" in namespace
        assert "PolicyValidationError" in namespace
        assert "SandboxExecutionError" in namespace
        assert "SandboxLogger" in namespace
        assert "list_session_files" in namespace
        assert "prune_sessions" in namespace
        assert "PruneResult" in namespace
        assert "SessionMetadata" in namespace


class TestPruningAPIImports:
    """Test that pruning-related API components can be imported."""

    def test_import_prune_sessions(self) -> None:
        """Test 'from sandbox import prune_sessions' works."""
        from sandbox import prune_sessions

        # Verify it's callable
        assert callable(prune_sessions)
        assert prune_sessions.__name__ == "prune_sessions"

    def test_import_prune_result(self) -> None:
        """Test 'from sandbox import PruneResult' works."""
        from sandbox import PruneResult

        # Verify it's the correct class
        assert PruneResult.__name__ == "PruneResult"

        # Verify it has expected fields
        from dataclasses import fields

        field_names = {f.name for f in fields(PruneResult)}
        assert "deleted_sessions" in field_names
        assert "skipped_sessions" in field_names
        assert "reclaimed_bytes" in field_names
        assert "errors" in field_names
        assert "dry_run" in field_names

    def test_import_session_metadata(self) -> None:
        """Test 'from sandbox import SessionMetadata' works."""
        from sandbox import SessionMetadata

        # Verify it's the correct class
        assert SessionMetadata.__name__ == "SessionMetadata"

        # Verify it has expected fields
        from dataclasses import fields

        field_names = {f.name for f in fields(SessionMetadata)}
        assert "session_id" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names
        assert "version" in field_names


class TestImportIntegration:
    """Integration tests verifying imports work together."""

    def test_import_and_use_create_sandbox_with_types(self) -> None:
        """Test importing and using create_sandbox with type imports."""
        from sandbox import ExecutionPolicy, RuntimeType, create_sandbox

        # Create custom policy
        policy = ExecutionPolicy(fuel_budget=1_000_000_000)

        # Create sandbox with type annotation
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

        # Verify sandbox works
        assert sandbox.policy.fuel_budget == 1_000_000_000

    def test_import_and_use_exception_types(self) -> None:
        """Test importing and raising/catching custom exceptions."""
        from sandbox import PolicyValidationError, SandboxExecutionError

        # Test PolicyValidationError
        try:
            raise PolicyValidationError("Test error")
        except PolicyValidationError as e:
            assert str(e) == "Test error"

        # Test SandboxExecutionError
        try:
            raise SandboxExecutionError("Test error")
        except SandboxExecutionError as e:
            assert str(e) == "Test error"

    def test_import_runtime_enum_values(self) -> None:
        """Test importing and using RuntimeType enum values."""
        from sandbox import RuntimeType

        # Test enum iteration
        runtimes = list(RuntimeType)
        assert len(runtimes) == 2
        assert RuntimeType.PYTHON in runtimes
        assert RuntimeType.JAVASCRIPT in runtimes

        # Test enum comparison
        assert RuntimeType.PYTHON != RuntimeType.JAVASCRIPT
        assert RuntimeType("python") == RuntimeType.PYTHON
