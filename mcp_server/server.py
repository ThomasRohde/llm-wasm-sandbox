"""
MCP Server for LLM WASM Sandbox.

This module implements a Model Context Protocol (MCP) server that exposes
the sandbox's secure code execution capabilities to MCP clients.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel

from sandbox.core.logging import SandboxLogger

from .audit import AuditLogger
from .config import MCPConfig
from .metrics import MCPMetricsCollector
from .rate_limiter import RateLimitConfig, RateLimiter
from .security import SecurityValidator
from .sessions import WorkspaceSessionManager
from .transports import HTTPTransportConfig


class MCPToolResult(BaseModel):
    """Result from an MCP tool execution."""

    content: str
    structured_content: dict[str, Any] | None = None
    execution_time_ms: float | None = None
    success: bool = True


class MCPServer:
    """
    MCP Server for secure code execution.

    Provides MCP tools for executing Python and JavaScript code in a
    WebAssembly sandbox with automatic session management.
    """

    def __init__(self, config: MCPConfig | None = None):
        self.config = config or MCPConfig()
        self.logger = SandboxLogger()
        self.audit_logger = AuditLogger()
        self.session_manager = WorkspaceSessionManager()
        self.metrics = MCPMetricsCollector()

        # Initialize rate limiter
        rate_limit_config = RateLimitConfig(
            requests_per_window=self.config.transport_http.rate_limit_requests,
            window_seconds=self.config.transport_http.rate_limit_window_seconds,
        )
        self.rate_limiter = RateLimiter(rate_limit_config)

        # Initialize FastMCP app
        self.app = FastMCP(
            name=self.config.server.name,
            version=self.config.server.version,
            instructions=self.config.server.instructions,
        )

        # Register tools
        self._register_tools()

        self.logger._emit(logging.INFO, "MCP server initialized", config=self.config.model_dump())

    async def _check_rate_limit(self, client_key: str = "default") -> bool:
        """Check rate limit for a client."""
        allowed, retry_after = await self.rate_limiter.check_rate_limit(client_key)
        if not allowed:
            client_stats = self.rate_limiter.get_client_stats(client_key) or {}
            self.audit_logger.log_rate_limit_violation(
                client_id=client_key,
                request_count=client_stats.get("requests_in_window", 0),
                limit=self.rate_limiter.config.requests_per_window,
                window_seconds=self.rate_limiter.config.window_seconds,
                blocked_duration=retry_after,
            )
            self.logger._emit(
                logging.WARNING,
                "mcp.rate_limit.blocked",
                client_key=client_key,
                retry_after=retry_after,
            )
        return allowed

    def _register_tools(self) -> None:
        """Register all MCP tools."""

        @self.app.tool(
            name="execute_code",
            description="Execute code in a secure WebAssembly sandbox. Supports Python and JavaScript.",
        )
        async def execute_code(
            code: str,
            language: str,
            timeout: int | None = None,
            session_id: str | None = None,
        ) -> MCPToolResult:
            """Execute code with automatic session management."""
            # Check rate limit
            if not await self._check_rate_limit(session_id or "anonymous"):
                return MCPToolResult(
                    content="Rate limit exceeded. Please try again later.",
                    success=False,
                )

            with self.metrics.time_tool_execution("execute_code"):
                try:
                    # Validate inputs
                    is_valid, error_msg = SecurityValidator.validate_code_input(code, language)
                    if not is_valid:
                        self.audit_logger.log_security_violation(
                            violation_type="invalid_code_input",
                            client_id=session_id or "anonymous",
                            details={"language": language, "error": error_msg},
                            severity="high",
                        )
                        return MCPToolResult(
                            content=f"Input validation failed: {error_msg}",
                            success=False,
                        )

                    # Validate timeout
                    timeout_valid, timeout_value = SecurityValidator.validate_timeout(timeout)
                    if not timeout_valid:
                        return MCPToolResult(
                            content="Invalid timeout value",
                            success=False,
                        )

                    # Validate language
                    if language not in ["python", "javascript"]:
                        return MCPToolResult(
                            content=f"Unsupported language: {language}. Supported: python, javascript",
                            success=False,
                        )

                    # Get or create session
                    session = await self.session_manager.get_or_create_session(
                        language=language, session_id=session_id
                    )

                    # Execute code
                    result = await session.execute_code(code, timeout=timeout_value)

                    # Record resource usage
                    self.metrics.record_resource_usage(
                        result.fuel_consumed or 0,
                        result.duration_ms / 1000,
                        result.memory_used_bytes,
                    )

                    # Audit log successful execution
                    self.audit_logger.log_tool_execution(
                        tool_name="execute_code",
                        client_id=session_id or "anonymous",
                        session_id=session_id,
                        success=result.success,
                        execution_time_ms=result.duration_ms,
                        fuel_consumed=result.fuel_consumed or 0,
                        language=language,
                    )

                    return MCPToolResult(
                        content=result.stdout or result.stderr,
                        structured_content={
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "exit_code": result.exit_code,
                            "execution_time_ms": result.duration_ms,
                            "fuel_consumed": result.fuel_consumed,
                            "success": result.success,
                        },
                        execution_time_ms=result.duration_ms,
                        success=result.success,
                    )

                except Exception as e:
                    error_msg = str(e)
                    self.audit_logger.log_tool_execution(
                        tool_name="execute_code",
                        client_id=session_id or "anonymous",
                        session_id=session_id,
                        success=False,
                        execution_time_ms=0.0,
                        fuel_consumed=0,
                        error_message=error_msg,
                        language=language,
                    )
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="execute_code", error=str(e)
                    )
                    return MCPToolResult(content=f"Execution failed: {e!s}", success=False)

        @self.app.tool(
            name="list_runtimes",
            description="List all available programming language runtimes in the sandbox",
        )
        async def list_runtimes() -> MCPToolResult:
            """List available runtimes."""
            with self.metrics.time_tool_execution("list_runtimes"):
                try:
                    runtimes = [
                        {
                            "name": "python",
                            "version": "3.12",
                            "description": "CPython compiled to WebAssembly",
                        },
                        {
                            "name": "javascript",
                            "version": "ES2023",
                            "description": "QuickJS JavaScript engine in WebAssembly",
                        },
                    ]

                    return MCPToolResult(
                        content=f"Available runtimes: {', '.join(r['name'] for r in runtimes)}",
                        structured_content={"runtimes": runtimes},
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="list_runtimes", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to list runtimes: {e!s}", success=False)

        @self.app.tool(
            name="create_session",
            description="Create a new workspace session for code execution with optional automatic global variable persistence",
        )
        async def create_session(
            language: str,
            session_id: str | None = None,
            auto_persist_globals: bool = False,
        ) -> MCPToolResult:
            """Create a new workspace session."""
            # Check rate limit
            if not await self._check_rate_limit(session_id or "anonymous"):
                return MCPToolResult(
                    content="Rate limit exceeded. Please try again later.",
                    success=False,
                )

            with self.metrics.time_tool_execution("create_session"):
                try:
                    # Validate language
                    if language not in ["python", "javascript"]:
                        return MCPToolResult(
                            content=f"Unsupported language: {language}. Supported: python, javascript",
                            success=False,
                        )

                    session = await self.session_manager.create_session(
                        language=language,
                        session_id=session_id,
                        auto_persist_globals=auto_persist_globals,
                    )

                    # Record session creation
                    self.metrics.record_session_created()

                    return MCPToolResult(
                        content=f"Created session {session.workspace_id} for {language}"
                        + (
                            " with automatic global variable persistence"
                            if auto_persist_globals
                            else ""
                        ),
                        structured_content={
                            "session_id": session.workspace_id,
                            "language": session.language,
                            "sandbox_session_id": session.sandbox_session_id,
                            "created_at": session.created_at,
                            "auto_persist_globals": session.auto_persist_globals,
                        },
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="create_session", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to create session: {e!s}", success=False)

        @self.app.tool(
            name="destroy_session",
            description="Destroy an existing workspace session",
        )
        async def destroy_session(session_id: str) -> MCPToolResult:
            """Destroy a workspace session."""
            with self.metrics.time_tool_execution("destroy_session"):
                try:
                    # Calculate lifetime before destroying
                    if session_id in self.session_manager._sessions:
                        session = self.session_manager._sessions[session_id]
                        lifetime = time.time() - session.created_at
                    else:
                        lifetime = 0.0

                    success = await self.session_manager.destroy_session(session_id)

                    if success:
                        # Record session destruction
                        self.metrics.record_session_destroyed(lifetime)

                        return MCPToolResult(
                            content=f"Destroyed session {session_id}",
                            structured_content={"session_id": session_id},
                        )
                    else:
                        return MCPToolResult(
                            content=f"Session {session_id} not found", success=False
                        )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="destroy_session", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to destroy session: {e!s}", success=False)

        @self.app.tool(
            name="list_available_packages",
            description="List pre-installed packages available in Python sessions (no installation required)",
        )
        async def list_available_packages() -> MCPToolResult:
            """List pre-installed packages."""
            with self.metrics.time_tool_execution("list_available_packages"):
                try:
                    packages = {
                        "document_processing": [
                            "openpyxl - Read/write Excel .xlsx files",
                            "XlsxWriter - Write Excel .xlsx files (write-only, lighter)",
                            "PyPDF2 - Read/write/merge PDF files",
                            "pdfminer.six - PDF text extraction (pure-Python mode)",
                            "odfpy - Read/write OpenDocument Format (.odf, .ods, .odp)",
                            "mammoth - Convert Word .docx to HTML/Markdown",
                        ],
                        "text_data": [
                            "tabulate - Pretty-print tabular data (ASCII, Markdown, HTML)",
                            "jinja2 - Template rendering engine",
                            "MarkupSafe - HTML/XML escaping (required by jinja2)",
                            "markdown - Convert Markdown to HTML",
                            "python-dateutil - Advanced date/time parsing",
                            "attrs - Classes without boilerplate",
                            "jsonschema - JSON schema validation",
                        ],
                        "utilities": [
                            "certifi - Mozilla's CA bundle",
                            "charset-normalizer - Character encoding detection",
                            "idna - Internationalized domain names",
                            "urllib3 - HTTP client (encoding utilities only, no networking)",
                            "six - Python 2/3 compatibility",
                            "tomli - TOML parser (Python <3.11)",
                            "cffi - Foreign function interface (limited WASM support)",
                        ],
                        "stdlib_highlights": [
                            "json, csv, xml - Data formats",
                            "re - Regular expressions",
                            "pathlib, os, shutil - File operations",
                            "math, statistics, decimal - Mathematics",
                            "datetime, time, calendar - Date/time",
                            "collections, itertools, functools - Data structures",
                            "base64, hashlib, hmac - Encoding/hashing",
                            "zipfile, tarfile, gzip - Compression",
                            "sqlite3 - In-memory SQL database",
                        ],
                        "incompatible_c_extensions": [
                            "❌ python-pptx - Requires lxml.etree (C extension not available in WASM)",
                            "❌ python-docx - Requires lxml.etree (C extension not available in WASM)",
                            "❌ Pillow/PIL - Image processing (C extension not available in WASM)",
                            "❌ lxml.etree - XML processing C extension (base lxml package imports but etree doesn't work)",
                            "Note: Use mammoth for Word .docx reading, PyPDF2 for PDFs, openpyxl for Excel",
                        ],
                    }

                    usage_note = (
                        "\nUsage: Add this at the start of your Python code:\n"
                        "import sys\n"
                        "sys.path.insert(0, '/data/site-packages')\n\n"
                        "Note: pip install is NOT supported (WASI limitation). "
                        "Use pre-installed packages or pure Python implementations.\n\n"
                        "⚠ IMPORTANT: PowerPoint (.pptx) creation/editing is NOT supported because:\n"
                        "  - python-pptx requires lxml.etree (C extension)\n"
                        "  - Pillow/PIL required for images (C extension)\n"
                        "  - These C extensions cannot run in the WASM sandbox\n\n"
                        "For document processing, use:\n"
                        "  - Excel: openpyxl, XlsxWriter\n"
                        "  - PDF: PyPDF2, pdfminer.six\n"
                        "  - Word: mammoth (read-only, converts to HTML/Markdown)\n"
                        "  - OpenDocument: odfpy (.odt, .ods, .odp)"
                    )

                    content_lines = []
                    for category, pkgs in packages.items():
                        content_lines.append(f"\n{category.replace('_', ' ').title()}:")
                        for pkg in pkgs:
                            content_lines.append(f"  - {pkg}")

                    content = "\n".join(content_lines) + usage_note

                    return MCPToolResult(
                        content=content,
                        structured_content={"packages": packages, "usage_note": usage_note},
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR,
                        "Tool execution failed",
                        tool="list_available_packages",
                        error=str(e),
                    )
                    return MCPToolResult(content=f"Failed to list packages: {e!s}", success=False)

        @self.app.tool(
            name="cancel_execution",
            description="Cancel a running execution (not yet implemented - executions are synchronous)",
        )
        async def cancel_execution(session_id: str) -> MCPToolResult:
            """Cancel a running execution."""
            with self.metrics.time_tool_execution("cancel_execution"):
                # Note: Current implementation is synchronous, so cancellation is not possible
                # This would require async execution support
                return MCPToolResult(
                    content="Execution cancellation is not yet supported (synchronous execution only)",
                    structured_content={"supported": False},
                    success=False,
                )

        @self.app.tool(
            name="get_workspace_info",
            description="Get information about a workspace session",
        )
        async def get_workspace_info(session_id: str) -> MCPToolResult:
            """Get workspace session information."""
            with self.metrics.time_tool_execution("get_workspace_info"):
                try:
                    info = await self.session_manager.get_session_info(session_id)

                    if info:
                        return MCPToolResult(
                            content=f"Session {session_id}: {info['language']}, {info['execution_count']} executions, {len(info['files'])} files",
                            structured_content=info,
                        )
                    else:
                        return MCPToolResult(
                            content=f"Session {session_id} not found", success=False
                        )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR,
                        "Tool execution failed",
                        tool="get_workspace_info",
                        error=str(e),
                    )
                    return MCPToolResult(
                        content=f"Failed to get workspace info: {e!s}", success=False
                    )

        @self.app.tool(
            name="reset_workspace",
            description="Reset a workspace session (clear all files but keep session)",
        )
        async def reset_workspace(session_id: str) -> MCPToolResult:
            """Reset a workspace session."""
            with self.metrics.time_tool_execution("reset_workspace"):
                try:
                    success = await self.session_manager.reset_session(session_id)

                    if success:
                        return MCPToolResult(
                            content=f"Reset workspace session {session_id}",
                            structured_content={"session_id": session_id},
                        )
                    else:
                        return MCPToolResult(
                            content=f"Failed to reset session {session_id}", success=False
                        )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="reset_workspace", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to reset workspace: {e!s}", success=False)

        @self.app.tool(
            name="get_metrics",
            description="Get performance metrics and monitoring data for the MCP server",
        )
        async def get_metrics() -> MCPToolResult:
            """Get MCP server metrics."""
            with self.metrics.time_tool_execution("get_metrics"):
                try:
                    metrics_summary = self.metrics.get_summary()

                    # Add version information
                    server_version = self.config.server.version
                    metrics_summary["server"] = {
                        "version": server_version,
                        "name": self.config.server.name,
                    }

                    return MCPToolResult(
                        content=f"MCP Server v{server_version}: {metrics_summary['tool_executions']['total_count']} tool executions, {metrics_summary['sessions']['active_count']} active sessions",
                        structured_content=metrics_summary,
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="get_metrics", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to get metrics: {e!s}", success=False)

    async def start_stdio(self) -> None:
        """Start the MCP server with stdio transport."""
        self.logger._emit(logging.INFO, "Starting MCP server with stdio transport")
        await self.app.run_stdio_async()

    async def start_http(self, config: HTTPTransportConfig | None = None) -> None:
        """Start the MCP server with HTTP transport."""
        if config is None:
            # Convert MCPConfig to HTTPTransportConfig
            http_config = HTTPTransportConfig(
                host=self.config.transport_http.host,
                port=self.config.transport_http.port,
                path=self.config.transport_http.path,
                cors_origins=self.config.transport_http.cors_origins,
                auth_token=self.config.transport_http.auth_token,
                rate_limit_requests=self.config.transport_http.rate_limit_requests,
                rate_limit_window_seconds=self.config.transport_http.rate_limit_window_seconds,
                max_concurrent_requests=self.config.transport_http.max_concurrent_requests,
                request_timeout_seconds=self.config.transport_http.request_timeout_seconds,
                max_request_size_mb=self.config.transport_http.max_request_size_mb,
            )
        else:
            http_config = config

        self.logger._emit(
            logging.INFO,
            "Starting MCP server with HTTP transport",
            host=http_config.host,
            port=http_config.port,
        )

        # Add CORS middleware for web clients
        http_app = self.app.http_app()
        http_app.add_middleware(
            http_config.get_cors_middleware_class(),  # type: ignore[arg-type]
            allow_origins=http_config.cors_origins,
            allow_credentials=True,
            allow_methods=["POST", "GET", "OPTIONS"],
            allow_headers=["*"],
        )

        # Note: HTTP timing would need to be integrated at the FastMCP level
        # For now, we rely on the tool-level timing

        # Get uvicorn config but extract host/port separately
        # to avoid duplicate parameter error in FastMCP
        uvicorn_config = http_config.get_uvicorn_config()
        host = uvicorn_config.pop("host")
        port = uvicorn_config.pop("port")

        await self.app.run_http_async(
            host=host,
            port=port,
            uvicorn_config=uvicorn_config,
        )

    async def shutdown(self) -> None:
        """Shutdown the MCP server and cleanup resources."""
        self.logger._emit(logging.INFO, "Shutting down MCP server")

        # Log final metrics
        metrics_summary = self.metrics.get_summary()
        self.logger._emit(logging.INFO, "Final MCP metrics", metrics=metrics_summary)

        # Stop rate limiter cleanup
        await self.rate_limiter.stop_cleanup_task()

        await self.session_manager.cleanup()


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncGenerator[None, None]:
    """FastMCP lifespan context manager."""
    # Start background tasks
    await server.rate_limiter.start_cleanup_task()
    await server.session_manager.start_cleanup_task()

    yield

    await server.shutdown()


def create_mcp_server(config: MCPConfig | None = None) -> MCPServer:
    """Create and configure an MCP server instance."""
    return MCPServer(config)
