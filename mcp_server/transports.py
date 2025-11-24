"""
MCP Server Transport Implementations.

Transport abstractions for MCP server communication.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class TransportType(Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"


class TransportConfig:
    """Base configuration for MCP transports."""

    def __init__(self, transport_type: TransportType):
        self.transport_type = transport_type


class StdioTransportConfig(TransportConfig):
    """Configuration for stdio transport."""

    def __init__(self) -> None:
        super().__init__(TransportType.STDIO)


class HTTPTransportConfig(TransportConfig):
    """Configuration for HTTP transport."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        path: str = "/mcp",
        cors_origins: list[str] | None = None,
        auth_token: str | None = None,
        rate_limit_requests: int = 100,
        rate_limit_window_seconds: int = 60,
        max_concurrent_requests: int = 10,
        request_timeout_seconds: int = 30,
        max_request_size_mb: int = 10,
    ):
        super().__init__(TransportType.HTTP)
        self.host = host
        self.port = port
        self.path = path
        self.cors_origins = cors_origins or ["*"]
        self.auth_token = auth_token
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self.max_concurrent_requests = max_concurrent_requests
        self.request_timeout_seconds = request_timeout_seconds
        self.max_request_size_mb = max_request_size_mb

    def get_uvicorn_config(self) -> dict[str, Any]:
        """Get uvicorn configuration for this transport."""
        return {
            "host": self.host,
            "port": self.port,
            "access_log": True,
            "log_level": "info",
            "limit_concurrency": self.max_concurrent_requests,
            "timeout_keep_alive": self.request_timeout_seconds,
            # Security limits
            "limit_max_requests": self.rate_limit_requests * 10,  # Allow some burst
        }

    def get_cors_middleware_class(self) -> type:
        """Get CORS middleware class for adding to Starlette app."""
        from starlette.middleware.cors import CORSMiddleware

        return CORSMiddleware
