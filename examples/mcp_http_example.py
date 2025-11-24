#!/usr/bin/env python3
"""
MCP Server HTTP Example

This example demonstrates how to start the MCP server with HTTP transport
for use with web-based MCP clients or remote access.

Usage:
    uv run python examples/mcp_http_example.py

Or with custom configuration:
    MCP_CONFIG=config/mcp.toml uv run python examples/mcp_http_example.py

The server will be available at http://localhost:8080/mcp
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp_server import HTTPTransportConfig, MCPConfig, create_mcp_server  # noqa: E402


async def main():
    """Start MCP server with HTTP transport."""

    # Load configuration from environment or use defaults
    config_path = os.getenv("MCP_CONFIG")
    if config_path and Path(config_path).exists():
        print(f"Loading configuration from: {config_path}", file=sys.stderr)
        config = MCPConfig.from_file(config_path)
    else:
        print("Using default configuration", file=sys.stderr)
        config = MCPConfig()

    # Configure HTTP transport
    http_config = HTTPTransportConfig(
        host=config.transport_http.host,
        port=config.transport_http.port,
        path=config.transport_http.path,
        cors_origins=config.transport_http.cors_origins,
        auth_token=config.transport_http.auth_token,
        rate_limit_requests=config.transport_http.rate_limit_requests,
        rate_limit_window_seconds=config.transport_http.rate_limit_window_seconds,
        max_concurrent_requests=config.transport_http.max_concurrent_requests,
        request_timeout_seconds=config.transport_http.request_timeout_seconds,
        max_request_size_mb=config.transport_http.max_request_size_mb,
    )

    # Create MCP server
    server = create_mcp_server(config)

    print("Starting MCP server with HTTP transport...", file=sys.stderr)
    print(
        f"Server URL: http://{http_config.host}:{http_config.port}{http_config.path}",
        file=sys.stderr,
    )
    print(f"CORS origins: {http_config.cors_origins}", file=sys.stderr)
    print(
        f"Rate limit: {http_config.rate_limit_requests} requests per {http_config.rate_limit_window_seconds}s",
        file=sys.stderr,
    )
    print(
        "Available tools: execute_code, list_runtimes, create_session, destroy_session, install_package, get_workspace_info, reset_workspace",
        file=sys.stderr,
    )

    if http_config.auth_token:
        print(f"Auth token required: {http_config.auth_token[:8]}...", file=sys.stderr)

    try:
        await server.start_http(http_config)
    except KeyboardInterrupt:
        print("Shutting down MCP server...", file=sys.stderr)
        await server.shutdown()
    except Exception as e:
        print(f"MCP server error: {e}", file=sys.stderr)
        await server.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
