"""
Rate Limiting and Abuse Prevention for MCP Server.

Provides rate limiting, abuse detection, and request throttling
to prevent DoS attacks and ensure fair resource usage.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sandbox.core.logging import SandboxLogger


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_window: int = 100
    window_seconds: int = 60
    burst_limit: int = 20
    cooldown_seconds: int = 300  # 5 minutes cooldown after violation


@dataclass
class ClientState:
    """State tracking for a client."""

    request_times: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    violation_count: int = 0
    last_violation_time: float = 0.0
    blocked_until: float = 0.0

    @property
    def is_blocked(self) -> bool:
        """Check if client is currently blocked."""
        return time.time() < self.blocked_until

    def record_request(self) -> None:
        """Record a request."""
        self.request_times.append(time.time())

    def get_requests_in_window(self, window_seconds: int) -> int:
        """Get number of requests in the last window."""
        cutoff = time.time() - window_seconds
        # Remove old requests
        while self.request_times and self.request_times[0] < cutoff:
            self.request_times.popleft()
        return len(self.request_times)

    def record_violation(self, cooldown_seconds: int) -> None:
        """Record a rate limit violation."""
        self.violation_count += 1
        self.last_violation_time = time.time()
        self.blocked_until = time.time() + cooldown_seconds


class RateLimiter:
    """
    Rate limiter with sliding window and abuse prevention.

    Tracks requests per client and enforces rate limits with progressive
    penalties for violations.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self.logger = SandboxLogger("mcp-rate-limiter")
        self.clients: dict[str, ClientState] = {}
        self._cleanup_task: asyncio.Task | None = None

    def get_client_key(self, request: Any) -> str:
        """
        Extract client identifier from request.

        For HTTP requests, this could be IP address or user ID.
        For stdio, it might be a session identifier.
        """
        # Default implementation - override for specific transports
        return "default_client"

    async def check_rate_limit(self, client_key: str) -> tuple[bool, float]:
        """
        Check if request should be allowed.

        Returns (allowed, retry_after_seconds)
        """
        now = time.time()
        client = self.clients.get(client_key)

        if client is None:
            client = ClientState()
            self.clients[client_key] = client

        # Check if client is blocked
        if client.is_blocked:
            retry_after = client.blocked_until - now
            return False, retry_after

        # Record the request
        client.record_request()

        # Check rate limit
        requests_in_window = client.get_requests_in_window(self.config.window_seconds)

        if requests_in_window > self.config.requests_per_window:
            # Rate limit exceeded
            client.record_violation(self.config.cooldown_seconds)
            self.logger._emit(
                logging.WARNING,
                "mcp.rate_limit.exceeded",
                client_key=client_key,
                requests_in_window=requests_in_window,
                limit=self.config.requests_per_window,
                violation_count=client.violation_count,
            )
            return False, self.config.cooldown_seconds

        # Check burst limit (requests in last few seconds)
        recent_requests = client.get_requests_in_window(10)  # Last 10 seconds
        if recent_requests > self.config.burst_limit:
            # Burst limit exceeded - temporary block
            client.blocked_until = now + 30  # 30 second block
            self.logger._emit(
                logging.WARNING,
                "mcp.burst_limit.exceeded",
                client_key=client_key,
                recent_requests=recent_requests,
                burst_limit=self.config.burst_limit,
            )
            return False, 30.0

        return True, 0.0

    def get_client_stats(self, client_key: str) -> dict[str, Any] | None:
        """Get statistics for a client."""
        client = self.clients.get(client_key)
        if not client:
            return None

        now = time.time()
        return {
            "requests_in_window": client.get_requests_in_window(self.config.window_seconds),
            "total_requests": len(client.request_times),
            "violation_count": client.violation_count,
            "is_blocked": client.is_blocked,
            "blocked_until": client.blocked_until,
            "time_until_unblock": max(0, client.blocked_until - now) if client.is_blocked else 0,
        }

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all clients."""
        time.time()
        client_stats = {}

        for client_key, _client in self.clients.items():
            client_stats[client_key] = self.get_client_stats(client_key)

        return {
            "total_clients": len(self.clients),
            "blocked_clients": sum(1 for c in self.clients.values() if c.is_blocked),
            "total_violations": sum(c.violation_count for c in self.clients.values()),
            "client_stats": client_stats,
            "config": {
                "requests_per_window": self.config.requests_per_window,
                "window_seconds": self.config.window_seconds,
                "burst_limit": self.config.burst_limit,
                "cooldown_seconds": self.config.cooldown_seconds,
            },
        }

    async def cleanup_old_clients(self) -> None:
        """Remove clients that haven't made requests recently."""
        now = time.time()
        cutoff = now - (self.config.window_seconds * 2)  # 2x window size

        to_remove = []
        for client_key, client in self.clients.items():
            if client.request_times and client.request_times[-1] < cutoff:
                to_remove.append(client_key)

        for client_key in to_remove:
            del self.clients[client_key]

        if to_remove:
            self.logger._emit(
                logging.INFO, "mcp.rate_limiter.cleanup", removed_clients=len(to_remove)
            )

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of old client data."""
        while True:
            await asyncio.sleep(300)  # Clean up every 5 minutes
            await self.cleanup_old_clients()


class HTTPRateLimiter(RateLimiter):
    """Rate limiter for HTTP transport using IP addresses."""

    def get_client_key(self, request: Any) -> str:
        """Extract client IP from HTTP request."""
        # This would need to be implemented based on the actual HTTP framework
        # For now, return a default
        return (
            getattr(request, "client", {}).get("host", "unknown")
            if hasattr(request, "client")
            else "unknown"
        )


class StdioRateLimiter(RateLimiter):
    """Rate limiter for stdio transport using session/process IDs."""

    def __init__(self, config: RateLimitConfig | None = None, session_id: str | None = None):
        super().__init__(config)
        self.session_id = session_id or "stdio_default"

    def get_client_key(self, request: Any) -> str:
        """Use session ID for stdio transport."""
        return self.session_id
