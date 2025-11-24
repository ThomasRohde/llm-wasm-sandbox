"""
MCP Server Configuration.

Configuration models for the MCP server.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


def _get_package_version() -> str:
    """Get package version from metadata."""
    try:
        import importlib.metadata

        return importlib.metadata.version("llm-wasm-sandbox")
    except Exception:
        return "0.3.0"  # Fallback to current version


class ServerConfig(BaseModel):
    """Server identification and metadata."""

    name: str = "llm-wasm-sandbox"
    version: str = Field(default_factory=_get_package_version)
    instructions: str = (
        "This server provides secure code execution in a WebAssembly sandbox. "
        "Use the execute_code tool to run Python or JavaScript code safely.\n\n"
        "IMPORTANT: Package installation via pip is NOT supported (WASI doesn't support subprocesses). "
        "However, Python sessions include 30+ pre-installed packages:\n"
        "- Document processing: openpyxl, XlsxWriter, PyPDF2, odfpy, mammoth\n"
        "- Text/data: tabulate, jinja2, markdown, python-dateutil, attrs\n"
        "- Utilities: certifi, charset-normalizer, idna, six, tomli\n"
        "- Full Python standard library (pathlib, json, csv, re, etc.)\n\n"
        "To use vendored packages in Python, add this at the start of your code:\n"
        "import sys\n"
        "sys.path.insert(0, '/data/site-packages')\n\n"
        "For numerical operations, use stdlib alternatives:\n"
        "- statistics module for mean, median, stdev\n"
        "- math module for sqrt, log, trig functions\n"
        "- Or implement pure Python algorithms\n\n"
        "Performance: Default fuel budget is 5B instructions, sufficient for most imports and operations. "
        "Use list_available_packages to see all pre-installed packages."
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
