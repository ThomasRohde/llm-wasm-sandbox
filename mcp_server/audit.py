"""
Audit Logging for MCP Server Security Events.

Provides comprehensive audit trails for security-relevant events,
compliance logging, and forensic analysis capabilities.
"""

from __future__ import annotations

import logging
from typing import Any

from sandbox.core.logging import SandboxLogger


class AuditLogger:
    """
    Audit logger for security and compliance events.

    Provides structured audit logging for:
    - Authentication/authorization events
    - Tool executions with security context
    - Rate limit violations
    - Session lifecycle events
    - Configuration changes
    - Security policy violations
    """

    def __init__(self, logger: Any = None):
        self.logger = logger or SandboxLogger("mcp-audit")

    def log_tool_execution(
        self,
        tool_name: str,
        client_id: str,
        session_id: str | None,
        success: bool,
        execution_time_ms: float,
        fuel_consumed: int,
        error_message: str | None = None,
        **extra: Any,
    ) -> None:
        """Log tool execution for audit purposes."""
        event_data = {
            "event_type": "tool_execution",
            "tool_name": tool_name,
            "client_id": client_id,
            "session_id": session_id,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "fuel_consumed": fuel_consumed,
            "error_message": error_message,
            **extra,
        }

        level = logging.INFO if success else logging.WARNING
        self.logger._emit(level, "mcp.audit.tool_execution", **event_data)

    def log_rate_limit_violation(
        self,
        client_id: str,
        request_count: int,
        limit: int,
        window_seconds: int,
        blocked_duration: float,
        **extra: Any,
    ) -> None:
        """Log rate limit violations."""
        event_data = {
            "event_type": "rate_limit_violation",
            "client_id": client_id,
            "request_count": request_count,
            "limit": limit,
            "window_seconds": window_seconds,
            "blocked_duration": blocked_duration,
            **extra,
        }

        self.logger._emit(logging.WARNING, "mcp.audit.rate_limit_violation", **event_data)

    def log_session_event(
        self,
        event_type: str,
        session_id: str,
        client_id: str,
        language: str | None = None,
        lifetime_seconds: float | None = None,
        **extra: Any,
    ) -> None:
        """Log session lifecycle events."""
        event_data = {
            "event_type": "session_event",
            "session_event_type": event_type,  # created, destroyed, expired
            "session_id": session_id,
            "client_id": client_id,
            "language": language,
            "lifetime_seconds": lifetime_seconds,
            **extra,
        }

        self.logger._emit(logging.INFO, "mcp.audit.session_event", **event_data)

    def log_security_violation(
        self,
        violation_type: str,
        client_id: str,
        details: dict[str, Any],
        severity: str = "medium",
        **extra: Any,
    ) -> None:
        """Log security violations."""
        event_data = {
            "event_type": "security_violation",
            "violation_type": violation_type,
            "client_id": client_id,
            "details": details,
            "severity": severity,
            **extra,
        }

        level = {
            "low": logging.INFO,
            "medium": logging.WARNING,
            "high": logging.ERROR,
            "critical": logging.CRITICAL,
        }.get(severity, logging.WARNING)

        self.logger._emit(level, "mcp.audit.security_violation", **event_data)

    def log_authentication_event(
        self,
        event_type: str,
        client_id: str,
        success: bool,
        auth_method: str | None = None,
        error_message: str | None = None,
        **extra: Any,
    ) -> None:
        """Log authentication events."""
        event_data = {
            "event_type": "authentication",
            "auth_event_type": event_type,  # login, logout, token_refresh
            "client_id": client_id,
            "success": success,
            "auth_method": auth_method,
            "error_message": error_message,
            **extra,
        }

        level = logging.INFO if success else logging.WARNING
        self.logger._emit(level, "mcp.audit.authentication", **event_data)

    def log_configuration_change(
        self,
        change_type: str,
        changed_by: str,
        old_value: Any,
        new_value: Any,
        config_section: str,
        **extra: Any,
    ) -> None:
        """Log configuration changes."""
        event_data = {
            "event_type": "configuration_change",
            "change_type": change_type,  # update, reset, reload
            "changed_by": changed_by,
            "old_value": old_value,
            "new_value": new_value,
            "config_section": config_section,
            **extra,
        }

        self.logger._emit(logging.INFO, "mcp.audit.configuration_change", **event_data)

    def log_system_event(
        self, event_type: str, details: dict[str, Any], severity: str = "info", **extra: Any
    ) -> None:
        """Log system-level events."""
        event_data = {
            "event_type": "system_event",
            "system_event_type": event_type,  # startup, shutdown, maintenance
            "details": details,
            "severity": severity,
            **extra,
        }

        level = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }.get(severity, logging.INFO)

        self.logger._emit(level, "mcp.audit.system_event", **event_data)
