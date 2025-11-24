#!/usr/bin/env python3
"""
MCP Server with Custom Security Configuration

This example demonstrates how to customize security filters when
creating an MCP server instance.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import ClassVar

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# CRITICAL: Monkey-patch at module level BEFORE any imports
import sys as _sys  # noqa: E402
import mcp_server.security  # noqa: E402


class CustomSecurityValidator(mcp_server.security.SecurityValidator):
    """
    Custom security validator with relaxed file operation rules.

    This validator allows basic file operations like 'open', 'json', etc.
    but still blocks dangerous operations like subprocess and network access.

    For JavaScript: Allows QuickJS 'std' and 'os' modules for file I/O.
    """

    # Custom dangerous patterns - removed file system restrictions
    DANGEROUS_CODE_PATTERNS: ClassVar[list[str]] = [
        # Network access (still blocked)
        r'\b(socket|urllib|requests|http|ftp)\b',
        # System commands (still blocked)
        r'\b(subprocess|os\.system|os\.popen|commands)\b',
        # Dynamic code execution (still blocked)
        r'\b(eval|exec|compile|__import__)\b',
        # Process manipulation (still blocked)
        r'\b(psutil|signal|kill|terminate)\b',
    ]

    # Custom dangerous packages - removed 'os', 'pathlib', etc.
    DANGEROUS_PACKAGES: ClassVar[set[str]] = {
        'subprocess', 'socket', 'urllib',
        'eval', 'exec', 'compile',
        'psutil', 'signal', 'multiprocessing', 'threading',
        'ctypes', 'mmap', 'resource', 'pickle', 'shelve',
    }

    @classmethod
    def _validate_javascript_code(cls, code: str) -> tuple[bool, str]:
        """
        Validate JavaScript code with relaxed rules for QuickJS.

        Allows:
        - QuickJS 'std' and 'os' modules (file I/O in sandbox)
        - Basic control flow (setTimeout/setInterval)

        Blocks:
        - Node.js-specific APIs (process, child_process)
        - Network access (http, https, net, XMLHttpRequest)
        - Browser DOM manipulation (window, document)
        """
        dangerous_js_patterns = [
            # Node.js process/system APIs (blocked)
            r'\b(child_process|cluster|worker_threads)\b',
            # Network APIs (blocked)
            r'\b(http|https|net|dgram|tls|XMLHttpRequest|fetch)\b',
            # Browser DOM (blocked)
            r'\b(window|document|navigator|location)\b',
            # Dangerous eval (blocked)
            r'\beval\s*\(',
        ]

        for pattern in dangerous_js_patterns:
            if re.search(pattern, code):
                return False, f"Potentially dangerous JavaScript pattern detected: {pattern}"

        return True, ""


# Replace in security module
mcp_server.security.SecurityValidator = CustomSecurityValidator

# Also inject into sys.modules to ensure all imports get our version
import mcp_server  # noqa: E402
mcp_server.SecurityValidator = CustomSecurityValidator  # type: ignore

# NOW import server components
from mcp_server import MCPConfig, create_mcp_server  # noqa: E402

# Verify the patch took effect
import mcp_server.server  # noqa: E402
mcp_server.server.SecurityValidator = CustomSecurityValidator


async def main():
    """Start MCP server with custom security configuration."""

    print("Starting MCP server with CUSTOM security filters...", file=sys.stderr)
    print("Allowed: file operations (open, json, os.path, pathlib)", file=sys.stderr)
    print("Blocked: network, subprocess, eval/exec, process manipulation", file=sys.stderr)
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
