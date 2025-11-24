# MCP Integration Guide

This guide covers integrating the LLM WASM Sandbox with the Model Context Protocol (MCP) for standardized tool use in AI applications.

## Overview

The Model Context Protocol (MCP) is an emerging standard for tool use in AI applications, providing:

- **Standardized API**: Consistent interface across different MCP clients (Claude Desktop, custom agents)
- **Stateful Sessions**: Automatic persistence of variables and execution context across tool calls
- **Streaming Support**: Real-time execution feedback for long-running code
- **Security Boundaries**: MCP layer enforces additional validation on top of WASM isolation

The sandbox provides MCP server functionality that exposes secure code execution capabilities to MCP clients.

## Quick Start

### Prerequisites

- Python 3.11+ with sandbox installed
- WASM binaries downloaded (`python.wasm` and `quickjs.wasm`)
- MCP client (Claude Desktop, custom MCP client, or HTTP client)

### Basic Setup

**Production (installed package):**
```bash
# Install from PyPI with bundled WASM runtimes
pip install llm-wasm-sandbox

# Start MCP server
python -m mcp_server
# OR use the command alias
llm-wasm-mcp
```

**Development (from source):**
```bash
# Clone and setup
git clone https://github.com/ThomasRohde/llm-wasm-sandbox.git
cd llm-wasm-sandbox
uv sync

# Fetch WASM binaries (required)
.\scripts\fetch_wlr_python.ps1
.\scripts\fetch_quickjs.ps1

# Run MCP server in development
uv run python -m mcp_server

# Note: 'llm-wasm-mcp' command only works after 'pip install'
```

### Stdio Transport (Local MCP Clients)

For use with Claude Desktop or other local MCP clients:

**Production (installed package):**
```bash
# Using the installed command
llm-wasm-mcp

# Or using Python module
python -m mcp_server
```

**Development (from source):**
```bash
# Option 1: Using the package directly (recommended)
uv run python -m mcp_server

# Option 2: Using example scripts
uv run python examples/mcp_stdio_example.py
uv run python examples/llm_wasm_mcp.py  # Promiscuous mode
```

### HTTP Transport (Remote/Web Clients)

For web-based MCP clients or remote access:

```python
# examples/mcp_http_example.py
from mcp_server import create_mcp_server, HTTPTransportConfig

# Configure HTTP transport
http_config = HTTPTransportConfig(
    host="127.0.0.1",
    port=8080,
    cors_origins=["http://localhost:3000"]  # Allow your web client
)

server = create_mcp_server()
await server.start_http(http_config)
```

Run with:
```bash
uv run python examples/mcp_http_example.py
```

## Configuration

### MCP Server Configuration

Configure the MCP server using `config/mcp.toml`:

```toml
[server]
name = "llm-wasm-sandbox"
version = "0.1.0"
instructions = "Secure code execution in WebAssembly sandbox"

[transport_stdio]
enabled = true

[transport_http]
enabled = false
host = "127.0.0.1"
port = 8080
path = "/mcp"
cors_origins = ["*"]
auth_token = null
rate_limit_requests = 100
rate_limit_window_seconds = 60
max_concurrent_requests = 10
request_timeout_seconds = 30
max_request_size_mb = 10

[sessions]
default_timeout_seconds = 600
max_sessions_per_client = 5
max_memory_mb = 256

[logging]
level = "INFO"
structured = true
```

Load configuration:

```python
from mcp_server import MCPConfig

config = MCPConfig.from_file("config/mcp.toml")
server = create_mcp_server(config)
```

### Execution Policy Configuration

MCP tools respect the sandbox's execution policies. Configure via `config/policy.toml`:

```toml
fuel_budget = 2000000000
memory_bytes = 134217728  # 128 MB
stdout_max_bytes = 1048576  # 1 MB
stderr_max_bytes = 1048576  # 1 MB
env = { "DEMO_GREETING" = "Hello from sandbox!" }
```

## MCP Tools

The MCP server provides the following tools:

### execute_code

Execute code in a secure WebAssembly sandbox.

**Parameters:**
- `code` (string): Code to execute
- `language` (string): "python" or "javascript"
- `timeout` (int, optional): Execution timeout in seconds
- `session_id` (string, optional): Session ID for stateful execution

**Example:**
```json
{
  "name": "execute_code",
  "arguments": {
    "code": "print('Hello, World!')",
    "language": "python"
  }
}
```

**Response:**
```json
{
  "content": "Hello, World!\n",
  "structured_content": {
    "stdout": "Hello, World!\n",
    "stderr": "",
    "exit_code": 0,
    "execution_time_ms": 45.2,
    "fuel_consumed": 125000,
    "success": true
  },
  "execution_time_ms": 45.2,
  "success": true
}
```

### list_runtimes

List available programming language runtimes.

**Parameters:** None

**Example:**
```json
{
  "name": "list_runtimes",
  "arguments": {}
}
```

**Response:**
```json
{
  "content": "Available runtimes: python, javascript",
  "structured_content": {
    "runtimes": [
      {
        "name": "python",
        "version": "3.11",
        "description": "CPython compiled to WebAssembly"
      },
      {
        "name": "javascript",
        "version": "ES2023",
        "description": "QuickJS JavaScript engine in WebAssembly"
      }
    ]
  }
}
```

### create_session

Create a new workspace session for code execution.

**Parameters:**
- `language` (string): "python" or "javascript"
- `session_id` (string, optional): Custom session ID

**Example:**
```json
{
  "name": "create_session",
  "arguments": {
    "language": "python",
    "session_id": "my-session-123"
  }
}
```

### destroy_session

Destroy an existing workspace session.

**Parameters:**
- `session_id` (string): Session ID to destroy

### install_package

Install a Python package in the current session (Python only).

**Parameters:**
- `package_name` (string): Package to install (e.g., "requests")
- `session_id` (string, optional): Session ID

### cancel_execution

Cancel a running execution (not yet implemented - executions are synchronous).

### get_workspace_info

Get information about a workspace session.

**Parameters:**
- `session_id` (string): Session ID to inspect

### reset_workspace

Reset a workspace session (clear all files but keep session).

**Parameters:**
- `session_id` (string): Session ID to reset

## Integration Examples

### Claude Desktop Integration

1. **Install Claude Desktop** from https://claude.ai/download

2. **Create Claude Desktop configuration**:

```json
// examples/mcp_claude_desktop_config.json
{
  "mcpServers": {
    "llm-wasm-sandbox": {
      "command": "uv",
      "args": ["run", "python", "examples/mcp_stdio_example.py"],
      "cwd": "/path/to/llm-wasm-sandbox"
    }
  }
}
```

3. **Configure Claude Desktop**:
   - Open Claude Desktop settings
   - Go to "Developer" → "Edit Config"
   - Add the MCP server configuration above
   - Restart Claude Desktop

4. **Test the integration**:
   - Ask Claude: "Execute Python code to calculate fibonacci(10)"
   - Claude will use the MCP tool to run code securely

### Custom MCP Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Connect to MCP server
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "examples/mcp_stdio_example.py"],
        cwd="/path/to/llm-wasm-sandbox"
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools.tools])

            # Execute code
            result = await session.call_tool(
                "execute_code",
                arguments={
                    "code": "print(42 * 2)",
                    "language": "python"
                }
            )
            print("Result:", result.content)

asyncio.run(main())
```

### HTTP Client Integration

```python
import httpx
import json

async def call_mcp_tool(tool_name: str, arguments: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            },
            headers={"Content-Type": "application/json"}
        )
        return response.json()

# Execute code via HTTP
result = await call_mcp_tool("execute_code", {
    "code": "print('Hello from HTTP!')",
    "language": "python"
})
print(result)
```

## Session Management

### Automatic Session Binding

MCP clients automatically get sessions bound to their connection:

- **Stdio transport**: Single workspace per process
- **HTTP transport**: Workspace per `Mcp-Session-Id` header

### Manual Session Management

For advanced use cases, manage sessions explicitly:

```python
# Create session
result = await session.call_tool("create_session", {
    "language": "python",
    "session_id": "my-session"
})

# Use session in subsequent calls
result = await session.call_tool("execute_code", {
    "code": "x = 42",
    "language": "python",
    "session_id": "my-session"
})

# Execute more code in same session
result = await session.call_tool("execute_code", {
    "code": "print(x * 2)",
    "language": "python",
    "session_id": "my-session"
})

# Clean up
await session.call_tool("destroy_session", {
    "session_id": "my-session"
})
```

### Session Persistence

Sessions persist variables and files across tool calls:

```python
# First execution - create data
await session.call_tool("execute_code", {
    "code": "data = [1, 2, 3]",
    "language": "python",
    "session_id": "persistent-session"
})

# Second execution - use data
await session.call_tool("execute_code", {
    "code": "print(sum(data))",
    "language": "python",
    "session_id": "persistent-session"
})
```

## Security Considerations

### MCP Layer Security

- **Input Validation**: All MCP inputs are validated using Pydantic models
- **Rate Limiting**: HTTP transport includes configurable rate limiting
- **Authentication**: Optional auth token support for HTTP transport
- **Timeout Controls**: Execution timeouts prevent hanging requests

### Sandbox Security

MCP tools inherit all sandbox security features:

- **WASM Isolation**: Code runs in WebAssembly memory sandbox
- **Filesystem Restriction**: Access limited to `/app` directory
- **Resource Limits**: Fuel and memory budgets prevent abuse
- **No Networking**: Zero network capabilities

### Production Deployment

For production use:

```python
# Secure HTTP configuration
http_config = HTTPTransportConfig(
    host="0.0.0.0",  # Listen on all interfaces
    port=8080,
    cors_origins=["https://your-domain.com"],
    auth_token="your-secure-token-here",
    rate_limit_requests=50,  # Conservative rate limiting
    max_concurrent_requests=5,
    request_timeout_seconds=60
)

# Use restrictive execution policies
policy = ExecutionPolicy(
    fuel_budget=500_000_000,  # Conservative fuel limit
    memory_bytes=64 * 1024 * 1024,  # 64 MB memory
    stdout_max_bytes=100_000  # 100 KB output limit
)
```

## Troubleshooting

### Common Issues

**MCP server won't start**
- Check that WASM binaries exist: `bin/python.wasm`, `bin/quickjs.wasm`
- Verify dependencies: `uv sync` or `pip install -r requirements.txt`
- Check configuration file syntax

**Tool calls fail with "OutOfFuel"**
- Increase fuel budget in `config/policy.toml`
- Simplify the code being executed

**HTTP transport not accessible**
- Check firewall settings
- Verify host/port configuration
- Ensure CORS origins allow your client

**Session not found errors**
- Sessions auto-create on first use
- Check session ID spelling
- Sessions timeout after 10 minutes by default

**Claude Desktop can't connect**
- Verify the command path in configuration
- Check that the MCP server starts without errors
- Restart Claude Desktop after configuration changes

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or configure via config file
[logging]
level = "DEBUG"
structured = true
```

Check MCP server logs for detailed error information.

### Performance Tuning

- **Fuel Budget**: Start with 2B instructions, increase for complex code
- **Memory Limit**: 128 MB default, increase for data processing
- **Concurrent Requests**: Limit to prevent resource exhaustion
- **Session Timeout**: Adjust based on usage patterns

## API Reference

### MCPConfig

Main configuration class for MCP server.

**Attributes:**
- `server`: Server metadata (name, version, instructions)
- `transport_stdio`: Stdio transport configuration
- `transport_http`: HTTP transport configuration
- `sessions`: Session management settings
- `logging`: Logging configuration

### MCPServer

Main MCP server class.

**Methods:**
- `start_stdio()`: Start with stdio transport
- `start_http(config)`: Start with HTTP transport
- `shutdown()`: Graceful shutdown

### WorkspaceSessionManager

Manages workspace sessions for MCP clients.

**Methods:**
- `get_or_create_session(language, session_id)`: Get or create session
- `create_session(language, session_id)`: Create new session
- `destroy_session(session_id)`: Destroy session
- `get_session_info(session_id)`: Get session metadata

## Examples Directory

Complete examples are available in the `examples/` directory:

- `mcp_stdio_example.py`: Basic stdio transport example
- `mcp_http_example.py`: HTTP transport with CORS configuration
- `mcp_claude_desktop_config.json`: Claude Desktop configuration template

## Contributing

When adding new MCP tools:

1. Define tool in `mcp_server/server.py`
2. Add comprehensive tests in `tests/test_mcp_tools.py`
3. Update this documentation
4. Test with both stdio and HTTP transports

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/specification)
- [FastMCP Documentation](https://fastmcp.com/)
- [Claude Desktop MCP Guide](https://docs.anthropic.com/claude/docs/desktop-mcp)