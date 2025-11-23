"""
MCP Server Performance Monitoring and Metrics.

Provides metrics collection for MCP server performance monitoring,
including tool execution times, session management, error rates,
and resource usage statistics.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from sandbox.core.logging import SandboxLogger


@dataclass
class MCPMetrics:
    """Metrics collected for MCP server performance monitoring."""

    # Tool execution metrics
    tool_execution_count: int = 0
    tool_execution_total_time: float = 0.0
    tool_execution_times: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    tool_error_count: int = 0
    tool_errors: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    # Session management metrics
    session_created_count: int = 0
    session_destroyed_count: int = 0
    session_active_count: int = 0
    session_lifetime_total: float = 0.0
    session_lifetimes: list[float] = field(default_factory=list)

    # Transport metrics
    http_request_count: int = 0
    http_request_total_time: float = 0.0
    http_error_count: int = 0
    stdio_message_count: int = 0

    # Resource usage metrics
    peak_memory_usage: int = 0
    total_fuel_consumed: int = 0
    total_execution_time: float = 0.0

    # Performance percentiles (calculated on demand)
    _tool_execution_percentiles: dict[str, dict[str, float]] | None = None

    def record_tool_execution(self, tool_name: str, duration: float, success: bool) -> None:
        """Record a tool execution."""
        self.tool_execution_count += 1
        self.tool_execution_total_time += duration
        self.tool_execution_times[tool_name].append(duration)

        if not success:
            self.tool_error_count += 1
            self.tool_errors[tool_name] += 1

        # Keep only last 1000 executions per tool for memory efficiency
        if len(self.tool_execution_times[tool_name]) > 1000:
            self.tool_execution_times[tool_name] = self.tool_execution_times[tool_name][-1000:]

        # Invalidate cached percentiles
        self._tool_execution_percentiles = None

    def record_session_created(self) -> None:
        """Record session creation."""
        self.session_created_count += 1
        self.session_active_count += 1

    def record_session_destroyed(self, lifetime: float) -> None:
        """Record session destruction."""
        self.session_destroyed_count += 1
        self.session_active_count = max(0, self.session_active_count - 1)
        self.session_lifetime_total += lifetime
        self.session_lifetimes.append(lifetime)

        # Keep only last 1000 lifetimes
        if len(self.session_lifetimes) > 1000:
            self.session_lifetimes = self.session_lifetimes[-1000:]

    def record_http_request(self, duration: float, success: bool) -> None:
        """Record an HTTP request."""
        self.http_request_count += 1
        self.http_request_total_time += duration
        if not success:
            self.http_error_count += 1

    def record_stdio_message(self) -> None:
        """Record a stdio message."""
        self.stdio_message_count += 1

    def record_resource_usage(self, fuel_consumed: int, execution_time: float, memory_used: int) -> None:
        """Record resource usage from sandbox execution."""
        self.total_fuel_consumed += fuel_consumed
        self.total_execution_time += execution_time
        self.peak_memory_usage = max(self.peak_memory_usage, memory_used)

    def get_tool_execution_percentiles(self, tool_name: str | None = None) -> dict[str, dict[str, float]]:
        """Get execution time percentiles for tools."""
        if self._tool_execution_percentiles is None:
            self._calculate_percentiles()

        if tool_name:
            return {tool_name: self._tool_execution_percentiles.get(tool_name, {})}
        return dict(self._tool_execution_percentiles)

    def _calculate_percentiles(self) -> None:
        """Calculate percentiles for tool execution times."""
        self._tool_execution_percentiles = {}

        for tool_name, times in self.tool_execution_times.items():
            if not times:
                continue

            sorted_times = sorted(times)
            n = len(sorted_times)

            self._tool_execution_percentiles[tool_name] = {
                "p50": sorted_times[n // 2],
                "p95": sorted_times[int(n * 0.95)],
                "p99": sorted_times[int(n * 0.99)] if n >= 100 else sorted_times[-1],
                "min": sorted_times[0],
                "max": sorted_times[-1],
                "avg": sum(sorted_times) / n,
                "count": n,
            }

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all metrics."""
        avg_tool_time = (
            self.tool_execution_total_time / self.tool_execution_count
            if self.tool_execution_count > 0
            else 0.0
        )

        avg_session_lifetime = (
            self.session_lifetime_total / self.session_destroyed_count
            if self.session_destroyed_count > 0
            else 0.0
        )

        avg_http_time = (
            self.http_request_total_time / self.http_request_count
            if self.http_request_count > 0
            else 0.0
        )

        return {
            "tool_executions": {
                "total_count": self.tool_execution_count,
                "error_count": self.tool_error_count,
                "error_rate": self.tool_error_count / self.tool_execution_count if self.tool_execution_count > 0 else 0.0,
                "average_time_ms": avg_tool_time * 1000,
                "total_time_ms": self.tool_execution_total_time * 1000,
                "errors_by_tool": dict(self.tool_errors),
            },
            "sessions": {
                "active_count": self.session_active_count,
                "created_count": self.session_created_count,
                "destroyed_count": self.session_destroyed_count,
                "average_lifetime_seconds": avg_session_lifetime,
            },
            "transport": {
                "http_requests": {
                    "total_count": self.http_request_count,
                    "error_count": self.http_error_count,
                    "error_rate": self.http_error_count / self.http_request_count if self.http_request_count > 0 else 0.0,
                    "average_time_ms": avg_http_time * 1000,
                },
                "stdio_messages": self.stdio_message_count,
            },
            "resources": {
                "total_fuel_consumed": self.total_fuel_consumed,
                "total_execution_time_seconds": self.total_execution_time,
                "peak_memory_usage_bytes": self.peak_memory_usage,
            },
            "tool_percentiles": self.get_tool_execution_percentiles(),
        }


class MCPMetricsCollector:
    """Collector for MCP server metrics with timing utilities."""

    def __init__(self):
        self.metrics = MCPMetrics()
        self.logger = SandboxLogger("mcp-metrics")

    @contextmanager
    def time_tool_execution(self, tool_name: str) -> Generator[None, None, None]:
        """Context manager to time tool execution."""
        start_time = time.perf_counter()
        try:
            yield
            success = True
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.metrics.record_tool_execution(tool_name, duration, success)
            self.logger._emit(
                logging.INFO,
                "mcp.tool.executed",
                tool_name=tool_name,
                duration_ms=duration * 1000,
                success=success,
            )

    @contextmanager
    def time_http_request(self) -> Generator[None, None, None]:
        """Context manager to time HTTP requests."""
        start_time = time.perf_counter()
        try:
            yield
            success = True
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.metrics.record_http_request(duration, success)

    def record_session_created(self) -> None:
        """Record session creation."""
        self.metrics.record_session_created()
        self.logger._emit(logging.INFO, "mcp.session.created")

    def record_session_destroyed(self, lifetime: float) -> None:
        """Record session destruction."""
        self.metrics.record_session_destroyed(lifetime)
        self.logger._emit(logging.INFO, "mcp.session.destroyed", lifetime_seconds=lifetime)

    def record_stdio_message(self) -> None:
        """Record stdio message."""
        self.metrics.record_stdio_message()

    def record_resource_usage(self, fuel_consumed: int, execution_time: float, memory_used: int) -> None:
        """Record resource usage from sandbox execution."""
        self.metrics.record_resource_usage(fuel_consumed, execution_time, memory_used)

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        return self.metrics.get_summary()

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        self.metrics = MCPMetrics()
        self.logger._emit(logging.INFO, "mcp.metrics.reset")
