"""Structured logging for sandbox execution events and security monitoring.

Provides SandboxLogger class that uses structlog for structured event emission
(execution.start, execution.complete, security events). Configures structlog
with console rendering by default but allows custom configuration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from sandbox.core.models import ExecutionPolicy, SandboxResult


def configure_structlog(level: int = logging.INFO, use_json: bool = False) -> None:
    """Configure structlog with sensible defaults for sandbox logging.

    Args:
        level: Minimum log level (default: logging.INFO)
        use_json: If True, use JSON renderer; otherwise use console renderer
    """
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if use_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class SandboxLogger:
    """Wrapper for structured logging of sandbox execution events.

    Accepts either structlog or standard logging.Logger instances and normalizes
    emission so callers do not need to care which backend is in use.
    """

    _PATH_TRUNCATION_SUFFIX = "...[truncated]"
    _MAX_PATH_LENGTH = 140

    def __init__(self, logger: Any = None) -> None:
        """Initialize SandboxLogger with optional custom logger.

        Args:
            logger: Optional structlog BoundLogger, logging.Logger, or string name.
                    If None, a default structlog logger named 'sandbox' is created.
                    If string, creates a structlog logger with that name.
        """
        if logger is None:
            self._logger = structlog.get_logger("sandbox")
        elif isinstance(logger, str):
            self._logger = structlog.get_logger(logger)
        else:
            self._logger = logger

    @property
    def logger(self) -> Any:
        """Expose the underlying logger instance (structlog or logging.Logger)."""
        return self._logger

    def _emit(self, level: int, message: str, **fields: Any) -> None:
        """Emit a log record regardless of logger backend."""
        extra = dict(fields)
        extra.setdefault("log_message", message)
        # Ensure event key is always present for downstream processors
        extra.setdefault("event", message.split(".", 1)[-1] if "." in message else message)
        extra.setdefault("event_type", extra.get("event"))

        if isinstance(self._logger, logging.Logger):
            # Standard logging expects structured data in the 'extra' mapping
            self._logger.log(level, message, extra=extra)
            return

        method_name = logging.getLevelName(level).lower()
        log_method = getattr(self._logger, method_name, None)
        if not callable(log_method):
            log_method = self._logger.info

        log_kwargs = dict(extra)
        event_value = log_kwargs.pop("event", None)
        event_arg = event_value if event_value is not None else message
        log_method(event_arg, **log_kwargs)

    def _truncate_path(self, path: str) -> str:
        """Truncate long file paths to keep logs concise."""
        if len(path) <= self._MAX_PATH_LENGTH:
            return path
        keep = self._MAX_PATH_LENGTH - len(self._PATH_TRUNCATION_SUFFIX)
        return f"{path[:keep]}{self._PATH_TRUNCATION_SUFFIX}"

    def log_execution_start(
        self, runtime: str, policy: ExecutionPolicy, session_id: str | None = None, **extra: Any
    ) -> None:
        """Log the start of a sandbox execution with policy details.

        Emits an INFO-level structured log event at execution.start with
        runtime type, fuel budget, memory limits, and custom extra fields.

        Args:
            runtime: Runtime type (e.g., "python", "javascript")
            policy: ExecutionPolicy containing resource limits
            session_id: Optional session identifier for session-aware executions
            **extra: Additional key-value pairs to include in log event
        """
        policy_snapshot = {
            "fuel_budget": policy.fuel_budget,
            "memory_bytes": policy.memory_bytes,
            "stdout_max_bytes": policy.stdout_max_bytes,
            "stderr_max_bytes": policy.stderr_max_bytes,
            "guest_mount_path": policy.guest_mount_path,
            "mount_data_dir": policy.mount_data_dir,
            "guest_data_path": policy.guest_data_path,
            "preserve_logs": getattr(policy, "preserve_logs", False),
        }

        log_kwargs: dict[str, Any] = {
            "event": "execution.start",
            "runtime": runtime,
            "policy": policy_snapshot,
            **policy_snapshot,
            **extra,
        }

        if session_id is not None:
            log_kwargs["session_id"] = session_id

        self._emit(logging.INFO, "sandbox.execution.start", **log_kwargs)

    def log_execution_complete(
        self, result: SandboxResult, runtime: str, session_id: str | None = None
    ) -> None:
        """Log the completion of a sandbox execution with result metrics.

        Emits an INFO-level structured log event at execution.complete with
        execution status, fuel consumed, memory usage, file operations,
        and duration.

        Args:
            result: SandboxResult containing execution metrics and outputs
            runtime: Runtime type (e.g., "python", "javascript")
            session_id: Optional session identifier for session-aware executions
        """
        files_created_paths = [self._truncate_path(p) for p in result.files_created]
        files_modified_paths = [self._truncate_path(p) for p in result.files_modified]

        log_kwargs: dict[str, Any] = {
            "event": "execution.complete",
            "runtime": runtime,
            "success": result.success,
            "exit_code": result.exit_code,
            "fuel_consumed": result.fuel_consumed,
            "memory_used_bytes": result.memory_used_bytes,
            "duration_ms": result.duration_ms,
            "stdout_bytes": len(result.stdout),
            "stderr_bytes": len(result.stderr),
            "files_created_count": len(result.files_created),
            "files_modified_count": len(result.files_modified),
            "files_created_paths": files_created_paths,
            "files_modified_paths": files_modified_paths,
        }

        stdout_truncated = result.metadata.get("stdout_truncated")
        stderr_truncated = result.metadata.get("stderr_truncated")
        trap_reason = result.metadata.get("trap_reason")
        if stdout_truncated is not None:
            log_kwargs["stdout_truncated"] = stdout_truncated
        if stderr_truncated is not None:
            log_kwargs["stderr_truncated"] = stderr_truncated
        if trap_reason is not None:
            log_kwargs["trap_reason"] = trap_reason

        if session_id is not None:
            log_kwargs["session_id"] = session_id

        self._emit(logging.INFO, "sandbox.execution.complete", **log_kwargs)

    def log_security_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log a security-relevant event at WARNING level.

        Emits a WARNING-level structured log for security monitoring,
        such as fuel exhaustion, filesystem access denials, memory limit
        violations, or suspicious behavior patterns.

        Args:
            event_type: Type of security event (e.g., "fuel_exhausted",
                       "fs_access_denied", "memory_limit_exceeded")
            details: Dict containing event-specific details
        """
        event = f"security.{event_type}"
        self._emit(logging.WARNING, f"sandbox.{event}", event=event, **details)

    def log_session_created(self, session_id: str, workspace_path: str) -> None:
        """Log the creation of a new session workspace.

        Emits an INFO-level structured log event at session.created with
        session identifier and workspace path.

        Args:
            session_id: UUIDv4 session identifier
            workspace_path: Absolute path to session workspace directory
        """
        self._emit(
            logging.INFO,
            "sandbox.session.created",
            event="session.created",
            session_id=session_id,
            workspace_path=workspace_path,
        )

    def log_session_retrieved(self, session_id: str, workspace_path: str) -> None:
        """Log retrieval of an existing session workspace.

        Emits an INFO-level structured log event at session.retrieved with
        session identifier and workspace path.

        Args:
            session_id: UUIDv4 session identifier
            workspace_path: Absolute path to session workspace directory
        """
        self._emit(
            logging.INFO,
            "sandbox.session.retrieved",
            event="session.retrieved",
            session_id=session_id,
            workspace_path=workspace_path,
        )

    def log_session_deleted(self, session_id: str) -> None:
        """Log deletion of a session workspace.

        Emits an INFO-level structured log event at session.deleted with
        session identifier.

        Args:
            session_id: UUIDv4 session identifier
        """
        self._emit(
            logging.INFO, "sandbox.session.deleted", event="session.deleted", session_id=session_id
        )

    def log_file_operation(self, operation: str, session_id: str, path: str, **kwargs: Any) -> None:
        """Log a session file operation.

        Emits an INFO-level structured log event for file operations
        (list, read, write, delete) with operation-specific metadata.

        Args:
            operation: Operation type ("list", "read", "write", "delete")
            session_id: UUIDv4 session identifier
            path: Relative path within session workspace
            **kwargs: Operation-specific metadata:
                - file_size: Size in bytes for read/write operations
                - file_count: Number of files for list operations
                - recursive: Boolean flag for delete operations
        """
        event = f"session.file.{operation}"
        self._emit(
            logging.INFO,
            f"sandbox.{event}",
            event=event,
            session_id=session_id,
            path=path,
            **kwargs,
        )

    def log_session_metadata_created(self, session_id: str, created_at: str) -> None:
        """Log creation of session metadata.

        Emits an INFO-level structured log event when .metadata.json is
        created for a new session.

        Args:
            session_id: UUIDv4 session identifier
            created_at: ISO 8601 UTC timestamp when session was created
        """
        self._emit(
            logging.INFO,
            "sandbox.session.metadata.created",
            event="session.metadata.created",
            session_id=session_id,
            created_at=created_at,
        )

    def log_session_metadata_updated(self, session_id: str, timestamp: str) -> None:
        """Log update of session metadata timestamp.

        Emits an INFO-level structured log event when session metadata
        updated_at timestamp is refreshed.

        Args:
            session_id: UUIDv4 session identifier
            timestamp: ISO 8601 UTC timestamp of the update
        """
        self._emit(
            logging.INFO,
            "sandbox.session.metadata.updated",
            event="session.metadata.updated",
            session_id=session_id,
            timestamp=timestamp,
        )

    def log_prune_started(self, threshold_hours: float, workspace_root: str, dry_run: bool) -> None:
        """Log the start of a pruning operation.

        Emits an INFO-level structured log event when pruning begins.

        Args:
            threshold_hours: Age threshold in hours
            workspace_root: Root directory for session workspaces
            dry_run: Whether this is a dry-run (no actual deletions)
        """
        self._emit(
            logging.INFO,
            "sandbox.session.prune.started",
            event="session.prune.started",
            threshold_hours=threshold_hours,
            workspace_root=workspace_root,
            dry_run=dry_run,
        )

    def log_prune_candidate(
        self, session_id: str, age_hours: float, threshold_hours: float
    ) -> None:
        """Log a session identified as a pruning candidate.

        Emits an INFO-level structured log event for each session that
        meets the age threshold for deletion.

        Args:
            session_id: UUIDv4 session identifier
            age_hours: Age of session in hours
            threshold_hours: Age threshold for pruning
        """
        self._emit(
            logging.INFO,
            "sandbox.session.prune.candidate",
            event="session.prune.candidate",
            session_id=session_id,
            age_hours=age_hours,
            threshold_hours=threshold_hours,
        )

    def log_prune_deleted(self, session_id: str, age_hours: float, reclaimed_bytes: int) -> None:
        """Log successful deletion of a session workspace.

        Emits an INFO-level structured log event after a session is deleted
        during pruning.

        Args:
            session_id: UUIDv4 session identifier
            age_hours: Age of session in hours
            reclaimed_bytes: Disk space reclaimed in bytes
        """
        self._emit(
            logging.INFO,
            "sandbox.session.prune.deleted",
            event="session.prune.deleted",
            session_id=session_id,
            age_hours=age_hours,
            reclaimed_bytes=reclaimed_bytes,
        )

    def log_prune_skipped(self, session_id: str, reason: str) -> None:
        """Log a session that was skipped during pruning.

        Emits a WARNING-level structured log event for sessions that could
        not be pruned (missing metadata, corrupted timestamps, etc.).

        Args:
            session_id: UUIDv4 session identifier
            reason: Reason for skipping (e.g., "missing_metadata")
        """
        self._emit(
            logging.WARNING,
            "sandbox.session.prune.skipped",
            event="session.prune.skipped",
            session_id=session_id,
            reason=reason,
        )

    def log_prune_error(self, session_id: str, error: str) -> None:
        """Log an error that occurred during session deletion.

        Emits an ERROR-level structured log event when deletion fails.

        Args:
            session_id: UUIDv4 session identifier
            error: Error message from deletion attempt
        """
        self._emit(
            logging.ERROR,
            "sandbox.session.prune.error",
            event="session.prune.error",
            session_id=session_id,
            error=error,
        )

    def log_prune_completed(
        self,
        deleted_count: int,
        skipped_count: int,
        error_count: int,
        reclaimed_bytes: int,
        dry_run: bool,
    ) -> None:
        """Log completion of pruning operation with summary statistics.

        Emits an INFO-level structured log event when pruning completes.

        Args:
            deleted_count: Number of sessions deleted
            skipped_count: Number of sessions skipped
            error_count: Number of deletion errors
            reclaimed_bytes: Total disk space reclaimed in bytes
            dry_run: Whether this was a dry-run
        """
        self._emit(
            logging.INFO,
            "sandbox.session.prune.completed",
            event="session.prune.completed",
            deleted_count=deleted_count,
            skipped_count=skipped_count,
            error_count=error_count,
            reclaimed_bytes=reclaimed_bytes,
            dry_run=dry_run,
        )
