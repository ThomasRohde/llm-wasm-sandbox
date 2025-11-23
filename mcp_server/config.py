"""
MCP Server Configuration.

Configuration models for the MCP server.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server identification and metadata."""

    name: str = "llm-wasm-sandbox"
    version: str = "0.1.0"
    instructions: str = (
        "This server provides secure code execution in a WebAssembly sandbox. "
        "Use the execute_code tool to run Python or JavaScript code safely."
    )


class StdioTransportConfig(BaseModel):
    """Configuration for stdio transport."""

    enabled: bool = True


class HTTPTransportConfig(BaseModel):
    """Configuration for HTTP transport."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    path: str = "/mcp"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    auth_token: str | None = None
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)
    max_concurrent_requests: int = Field(default=10, ge=1)
    request_timeout_seconds: int = Field(default=30, ge=1)
    max_request_size_mb: int = Field(default=10, ge=1, le=100)


class SessionsConfig(BaseModel):
    """Configuration for session management."""

    default_timeout_seconds: int = Field(default=600, ge=60, le=3600)
    max_sessions_per_client: int = Field(default=5, ge=1, le=20)
    max_memory_mb: int = Field(default=256, ge=64, le=1024)


class LoggingConfig(BaseModel):
    """Configuration for MCP logging."""

    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    structured: bool = True


class MCPConfig(BaseModel):
    """Main MCP server configuration."""

    server: ServerConfig = ServerConfig()
    transport_stdio: StdioTransportConfig = StdioTransportConfig()
    transport_http: HTTPTransportConfig = HTTPTransportConfig()
    sessions: SessionsConfig = SessionsConfig()
    logging: LoggingConfig = LoggingConfig()

    @classmethod
    def from_file(cls, path: Path | str) -> MCPConfig:
        """Load configuration from TOML file."""
        import tomllib

        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        return cls.model_validate(data)
