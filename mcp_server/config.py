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
        "⚠️ FUEL BUDGET REQUIREMENTS:\n"
        "- DEFAULT budget (5B instructions): Works for most stdlib and lightweight packages\n"
        "- INCREASE to 10B for: openpyxl, PyPDF2, jinja2 (first import only)\n"
        "- First imports are expensive, subsequent imports use cached modules\n"
        "- Sessions with auto_persist_globals=True automatically cache imports\n\n"
        "📦 PRE-INSTALLED PACKAGES (30+ packages, no pip install needed):\n"
        "- Document processing: openpyxl (10B fuel), PyPDF2 (10B fuel), mammoth, odfpy\n"
        "- Text/data: tabulate (2B fuel), markdown (2B fuel), python-dateutil (2B fuel)\n"
        "- Heavy packages: jinja2 (5-10B fuel) - template rendering\n"
        "- Utilities: certifi, charset-normalizer, idna, six, tomli, attrs\n"
        "- Full Python standard library (pathlib, json, csv, re, math, statistics, etc.)\n\n"
        "✅ PACKAGE USAGE (AUTOMATIC - no sys.path needed!):\n"
        "Packages are automatically available - just import them:\n"
        "  from tabulate import tabulate\n"
        "  import openpyxl\n"
        "  from markdown import markdown\n\n"
        "💡 BEST PRACTICES:\n"
        "1. Create sessions with auto_persist_globals=True for automatic caching\n"
        "2. Import heavy packages once at session start\n"
        "3. Reuse sessions to benefit from cached imports (100x faster!)\n"
        "4. Use list_available_packages tool to see all packages and fuel requirements\n\n"
        "🚫 NOT SUPPORTED:\n"
        "- pip install (WASI limitation)\n"
        "- PowerPoint/PPTX (requires C extensions: python-pptx, Pillow)\n"
        "- Image processing (Pillow/PIL requires C extensions)\n\n"
        "Performance: Default fuel budget is 5B instructions. "
        "Use list_available_packages to see fuel requirements for each package."
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
    external_files: list[str] = Field(
        default_factory=list,
        description="List of file paths to copy to ./storage and mount read-only at /external",
    )
    max_external_file_size_mb: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum size in MB for each external file",
    )


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
