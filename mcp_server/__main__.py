#!/usr/bin/env python3
"""
MCP Server CLI for LLM WASM Sandbox.

Command-line interface to run the MCP server with different transports.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import MCPConfig
from .server import create_mcp_server


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Server for LLM WASM Sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with stdio transport (for Claude Desktop)
  python -m mcp.server

  # Run with HTTP transport
  python -m mcp.server --transport http --port 8080

  # Load custom config
  python -m mcp.server --config /path/to/mcp.toml
        """,
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport to use (default: stdio)",
    )

    parser.add_argument(
        "--host", default="127.0.0.1", help="Host for HTTP transport (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP transport (default: 8080)"
    )

    parser.add_argument("--config", type=Path, help="Path to MCP configuration file")

    args = parser.parse_args()

    # Load configuration
    config = MCPConfig.from_file(args.config) if args.config else MCPConfig()

    # Override transport config from CLI
    if args.transport == "http":
        config.transport_http.enabled = True
        config.transport_http.host = args.host
        config.transport_http.port = args.port

    # Create and start server
    server = create_mcp_server(config)

    try:
        if args.transport == "stdio":
            import asyncio

            asyncio.run(server.start_stdio())
        else:
            import asyncio

            asyncio.run(
                server.start_http(host=config.transport_http.host, port=config.transport_http.port)
            )
    except KeyboardInterrupt:
        print("\nShutting down MCP server...", file=sys.stderr)
        import asyncio

        asyncio.run(server.shutdown())


if __name__ == "__main__":
    main()
