from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import ClassVar

"""
MCP Server with Custom Security Configuration

This example demonstrates how to customize security filters when
creating an MCP server instance.
"""

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the security module FIRST
from mcp_server.security import SecurityValidator  # noqa: E402


class CustomSecurityValidator(SecurityValidator):
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


# Monkey-patch the security module
import mcp_server.security  # noqa: E402
import mcp_server.server  # noqa: E402

mcp_server.security.SecurityValidator = CustomSecurityValidator
# CRITICAL: Also patch the server module's direct import
mcp_server.server.SecurityValidator = CustomSecurityValidator

# Import server components AFTER patching
from mcp_server import MCPConfig, create_mcp_server  # noqa: E402


async def main():
    """Start MCP server with custom security configuration."""

    print("Starting MCP server with PROMISCUOUS security (ALL CODE ALLOWED)...", file=sys.stderr)
    print("WARNING: All security filters disabled!", file=sys.stderr)
    print("Security relies entirely on WASM sandbox boundaries.", file=sys.stderr)
    print("", file=sys.stderr)

    # Create MCP server (will use custom security validator)
    config = MCPConfig()
    server = create_mcp_server(config)

    print("Available tools: execute_code, list_runtimes, create_session, etc.", file=sys.stderr)

    try:
        await server.start_stdio()
    except KeyboardInterrupt:
        print("Shutting down MCP server...", file=sys.stderr)
        await server.shutdown()
    except Exception as e:
        print(f"MCP server error: {e}", file=sys.stderr)
        await server.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
