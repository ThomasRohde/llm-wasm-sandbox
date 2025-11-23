# MCP Server Package
"""
Model Context Protocol server for LLM WASM Sandbox.

This package provides MCP server functionality that exposes the sandbox's
secure code execution capabilities to MCP clients like Claude Desktop.
"""

__version__ = "0.1.0"

from .config import MCPConfig
from .server import MCPServer, create_mcp_server
from .sessions import WorkspaceSessionManager
from .transports import HTTPTransportConfig, StdioTransportConfig, TransportConfig, TransportType

__all__ = [
    "HTTPTransportConfig",
    "MCPConfig",
    "MCPServer",
    "StdioTransportConfig",
    "TransportConfig",
    "TransportType",
    "WorkspaceSessionManager",
    "create_mcp_server",
]
