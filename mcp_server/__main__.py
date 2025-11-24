#!/usr/bin/env python3
"""
MCP Server CLI for LLM WASM Sandbox.

Command-line interface to run the MCP server with promiscuous security
(all code allowed - security relies on WASM sandbox boundaries).
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any, ClassVar

from .config import MCPConfig
from .security import SecurityValidator
from .server import create_mcp_server


class ProtocolFilterIO:
    """
    A smart wrapper for stdout that directs JSON-RPC messages to real stdout
    and everything else (banners, logs) to stderr.

    This prevents FastMCP's ASCII art banner from breaking the MCP protocol.
    """

    def __init__(self, original_stdout: Any, stderr: Any) -> None:
        self.original_stdout = original_stdout
        self.stderr = stderr
        # Expose the underlying buffer for binary I/O operations
        self.buffer = original_stdout.buffer if hasattr(original_stdout, "buffer") else None

    def write(self, message: str) -> int:
        # Heuristic: MCP JSON-RPC messages are JSON objects starting with '{'
        # Redirect banners and logs to stderr, JSON-RPC to stdout
        if message.strip().startswith("{"):
            self.original_stdout.write(message)
            self.original_stdout.flush()
        else:
            self.stderr.write(message)
            self.stderr.flush()
        return len(message)

    def flush(self) -> None:
        self.original_stdout.flush()
        self.stderr.flush()

    def isatty(self) -> bool:
        return bool(self.original_stdout.isatty())

    def __getattr__(self, name: str) -> Any:
        # Proxy any other attributes to the original stdout
        return getattr(self.original_stdout, name)


class PromiscuousSecurityValidator(SecurityValidator):
    """
    Promiscuous security validator - ALLOWS EVERYTHING.

    WARNING: This validator disables all security checks.
    Use only in trusted environments where the WASM sandbox
    provides the primary security boundary.
    """

    # No patterns blocked - allow everything
    DANGEROUS_CODE_PATTERNS: ClassVar[list[str]] = []

    # No packages blocked - allow everything
    DANGEROUS_PACKAGES: ClassVar[set[str]] = set()

    @classmethod
    def _validate_javascript_code(cls, code: str) -> tuple[bool, str]:
        """
        Validate JavaScript code - ALLOWS EVERYTHING.

        All JavaScript code is permitted. Security relies entirely
        on the WASM sandbox boundaries.
        """
        return True, ""


def main() -> None:
    """Main CLI entry point."""
    print("Starting MCP server with PROMISCUOUS security (ALL CODE ALLOWED)...", file=sys.stderr)
    print("WARNING: All security filters disabled!", file=sys.stderr)
    print("Security relies entirely on WASM sandbox boundaries.", file=sys.stderr)
    print("", file=sys.stderr)

    # Install the smart stdout filter to redirect banners to stderr
    # while preserving JSON-RPC messages on stdout
    original_stdout = sys.stdout
    sys.stdout = ProtocolFilterIO(original_stdout, sys.stderr)

    # Monkey-patch the security module to use promiscuous validator
    import mcp_server.security
    import mcp_server.server

    mcp_server.security.SecurityValidator = PromiscuousSecurityValidator  # type: ignore[misc]
    mcp_server.server.SecurityValidator = PromiscuousSecurityValidator  # type: ignore[misc]

    config = MCPConfig()
    server = create_mcp_server(config)

    print("Available tools: execute_code, list_runtimes, create_session, etc.", file=sys.stderr)

    try:
        asyncio.run(server.start_stdio())
    except KeyboardInterrupt:
        print("\nShutting down MCP server...", file=sys.stderr)
        asyncio.run(server.shutdown())
    except Exception as e:
        print(f"MCP server error: {e}", file=sys.stderr)
        asyncio.run(server.shutdown())
        sys.exit(1)


if __name__ == "__main__":
    main()
