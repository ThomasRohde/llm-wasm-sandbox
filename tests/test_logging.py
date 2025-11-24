"""Tests for sandbox.core.logging module.

Verifies SandboxLogger functionality with structlog including
structured event logging, key-value pairs, and event emission.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
import structlog

from sandbox.core.logging import SandboxLogger, configure_structlog
from sandbox.core.models import ExecutionPolicy, SandboxResult


class StructlogCapture:
    """Helper to capture structlog events."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        """Capture event dict (structlog processor signature)."""
        self.events.append(event_dict.copy())
        return event_dict


@pytest.fixture
def log_capture() -> StructlogCapture:
    """Fixture providing structlog event capture."""
    return StructlogCapture()


@pytest.fixture
def custom_logger(log_capture: StructlogCapture) -> Any:
    """Fixture providing a structlog logger with capture processor."""
    # Configure structlog with capture processor
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            log_capture,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    return structlog.get_logger("test_sandbox")


@pytest.fixture
def std_logger() -> logging.Logger:
    """Fixture providing a standard library logger for compatibility tests."""
    logger = logging.getLogger("sandbox-test-logger")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = True
    return logger


def test_configure_structlog_console_renderer() -> None:
    """Test structlog configuration with console renderer."""
    configure_structlog(use_json=False)

    # Verify configuration was applied
    logger = structlog.get_logger()
    assert logger is not None


def test_configure_structlog_json_renderer() -> None:
    """Test structlog configuration with JSON renderer."""
    configure_structlog(use_json=True)

    # Verify configuration was applied
    logger = structlog.get_logger()
    assert logger is not None


def test_sandbox_logger_wraps_provided_logger(custom_logger: Any) -> None:
    """Test SandboxLogger accepts and wraps a custom logger."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    # Should wrap the provided logger
    assert sandbox_logger._logger is custom_logger


def test_sandbox_logger_creates_default_logger() -> None:
    """Test SandboxLogger creates default logger if none provided."""
    sandbox_logger = SandboxLogger()

    # Should create structlog logger
    assert sandbox_logger._logger is not None


def test_sandbox_logger_accepts_standard_logging_logger(
    std_logger: logging.Logger, caplog: pytest.LogCaptureFixture
) -> None:
    """Test SandboxLogger works with a standard logging.Logger."""
    sandbox_logger = SandboxLogger(logger=std_logger)
    policy = ExecutionPolicy()

    with caplog.at_level(logging.INFO, logger=std_logger.name):
        sandbox_logger.log_execution_start(runtime="python", policy=policy, workspace="/tmp/test")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.event == "execution.start"
    assert record.runtime == "python"
    assert record.log_message == "sandbox.execution.start"


def test_log_execution_start_structure(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test execution.start log event structure and content."""
    sandbox_logger = SandboxLogger(logger=custom_logger)
    policy = ExecutionPolicy(
        fuel_budget=500_000_000,
        memory_bytes=64_000_000,
        stdout_max_bytes=1_000_000,
        stderr_max_bytes=500_000,
        guest_mount_path="/app",
    )

    # Log execution start with extra fields
    sandbox_logger.log_execution_start(
        runtime="python", policy=policy, trace_id="test-trace-123", user_id="test-user"
    )

    # Verify event was captured
    assert len(log_capture.events) == 1
    event = log_capture.events[0]

    # Verify log level and event type
    assert event["level"] == "info"
    assert event["event"] == "execution.start"
    assert event["log_message"] == "sandbox.execution.start"

    # Verify structured data
    assert event["runtime"] == "python"
    assert event["fuel_budget"] == 500_000_000
    assert event["memory_bytes"] == 64_000_000
    assert event["stdout_max_bytes"] == 1_000_000
    assert event["stderr_max_bytes"] == 500_000
    assert event["guest_mount_path"] == "/app"
    assert event["policy"]["fuel_budget"] == 500_000_000

    # Verify extra fields passed through
    assert event["trace_id"] == "test-trace-123"
    assert event["user_id"] == "test-user"


def test_log_execution_complete_success_structure(
    custom_logger: Any, log_capture: StructlogCapture
) -> None:
    """Test execution.complete log event for successful execution."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    result = SandboxResult(
        success=True,
        stdout="Hello, world!\n",
        stderr="",
        exit_code=0,
        fuel_consumed=125_000,
        memory_used_bytes=8_000_000,
        duration_ms=42.5,
        files_created=["output.txt"],
        files_modified=["data.json"],
        workspace_path="/workspace",
    )

    sandbox_logger.log_execution_complete(result, runtime="python")

    # Verify event
    assert len(log_capture.events) == 1
    event = log_capture.events[0]

    assert event["level"] == "info"
    assert event["event"] == "execution.complete"
    assert event["log_message"] == "sandbox.execution.complete"

    # Verify structured data
    assert event["runtime"] == "python"
    assert event["success"] is True
    assert event["exit_code"] == 0
    assert event["fuel_consumed"] == 125_000
    assert event["memory_used_bytes"] == 8_000_000
    assert event["duration_ms"] == 42.5
    assert event["stdout_bytes"] == len("Hello, world!\n")
    assert event["stderr_bytes"] == 0
    assert event["files_created_count"] == 1
    assert event["files_modified_count"] == 1
    assert event["files_created_paths"] == ["output.txt"]
    assert event["files_modified_paths"] == ["data.json"]


def test_log_execution_complete_truncates_long_paths(
    custom_logger: Any, log_capture: StructlogCapture
) -> None:
    """Test filesystem delta logging truncates very long paths."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    long_name = "nested/" + ("a" * 180) + ".txt"
    result = SandboxResult(
        success=True,
        stdout="",
        stderr="",
        exit_code=0,
        fuel_consumed=None,
        memory_used_bytes=123,
        duration_ms=1.0,
        files_created=[long_name],
        files_modified=[],
        workspace_path="/workspace",
    )

    sandbox_logger.log_execution_complete(result, runtime="python")

    event = log_capture.events[0]
    assert event["files_created_count"] == 1
    truncated_path = event["files_created_paths"][0]
    assert truncated_path.endswith(SandboxLogger._PATH_TRUNCATION_SUFFIX)
    assert len(truncated_path) <= SandboxLogger._MAX_PATH_LENGTH


def test_log_execution_complete_failure_structure(
    custom_logger: Any, log_capture: StructlogCapture
) -> None:
    """Test execution.complete log event for failed execution."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    result = SandboxResult(
        success=False,
        stdout="",
        stderr="ZeroDivisionError: division by zero\n",
        exit_code=1,
        fuel_consumed=50_000,
        memory_used_bytes=4_000_000,
        duration_ms=15.0,
        files_created=[],
        files_modified=[],
        workspace_path="/workspace",
    )

    sandbox_logger.log_execution_complete(result, runtime="python")

    # Verify event
    assert len(log_capture.events) == 1
    event = log_capture.events[0]

    assert event["level"] == "info"
    assert event["event"] == "execution.complete"
    assert event["success"] is False
    assert event["exit_code"] == 1


def test_log_security_event_structure(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test security event logging at WARNING level."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    details = {
        "fuel_budget": 400_000_000,
        "fuel_consumed": 400_000_000,
        "code_snippet": "while True: pass",
    }

    sandbox_logger.log_security_event(event_type="fuel_exhausted", details=details)

    # Verify event
    assert len(log_capture.events) == 1
    event = log_capture.events[0]

    # Security events should be WARNING level
    assert event["level"] == "warning"
    assert event["event"] == "security.fuel_exhausted"
    assert event["log_message"] == "sandbox.security.fuel_exhausted"

    # Verify structured data
    assert event["fuel_budget"] == 400_000_000
    assert event["fuel_consumed"] == 400_000_000
    assert event["code_snippet"] == "while True: pass"


def test_log_security_event_fs_access_denied(
    custom_logger: Any, log_capture: StructlogCapture
) -> None:
    """Test security event for filesystem access denial."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    details = {"attempted_path": "/etc/passwd", "allowed_paths": ["/app"], "operation": "read"}

    sandbox_logger.log_security_event(event_type="fs_access_denied", details=details)

    event = log_capture.events[0]

    assert event["level"] == "warning"
    assert event["event"] == "security.fs_access_denied"
    assert event["attempted_path"] == "/etc/passwd"
    assert event["allowed_paths"] == ["/app"]
    assert event["operation"] == "read"


def test_multiple_extra_fields_in_execution_start(
    custom_logger: Any, log_capture: StructlogCapture
) -> None:
    """Test multiple custom extra fields in execution.start."""
    sandbox_logger = SandboxLogger(logger=custom_logger)
    policy = ExecutionPolicy()

    sandbox_logger.log_execution_start(
        runtime="python",
        policy=policy,
        span_id="span-456",
        parent_span_id="span-123",
        correlation_id="corr-789",
        request_id="req-abc",
    )

    event = log_capture.events[0]
    assert event["event"] == "execution.start"
    assert event["log_message"] == "sandbox.execution.start"

    # Verify all extra fields are attached
    assert event["span_id"] == "span-456"
    assert event["parent_span_id"] == "span-123"
    assert event["correlation_id"] == "corr-789"
    assert event["request_id"] == "req-abc"


def test_log_execution_start_with_session_id(
    custom_logger: Any, log_capture: StructlogCapture
) -> None:
    """Test execution.start includes session_id when provided."""
    sandbox_logger = SandboxLogger(logger=custom_logger)
    policy = ExecutionPolicy()

    sandbox_logger.log_execution_start(
        runtime="python", policy=policy, session_id="test-session-123"
    )

    event = log_capture.events[0]
    assert event["session_id"] == "test-session-123"


def test_log_execution_complete_with_session_id(
    custom_logger: Any, log_capture: StructlogCapture
) -> None:
    """Test execution.complete includes session_id when provided."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    result = SandboxResult(
        success=True,
        stdout="",
        stderr="",
        exit_code=0,
        fuel_consumed=100_000,
        memory_used_bytes=5_000_000,
        duration_ms=10.0,
        files_created=[],
        files_modified=[],
        workspace_path="/workspace",
    )

    sandbox_logger.log_execution_complete(result, runtime="python", session_id="test-session-456")

    event = log_capture.events[0]
    assert event["session_id"] == "test-session-456"


def test_log_session_created(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test session.created log event."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    sandbox_logger.log_session_created(
        session_id="session-abc-123", workspace_path="/workspace/session-abc-123"
    )

    assert len(log_capture.events) == 1
    event = log_capture.events[0]

    assert event["level"] == "info"
    assert event["event"] == "session.created"
    assert event["log_message"] == "sandbox.session.created"
    assert event["session_id"] == "session-abc-123"
    assert event["workspace_path"] == "/workspace/session-abc-123"


def test_log_session_retrieved(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test session.retrieved log event."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    sandbox_logger.log_session_retrieved(
        session_id="session-def-456", workspace_path="/workspace/session-def-456"
    )

    event = log_capture.events[0]
    assert event["event"] == "session.retrieved"
    assert event["session_id"] == "session-def-456"


def test_log_session_deleted(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test session.deleted log event."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    sandbox_logger.log_session_deleted(session_id="session-ghi-789")

    event = log_capture.events[0]
    assert event["event"] == "session.deleted"
    assert event["session_id"] == "session-ghi-789"


def test_log_file_operation_write(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test session.file.write log event."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    sandbox_logger.log_file_operation(
        operation="write", session_id="session-123", path="data/output.txt", file_size=1024
    )

    event = log_capture.events[0]
    assert event["event"] == "session.file.write"
    assert event["session_id"] == "session-123"
    assert event["path"] == "data/output.txt"
    assert event["file_size"] == 1024


def test_log_file_operation_list(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test session.file.list log event."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    sandbox_logger.log_file_operation(
        operation="list", session_id="session-456", path="data/", file_count=5
    )

    event = log_capture.events[0]
    assert event["event"] == "session.file.list"
    assert event["file_count"] == 5


def test_log_file_operation_delete(custom_logger: Any, log_capture: StructlogCapture) -> None:
    """Test session.file.delete log event."""
    sandbox_logger = SandboxLogger(logger=custom_logger)

    sandbox_logger.log_file_operation(
        operation="delete", session_id="session-789", path="temp/", recursive=True
    )

    event = log_capture.events[0]
    assert event["event"] == "session.file.delete"
    assert event["recursive"] is True
