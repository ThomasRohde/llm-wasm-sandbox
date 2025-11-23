#!/usr/bin/env python3
"""
MCP Server Stdio Example

This example demonstrates how to start the MCP server with stdio transport
for use with local MCP clients like Claude Desktop.

Usage:
    uv run python examples/mcp_stdio_example.py

Or with custom configuration:
    MCP_CONFIG=config/mcp.toml uv run python examples/mcp_stdio_example.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp_server import create_mcp_server, MCPConfig


async def main():
    """Start MCP server with stdio transport."""

    # Load configuration from environment or use defaults
    config_path = os.getenv("MCP_CONFIG")
    if config_path and Path(config_path).exists():
        print(f"Loading configuration from: {config_path}", file=sys.stderr)
        config = MCPConfig.from_file(config_path)
    else:
        print("Using default configuration", file=sys.stderr)
        config = None

    # Create and start MCP server
    server = create_mcp_server(config)

    print("Starting MCP server with stdio transport...", file=sys.stderr)
    print("Available tools: execute_code, list_runtimes, create_session, destroy_session, install_package, get_workspace_info, reset_workspace", file=sys.stderr)

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
