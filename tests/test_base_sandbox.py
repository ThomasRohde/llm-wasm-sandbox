"""Tests for BaseSandbox abstract base class.

Verifies that BaseSandbox enforces the contract for runtime implementations,
including abstract method requirements, proper initialization, and helper methods.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from sandbox.core.base import BaseSandbox
from sandbox.core.logging import SandboxLogger
from sandbox.core.models import ExecutionPolicy, SandboxResult
from sandbox.core.storage import DiskStorageAdapter


@pytest.fixture
def mock_logger() -> MagicMock:
    """Create a mock structlog logger for testing."""
    return MagicMock()


class CompleteSandbox(BaseSandbox):
    """Concrete implementation of BaseSandbox for testing."""

    def execute(self, code: str, **kwargs: Any) -> SandboxResult:
        return SandboxResult(
            success=True, stdout="", stderr="", exit_code=0,
            fuel_consumed=None, memory_used_bytes=0, duration_ms=0.0,
            files_created=[], files_modified=[], workspace_path="", metadata={}
        )

    def validate_code(self, code: str) -> bool:
        return True


class TestBaseSandboxInstantiation:
    """Test that BaseSandbox cannot be instantiated directly."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """BaseSandbox is abstract and cannot be instantiated."""
        policy = ExecutionPolicy()
        session_id = "test-session"
        storage_adapter = DiskStorageAdapter(Path("workspace"))

        with pytest.raises(TypeError) as exc_info:
            BaseSandbox(policy, session_id, storage_adapter)  # type: ignore

        assert "Can't instantiate abstract class" in str(exc_info.value)
        assert "execute" in str(exc_info.value) or "validate_code" in str(exc_info.value)


class TestBaseSandboxSubclassing:
    """Test that BaseSandbox subclasses must implement abstract methods."""

    def test_subclass_without_execute_fails(self) -> None:
        """Subclass missing execute() cannot be instantiated."""

        class IncompleteRuntime(BaseSandbox):
            def validate_code(self, code: str) -> bool:
                return True

        policy = ExecutionPolicy()
        session_id = "test-session"
        storage_adapter = DiskStorageAdapter(Path("workspace"))

        with pytest.raises(TypeError) as exc_info:
            IncompleteRuntime(policy, session_id, storage_adapter)  # type: ignore

        assert "Can't instantiate abstract class" in str(exc_info.value)
        assert "execute" in str(exc_info.value)

    def test_subclass_without_validate_code_fails(self) -> None:
        """Subclass missing validate_code() cannot be instantiated."""

        class IncompleteRuntime(BaseSandbox):
            def execute(self, code: str, **kwargs: Any) -> SandboxResult:
                return SandboxResult(
                    success=True,
                    stdout="",
                    stderr="",
                    exit_code=0,
                    fuel_consumed=None,
                    memory_used_bytes=0,
                    duration_ms=0.0,
                    files_created=[],
                    files_modified=[],
                    workspace_path="",
                    metadata={}
                )

        policy = ExecutionPolicy()
        session_id = "test-session"
        storage_adapter = DiskStorageAdapter(Path("workspace"))

        with pytest.raises(TypeError) as exc_info:
            IncompleteRuntime(policy, session_id, storage_adapter)  # type: ignore

        assert "Can't instantiate abstract class" in str(exc_info.value)
        assert "validate_code" in str(exc_info.value)

    def test_complete_subclass_can_be_instantiated(self) -> None:
        """Subclass implementing all abstract methods can be instantiated."""

        class CompleteRuntime(BaseSandbox):
            def execute(self, code: str, **kwargs: Any) -> SandboxResult:
                return SandboxResult(
                    success=True,
                    stdout="test output",
                    stderr="",
                    exit_code=0,
                    fuel_consumed=1000,
                    memory_used_bytes=1024,
                    duration_ms=5.0,
                    files_created=[],
                    files_modified=[],
                    workspace_path=str(self.workspace),
                    metadata={}
                )

            def validate_code(self, code: str) -> bool:
                return len(code) > 0

        policy = ExecutionPolicy()
        session_id = "test-session"
        storage_adapter = DiskStorageAdapter(Path("workspace"))

        runtime = CompleteRuntime(policy, session_id, storage_adapter)

        assert isinstance(runtime, BaseSandbox)
        assert runtime.policy == policy
        assert runtime.session_id == session_id
        assert runtime.workspace_root == Path("workspace")
        assert runtime.workspace == Path("workspace") / session_id
        assert isinstance(runtime.logger, SandboxLogger)


class TestBaseSandboxInitialization:
    """Test BaseSandbox initialization behavior."""

    def test_init_with_default_logger(self) -> None:
        """__init__ creates default SandboxLogger when logger=None."""

        class TestRuntime(BaseSandbox):
            def execute(self, code: str, **kwargs: Any) -> SandboxResult:
                return SandboxResult(
                    success=True, stdout="", stderr="", exit_code=0,
                    fuel_consumed=None, memory_used_bytes=0, duration_ms=0.0,
                    files_created=[], files_modified=[], workspace_path="", metadata={}
                )

            def validate_code(self, code: str) -> bool:
                return True

        policy = ExecutionPolicy()
        session_id = "test-session"
        storage_adapter = DiskStorageAdapter(Path("workspace"))

        runtime = TestRuntime(policy, session_id, storage_adapter)

        assert runtime.logger is not None
        assert isinstance(runtime.logger, SandboxLogger)

    def test_init_with_custom_logger(self) -> None:
        """__init__ uses provided SandboxLogger when logger is not None."""

        class TestRuntime(BaseSandbox):
            def execute(self, code: str, **kwargs: Any) -> SandboxResult:
                return SandboxResult(
                    success=True, stdout="", stderr="", exit_code=0,
                    fuel_consumed=None, memory_used_bytes=0, duration_ms=0.0,
                    files_created=[], files_modified=[], workspace_path="", metadata={}
                )

            def validate_code(self, code: str) -> bool:
                return True

        policy = ExecutionPolicy()
        session_id = "test-session"
        storage_adapter = DiskStorageAdapter(Path("workspace"))
        custom_logger = SandboxLogger()

        runtime = TestRuntime(policy, session_id, storage_adapter, custom_logger)

        assert runtime.logger is custom_logger

    def test_init_sets_policy_attribute(self) -> None:
        """__init__ sets self.policy from constructor argument."""

        class TestRuntime(BaseSandbox):
            def execute(self, code: str, **kwargs: Any) -> SandboxResult:
                return SandboxResult(
                    success=True, stdout="", stderr="", exit_code=0,
                    fuel_consumed=None, memory_used_bytes=0, duration_ms=0.0,
                    files_created=[], files_modified=[], workspace_path="", metadata={}
                )

            def validate_code(self, code: str) -> bool:
                return True

        policy = ExecutionPolicy(fuel_budget=1_000_000, memory_bytes=64_000_000)
        session_id = "test-session"
        storage_adapter = DiskStorageAdapter(Path("workspace"))

        runtime = TestRuntime(policy, session_id, storage_adapter)

        assert runtime.policy is policy
        assert runtime.policy.fuel_budget == 1_000_000
        assert runtime.policy.memory_bytes == 64_000_000

    def test_init_sets_workspace_attribute(self) -> None:
        """__init__ sets self.workspace_root and self.workspace from constructor arguments."""

        class TestRuntime(BaseSandbox):
            def execute(self, code: str, **kwargs: Any) -> SandboxResult:
                return SandboxResult(
                    success=True, stdout="", stderr="", exit_code=0,
                    fuel_consumed=None, memory_used_bytes=0, duration_ms=0.0,
                    files_created=[], files_modified=[], workspace_path="", metadata={}
                )

            def validate_code(self, code: str) -> bool:
                return True

        policy = ExecutionPolicy()
        session_id = "test-session-123"
        storage_adapter = DiskStorageAdapter(Path("custom/workspace"))

        runtime = TestRuntime(policy, session_id, storage_adapter)

        assert runtime.workspace_root == Path("custom/workspace")
        assert runtime.session_id == session_id
        assert runtime.workspace == Path("custom/workspace") / session_id
        assert runtime.workspace.parts[-1] == "test-session-123"


class TestBaseSandboxHelperMethods:
    """Test BaseSandbox helper methods."""

    def test_log_execution_metrics_calls_logger(self, mock_logger: MagicMock) -> None:
        """_log_execution_metrics calls logger.log_execution_complete."""
        sandbox = CompleteSandbox(
            policy=ExecutionPolicy(),
            session_id="test-session",
            storage_adapter=DiskStorageAdapter(Path("/tmp")),
            logger=SandboxLogger(mock_logger)
        )

        result = SandboxResult(
            success=True,
            stdout="Hello",
            stderr="",
            exit_code=0,
            fuel_consumed=5000,
            memory_used_bytes=2048,
            duration_ms=10.5,
            files_created=["output.txt"],
            files_modified=[],
            workspace_path="/tmp/test"
        )

        # Call the helper method
        sandbox._log_execution_metrics(result, "test-runtime")

        # Verify logger.info was called (structlog logs via info method)
        assert mock_logger.info.called
