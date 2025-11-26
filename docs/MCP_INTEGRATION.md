# MCP Integration Guide

This guide covers integrating the LLM WASM Sandbox with the Model Context Protocol (MCP) for standardized tool use in AI applications.

## Overview

The Model Context Protocol (MCP) is an emerging standard for tool use in AI applications, providing:

- **Standardized API**: Consistent interface across different MCP clients (Claude Desktop, custom agents)
- **Stateful Sessions**: Automatic persistence of variables and execution context across tool calls
- **Streaming Support**: Real-time execution feedback for long-running code
- **Security Boundaries**: MCP layer enforces additional validation on top of WASM isolation

The sandbox provides MCP server functionality that exposes secure code execution capabilities to MCP clients.

---

## Development vs Production

### Quick Answer

| Environment | Command | When to Use |
|-------------|---------|-------------|
| **Development** | `.\scripts\run-mcp-dev.ps1` | Local development (easiest) |
| **Development** | `uv run python -m mcp_server` | Local development (direct) |
| **Production** | `llm-wasm-mcp` | After `pip install llm-wasm-sandbox` |
| **Production** | `python -m mcp_server` | After `pip install` (alternative) |

The `llm-wasm-mcp` console script is only available **after the package is installed** via `pip install`. In development, use `uv run python -m mcp_server`.

---

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
max_total_sessions = 10  # Maximum concurrent sessions across all clients
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

The MCP server provides the following tools with comprehensive metadata to guide LLM decision-making:

### execute_code

Execute code in a secure WebAssembly sandbox with comprehensive capability information.

**Enhanced Tool Description** (visible to LLMs):
The tool description now includes:
- ⚙️ **When to use** vs. **when not to use** guidance
- 🐍 **Python runtime capabilities** (pre-installed packages, import patterns, pitfalls)
- 🟨 **JavaScript runtime capabilities** (QuickJS modules, global helpers, vendored packages)
- ⚠️ **Common pitfalls** (fuel limits, path restrictions, tuple returns, C extensions)
- 🔄 **State persistence patterns** (Python globals, JavaScript _state object)
- 📋 **Usage patterns** (one-off, file processing, stateful workflows, heavy packages)

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
    "success": true,
    "files_changed": []
  },
  "execution_time_ms": 45.2,
  "success": true
}
```

#### Files Changed (v0.5.1+)

When code creates or modifies files, the response includes a `files_changed` array with structured file information:

```json
{
  "structured_content": {
    "stdout": "File created\n",
    "success": true,
    "files_changed": [
      {
        "absolute": "C:\\Users\\user\\project\\workspace\\session-id\\data.csv",
        "relative": "workspace\\session-id\\data.csv",
        "filename": "data.csv"
      },
      {
        "absolute": "C:\\Users\\user\\project\\workspace\\session-id\\report.json",
        "relative": "workspace\\session-id\\report.json",
        "filename": "report.json"
      }
    ]
  }
}
```

**File Path Fields:**
- `absolute`: Full filesystem path to the file
- `relative`: Path relative to the project/server working directory
- `filename`: Just the filename without any path components

**Notes:**
- System files (`.metadata.json`, `user_code.py`, `__state__.json`, `site-packages/`, `__pycache__/`) are automatically filtered out
- Files appearing in both `files_created` and `files_modified` are deduplicated
- Useful for LLMs to know which files were affected and where to find them

#### Error Guidance (v0.4.1+)

When execution fails, the `execute_code` tool automatically provides structured error guidance in `structured_content.error_guidance`:

**Error Guidance Structure:**
```json
{
  "error_type": "OutOfFuel",
  "actionable_guidance": [
    "Code execution exceeded the fuel budget (instruction limit).",
    "This typically occurs with:",
    "  - Heavy package imports (openpyxl: 5-7B, PyPDF2: 5-6B, jinja2: 5-10B fuel on first import)",
    "  - Large dataset processing (loops over big files/arrays)",
    "  - Infinite loops or very deep recursion",
    "Solutions:",
    "1. Increase fuel_budget when creating session or calling execute_code:",
    "   - For heavy packages: Use 10B+ for first import, 2B+ for subsequent executions",
    "   - For large datasets: Estimate ~1B fuel per 100K loop iterations",
    "2. Use persistent sessions (auto_persist_globals=True) to cache imports across executions",
    "Concrete recommendation: Increase fuel_budget from 5,000,000,000 to 10,000,000,000 instructions"
  ],
  "related_docs": [
    "docs/PYTHON_CAPABILITIES.md#fuel-requirements",
    "docs/MCP_INTEGRATION.md#fuel-budgeting"
  ],
  "code_examples": [
    {
      "before": "sandbox.execute(code)  # Uses default 5B fuel",
      "after": "sandbox.execute(code, fuel_budget=10_000_000_000)  # 10B for heavy packages",
      "explanation": "Increase fuel budget for package imports or large computations"
    }
  ]
}
```

**Supported Error Types:**

| Error Type | When It Occurs | Key Guidance |
|-----------|---------------|-------------|
| `OutOfFuel` | Fuel budget exhausted | Increase fuel_budget, use sessions for import caching |
| `PathRestriction` | File access outside /app | Use /app prefix or relative paths |
| `QuickJSTupleDestructuring` | JS destructuring error | Use `[a, b] = func()` not `(a, b) = func()` |
| `MissingVendoredPackage` | Python import error | Add `sys.path.insert(0, '/data/site-packages')` |
| `MissingRequireVendor` | JS vendored import | Use `requireVendor('package')` not `require()` |
| `MemoryExhausted` | Memory limit exceeded | Increase memory_bytes or process data in chunks |

**Example Error Response:**
```json
{
  "content": "Execution trapped: OutOfFuel",
  "structured_content": {
    "stdout": "",
    "stderr": "Execution trapped: OutOfFuel",
    "exit_code": 1,
    "success": false,
    "error_guidance": {
      "error_type": "OutOfFuel",
      "actionable_guidance": [
        "Code execution exceeded the fuel budget (instruction limit).",
        "Detected heavy package(s): openpyxl",
        "These packages require higher fuel budgets on first import (5-10B).",
        "Solutions:",
        "1. Increase fuel_budget when creating session:",
        "   sandbox.execute(code, fuel_budget=10_000_000_000)",
        "2. Use persistent sessions to cache imports (100x faster subsequent runs)",
        "Concrete recommendation: Increase fuel_budget from 5,000,000,000 to 10,000,000,000 instructions"
      ],
      "related_docs": [
        "docs/PYTHON_CAPABILITIES.md#fuel-requirements"
      ],
      "code_examples": [...]
    }
  }
}
```

**Best Practices:**
1. **Check error_guidance field** when `success: false`
2. **Follow actionable_guidance** steps in order (most specific first)
3. **Use code_examples** as templates for fixing errors
4. **Reference related_docs** for deeper understanding
5. **Retry with recommendations** (e.g., increased fuel_budget) when applicable

#### Fuel Budget Analysis (v0.5.0+)

All executions now include proactive fuel budget analysis in `structured_content.fuel_analysis`, helping LLMs make informed decisions about resource allocation:

**Fuel Analysis Structure:**
```json
{
  "consumed": 4500000000,
  "budget": 5000000000,
  "utilization_percent": 90.0,
  "status": "critical",
  "recommendation": "🚨 Fuel usage is critical (90.0%). Increase budget to 9B instructions to avoid exhaustion (current: 5B). Package fuel requirements: openpyxl requires 5-7B for first import. Note: Using a persistent session will cache imports, reducing fuel needs for subsequent executions",
  "likely_causes": [
    "Heavy package imports detected: openpyxl",
    "Note: Subsequent imports in this session will be faster (cached)"
  ]
}
```

**Status Classifications:**

| Status | Utilization | Meaning | Action Required |
|--------|-------------|---------|----------------|
| `efficient` | <50% | Budget is appropriate | None - continue using current settings |
| `moderate` | 50-75% | Budget is adequate | Monitor for similar workloads |
| `warning` | 75-90% | Approaching limit | Consider increasing for future runs |
| `critical` | 90-100% | Near exhaustion | Must increase budget for similar code |
| `exhausted` | 100% | Budget exceeded | Execution failed - increase immediately |

**Example Fuel Analysis Response:**
```json
{
  "content": "Success output here",
  "structured_content": {
    "stdout": "Imported openpyxl\nProcessed data\n",
    "stderr": "",
    "exit_code": 0,
    "success": true,
    "fuel_consumed": 6500000000,
    "fuel_analysis": {
      "consumed": 6500000000,
      "budget": 10000000000,
      "utilization_percent": 65.0,
      "status": "moderate",
      "recommendation": "Fuel usage is moderate (65.0%). Current budget is adequate, but consider increasing if similar tasks are planned",
      "likely_causes": [
        "Heavy package imports detected: openpyxl"
      ]
    }
  }
}
```

**Proactive Recommendations:**

The `recommendation` field provides concrete, actionable guidance:
- **Specific numbers**: "Increase to 15B" not "increase budget"
- **Package requirements**: "openpyxl requires 5-7B for first import"
- **Session optimization**: Suggests persistent sessions for import caching
- **Safety margins**: 50-100% buffer to prevent future exhaustion

**Best Practices:**
1. **Monitor fuel_analysis.status** even on successful executions
2. **Act on warning/critical status** before hitting OutOfFuel errors
3. **Use persistent sessions** for heavy packages (100x faster subsequent imports)
4. **Follow concrete recommendations** (e.g., "Increase to 15B instructions")
5. **Check likely_causes** to understand fuel consumption patterns


### `list_runtimes`

List available programming language runtimes with comprehensive metadata.

**Enhanced Response** (v0.4.0+):
The tool now returns detailed runtime information including:
- Version details (Python 3.12, JavaScript ES2023)
- Feature support (ES2020+, async/await, etc.)
- Pre-installed package counts and notable packages
- API patterns (import syntax, file I/O, state access)
- Helper functions available per runtime
- Fuel requirements per package/module

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
  "content": "Available runtimes:\n\n🔹 python (3.12)\n   CPython compiled to WebAssembly\n   📦 Packages: 30\n   💡 Notable: openpyxl (Excel .xlsx), PyPDF2 (PDF processing), tabulate (table formatting)\n\n🔹 javascript (ES2023)\n   QuickJS JavaScript engine in WebAssembly\n   📦 Packages: 5\n   💡 Notable: csv.js (CSV parsing/generation), json_path.js (JSONPath queries), string_utils.js (string manipulation)\n\n💡 Tip: Use list_available_packages for complete package list with fuel requirements",
  "structured_content": {
    "runtimes": [
      {
        "name": "python",
        "version": "3.12",
        "description": "CPython compiled to WebAssembly",
        "features": {
          "es_version": "N/A (Python, not JavaScript)",
          "standard_library": "Full Python 3.12 stdlib",
          "pre_installed_packages": 30,
          "notable_packages": [
            "openpyxl (Excel .xlsx)",
            "PyPDF2 (PDF processing)",
            "tabulate (table formatting)",
            "jinja2 (templating)",
            "markdown, python-dateutil, attrs"
          ],
          "state_persistence": "All global variables (when auto_persist_globals=True)",
          "import_caching": "Automatic in sessions (100x faster subsequent imports)"
        },
        "api_patterns": {
          "file_io": "Standard Python: open('/app/file.txt', 'r')",
          "import_syntax": "import openpyxl  # No sys.path needed, automatic",
          "state_access": "globals().get('var_name', default)  # Recommended pattern",
          "path_requirement": "All paths must start with /app/ (WASI restriction)"
        },
        "helper_functions": [
          "N/A - Use standard Python built-ins and stdlib",
          "pathlib.Path for path operations",
          "json.load/dump, csv.reader/writer for data"
        ],
        "fuel_requirements": {
          "stdlib_modules": "<500M fuel per import",
          "light_packages": "1-3B fuel (tabulate, markdown, dateutil)",
          "heavy_packages": "5-10B fuel (openpyxl, PyPDF2, jinja2) - FIRST import only",
          "cached_imports": "<100M fuel (subsequent imports in same session)"
        }
      },
      {
        "name": "javascript",
        "version": "ES2023",
        "description": "QuickJS JavaScript engine in WebAssembly",
        "features": {
          "es_version": "ES2020+ (async/await, optional chaining, nullish coalescing, etc.)",
          "standard_library": "Full ES2023 built-ins (Array, Object, Map, Set, Promise, etc.)",
          "quickjs_modules": ["std (file I/O)", "os (filesystem operations)"],
          "vendored_packages": 5,
          "notable_packages": [
            "csv.js (CSV parsing/generation)",
            "json_path.js (JSONPath queries)",
            "string_utils.js (string manipulation)",
            "sandbox_utils.js (file I/O helpers - auto-injected)"
          ],
          "state_persistence": "_state object (when auto_persist_globals=True)",
          "global_helpers": "Auto-injected: readJson, writeJson, readText, writeText, listFiles, etc."
        },
        "api_patterns": {
          "file_io_simple": "readJson('/app/data.json')  # Global helper, returns data or null",
          "file_io_advanced": "import * as std from 'std'; const f = std.open('/app/file.txt', 'r');",
          "vendored_packages": "const csv = requireVendor('csv.js');  # Function auto-injected",
          "state_access": "_state.counter = (_state.counter || 0) + 1;  # Always initialize",
          "path_requirement": "All paths must start with /app/ (WASI restriction)",
          "tuple_returns": "⚠️ QuickJS functions return [value, error] tuples - check truthiness before use"
        },
        "helper_functions": [
          "readJson(path), writeJson(path, data) - JSON I/O",
          "readText(path), writeText(path, text) - Text I/O",
          "readLines(path), writeLines(path, lines) - Line-based I/O",
          "appendText(path, text) - Append to file",
          "listFiles(dirPath) - List directory contents",
          "fileExists(path), fileSize(path) - File info",
          "copyFile(src, dest), removeFile(path) - File ops"
        ],
        "fuel_requirements": {
          "vendored_packages": "<100M fuel per requireVendor() call",
          "std_os_modules": "<50M fuel per import",
          "helper_functions": "<10M fuel per call (negligible overhead)"
        }
      }
    ]
  }
}
```

### create_session

Create a new workspace session for code execution with comprehensive decision guidance.

**Enhanced Tool Description** (v0.4.0+):
The tool description now includes:
- 🤔 **When to create session** vs. **use default** decision tree
- 🔄 **Auto-persist guidelines** (what gets persisted, limitations, performance)
- 🔧 **Session lifecycle patterns** (create, execute, check status, cleanup)
- ⚡ **Custom configuration guidance** (fuel budgets for heavy packages)
- 📋 **Usage examples** (counter patterns, import caching, multi-step pipelines)

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

**Package import errors (ModuleNotFoundError)**
- **CRITICAL**: Vendored packages are now automatically available - no manual `sys.path.insert()` needed!
- MCP server automatically configures `/data/site-packages` in Python path
- Just import packages directly:
  ```python
  from openpyxl import Workbook  # Works automatically!
  import tabulate
  import PyPDF2
  ```
- Use `list_available_packages` tool to see all 50+ pre-installed packages
- Available packages include: openpyxl, XlsxWriter, PyPDF2, tabulate, jinja2, markdown, python-dateutil, and more
- Note: Only pure-Python packages work in WASM (no C/Rust extensions)

**Fuel budget errors (OutOfFuel) when importing packages**
- **MCP server uses 10B default fuel budget** (10x higher than library default of 2B)
- Heavy packages require more fuel for first import:
  - `openpyxl`: ~5-7B fuel (first import only)
  - `PyPDF2`: ~5-6B fuel (first import only)
  - `jinja2`: ~4-5B fuel (first import only)
  - `tabulate`, `markdown`: <2B (work with any budget)
- Subsequent imports in same session use cached modules (<100M fuel)
- For custom policies, use 10B+ for heavy packages:
  ```python
  policy = ExecutionPolicy(fuel_budget=10_000_000_000)
  ```

**Path confusion (/app vs /data)**
- `/app` = Your session workspace (read/write files here)
- `/data/site-packages` = Vendored packages (read-only, shared across sessions)
- Example workflow:
  ```python
  import sys
  sys.path.insert(0, '/data/site-packages')  # Add vendored packages
  from openpyxl import Workbook  # Import from /data
  
  wb = Workbook()
  wb.save('/app/output.xlsx')  # Save to workspace
  ```

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

---

## JavaScript Runtime via MCP

All JavaScript features documented for the Python API are fully functional via MCP:

- ✅ `std` module (file I/O with `std.open()`, `std.loadFile()`, etc.)
- ✅ `os` module (environment variables, file stats, directory operations)
- ✅ `requireVendor()` function for loading vendored packages
- ✅ Helper functions (`readJson`, `writeJson`, `readText`, `listFiles`, etc.)
- ✅ `_state` object for automatic state persistence (requires `auto_persist_globals=True`)

### JavaScript Usage Patterns

**One-Shot Execution (no session):**
```javascript
const data = {message: "Hello, MCP!"};
writeJson('/app/output.json', data);
const result = readJson('/app/output.json');
console.log("Data:", JSON.stringify(result));
```

**Persistent Session with State:**
```json
// Step 1: Create session with auto_persist_globals
{"tool": "create_session", "arguments": {"language": "javascript", "auto_persist_globals": true}}

// Step 2: Use _state object
{"tool": "execute_code", "arguments": {"code": "_state.counter = (_state.counter || 0) + 1; console.log(_state.counter);"}}
```

**Using Vendored Packages:**
```javascript
const csv = requireVendor('csv');
const data = csv.parse("name,age\nAlice,30\nBob,25");
console.log(JSON.stringify(data));
```

### JavaScript Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Missing `_state` | `ReferenceError: _state is not defined` | Create session with `auto_persist_globals: true` |
| Node.js APIs | `require('fs')` not available | Use QuickJS `std`/`os` modules |
| No session reuse | State lost between calls | Pass `session_id` to all `execute_code` calls |

### Feature Parity

| Feature | Python API | MCP Server |
|---------|-----------|-----------|
| std module | ✅ | ✅ |
| os module | ✅ | ✅ |
| requireVendor() | ✅ | ✅ |
| Helper functions | ✅ | ✅ |
| _state persistence | ✅ | ✅ |
| Vendored packages | ✅ | ✅ |
| Session reuse | ✅ | ✅ |

See [JAVASCRIPT_CAPABILITIES.md](./JAVASCRIPT_CAPABILITIES.md) for complete JavaScript runtime documentation.