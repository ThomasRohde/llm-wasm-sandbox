# LLM WASM Sandbox MCP Server

## Product Requirements Document (PRD)

**Project:** `llm-wasm-sandbox-mcp`  
**Repository:** ThomasRohde/llm-wasm-sandbox  
**MCP Protocol Version:** 2025-06-18  
**Document Version:** 1.0.0  
**Date:** November 2025

---

## 1. Executive Summary

### 1.1 Purpose

This document defines the requirements for developing a Model Context Protocol (MCP) server that provides secure, sandboxed code execution capabilities using WebAssembly (WASM). The server enables Large Language Models (LLMs) to safely execute generated code within an isolated WASM environment, eliminating the security risks associated with running untrusted code on host systems.

### 1.2 Key Value Proposition

- **Security**: WASM sandboxing provides memory-safe, isolated execution with no host system access
- **Portability**: Single binary, cross-platform compatibility
- **Performance**: Near-native execution speed with minimal overhead
- **Lightweight**: No container orchestration required (unlike Docker/Kubernetes alternatives)
- **Standards-Compliant**: Full MCP 2025-06-18 specification compliance
- **Modern Framework**: Built with FastMCP 2.0 for production-ready MCP development

### 1.3 Target Users

- AI application developers integrating code execution capabilities
- Enterprise architects deploying agentic AI systems
- Claude Desktop and other MCP client users
- Development teams requiring secure code interpreter functionality

---

## 2. Technical Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP Clients                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │Claude Desktop│  │ Claude Code  │  │  Custom MCP Clients      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
└─────────┼─────────────────┼────────────────────────┼────────────────┘
          │                 │                        │
          │    stdio        │    Streamable HTTP     │
          │                 │                        │
┌─────────▼─────────────────▼────────────────────────▼────────────────┐
│                    LLM WASM Sandbox MCP Server                       │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Transport Layer                              │ │
│  │  ┌──────────────────┐    ┌───────────────────────────────────┐ │ │
│  │  │  stdio Transport │    │  Streamable HTTP Transport        │ │ │
│  │  │  (JSON-RPC/NL)   │    │  (JSON-RPC/SSE)                   │ │ │
│  │  └──────────────────┘    └───────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    MCP Protocol Handler                         │ │
│  │  • Lifecycle Management (initialize/initialized/shutdown)       │ │
│  │  • Capability Negotiation                                       │ │
│  │  • JSON-RPC Message Processing                                  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Tools Layer                                  │ │
│  │  ┌──────────────┐ ┌─────────────┐ ┌──────────────────────────┐ │ │
│  │  │ execute_code │ │ list_runtimes│ │ get_execution_result    │ │ │
│  │  └──────────────┘ └─────────────┘ └──────────────────────────┘ │ │
│  │  ┌──────────────┐ ┌─────────────┐ ┌──────────────────────────┐ │ │
│  │  │install_package││create_session││    cancel_execution      │ │ │
│  │  └──────────────┘ └─────────────┘ └──────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    WASM Sandbox Engine                          │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │                 WASI Runtime (wasmtime)                   │  │ │
│  │  │  • Memory isolation     • Resource limits                │  │ │
│  │  │  • Filesystem sandboxing • Execution timeouts            │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │  ┌──────────────────────────────────────────────────────────┐  │ │
│  │  │              Language Runtimes (WASM modules)             │  │ │
│  │  │  ┌─────────┐  ┌────────────┐  ┌─────────────────────┐   │  │ │
│  │  │  │ Python  │  │ JavaScript │  │   Additional Langs  │   │  │ │
│  │  │  │(Pyodide)│  │  (QuickJS) │  │    (Lua, Ruby...)   │   │  │ │
│  │  │  └─────────┘  └────────────┘  └─────────────────────┘   │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| Transport Layer | Handle stdio and Streamable HTTP communication |
| Protocol Handler | MCP lifecycle, capability negotiation, JSON-RPC |
| Tools Layer | Expose MCP tools for code execution operations |
| WASM Sandbox Engine | Secure, isolated code execution environment |
| Language Runtimes | Language-specific interpreters compiled to WASM |

### 2.3 FastMCP 2.0 Framework

This implementation uses **FastMCP 2.0**, the production-ready Python framework for MCP development. FastMCP 2.0 provides:

#### Why FastMCP 2.0?

1. **Pythonic API**: Decorators and type hints for tool definitions
2. **Automatic Schema Generation**: Input/output schemas from type annotations
3. **Structured Outputs**: Native support for MCP 2025-06-18 `structuredContent`
4. **Built-in Transports**: stdio and Streamable HTTP out of the box
5. **Context Injection**: Access to logging, progress reporting, and resources
6. **Production Features**: Error handling, validation, async support

#### Key FastMCP 2.0 Patterns Used

```python
# 1. Tool with annotations (metadata for clients)
@mcp.tool(
    annotations={
        "title": "Execute Code",
        "readOnlyHint": False,
        "destructiveHint": False,
    }
)
async def execute_code(...) -> ExecutionResult:
    ...

# 2. Typed parameters with Annotated + Field
from typing import Annotated
from pydantic import Field

async def tool(
    param: Annotated[int, Field(description="...", ge=1, le=100)] = 10
):
    ...

# 3. Structured output with dataclasses
@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    exit_code: int

# 4. ToolResult for advanced control
from fastmcp.tools.tool import ToolResult

return ToolResult(
    content="Human readable message",
    structured_content={"machine": "readable"},
    meta={"execution_time_ms": 45.2}
)

# 5. Context for logging and progress
async def tool(ctx: Context):
    await ctx.info("Starting execution")
    await ctx.report_progress(progress=50, total=100)
```

---

## 3. MCP Protocol Compliance

### 3.1 Protocol Version

This server MUST implement **MCP Protocol Version 2025-06-18**, the latest stable specification.

### 3.2 Server Capabilities Declaration

```json
{
  "capabilities": {
    "tools": {
      "listChanged": true
    },
    "logging": {},
    "experimental": {
      "streaming_execution": true
    }
  },
  "serverInfo": {
    "name": "llm-wasm-sandbox",
    "title": "LLM WASM Sandbox",
    "version": "1.0.0"
  },
  "instructions": "This server provides secure code execution in a WebAssembly sandbox. Use the execute_code tool to run Python or JavaScript code safely."
}
```

### 3.3 Lifecycle Implementation

#### 3.3.1 Initialization Phase

The server MUST handle the `initialize` request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {
      "roots": { "listChanged": true },
      "sampling": {}
    },
    "clientInfo": {
      "name": "ExampleClient",
      "version": "1.0.0"
    }
  }
}
```

Response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2025-06-18",
    "capabilities": {
      "tools": { "listChanged": true },
      "logging": {}
    },
    "serverInfo": {
      "name": "llm-wasm-sandbox",
      "title": "LLM WASM Sandbox",
      "version": "1.0.0"
    },
    "instructions": "Secure code execution sandbox using WebAssembly. Supports Python and JavaScript."
  }
}
```

#### 3.3.2 Operation Phase

After receiving `notifications/initialized`, the server enters the operation phase and processes tool calls.

#### 3.3.3 Shutdown Phase

- **stdio**: Server exits when stdin is closed or upon receiving SIGTERM
- **HTTP**: Session terminates on HTTP DELETE to MCP endpoint or session timeout

---

## 4. Transport Implementations

### 4.1 stdio Transport

#### 4.1.1 Specification

- Server reads JSON-RPC messages from `stdin`
- Server writes JSON-RPC messages to `stdout`
- Messages are newline-delimited (`\n`)
- Messages MUST NOT contain embedded newlines
- Logging MAY be written to `stderr`
- UTF-8 encoding REQUIRED

#### 4.1.2 Usage

```bash
# Direct execution
python -m llm_wasm_sandbox.server

# Via fastmcp CLI
fastmcp run server.py
```

#### 4.1.3 Claude Desktop Configuration

```json
{
  "mcpServers": {
    "llm-wasm-sandbox": {
      "command": "python3",
      "args": ["-m", "llm_wasm_sandbox.server"],
      "env": {
        "WASM_SANDBOX_TIMEOUT": "30",
        "WASM_SANDBOX_MEMORY_MB": "256"
      }
    }
  }
}
```

### 4.2 Streamable HTTP Transport

#### 4.2.1 Specification

- Single MCP endpoint (e.g., `https://localhost:8080/mcp`)
- Supports both POST and GET methods
- POST: Client sends JSON-RPC messages
- GET: Opens SSE stream for server-initiated messages
- Session management via `Mcp-Session-Id` header
- Protocol version via `MCP-Protocol-Version` header

#### 4.2.2 Security Requirements

1. **MUST** validate `Origin` header on all requests
2. **SHOULD** bind to localhost (127.0.0.1) for local deployments
3. **SHOULD** implement authentication for remote deployments
4. **MUST** use HTTPS in production

#### 4.2.3 HTTP Endpoint Behavior

**POST Request (Client → Server)**:
```http
POST /mcp HTTP/1.1
Host: localhost:8080
Content-Type: application/json
Accept: application/json, text/event-stream
MCP-Protocol-Version: 2025-06-18
Mcp-Session-Id: <session-id>

{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"execute_code","arguments":{"code":"print('hello')","language":"python"}}}
```

**Response Options**:
1. `Content-Type: application/json` - Single JSON response
2. `Content-Type: text/event-stream` - SSE stream for streaming results

**GET Request (Server → Client channel)**:
```http
GET /mcp HTTP/1.1
Host: localhost:8080
Accept: text/event-stream
MCP-Protocol-Version: 2025-06-18
Mcp-Session-Id: <session-id>
```

#### 4.2.4 Session Management

```python
# Session ID generation (cryptographically secure)
import secrets
session_id = secrets.token_urlsafe(32)

# Session lifecycle
# 1. Server returns Mcp-Session-Id on InitializeResult
# 2. Client includes Mcp-Session-Id on all subsequent requests
# 3. Session expires on timeout or HTTP DELETE
```

#### 4.2.5 Server Startup

```bash
# HTTP transport on port 8080
python -m llm_wasm_sandbox.server --transport http --port 8080

# With authentication
python -m llm_wasm_sandbox.server --transport http --port 8080 --auth-token $TOKEN
```

---

## 5. Tool Definitions

### 5.1 Core Tools

#### 5.1.1 execute_code

Execute code in the WASM sandbox.

```json
{
  "name": "execute_code",
  "title": "Execute Code",
  "description": "Execute code in a secure WebAssembly sandbox. Supports Python and JavaScript. Returns stdout, stderr, and execution status.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "code": {
        "type": "string",
        "description": "The source code to execute"
      },
      "language": {
        "type": "string",
        "enum": ["python", "javascript"],
        "description": "Programming language of the code"
      },
      "timeout": {
        "type": "integer",
        "description": "Execution timeout in seconds (default: 30, max: 300)",
        "minimum": 1,
        "maximum": 300
      },
      "session_id": {
        "type": "string",
        "description": "Optional session ID for stateful execution (preserves variables between calls)"
      }
    },
    "required": ["code", "language"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "stdout": {
        "type": "string",
        "description": "Standard output from execution"
      },
      "stderr": {
        "type": "string",
        "description": "Standard error from execution"
      },
      "exit_code": {
        "type": "integer",
        "description": "Exit code (0 = success)"
      },
      "execution_time_ms": {
        "type": "number",
        "description": "Execution time in milliseconds"
      },
      "memory_used_bytes": {
        "type": "integer",
        "description": "Peak memory usage in bytes"
      },
      "truncated": {
        "type": "boolean",
        "description": "Whether output was truncated due to size limits"
      }
    },
    "required": ["stdout", "stderr", "exit_code", "execution_time_ms"]
  },
  "annotations": {
    "destructive": false,
    "idempotent": false,
    "openWorld": false
  }
}
```

**Example Request**:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "import math\nprint(f'Pi is approximately {math.pi:.10f}')",
      "language": "python",
      "timeout": 10
    }
  }
}
```

**Example Response**:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Pi is approximately 3.1415926536"
      }
    ],
    "structuredContent": {
      "stdout": "Pi is approximately 3.1415926536\n",
      "stderr": "",
      "exit_code": 0,
      "execution_time_ms": 45.2,
      "memory_used_bytes": 4194304,
      "truncated": false
    },
    "isError": false
  }
}
```

#### 5.1.2 list_runtimes

List available language runtimes.

```json
{
  "name": "list_runtimes",
  "title": "List Available Runtimes",
  "description": "List all available programming language runtimes in the sandbox",
  "inputSchema": {
    "type": "object",
    "properties": {}
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "runtimes": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "language": { "type": "string" },
            "version": { "type": "string" },
            "wasm_module": { "type": "string" },
            "features": {
              "type": "array",
              "items": { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

#### 5.1.3 create_session

Create a stateful execution session.

```json
{
  "name": "create_session",
  "title": "Create Execution Session",
  "description": "Create a new stateful execution session. Variables and imports persist across execute_code calls within the same session.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "language": {
        "type": "string",
        "enum": ["python", "javascript"],
        "description": "Programming language for this session"
      },
      "memory_limit_mb": {
        "type": "integer",
        "description": "Memory limit in MB (default: 256, max: 1024)",
        "minimum": 64,
        "maximum": 1024
      },
      "timeout_seconds": {
        "type": "integer",
        "description": "Session inactivity timeout (default: 600)",
        "minimum": 60,
        "maximum": 3600
      }
    },
    "required": ["language"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "session_id": { "type": "string" },
      "language": { "type": "string" },
      "created_at": { "type": "string", "format": "date-time" },
      "expires_at": { "type": "string", "format": "date-time" }
    },
    "required": ["session_id", "language", "created_at", "expires_at"]
  }
}
```

#### 5.1.4 destroy_session

Destroy an execution session.

```json
{
  "name": "destroy_session",
  "title": "Destroy Execution Session",
  "description": "Destroy a stateful execution session and free its resources",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {
        "type": "string",
        "description": "Session ID to destroy"
      }
    },
    "required": ["session_id"]
  }
}
```

#### 5.1.5 install_package (Python only)

Install a Python package in a session.

```json
{
  "name": "install_package",
  "title": "Install Python Package",
  "description": "Install a Python package using micropip in an active session. Only works with pure Python packages or packages with pre-built WASM wheels.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {
        "type": "string",
        "description": "Session ID to install the package in"
      },
      "package": {
        "type": "string",
        "description": "Package name (e.g., 'numpy', 'pandas')"
      },
      "version": {
        "type": "string",
        "description": "Optional version specifier (e.g., '>=1.0.0')"
      }
    },
    "required": ["session_id", "package"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "success": { "type": "boolean" },
      "package": { "type": "string" },
      "version_installed": { "type": "string" },
      "message": { "type": "string" }
    }
  }
}
```

#### 5.1.6 cancel_execution

Cancel a running execution.

```json
{
  "name": "cancel_execution",
  "title": "Cancel Execution",
  "description": "Cancel a currently running code execution",
  "inputSchema": {
    "type": "object",
    "properties": {
      "execution_id": {
        "type": "string",
        "description": "Execution ID to cancel (returned from execute_code with streaming)"
      }
    },
    "required": ["execution_id"]
  }
}
```

### 5.2 Tools List Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "execute_code",
        "title": "Execute Code in WASM Sandbox",
        "description": "Execute code in a secure WebAssembly sandbox. State persists automatically between calls.",
        "inputSchema": { "..." }
      },
      {
        "name": "list_runtimes",
        "title": "List Available Runtimes",
        "description": "List all available programming language runtimes",
        "inputSchema": { "..." }
      },
      {
        "name": "get_workspace_info",
        "title": "Get Workspace Information",
        "description": "Get information about the current workspace session including defined variables and imported modules",
        "inputSchema": { "..." }
      },
      {
        "name": "reset_workspace",
        "title": "Reset Workspace",
        "description": "Reset the current workspace session, clearing all variables and imports",
        "inputSchema": { "..." }
      },
      {
        "name": "create_session",
        "title": "Create Execution Session",
        "description": "Create a new explicit stateful execution session (for advanced use)",
        "inputSchema": { "..." }
      },
      {
        "name": "destroy_session",
        "title": "Destroy Execution Session",
        "description": "Destroy an explicit stateful execution session",
        "inputSchema": { "..." }
      },
      {
        "name": "install_package",
        "title": "Install Python Package",
        "description": "Install a Python package in the current workspace",
        "inputSchema": { "..." }
      },
      {
        "name": "cancel_execution",
        "title": "Cancel Execution",
        "description": "Cancel a currently running code execution",
        "inputSchema": { "..." }
      }
    ]
  }
}
```

---

## 6. Workspace Session Management

### 6.1 Overview

A critical requirement for agentic AI workflows is **state persistence across multiple tool calls**. When an AI agent executes code in multiple steps, variables, imports, and state must persist between calls without requiring the agent to explicitly manage session IDs.

```
Agent Call 1: execute_code("x = 42", "python")           → Success
Agent Call 2: execute_code("y = x * 2", "python")        → Success (x is remembered)
Agent Call 3: execute_code("print(f'Result: {y}')", "python") → "Result: 84"
```

### 6.2 Automatic Workspace Sessions

The MCP server maintains **one workspace session per MCP client connection**. This workspace is automatically created on first use and reused for all subsequent calls from the same agent/client.

#### 6.2.1 Session Binding Strategy

| Transport | Session Binding | Lifecycle |
|-----------|-----------------|-----------|
| **stdio** | Single workspace per process | Lives until server process exits |
| **Streamable HTTP** | Bound to `Mcp-Session-Id` header | Lives until MCP session expires or DELETE |

#### 6.2.2 How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AI Agent (Claude, etc.)                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ MCP calls (same Mcp-Session-Id)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MCP Server                                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    Session Manager                                 │  │
│  │                                                                    │  │
│  │   MCP Session A ──────────► Workspace Session (Python)            │  │
│  │   (Mcp-Session-Id: abc123)     • Variables: {x: 42, y: 84}        │  │
│  │                                • Imports: [numpy, pandas]          │  │
│  │                                • History: [code1, code2, ...]      │  │
│  │                                                                    │  │
│  │   MCP Session B ──────────► Workspace Session (Python)            │  │
│  │   (Mcp-Session-Id: xyz789)     • Variables: {data: [...]}         │  │
│  │                                • Imports: [json]                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Updated Tool Behavior

#### 6.3.1 execute_code with Automatic Sessions

The `execute_code` tool supports three modes:

| Mode | `session_id` Parameter | Behavior |
|------|------------------------|----------|
| **Auto (Default)** | `None` or omitted | Uses/creates workspace session for current MCP client |
| **Explicit** | Valid session ID | Uses specified session |
| **Stateless** | `"__stateless__"` | Fresh execution, no state persistence |

```python
# Agent doesn't need to track sessions - state persists automatically
await client.call_tool("execute_code", {"code": "x = 42", "language": "python"})
await client.call_tool("execute_code", {"code": "print(x)", "language": "python"})  # Works!

# Explicitly stateless if needed
await client.call_tool("execute_code", {
    "code": "print('isolated')",
    "language": "python",
    "session_id": "__stateless__"
})
```

#### 6.3.2 Session Information Tool

New tool to inspect current workspace state:

```json
{
  "name": "get_workspace_info",
  "title": "Get Workspace Information",
  "description": "Get information about the current workspace session including defined variables and imported modules.",
  "inputSchema": {
    "type": "object",
    "properties": {}
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "session_id": { "type": "string" },
      "language": { "type": "string" },
      "variables": { 
        "type": "array",
        "items": { "type": "string" },
        "description": "List of defined variable names"
      },
      "imports": {
        "type": "array", 
        "items": { "type": "string" },
        "description": "List of imported module names"
      },
      "execution_count": { "type": "integer" },
      "memory_used_bytes": { "type": "integer" },
      "created_at": { "type": "string", "format": "date-time" }
    }
  }
}
```

#### 6.3.3 Reset Workspace Tool

Allow agents to reset their workspace without destroying the MCP session:

```json
{
  "name": "reset_workspace",
  "title": "Reset Workspace",
  "description": "Reset the current workspace session, clearing all variables and imports while maintaining the MCP connection.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "language": {
        "type": "string",
        "enum": ["python", "javascript"],
        "description": "Language for the new workspace (default: same as before)"
      }
    }
  }
}
```

### 6.4 Implementation

#### 6.4.1 Session Manager

```python
# src/llm_wasm_sandbox/sessions/manager.py
"""
Workspace Session Manager

Maps MCP client sessions to WASM sandbox sessions for automatic
state persistence across tool calls.
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import secrets

from fastmcp import Context


@dataclass
class WorkspaceSession:
    """A workspace session bound to an MCP client."""
    workspace_id: str
    mcp_session_id: str
    language: str
    sandbox_session_id: str  # Underlying WASM session
    created_at: datetime
    last_used_at: datetime
    execution_count: int = 0
    variables: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


class WorkspaceSessionManager:
    """
    Manages workspace sessions for MCP clients.
    
    Each MCP client (identified by Mcp-Session-Id or stdio connection)
    gets one workspace session per language that persists across calls.
    """
    
    def __init__(
        self,
        sandbox_engine,
        default_timeout_minutes: int = 60,
        max_sessions_per_client: int = 5,
    ):
        self.sandbox = sandbox_engine
        self.default_timeout = timedelta(minutes=default_timeout_minutes)
        self.max_sessions_per_client = max_sessions_per_client
        
        # MCP Session ID -> Language -> WorkspaceSession
        self._workspaces: dict[str, dict[str, WorkspaceSession]] = {}
        self._lock = asyncio.Lock()
        
        # For stdio transport (single client)
        self._stdio_session_id = "__stdio__"
    
    async def get_or_create_workspace(
        self,
        mcp_session_id: Optional[str],
        language: str,
        ctx: Optional[Context] = None,
    ) -> WorkspaceSession:
        """
        Get existing workspace or create new one for the MCP client.
        
        Args:
            mcp_session_id: MCP session ID (None for stdio)
            language: Programming language
            ctx: FastMCP context for logging
        
        Returns:
            WorkspaceSession for this client/language combination
        """
        session_id = mcp_session_id or self._stdio_session_id
        
        async with self._lock:
            # Get or create client's workspace dict
            if session_id not in self._workspaces:
                self._workspaces[session_id] = {}
            
            client_workspaces = self._workspaces[session_id]
            
            # Check for existing workspace for this language
            if language in client_workspaces:
                workspace = client_workspaces[language]
                workspace.last_used_at = datetime.utcnow()
                
                if ctx:
                    await ctx.debug(f"Reusing workspace {workspace.workspace_id[:8]}...")
                
                return workspace
            
            # Check session limit
            if len(client_workspaces) >= self.max_sessions_per_client:
                # Remove oldest workspace
                oldest = min(
                    client_workspaces.values(),
                    key=lambda w: w.last_used_at
                )
                await self._destroy_workspace(oldest)
                del client_workspaces[oldest.language]
            
            # Create new workspace
            workspace = await self._create_workspace(session_id, language)
            client_workspaces[language] = workspace
            
            if ctx:
                await ctx.info(
                    f"Created new {language} workspace {workspace.workspace_id[:8]}..."
                )
            
            return workspace
    
    async def _create_workspace(
        self,
        mcp_session_id: str,
        language: str,
    ) -> WorkspaceSession:
        """Create a new workspace with underlying WASM session."""
        # Create WASM sandbox session
        sandbox_session = await self.sandbox.create_session(
            language=language,
            memory_limit_mb=256,
            timeout_seconds=int(self.default_timeout.total_seconds())
        )
        
        now = datetime.utcnow()
        return WorkspaceSession(
            workspace_id=secrets.token_urlsafe(16),
            mcp_session_id=mcp_session_id,
            language=language,
            sandbox_session_id=sandbox_session["session_id"],
            created_at=now,
            last_used_at=now,
        )
    
    async def _destroy_workspace(self, workspace: WorkspaceSession) -> None:
        """Destroy a workspace and its underlying WASM session."""
        await self.sandbox.destroy_session(workspace.sandbox_session_id)
    
    async def execute_in_workspace(
        self,
        mcp_session_id: Optional[str],
        code: str,
        language: str,
        timeout: int = 30,
        ctx: Optional[Context] = None,
    ) -> dict:
        """
        Execute code in the client's workspace session.
        
        Automatically gets or creates a workspace for the client.
        """
        workspace = await self.get_or_create_workspace(
            mcp_session_id, language, ctx
        )
        
        # Execute in the workspace's WASM session
        result = await self.sandbox.execute(
            code=code,
            language=language,
            timeout=timeout,
            session_id=workspace.sandbox_session_id
        )
        
        # Update workspace metadata
        workspace.execution_count += 1
        workspace.last_used_at = datetime.utcnow()
        
        # Track variables (for Python, extract from namespace)
        if language == "python" and result.get("exit_code") == 0:
            await self._update_workspace_metadata(workspace, code)
        
        return result
    
    async def _update_workspace_metadata(
        self,
        workspace: WorkspaceSession,
        code: str
    ) -> None:
        """Update workspace metadata after execution."""
        # Simple heuristic: track import statements and assignments
        import re
        
        # Track imports
        import_pattern = r'^(?:from\s+(\w+)|import\s+(\w+))'
        for match in re.finditer(import_pattern, code, re.MULTILINE):
            module = match.group(1) or match.group(2)
            if module and module not in workspace.imports:
                workspace.imports.append(module)
        
        # Track top-level assignments (simple heuristic)
        assign_pattern = r'^(\w+)\s*='
        for match in re.finditer(assign_pattern, code, re.MULTILINE):
            var = match.group(1)
            if var and var not in workspace.variables and not var.startswith('_'):
                workspace.variables.append(var)
    
    async def get_workspace_info(
        self,
        mcp_session_id: Optional[str],
        language: str,
    ) -> Optional[dict]:
        """Get information about a client's workspace."""
        session_id = mcp_session_id or self._stdio_session_id
        
        if session_id not in self._workspaces:
            return None
        
        if language not in self._workspaces[session_id]:
            return None
        
        workspace = self._workspaces[session_id][language]
        return {
            "session_id": workspace.workspace_id,
            "language": workspace.language,
            "variables": workspace.variables.copy(),
            "imports": workspace.imports.copy(),
            "execution_count": workspace.execution_count,
            "created_at": workspace.created_at.isoformat() + "Z",
            "last_used_at": workspace.last_used_at.isoformat() + "Z",
        }
    
    async def reset_workspace(
        self,
        mcp_session_id: Optional[str],
        language: str,
        ctx: Optional[Context] = None,
    ) -> dict:
        """Reset a client's workspace, clearing all state."""
        session_id = mcp_session_id or self._stdio_session_id
        
        async with self._lock:
            if session_id in self._workspaces:
                if language in self._workspaces[session_id]:
                    old_workspace = self._workspaces[session_id][language]
                    await self._destroy_workspace(old_workspace)
                    del self._workspaces[session_id][language]
            
            # Create fresh workspace
            workspace = await self.get_or_create_workspace(
                mcp_session_id, language, ctx
            )
        
        return {
            "success": True,
            "new_session_id": workspace.workspace_id,
            "language": language,
        }
    
    async def cleanup_mcp_session(self, mcp_session_id: str) -> None:
        """
        Clean up all workspaces for an MCP session.
        
        Called when MCP session ends (HTTP DELETE or stdio close).
        """
        async with self._lock:
            if mcp_session_id in self._workspaces:
                for workspace in self._workspaces[mcp_session_id].values():
                    await self._destroy_workspace(workspace)
                del self._workspaces[mcp_session_id]
```

#### 6.4.2 Updated Server with Workspace Manager

```python
# src/llm_wasm_sandbox/server.py (updated sections)

from .sessions.manager import WorkspaceSessionManager

# Global workspace manager
_workspace_manager: WorkspaceSessionManager | None = None

def get_workspace_manager() -> WorkspaceSessionManager:
    """Get or create the workspace manager."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceSessionManager(get_sandbox())
    return _workspace_manager


def _get_mcp_session_id(ctx: Context | None) -> str | None:
    """Extract MCP session ID from context."""
    if ctx is None:
        return None
    # FastMCP provides request context
    return getattr(ctx, 'session_id', None) or getattr(ctx, 'client_id', None)


@mcp.tool(
    name="execute_code",
    description="""Execute code in a secure WebAssembly sandbox.

State persists automatically between calls - variables and imports from previous 
executions are available. Use session_id='__stateless__' for isolated execution.""",
    annotations={
        "title": "Execute Code in WASM Sandbox",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def execute_code(
    code: Annotated[str, "The source code to execute"],
    language: Annotated[str, Field(description="Programming language", pattern="^(python|javascript)$")],
    timeout: Annotated[int, Field(description="Execution timeout in seconds", ge=1, le=300)] = 30,
    session_id: Annotated[str | None, "Session ID: None=auto (default), '__stateless__'=isolated, or explicit ID"] = None,
    ctx: Context = None,
) -> ExecutionResult:
    """
    Execute code in a secure WebAssembly sandbox.
    
    **Automatic State Persistence**: By default, variables and imports persist
    across calls within the same conversation/MCP session. The agent does not
    need to manage session IDs.
    
    Examples:
        # Call 1: Define a variable
        execute_code("x = 42", "python")
        
        # Call 2: Use the variable (works automatically!)
        execute_code("print(x * 2)", "python")  # Output: 84
        
        # Isolated execution (no state)
        execute_code("print('isolated')", "python", session_id="__stateless__")
    """
    manager = get_workspace_manager()
    mcp_session = _get_mcp_session_id(ctx)
    
    if ctx:
        await ctx.info(f"Executing {language} code (timeout: {timeout}s)")
        await ctx.report_progress(progress=0, total=100)
    
    # Handle session modes
    if session_id == "__stateless__":
        # Stateless execution - use sandbox directly
        result = await get_sandbox().execute(
            code=code,
            language=language,
            timeout=min(timeout, 300),
            session_id=None  # Fresh execution
        )
    elif session_id:
        # Explicit session ID provided
        result = await get_sandbox().execute(
            code=code,
            language=language,
            timeout=min(timeout, 300),
            session_id=session_id
        )
    else:
        # Auto mode - use workspace manager
        result = await manager.execute_in_workspace(
            mcp_session_id=mcp_session,
            code=code,
            language=language,
            timeout=min(timeout, 300),
            ctx=ctx
        )
    
    if ctx:
        await ctx.report_progress(progress=100, total=100)
    
    return ExecutionResult(**result) if isinstance(result, dict) else result


@mcp.tool(
    name="get_workspace_info",
    description="Get information about the current workspace session including defined variables and imported modules.",
    annotations={
        "title": "Get Workspace Information",
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_workspace_info(
    language: Annotated[str, Field(description="Programming language", pattern="^(python|javascript)$")] = "python",
    ctx: Context = None,
) -> dict:
    """
    Get information about the current workspace session.
    
    Returns details about the workspace including:
    - Defined variables
    - Imported modules
    - Execution count
    - Memory usage
    """
    manager = get_workspace_manager()
    mcp_session = _get_mcp_session_id(ctx)
    
    info = await manager.get_workspace_info(mcp_session, language)
    
    if info is None:
        return {
            "session_id": None,
            "language": language,
            "variables": [],
            "imports": [],
            "execution_count": 0,
            "message": "No workspace session exists yet. Execute code to create one."
        }
    
    return info


@mcp.tool(
    name="reset_workspace",
    description="Reset the current workspace session, clearing all variables and imports.",
    annotations={
        "title": "Reset Workspace",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def reset_workspace(
    language: Annotated[str, Field(description="Programming language", pattern="^(python|javascript)$")] = "python",
    ctx: Context = None,
) -> ToolResult:
    """
    Reset the current workspace session.
    
    Clears all variables, imports, and state while maintaining the
    MCP connection. A fresh workspace will be created on the next
    execute_code call.
    """
    manager = get_workspace_manager()
    mcp_session = _get_mcp_session_id(ctx)
    
    result = await manager.reset_workspace(mcp_session, language, ctx)
    
    if ctx:
        await ctx.info(f"Workspace reset for {language}")
    
    return ToolResult(
        content=f"Workspace reset successfully. New session: {result['new_session_id'][:8]}...",
        structured_content=result
    )
```

### 6.5 Configuration Options

```yaml
# config.yaml - Session management settings
sessions:
  # Default workspace timeout (minutes of inactivity)
  workspace_timeout_minutes: 60
  
  # Maximum workspaces per MCP client (one per language typically)
  max_workspaces_per_client: 5
  
  # Auto-cleanup on MCP session end
  cleanup_on_disconnect: true
  
  # Memory limit per workspace (MB)
  default_memory_mb: 256
  
  # Persist workspace metadata for debugging
  persist_metadata: true
```

### 6.6 Agent Usage Examples

#### 6.6.1 Automatic State Persistence (Default)

```python
# Agent conversation - state persists automatically

# Call 1: Import and define
response = await client.call_tool("execute_code", {
    "code": """
import pandas as pd
import numpy as np

data = pd.DataFrame({
    'name': ['Alice', 'Bob', 'Charlie'],
    'score': [85, 92, 78]
})
print("Data loaded!")
""",
    "language": "python"
})
# Output: "Data loaded!"

# Call 2: Use previous imports and variables
response = await client.call_tool("execute_code", {
    "code": """
# 'data' and 'pd' are still available!
avg_score = data['score'].mean()
print(f"Average score: {avg_score:.1f}")
""",
    "language": "python"
})
# Output: "Average score: 85.0"

# Call 3: Continue building on state
response = await client.call_tool("execute_code", {
    "code": """
data['grade'] = data['score'].apply(lambda x: 'A' if x >= 90 else 'B' if x >= 80 else 'C')
print(data.to_string())
""",
    "language": "python"
})
# Output: Full dataframe with grades
```

#### 6.6.2 Checking Workspace State

```python
# Agent can inspect what's available
response = await client.call_tool("get_workspace_info", {"language": "python"})
# Returns:
# {
#   "session_id": "abc123...",
#   "language": "python",
#   "variables": ["data", "avg_score"],
#   "imports": ["pandas", "numpy"],
#   "execution_count": 3,
#   "created_at": "2025-11-23T10:30:00Z"
# }
```

#### 6.6.3 Isolated Execution

```python
# When agent needs isolated execution (no state pollution)
response = await client.call_tool("execute_code", {
    "code": "print('This is isolated')",
    "language": "python",
    "session_id": "__stateless__"  # Explicit stateless mode
})
```

---

## 7. WASM Sandbox Implementation

### 6.1 Runtime Selection

| Runtime | Use Case | WASM Module | Notes |
|---------|----------|-------------|-------|
| **wasmtime** | Primary | wasmtime-py | WASI 0.2 support, fuel metering |
| **wasmer** | Alternative | wasmer-python | Good performance, broad compatibility |
| **Pyodide** | Python | pyodide.wasm | Full CPython, numpy/pandas support |
| **QuickJS** | JavaScript | quickjs.wasm | Lightweight, fast startup |

### 6.2 Security Model

#### 6.2.1 WASM Isolation Guarantees

1. **Memory Safety**: Linear memory is bounds-checked; no access to host memory
2. **Capability-Based Security**: No implicit filesystem/network access
3. **Deterministic Execution**: Reproducible behavior
4. **Resource Limits**: Configurable memory and fuel (instruction count)

#### 6.2.2 WASI Permissions

```python
# Minimal WASI configuration
wasi_config = WasiConfig()
wasi_config.argv = ("python", "-c", code)

# Restricted filesystem - only sandbox directory
wasi_config.preopen_dir(sandbox_temp_dir, "/sandbox")

# No network access (WASI doesn't expose networking by default)
# No environment variables exposed
# stdout/stderr captured to files
```

#### 6.2.3 Resource Limits

```python
# Fuel-based execution limits (wasmtime)
engine_config = Config()
engine_config.consume_fuel = True

store = Store(engine)
store.set_fuel(400_000_000)  # ~30 seconds of execution

# Memory limits
engine_config.max_wasm_pages = 4096  # 256 MB max memory
```

### 6.3 Python Runtime (Pyodide/wasmtime)

#### 6.3.1 Supported Features

- Standard library (limited I/O)
- Pure Python packages via micropip
- Pre-compiled packages: numpy, pandas, scipy, matplotlib
- JSON, CSV data processing
- Mathematical computations

#### 6.3.2 Limitations

- No networking
- No subprocess/os.system
- No file persistence beyond session
- Limited C extension support

### 6.4 JavaScript Runtime (QuickJS)

#### 6.4.1 Supported Features

- ES2020 syntax
- JSON processing
- Mathematical computations
- String manipulation
- Basic data structures

#### 6.4.2 Limitations

- No DOM access
- No fetch/XMLHttpRequest
- No Node.js APIs
- Limited to 256MB memory

---

## 8. Implementation Guide

### 8.1 Project Structure

```
llm-wasm-sandbox/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── llm_wasm_sandbox/
│       ├── __init__.py
│       ├── __main__.py           # Entry point
│       ├── server.py             # MCP server implementation
│       ├── config.py             # Configuration management
│       ├── transports/
│       │   ├── __init__.py
│       │   ├── stdio.py          # stdio transport
│       │   └── http.py           # Streamable HTTP transport
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── execute_code.py
│       │   ├── workspace.py      # get_workspace_info, reset_workspace
│       │   ├── sessions.py       # create_session, destroy_session
│       │   └── packages.py       # install_package
│       ├── sessions/
│       │   ├── __init__.py
│       │   └── manager.py        # WorkspaceSessionManager
│       ├── sandbox/
│       │   ├── __init__.py
│       │   ├── engine.py         # WASM runtime management
│       │   ├── python_runtime.py
│       │   ├── js_runtime.py
│       │   └── security.py       # Security policies
│       └── runtimes/             # Pre-built WASM modules
│           ├── python-3.11.wasm
│           └── quickjs.wasm
├── tests/
│   ├── __init__.py
│   ├── test_server.py
│   ├── test_transports.py
│   ├── test_tools.py
│   ├── test_sessions.py          # Workspace session tests
│   └── test_sandbox.py
└── examples/
    ├── claude_desktop_config.json
    ├── agentic_workflow.py       # Multi-step agent example
    └── http_client_example.py
```

### 7.2 Dependencies

```toml
# pyproject.toml
[project]
name = "llm-wasm-sandbox"
version = "1.0.0"
requires-python = ">=3.10"
dependencies = [
    "wasmtime>=23.0.0",          # WASM runtime
    "fastmcp>=2.8.0",            # FastMCP 2.0 server framework
    "starlette>=0.38.0",         # HTTP framework (included with FastMCP)
    "uvicorn>=0.30.0",           # ASGI server
    "pydantic>=2.0.0",           # Data validation
    "httpx>=0.27.0",             # HTTP client (for testing)
    "anyio>=4.0.0",              # Async utilities
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
]

[project.scripts]
llm-wasm-sandbox = "llm_wasm_sandbox.server:main"
```

### 7.2.1 FastMCP 2.0 Key Features Used

This implementation leverages FastMCP 2.0's advanced features:

| Feature | Version | Usage |
|---------|---------|-------|
| `@mcp.tool` decorator | 2.0+ | Core tool registration |
| `annotations` parameter | 2.2.7+ | Tool metadata (readOnlyHint, destructiveHint) |
| `output_schema` | 2.10.0+ | Structured output validation |
| `ToolResult` | 2.10.0+ | Advanced return value control |
| `structuredContent` | 2.10.0+ | Machine-readable JSON responses |
| `Context` injection | 2.0+ | Logging, progress reporting |
| Async tool support | 2.0+ | Non-blocking execution |
| HTTP transport | 2.0+ | Streamable HTTP (replaces SSE) |

### 7.3 Core Server Implementation (FastMCP 2.0)

```python
# src/llm_wasm_sandbox/server.py
"""
LLM WASM Sandbox MCP Server - FastMCP 2.0 Implementation

A secure code execution sandbox using WebAssembly, exposed via MCP.
Supports both stdio and Streamable HTTP transports.
"""
from dataclasses import dataclass
from typing import Annotated
from datetime import datetime

from fastmcp import FastMCP, Context
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from .sandbox.engine import WASMSandboxEngine

# Initialize FastMCP server with configuration
mcp = FastMCP(
    name="llm-wasm-sandbox",
    version="1.0.0",
    instructions="""
    Secure code execution sandbox using WebAssembly.
    
    Supported languages: Python, JavaScript
    
    Usage:
    1. Use execute_code for stateless execution
    2. Use create_session + execute_code for stateful execution
    3. Use install_package to add Python packages to a session
    
    Security: All code runs in an isolated WASM sandbox with no host access.
    """,
    # FastMCP 2.0 settings
    on_duplicate_tools="error",  # Strict duplicate handling
)

# Initialize sandbox engine (lazy loaded)
_sandbox: WASMSandboxEngine | None = None

def get_sandbox() -> WASMSandboxEngine:
    """Get or create the sandbox engine instance."""
    global _sandbox
    if _sandbox is None:
        _sandbox = WASMSandboxEngine()
    return _sandbox


# ============================================================================
# Data Models for Structured Output (FastMCP 2.0)
# ============================================================================

@dataclass
class ExecutionResult:
    """Structured result from code execution."""
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    memory_used_bytes: int = 0
    truncated: bool = False


@dataclass
class RuntimeInfo:
    """Information about a language runtime."""
    language: str
    version: str
    wasm_module: str
    features: list[str]


@dataclass
class SessionInfo:
    """Information about an execution session."""
    session_id: str
    language: str
    created_at: str
    expires_at: str


# ============================================================================
# MCP Tools (FastMCP 2.0 @mcp.tool decorator)
# ============================================================================

@mcp.tool(
    name="execute_code",
    description="Execute code in a secure WebAssembly sandbox. Supports Python and JavaScript.",
    annotations={
        "title": "Execute Code in WASM Sandbox",
        "readOnlyHint": False,      # Code execution may have side effects
        "destructiveHint": False,   # Sandboxed, no host modifications
        "idempotentHint": False,    # Same code may produce different results
        "openWorldHint": False,     # No external system access
    },
)
async def execute_code(
    code: Annotated[str, "The source code to execute"],
    language: Annotated[str, Field(description="Programming language", pattern="^(python|javascript)$")],
    timeout: Annotated[int, Field(description="Execution timeout in seconds", ge=1, le=300)] = 30,
    session_id: Annotated[str | None, "Optional session ID for stateful execution"] = None,
    ctx: Context = None,
) -> ExecutionResult:
    """
    Execute code in a secure WebAssembly sandbox.
    
    The sandbox provides complete isolation from the host system:
    - No filesystem access beyond temporary sandbox directory
    - No network access
    - Memory and CPU limits enforced
    - Execution timeout enforced
    
    Args:
        code: The source code to execute
        language: Programming language ('python' or 'javascript')
        timeout: Execution timeout in seconds (default: 30, max: 300)
        session_id: Optional session ID for stateful execution (preserves variables)
        ctx: FastMCP context for logging and progress
    
    Returns:
        ExecutionResult with stdout, stderr, exit_code, and metadata
    """
    sandbox = get_sandbox()
    
    # Log execution start
    if ctx:
        await ctx.info(f"Executing {language} code (timeout: {timeout}s)")
        await ctx.report_progress(progress=0, total=100)
    
    # Execute in sandbox
    result = await sandbox.execute(
        code=code,
        language=language,
        timeout=min(timeout, 300),
        session_id=session_id
    )
    
    if ctx:
        await ctx.report_progress(progress=100, total=100)
        if result.exit_code != 0:
            await ctx.warning(f"Execution completed with exit code {result.exit_code}")
    
    return result


@mcp.tool(
    name="list_runtimes",
    description="List all available programming language runtimes in the sandbox.",
    annotations={
        "title": "List Available Runtimes",
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_runtimes() -> dict[str, list[RuntimeInfo]]:
    """
    List all available programming language runtimes.
    
    Returns information about each supported language including
    version, WASM module name, and available features/packages.
    """
    return {
        "runtimes": [
            RuntimeInfo(
                language="python",
                version="3.11",
                wasm_module="python-3.11.wasm",
                features=["numpy", "pandas", "matplotlib", "scipy", "json", "csv"]
            ),
            RuntimeInfo(
                language="javascript",
                version="ES2020",
                wasm_module="quickjs.wasm",
                features=["JSON", "Math", "Date", "RegExp", "Promise"]
            )
        ]
    }


@mcp.tool(
    name="create_session",
    description="Create a new stateful execution session. Variables persist across execute_code calls.",
    annotations={
        "title": "Create Execution Session",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def create_session(
    language: Annotated[str, Field(description="Programming language", pattern="^(python|javascript)$")],
    memory_limit_mb: Annotated[int, Field(description="Memory limit in MB", ge=64, le=1024)] = 256,
    timeout_seconds: Annotated[int, Field(description="Session inactivity timeout", ge=60, le=3600)] = 600,
    ctx: Context = None,
) -> SessionInfo:
    """
    Create a new stateful execution session.
    
    Sessions allow variables, imports, and state to persist across
    multiple execute_code calls. Useful for interactive workflows.
    
    Args:
        language: Programming language for this session
        memory_limit_mb: Memory limit in MB (default: 256, max: 1024)
        timeout_seconds: Session inactivity timeout (default: 600)
    
    Returns:
        SessionInfo with session_id and expiration time
    """
    sandbox = get_sandbox()
    
    session = await sandbox.create_session(
        language=language,
        memory_limit_mb=min(memory_limit_mb, 1024),
        timeout_seconds=min(timeout_seconds, 3600)
    )
    
    if ctx:
        await ctx.info(f"Created {language} session: {session['session_id'][:8]}...")
    
    return SessionInfo(
        session_id=session["session_id"],
        language=session["language"],
        created_at=session["created_at"],
        expires_at=session["expires_at"]
    )


@mcp.tool(
    name="destroy_session",
    description="Destroy a stateful execution session and free its resources.",
    annotations={
        "title": "Destroy Execution Session",
        "readOnlyHint": False,
        "destructiveHint": True,  # Destroys session state
        "idempotentHint": True,   # Destroying twice is same as once
        "openWorldHint": False,
    },
)
async def destroy_session(
    session_id: Annotated[str, "Session ID to destroy"],
    ctx: Context = None,
) -> ToolResult:
    """
    Destroy a stateful execution session.
    
    Frees all resources associated with the session including
    memory, temporary files, and any stored state.
    """
    sandbox = get_sandbox()
    await sandbox.destroy_session(session_id)
    
    if ctx:
        await ctx.info(f"Destroyed session: {session_id[:8]}...")
    
    # Use ToolResult for explicit control over response
    return ToolResult(
        content=f"Session {session_id} destroyed successfully",
        structured_content={
            "success": True,
            "session_id": session_id,
            "destroyed_at": datetime.utcnow().isoformat() + "Z"
        }
    )


@mcp.tool(
    name="install_package",
    description="Install a Python package in an active session using micropip.",
    annotations={
        "title": "Install Python Package",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,  # Installing same package twice is safe
        "openWorldHint": False,  # Packages bundled, no network fetch
    },
)
async def install_package(
    session_id: Annotated[str, "Session ID to install the package in"],
    package: Annotated[str, "Package name (e.g., 'numpy', 'pandas')"],
    version: Annotated[str | None, "Optional version specifier (e.g., '>=1.0.0')"] = None,
    ctx: Context = None,
) -> ToolResult:
    """
    Install a Python package in an active session.
    
    Uses micropip to install packages. Only works with:
    - Pure Python packages
    - Packages with pre-built WASM wheels (numpy, pandas, etc.)
    
    Note: Not all PyPI packages are available in WASM environment.
    """
    sandbox = get_sandbox()
    
    if ctx:
        await ctx.info(f"Installing {package} in session {session_id[:8]}...")
    
    result = await sandbox.install_package(
        session_id=session_id,
        package=package,
        version=version
    )
    
    success = result.get("success", False)
    
    if ctx:
        if success:
            await ctx.info(f"Successfully installed {package}")
        else:
            await ctx.warning(f"Failed to install {package}: {result.get('message')}")
    
    return ToolResult(
        content=result.get("message", ""),
        structured_content=result,
        meta={"package": package, "session_id": session_id}
    )


@mcp.tool(
    name="cancel_execution",
    description="Cancel a currently running code execution.",
    annotations={
        "title": "Cancel Execution",
        "readOnlyHint": False,
        "destructiveHint": True,  # Interrupts running execution
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cancel_execution(
    execution_id: Annotated[str, "Execution ID to cancel"],
    ctx: Context = None,
) -> ToolResult:
    """
    Cancel a currently running code execution.
    
    The execution will be terminated and partial results (if any)
    will be discarded.
    """
    sandbox = get_sandbox()
    await sandbox.cancel_execution(execution_id)
    
    if ctx:
        await ctx.info(f"Cancelled execution: {execution_id}")
    
    return ToolResult(
        content=f"Execution {execution_id} cancelled",
        structured_content={
            "success": True,
            "execution_id": execution_id,
            "cancelled_at": datetime.utcnow().isoformat() + "Z"
        }
    )


# ============================================================================
# Entry Point
# ============================================================================

def main():
    """Main entry point for the MCP server."""
    import sys
    
    transport = "stdio"
    port = 8080
    host = "127.0.0.1"
    
    # Parse command line arguments
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--transport" and i + 1 < len(args):
            transport = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        elif args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        else:
            i += 1
    
    # Run server with selected transport
    if transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()  # stdio default


if __name__ == "__main__":
    main()
```

### 7.4 WASM Sandbox Engine

```python
# src/llm_wasm_sandbox/sandbox/engine.py
import asyncio
import os
import tempfile
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from wasmtime import Config, Engine, Linker, Module, Store, WasiConfig

class ExecutionResult:
    def __init__(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        execution_time_ms: float,
        memory_used_bytes: int = 0,
        truncated: bool = False
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time_ms = execution_time_ms
        self.memory_used_bytes = memory_used_bytes
        self.truncated = truncated
    
    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_bytes": self.memory_used_bytes,
            "truncated": self.truncated
        }

class Session:
    def __init__(
        self,
        session_id: str,
        language: str,
        memory_limit_mb: int,
        expires_at: datetime
    ):
        self.session_id = session_id
        self.language = language
        self.memory_limit_mb = memory_limit_mb
        self.expires_at = expires_at
        self.store: Optional[Store] = None
        self.context: dict = {}  # For stateful execution

class WASMSandboxEngine:
    def __init__(self, runtimes_dir: Optional[Path] = None):
        self.runtimes_dir = runtimes_dir or Path(__file__).parent.parent / "runtimes"
        self.sessions: dict[str, Session] = {}
        self.active_executions: dict[str, asyncio.Task] = {}
        
        # Initialize WASM engine with fuel metering
        self.engine_config = Config()
        self.engine_config.consume_fuel = True
        self.engine_config.cache = True
        self.engine = Engine(self.engine_config)
        
        # Load WASM modules
        self._load_modules()
    
    def _load_modules(self):
        """Load available WASM runtime modules."""
        self.modules = {}
        
        python_wasm = self.runtimes_dir / "python-3.11.wasm"
        if python_wasm.exists():
            self.modules["python"] = Module.from_file(self.engine, str(python_wasm))
        
        quickjs_wasm = self.runtimes_dir / "quickjs.wasm"
        if quickjs_wasm.exists():
            self.modules["javascript"] = Module.from_file(self.engine, str(quickjs_wasm))
    
    async def execute(
        self,
        code: str,
        language: str,
        timeout: int = 30,
        session_id: Optional[str] = None
    ) -> dict:
        """Execute code in the WASM sandbox."""
        if language not in self.modules:
            return {
                "stdout": "",
                "stderr": f"Language '{language}' is not available",
                "exit_code": 1,
                "execution_time_ms": 0
            }
        
        execution_id = secrets.token_urlsafe(16)
        
        try:
            # Run execution in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            task = loop.run_in_executor(
                None,
                self._execute_sync,
                code,
                language,
                timeout,
                session_id
            )
            
            self.active_executions[execution_id] = task
            result = await asyncio.wait_for(task, timeout=timeout + 5)
            
            return result.to_dict()
            
        except asyncio.TimeoutError:
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds",
                "exit_code": 124,
                "execution_time_ms": timeout * 1000
            }
        finally:
            self.active_executions.pop(execution_id, None)
    
    def _execute_sync(
        self,
        code: str,
        language: str,
        timeout: int,
        session_id: Optional[str]
    ) -> ExecutionResult:
        """Synchronous execution in WASM sandbox."""
        import time
        start_time = time.perf_counter()
        
        # Create WASI configuration
        linker = Linker(self.engine)
        linker.define_wasi()
        
        wasi_config = WasiConfig()
        
        with tempfile.TemporaryDirectory() as sandbox_dir:
            stdout_file = os.path.join(sandbox_dir, "stdout.log")
            stderr_file = os.path.join(sandbox_dir, "stderr.log")
            
            wasi_config.stdout_file = stdout_file
            wasi_config.stderr_file = stderr_file
            wasi_config.preopen_dir(sandbox_dir, "/sandbox")
            
            if language == "python":
                wasi_config.argv = ("python", "-c", code)
            else:  # javascript
                wasi_config.argv = ("quickjs", "-e", code)
            
            # Create store with fuel limit
            store = Store(self.engine)
            fuel_limit = timeout * 10_000_000  # Approximate fuel per second
            store.set_fuel(fuel_limit)
            store.set_wasi(wasi_config)
            
            try:
                # Instantiate and run module
                instance = linker.instantiate(store, self.modules[language])
                start_func = instance.exports(store).get("_start")
                
                if start_func:
                    start_func(store)
                
                exit_code = 0
                
            except Exception as e:
                exit_code = 1
                # Write error to stderr file
                with open(stderr_file, "a") as f:
                    f.write(str(e))
            
            # Read outputs
            stdout = ""
            stderr = ""
            
            if os.path.exists(stdout_file):
                with open(stdout_file, "r") as f:
                    stdout = f.read()
            
            if os.path.exists(stderr_file):
                with open(stderr_file, "r") as f:
                    stderr = f.read()
            
            # Truncate if necessary
            max_output = 1_000_000  # 1MB max
            truncated = False
            if len(stdout) > max_output:
                stdout = stdout[:max_output] + "\n...[truncated]"
                truncated = True
            if len(stderr) > max_output:
                stderr = stderr[:max_output] + "\n...[truncated]"
                truncated = True
            
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            fuel_consumed = fuel_limit - (store.get_fuel() or 0)
            
            return ExecutionResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=execution_time_ms,
                memory_used_bytes=fuel_consumed,  # Approximate
                truncated=truncated
            )
    
    async def create_session(
        self,
        language: str,
        memory_limit_mb: int,
        timeout_seconds: int
    ) -> dict:
        """Create a new stateful execution session."""
        session_id = secrets.token_urlsafe(24)
        expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        
        session = Session(
            session_id=session_id,
            language=language,
            memory_limit_mb=memory_limit_mb,
            expires_at=expires_at
        )
        
        self.sessions[session_id] = session
        
        return {
            "session_id": session_id,
            "language": language,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "expires_at": expires_at.isoformat() + "Z"
        }
    
    async def destroy_session(self, session_id: str) -> None:
        """Destroy an execution session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    async def install_package(
        self,
        session_id: str,
        package: str,
        version: Optional[str]
    ) -> dict:
        """Install a Python package in a session."""
        if session_id not in self.sessions:
            return {
                "success": False,
                "package": package,
                "message": f"Session '{session_id}' not found"
            }
        
        session = self.sessions[session_id]
        if session.language != "python":
            return {
                "success": False,
                "package": package,
                "message": "Package installation only supported for Python sessions"
            }
        
        # Execute micropip install in the session
        version_spec = f"=={version}" if version else ""
        install_code = f"import micropip; await micropip.install('{package}{version_spec}')"
        
        result = await self.execute(
            code=install_code,
            language="python",
            timeout=60,
            session_id=session_id
        )
        
        success = result.get("exit_code", 1) == 0
        return {
            "success": success,
            "package": package,
            "version_installed": version or "latest",
            "message": result.get("stderr", "") if not success else f"Successfully installed {package}"
        }
    
    async def cancel_execution(self, execution_id: str) -> None:
        """Cancel a running execution."""
        if execution_id in self.active_executions:
            self.active_executions[execution_id].cancel()
```

### 7.5 Streamable HTTP Transport Implementation

```python
# src/llm_wasm_sandbox/transports/http.py
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import Response, JSONResponse, StreamingResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import json
import secrets
import asyncio
from typing import AsyncIterator

class StreamableHTTPTransport:
    """Streamable HTTP transport for MCP 2025-06-18."""
    
    def __init__(self, mcp_server, host: str = "127.0.0.1", port: int = 8080):
        self.mcp_server = mcp_server
        self.host = host
        self.port = port
        self.sessions: dict[str, dict] = {}
        self.sse_streams: dict[str, asyncio.Queue] = {}
    
    def create_app(self) -> Starlette:
        """Create Starlette ASGI application."""
        
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],  # Configure appropriately for production
                allow_methods=["GET", "POST", "DELETE"],
                allow_headers=["*"],
            )
        ]
        
        routes = [
            Route("/mcp", self.handle_mcp, methods=["GET", "POST", "DELETE"]),
            Route("/health", self.health_check, methods=["GET"]),
        ]
        
        return Starlette(routes=routes, middleware=middleware)
    
    async def health_check(self, request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "server": "llm-wasm-sandbox"})
    
    async def handle_mcp(self, request: Request) -> Response:
        """Main MCP endpoint handler."""
        
        # Validate Origin header for security
        origin = request.headers.get("Origin")
        if origin and not self._validate_origin(origin):
            return JSONResponse(
                {"error": "Invalid origin"},
                status_code=403
            )
        
        method = request.method
        
        if method == "POST":
            return await self._handle_post(request)
        elif method == "GET":
            return await self._handle_get(request)
        elif method == "DELETE":
            return await self._handle_delete(request)
        else:
            return JSONResponse(
                {"error": "Method not allowed"},
                status_code=405
            )
    
    async def _handle_post(self, request: Request) -> Response:
        """Handle POST requests (client → server messages)."""
        
        # Parse JSON-RPC message
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
                status_code=400
            )
        
        # Check Accept header
        accept = request.headers.get("Accept", "")
        supports_sse = "text/event-stream" in accept
        
        # Get session ID
        session_id = request.headers.get("Mcp-Session-Id")
        
        # Handle different message types
        method = body.get("method")
        msg_id = body.get("id")
        
        if method == "initialize":
            # Initialization request
            result = await self._handle_initialize(body.get("params", {}))
            
            # Generate new session ID
            new_session_id = secrets.token_urlsafe(32)
            self.sessions[new_session_id] = {"initialized": True}
            
            response = JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            })
            response.headers["Mcp-Session-Id"] = new_session_id
            return response
        
        # Validate session for other requests
        if not session_id or session_id not in self.sessions:
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid session"}},
                status_code=400
            )
        
        # Process the message
        if method and method.startswith("notifications/"):
            # Notification - no response expected
            await self._handle_notification(method, body.get("params", {}))
            return Response(status_code=202)
        
        # Request - return response
        if supports_sse and self._should_stream(method):
            return await self._stream_response(msg_id, method, body.get("params", {}))
        else:
            result = await self._process_request(method, body.get("params", {}))
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            })
    
    async def _handle_get(self, request: Request) -> Response:
        """Handle GET requests (open SSE stream)."""
        
        accept = request.headers.get("Accept", "")
        if "text/event-stream" not in accept:
            return JSONResponse(
                {"error": "Accept header must include text/event-stream"},
                status_code=400
            )
        
        session_id = request.headers.get("Mcp-Session-Id")
        if not session_id or session_id not in self.sessions:
            return JSONResponse(
                {"error": "Invalid session"},
                status_code=400
            )
        
        # Create SSE stream
        return StreamingResponse(
            self._sse_generator(session_id),
            media_type="text/event-stream"
        )
    
    async def _handle_delete(self, request: Request) -> Response:
        """Handle DELETE requests (terminate session)."""
        
        session_id = request.headers.get("Mcp-Session-Id")
        if session_id and session_id in self.sessions:
            del self.sessions[session_id]
            return Response(status_code=204)
        else:
            return JSONResponse(
                {"error": "Session not found"},
                status_code=404
            )
    
    async def _handle_initialize(self, params: dict) -> dict:
        """Handle initialization."""
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {
                "tools": {"listChanged": True},
                "logging": {}
            },
            "serverInfo": {
                "name": "llm-wasm-sandbox",
                "title": "LLM WASM Sandbox",
                "version": "1.0.0"
            },
            "instructions": "Secure WebAssembly code execution sandbox."
        }
    
    async def _handle_notification(self, method: str, params: dict) -> None:
        """Handle notifications."""
        if method == "notifications/initialized":
            pass  # Ready for operation
        elif method == "notifications/cancelled":
            # Handle cancellation
            request_id = params.get("requestId")
            if request_id:
                await self.mcp_server.cancel_execution(request_id)
    
    async def _process_request(self, method: str, params: dict) -> dict:
        """Process a request and return result."""
        if method == "tools/list":
            return await self.mcp_server.list_tools()
        elif method == "tools/call":
            return await self.mcp_server.call_tool(
                params.get("name"),
                params.get("arguments", {})
            )
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def _should_stream(self, method: str) -> bool:
        """Determine if response should be streamed."""
        return method == "tools/call"  # Stream tool execution results
    
    async def _stream_response(
        self,
        msg_id: int,
        method: str,
        params: dict
    ) -> StreamingResponse:
        """Stream response via SSE."""
        
        async def generate() -> AsyncIterator[str]:
            # Process and stream results
            result = await self._process_request(method, params)
            
            # Send final response
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            }
            yield f"data: {json.dumps(response)}\n\n"
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    
    async def _sse_generator(self, session_id: str) -> AsyncIterator[str]:
        """Generate SSE events for a session."""
        
        queue = asyncio.Queue()
        self.sse_streams[session_id] = queue
        
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            del self.sse_streams[session_id]
    
    def _validate_origin(self, origin: str) -> bool:
        """Validate Origin header to prevent DNS rebinding attacks."""
        # In production, implement proper origin validation
        allowed_origins = [
            "http://localhost",
            "http://127.0.0.1",
            "https://claude.ai",
        ]
        return any(origin.startswith(ao) for ao in allowed_origins)
```

---

## 9. Configuration

### 8.1 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WASM_SANDBOX_TIMEOUT` | Default execution timeout (seconds) | `30` |
| `WASM_SANDBOX_MEMORY_MB` | Default memory limit (MB) | `256` |
| `WASM_SANDBOX_MAX_OUTPUT` | Maximum output size (bytes) | `1000000` |
| `WASM_SANDBOX_FUEL_PER_SEC` | Fuel units per second of execution | `10000000` |
| `MCP_HTTP_PORT` | HTTP transport port | `8080` |
| `MCP_HTTP_HOST` | HTTP transport host | `127.0.0.1` |
| `MCP_AUTH_TOKEN` | Authentication token for HTTP | `None` |
| `LOG_LEVEL` | Logging level | `INFO` |

### 8.2 Configuration File

```yaml
# config.yaml
server:
  name: llm-wasm-sandbox
  version: 1.0.0

transport:
  default: stdio
  http:
    host: 127.0.0.1
    port: 8080
    cors_origins:
      - http://localhost:*
      - https://claude.ai

sandbox:
  default_timeout: 30
  max_timeout: 300
  default_memory_mb: 256
  max_memory_mb: 1024
  max_output_bytes: 1000000

runtimes:
  python:
    enabled: true
    version: "3.11"
    wasm_module: python-3.11.wasm
    packages:
      - numpy
      - pandas
      - matplotlib
  
  javascript:
    enabled: true
    version: ES2020
    wasm_module: quickjs.wasm

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

---

## 10. Testing Requirements

### 10.1 Unit Tests

```python
# tests/test_tools.py
import pytest
from llm_wasm_sandbox.server import execute_code, list_runtimes, create_session

@pytest.mark.asyncio
async def test_execute_python_simple():
    result = await execute_code(
        code="print('Hello, World!')",
        language="python"
    )
    assert result["exit_code"] == 0
    assert "Hello, World!" in result["stdout"]

@pytest.mark.asyncio
async def test_execute_python_math():
    result = await execute_code(
        code="import math; print(math.pi)",
        language="python"
    )
    assert result["exit_code"] == 0
    assert "3.14" in result["stdout"]

@pytest.mark.asyncio
async def test_execute_timeout():
    result = await execute_code(
        code="while True: pass",
        language="python",
        timeout=1
    )
    assert result["exit_code"] == 124  # Timeout exit code

@pytest.mark.asyncio
async def test_list_runtimes():
    result = await list_runtimes()
    assert "runtimes" in result
    languages = [r["language"] for r in result["runtimes"]]
    assert "python" in languages

@pytest.mark.asyncio
async def test_session_lifecycle():
    # Create session
    session = await create_session(language="python")
    assert "session_id" in session
    
    # Execute in session
    result = await execute_code(
        code="x = 42",
        language="python",
        session_id=session["session_id"]
    )
    assert result["exit_code"] == 0
    
    # Variable should persist
    result = await execute_code(
        code="print(x)",
        language="python",
        session_id=session["session_id"]
    )
    assert "42" in result["stdout"]
```

### 10.2 Workspace Session Tests

```python
# tests/test_sessions.py
"""
Tests for automatic workspace session management.

These tests verify that state persists across multiple tool calls
within the same MCP client session.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from llm_wasm_sandbox.sessions.manager import WorkspaceSessionManager
from llm_wasm_sandbox.sandbox.engine import WASMSandboxEngine


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox engine."""
    sandbox = MagicMock(spec=WASMSandboxEngine)
    sandbox.create_session = AsyncMock(return_value={
        "session_id": "test-session-123",
        "language": "python",
        "created_at": "2025-01-01T00:00:00Z",
        "expires_at": "2025-01-01T01:00:00Z"
    })
    sandbox.execute = AsyncMock(return_value={
        "stdout": "42\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time_ms": 10.0
    })
    sandbox.destroy_session = AsyncMock()
    return sandbox


@pytest.fixture
def session_manager(mock_sandbox):
    """Create a session manager with mock sandbox."""
    return WorkspaceSessionManager(mock_sandbox)


class TestWorkspaceSessionManager:
    """Test workspace session management."""
    
    @pytest.mark.asyncio
    async def test_auto_create_workspace(self, session_manager, mock_sandbox):
        """Test automatic workspace creation on first use."""
        workspace = await session_manager.get_or_create_workspace(
            mcp_session_id="client-1",
            language="python"
        )
        
        assert workspace.language == "python"
        assert workspace.mcp_session_id == "client-1"
        mock_sandbox.create_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reuse_existing_workspace(self, session_manager, mock_sandbox):
        """Test that existing workspace is reused."""
        # First call creates workspace
        ws1 = await session_manager.get_or_create_workspace(
            mcp_session_id="client-1",
            language="python"
        )
        
        # Second call should reuse
        ws2 = await session_manager.get_or_create_workspace(
            mcp_session_id="client-1",
            language="python"
        )
        
        assert ws1.workspace_id == ws2.workspace_id
        # create_session should only be called once
        assert mock_sandbox.create_session.call_count == 1
    
    @pytest.mark.asyncio
    async def test_separate_workspaces_per_client(self, session_manager, mock_sandbox):
        """Test that different clients get different workspaces."""
        ws1 = await session_manager.get_or_create_workspace(
            mcp_session_id="client-1",
            language="python"
        )
        
        ws2 = await session_manager.get_or_create_workspace(
            mcp_session_id="client-2",
            language="python"
        )
        
        assert ws1.workspace_id != ws2.workspace_id
        assert mock_sandbox.create_session.call_count == 2
    
    @pytest.mark.asyncio
    async def test_separate_workspaces_per_language(self, session_manager, mock_sandbox):
        """Test that different languages get different workspaces."""
        ws_python = await session_manager.get_or_create_workspace(
            mcp_session_id="client-1",
            language="python"
        )
        
        ws_js = await session_manager.get_or_create_workspace(
            mcp_session_id="client-1",
            language="javascript"
        )
        
        assert ws_python.workspace_id != ws_js.workspace_id
        assert ws_python.language == "python"
        assert ws_js.language == "javascript"
    
    @pytest.mark.asyncio
    async def test_execute_in_workspace(self, session_manager, mock_sandbox):
        """Test execution uses correct workspace session."""
        result = await session_manager.execute_in_workspace(
            mcp_session_id="client-1",
            code="print(42)",
            language="python"
        )
        
        assert result["exit_code"] == 0
        # Should use the workspace's sandbox session
        mock_sandbox.execute.assert_called_once()
        call_args = mock_sandbox.execute.call_args
        assert call_args.kwargs["session_id"] == "test-session-123"
    
    @pytest.mark.asyncio
    async def test_workspace_metadata_updated(self, session_manager):
        """Test that workspace metadata is updated after execution."""
        # Execute some code
        await session_manager.execute_in_workspace(
            mcp_session_id="client-1",
            code="import pandas as pd\nx = 42",
            language="python"
        )
        
        # Get workspace info
        info = await session_manager.get_workspace_info("client-1", "python")
        
        assert info is not None
        assert "pandas" in info["imports"]
        assert "x" in info["variables"]
        assert info["execution_count"] == 1
    
    @pytest.mark.asyncio
    async def test_reset_workspace(self, session_manager, mock_sandbox):
        """Test workspace reset creates new session."""
        # Create initial workspace
        ws1 = await session_manager.get_or_create_workspace(
            mcp_session_id="client-1",
            language="python"
        )
        
        # Reset workspace
        result = await session_manager.reset_workspace("client-1", "python")
        
        assert result["success"] is True
        mock_sandbox.destroy_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_mcp_session(self, session_manager, mock_sandbox):
        """Test cleanup destroys all workspaces for a client."""
        # Create workspaces
        await session_manager.get_or_create_workspace("client-1", "python")
        await session_manager.get_or_create_workspace("client-1", "javascript")
        
        # Cleanup
        await session_manager.cleanup_mcp_session("client-1")
        
        # Both sessions should be destroyed
        assert mock_sandbox.destroy_session.call_count == 2
        
        # Client should have no workspaces
        info = await session_manager.get_workspace_info("client-1", "python")
        assert info is None
    
    @pytest.mark.asyncio
    async def test_stdio_session_handling(self, session_manager):
        """Test stdio transport (no MCP session ID)."""
        # None session_id should use __stdio__ internally
        ws = await session_manager.get_or_create_workspace(
            mcp_session_id=None,
            language="python"
        )
        
        assert ws.mcp_session_id == "__stdio__"


class TestStatePersistence:
    """Integration tests for state persistence across calls."""
    
    @pytest.mark.asyncio
    async def test_variable_persistence(self, session_manager):
        """Test that variables persist across execute_code calls."""
        # This would be an integration test with real WASM sandbox
        # Here we just verify the session is reused
        
        # Call 1: Define variable
        await session_manager.execute_in_workspace(
            mcp_session_id="agent-1",
            code="x = 42",
            language="python"
        )
        
        # Call 2: Use variable (should work if state persists)
        await session_manager.execute_in_workspace(
            mcp_session_id="agent-1",
            code="y = x * 2",
            language="python"
        )
        
        # Verify same session was used
        info = await session_manager.get_workspace_info("agent-1", "python")
        assert info["execution_count"] == 2
```

### 9.2 Integration Tests

```python
# tests/test_transports.py
import pytest
import httpx
import asyncio
import json

@pytest.mark.asyncio
async def test_http_initialize():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8080/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["protocolVersion"] == "2025-06-18"
        assert "Mcp-Session-Id" in response.headers

@pytest.mark.asyncio
async def test_http_tools_call():
    async with httpx.AsyncClient() as client:
        # Initialize first
        init_response = await client.post(
            "http://localhost:8080/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            },
            headers={"Accept": "application/json, text/event-stream"}
        )
        session_id = init_response.headers["Mcp-Session-Id"]
        
        # Call tool
        response = await client.post(
            "http://localhost:8080/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "execute_code",
                    "arguments": {
                        "code": "print(2 + 2)",
                        "language": "python"
                    }
                }
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id,
                "MCP-Protocol-Version": "2025-06-18"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "4" in data["result"]["content"][0]["text"]
```

### 9.3 Security Tests

```python
# tests/test_security.py
import pytest
from llm_wasm_sandbox.server import execute_code

@pytest.mark.asyncio
async def test_no_filesystem_access():
    """Verify sandbox cannot access host filesystem."""
    result = await execute_code(
        code="import os; print(os.listdir('/'))",
        language="python"
    )
    # Should fail or return only sandbox contents
    assert "etc" not in result["stdout"]
    assert "home" not in result["stdout"]

@pytest.mark.asyncio
async def test_no_network_access():
    """Verify sandbox cannot make network requests."""
    result = await execute_code(
        code="""
import urllib.request
urllib.request.urlopen('http://example.com')
""",
        language="python"
    )
    assert result["exit_code"] != 0

@pytest.mark.asyncio
async def test_memory_limit():
    """Verify memory limits are enforced."""
    result = await execute_code(
        code="x = 'a' * (500 * 1024 * 1024)",  # Try to allocate 500MB
        language="python",
        timeout=10
    )
    assert result["exit_code"] != 0

@pytest.mark.asyncio
async def test_no_subprocess():
    """Verify subprocess creation is blocked."""
    result = await execute_code(
        code="import subprocess; subprocess.run(['ls'])",
        language="python"
    )
    assert result["exit_code"] != 0
```

---

## 11. Deployment

### 10.1 Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application
COPY src/ src/

# Download WASM runtimes
RUN mkdir -p src/llm_wasm_sandbox/runtimes && \
    curl -L -o src/llm_wasm_sandbox/runtimes/python-3.11.wasm \
    https://github.com/vmware-labs/webassembly-language-runtimes/releases/download/python%2F3.11.4%2B20230714-11be424/python-3.11.4.wasm

# Create non-root user
RUN useradd -m -u 1000 sandbox
USER sandbox

EXPOSE 8080

CMD ["python", "-m", "llm_wasm_sandbox.server", "--transport", "http", "--port", "8080"]
```

### 10.2 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  llm-wasm-sandbox:
    build: .
    ports:
      - "8080:8080"
    environment:
      - WASM_SANDBOX_TIMEOUT=30
      - WASM_SANDBOX_MEMORY_MB=256
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '2'
```

### 10.3 Kubernetes Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-wasm-sandbox
spec:
  replicas: 3
  selector:
    matchLabels:
      app: llm-wasm-sandbox
  template:
    metadata:
      labels:
        app: llm-wasm-sandbox
    spec:
      containers:
      - name: sandbox
        image: llm-wasm-sandbox:latest
        ports:
        - containerPort: 8080
        env:
        - name: WASM_SANDBOX_TIMEOUT
          value: "30"
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        securityContext:
          runAsNonRoot: true
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
---
apiVersion: v1
kind: Service
metadata:
  name: llm-wasm-sandbox
spec:
  selector:
    app: llm-wasm-sandbox
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

---

## 12. Client Integration Examples

### 11.1 Claude Desktop Configuration

```json
{
  "mcpServers": {
    "llm-wasm-sandbox": {
      "command": "python3",
      "args": ["-m", "llm_wasm_sandbox.server"],
      "env": {
        "WASM_SANDBOX_TIMEOUT": "60",
        "LOG_LEVEL": "WARNING"
      }
    }
  }
}
```

### 12.2 Python Client Example

```python
# examples/python_client.py
import httpx
import json

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8080") as client:
        # Initialize session
        init_response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "python-client", "version": "1.0"}
                }
            },
            headers={"Accept": "application/json, text/event-stream"}
        )
        
        session_id = init_response.headers["Mcp-Session-Id"]
        print(f"Session: {session_id}")
        
        # Send initialized notification
        await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            },
            headers={
                "Mcp-Session-Id": session_id,
                "MCP-Protocol-Version": "2025-06-18"
            }
        )
        
        # Execute code
        response = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "execute_code",
                    "arguments": {
                        "code": """
import json
data = {"message": "Hello from WASM sandbox!", "numbers": [1, 2, 3, 4, 5]}
print(json.dumps(data, indent=2))
""",
                        "language": "python"
                    }
                }
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": session_id,
                "MCP-Protocol-Version": "2025-06-18"
            }
        )
        
        result = response.json()
        print("Result:", json.dumps(result, indent=2))
        
        # Terminate session
        await client.delete(
            "/mcp",
            headers={"Mcp-Session-Id": session_id}
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 12.3 Agentic Workflow Example (State Persistence)

```python
# examples/agentic_workflow.py
"""
Example demonstrating automatic state persistence for AI agent workflows.

This example shows how an AI agent can execute multiple code steps
with state automatically persisting between calls.
"""
import asyncio
import httpx

MCP_URL = "http://localhost:8080/mcp"


async def call_tool(client: httpx.AsyncClient, session_id: str, name: str, arguments: dict, request_id: int):
    """Call an MCP tool and return the result."""
    response = await client.post(
        MCP_URL,
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments}
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": session_id,
            "MCP-Protocol-Version": "2025-06-18"
        }
    )
    result = response.json()
    if "error" in result:
        raise Exception(f"Tool error: {result['error']}")
    return result["result"]


async def simulate_agent_workflow():
    """
    Simulate an AI agent workflow with multiple code execution steps.
    
    This demonstrates how state persists automatically between calls,
    allowing the agent to build up computations incrementally.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Initialize MCP session
        init_response = await client.post(
            MCP_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "agent-example", "version": "1.0"}
                }
            },
            headers={"Accept": "application/json, text/event-stream"}
        )
        session_id = init_response.headers["Mcp-Session-Id"]
        print(f"✓ MCP Session established: {session_id[:16]}...")
        
        # Send initialized notification
        await client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={"Mcp-Session-Id": session_id, "MCP-Protocol-Version": "2025-06-18"}
        )
        
        request_id = 2
        
        # ================================================================
        # AGENT STEP 1: Load and prepare data
        # ================================================================
        print("\n📊 Agent Step 1: Loading data...")
        result = await call_tool(client, session_id, "execute_code", {
            "code": """
import json

# Simulated data that an agent might fetch from an API
sales_data = [
    {"month": "Jan", "revenue": 10000, "units": 150},
    {"month": "Feb", "revenue": 12000, "units": 180},
    {"month": "Mar", "revenue": 15000, "units": 220},
    {"month": "Apr", "revenue": 11000, "units": 160},
    {"month": "May", "revenue": 18000, "units": 270},
]

print(f"Loaded {len(sales_data)} months of sales data")
print(json.dumps(sales_data[0], indent=2))
""",
            "language": "python"
        }, request_id)
        print(f"Output: {result['content'][0]['text']}")
        request_id += 1
        
        # ================================================================
        # AGENT STEP 2: Analyze data (uses variables from Step 1!)
        # ================================================================
        print("\n📈 Agent Step 2: Analyzing data...")
        result = await call_tool(client, session_id, "execute_code", {
            "code": """
# sales_data is still available from the previous execution!
total_revenue = sum(d['revenue'] for d in sales_data)
total_units = sum(d['units'] for d in sales_data)
avg_price = total_revenue / total_units

print(f"Total Revenue: ${total_revenue:,}")
print(f"Total Units: {total_units:,}")
print(f"Average Price per Unit: ${avg_price:.2f}")

# Find best month
best_month = max(sales_data, key=lambda x: x['revenue'])
print(f"Best Month: {best_month['month']} (${best_month['revenue']:,})")
""",
            "language": "python"
        }, request_id)
        print(f"Output: {result['content'][0]['text']}")
        request_id += 1
        
        # ================================================================
        # AGENT STEP 3: Create visualization (builds on previous steps!)
        # ================================================================
        print("\n🎨 Agent Step 3: Creating visualization...")
        result = await call_tool(client, session_id, "execute_code", {
            "code": """
# All variables still available: sales_data, total_revenue, best_month, etc.

# Create ASCII chart of revenue by month
print("Revenue by Month")
print("=" * 40)

max_rev = max(d['revenue'] for d in sales_data)
for d in sales_data:
    bar_len = int(d['revenue'] / max_rev * 20)
    bar = '█' * bar_len
    print(f"{d['month']}: {bar} ${d['revenue']:,}")

print("=" * 40)
print(f"Peak: {best_month['month']} with ${best_month['revenue']:,}")
""",
            "language": "python"
        }, request_id)
        print(f"Output:\n{result['content'][0]['text']}")
        request_id += 1
        
        # ================================================================
        # Check workspace state
        # ================================================================
        print("\n📋 Checking workspace state...")
        result = await call_tool(client, session_id, "get_workspace_info", {
            "language": "python"
        }, request_id)
        
        structured = result.get("structuredContent", result.get("content", [{}])[0])
        if isinstance(structured, dict):
            print(f"Variables defined: {structured.get('variables', [])}")
            print(f"Imports: {structured.get('imports', [])}")
            print(f"Execution count: {structured.get('execution_count', 'N/A')}")
        request_id += 1
        
        # ================================================================
        # Cleanup
        # ================================================================
        await client.delete(MCP_URL, headers={"Mcp-Session-Id": session_id})
        print("\n✓ Session closed")


if __name__ == "__main__":
    print("=" * 60)
    print("LLM WASM Sandbox - Agentic Workflow Demo")
    print("Demonstrating automatic state persistence across tool calls")
    print("=" * 60)
    asyncio.run(simulate_agent_workflow())
```

**Expected Output:**
```
============================================================
LLM WASM Sandbox - Agentic Workflow Demo
Demonstrating automatic state persistence across tool calls
============================================================
✓ MCP Session established: abc123def456...

📊 Agent Step 1: Loading data...
Output: Loaded 5 months of sales data
{
  "month": "Jan",
  "revenue": 10000,
  "units": 150
}

📈 Agent Step 2: Analyzing data...
Output: Total Revenue: $66,000
Total Units: 980
Average Price per Unit: $67.35
Best Month: May ($18,000)

🎨 Agent Step 3: Creating visualization...
Output:
Revenue by Month
========================================
Jan: ███████████ $10,000
Feb: █████████████ $12,000
Mar: ████████████████ $15,000
Apr: ████████████ $11,000
May: ████████████████████ $18,000
========================================
Peak: May with $18,000

📋 Checking workspace state...
Variables defined: ['sales_data', 'total_revenue', 'total_units', 'avg_price', 'best_month', 'max_rev', 'd', 'bar_len', 'bar']
Imports: ['json']
Execution count: 3

✓ Session closed
```

---

## 13. Error Handling

### 12.1 JSON-RPC Error Codes

| Code | Message | Description |
|------|---------|-------------|
| `-32700` | Parse error | Invalid JSON |
| `-32600` | Invalid Request | Invalid JSON-RPC request |
| `-32601` | Method not found | Unknown method |
| `-32602` | Invalid params | Invalid method parameters |
| `-32603` | Internal error | Server error |
| `-32000` | Execution timeout | Code execution timed out |
| `-32001` | Memory limit exceeded | Sandbox memory limit exceeded |
| `-32002` | Session not found | Invalid session ID |
| `-32003` | Runtime unavailable | Requested language runtime not available |

### 12.2 Error Response Examples

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32000,
    "message": "Execution timeout",
    "data": {
      "timeout_seconds": 30,
      "execution_id": "abc123"
    }
  }
}
```

---

## 14. Monitoring and Observability

### 13.1 Logging

```python
import logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()

# Log execution
logger.info(
    "code_execution",
    language="python",
    execution_time_ms=45.2,
    exit_code=0,
    session_id="abc123"
)
```

### 13.2 Metrics

- `mcp_requests_total` - Total MCP requests by method
- `mcp_request_duration_seconds` - Request duration histogram
- `sandbox_executions_total` - Total code executions by language
- `sandbox_execution_duration_seconds` - Execution duration histogram
- `sandbox_memory_usage_bytes` - Memory usage gauge
- `sandbox_active_sessions` - Active session count

---

## 15. Security Considerations

### 14.1 Threat Model

| Threat | Mitigation |
|--------|------------|
| Arbitrary code execution on host | WASM sandbox isolation |
| Memory exhaustion | Configurable memory limits |
| CPU exhaustion | Fuel-based execution limits |
| Filesystem access | WASI capability restrictions |
| Network access | No networking capabilities exposed |
| Session hijacking | Cryptographically secure session IDs |
| DNS rebinding | Origin header validation |

### 14.2 Security Recommendations

1. **Production Deployment**
   - Always use HTTPS for HTTP transport
   - Implement authentication (API keys, JWT)
   - Rate limit requests
   - Monitor for abuse patterns

2. **Network Security**
   - Bind to localhost for local deployments
   - Use network policies in Kubernetes
   - Implement proper firewall rules

3. **Update Management**
   - Regularly update wasmtime runtime
   - Update WASM language modules
   - Monitor CVEs for dependencies

---

## 16. Roadmap

### Phase 1 (MVP)
- [x] stdio transport
- [x] Streamable HTTP transport
- [x] Python runtime (Pyodide)
- [x] JavaScript runtime (QuickJS)
- [x] Basic session management
- [x] Core security controls

### Phase 2 (Enhanced)
- [ ] Additional language runtimes (Lua, Ruby)
- [ ] Package installation for Python
- [ ] Artifact extraction (images, files)
- [ ] Streaming execution output
- [ ] Enhanced monitoring

### Phase 3 (Enterprise)
- [ ] Multi-tenant support
- [ ] Custom security policies
- [ ] Audit logging
- [ ] RBAC integration
- [ ] High availability deployment

---

## 17. References

### MCP Specification
- [MCP Specification 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18)
- [MCP Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [MCP Tools](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [MCP Lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)

### FastMCP 2.0
- [FastMCP Documentation](https://gofastmcp.com/)
- [FastMCP GitHub](https://github.com/jlowin/fastmcp)
- [FastMCP Tools Guide](https://gofastmcp.com/servers/tools)
- [FastMCP Running Servers](https://gofastmcp.com/deployment/running-server)
- [FastMCP HTTP Deployment](https://gofastmcp.com/deployment/http)
- [FastMCP Context](https://gofastmcp.com/servers/context)

### WebAssembly / WASI
- [WASI Specification](https://wasi.dev/)
- [wasmtime Documentation](https://docs.wasmtime.dev/)
- [wasmtime-py (Python bindings)](https://github.com/bytecodealliance/wasmtime-py)

### Language Runtimes
- [Pyodide Documentation](https://pyodide.org/en/stable/)
- [VMware WASM Language Runtimes](https://github.com/vmware-labs/webassembly-language-runtimes)
- [QuickJS Engine](https://bellard.org/quickjs/)

---

## Appendix A: Complete Tool Schema Reference

```json
{
  "tools": [
    {
      "name": "execute_code",
      "title": "Execute Code in WASM Sandbox",
      "description": "Execute code in a secure WebAssembly sandbox. State persists automatically between calls - variables and imports from previous executions are available. Use session_id='__stateless__' for isolated execution.",
      "inputSchema": {
        "type": "object",
        "properties": {
          "code": {"type": "string", "description": "The source code to execute"},
          "language": {"type": "string", "enum": ["python", "javascript"], "description": "Programming language"},
          "timeout": {"type": "integer", "description": "Timeout in seconds", "minimum": 1, "maximum": 300},
          "session_id": {"type": "string", "description": "Session ID: null=auto (default), '__stateless__'=isolated, or explicit ID"}
        },
        "required": ["code", "language"]
      },
      "outputSchema": {
        "type": "object",
        "properties": {
          "stdout": {"type": "string"},
          "stderr": {"type": "string"},
          "exit_code": {"type": "integer"},
          "execution_time_ms": {"type": "number"},
          "memory_used_bytes": {"type": "integer"},
          "truncated": {"type": "boolean"}
        },
        "required": ["stdout", "stderr", "exit_code", "execution_time_ms"]
      },
      "annotations": {
        "title": "Execute Code in WASM Sandbox",
        "readOnlyHint": false,
        "destructiveHint": false,
        "idempotentHint": false,
        "openWorldHint": false
      }
    },
    {
      "name": "list_runtimes",
      "title": "List Available Runtimes",
      "description": "List all available programming language runtimes in the sandbox",
      "inputSchema": {"type": "object", "properties": {}},
      "annotations": {
        "readOnlyHint": true,
        "idempotentHint": true,
        "openWorldHint": false
      }
    },
    {
      "name": "get_workspace_info",
      "title": "Get Workspace Information",
      "description": "Get information about the current workspace session including defined variables and imported modules",
      "inputSchema": {
        "type": "object",
        "properties": {
          "language": {"type": "string", "enum": ["python", "javascript"], "default": "python"}
        }
      },
      "outputSchema": {
        "type": "object",
        "properties": {
          "session_id": {"type": "string"},
          "language": {"type": "string"},
          "variables": {"type": "array", "items": {"type": "string"}},
          "imports": {"type": "array", "items": {"type": "string"}},
          "execution_count": {"type": "integer"},
          "created_at": {"type": "string", "format": "date-time"}
        }
      },
      "annotations": {
        "readOnlyHint": true,
        "idempotentHint": true,
        "openWorldHint": false
      }
    },
    {
      "name": "reset_workspace",
      "title": "Reset Workspace",
      "description": "Reset the current workspace session, clearing all variables and imports",
      "inputSchema": {
        "type": "object",
        "properties": {
          "language": {"type": "string", "enum": ["python", "javascript"], "default": "python"}
        }
      },
      "annotations": {
        "readOnlyHint": false,
        "destructiveHint": true,
        "idempotentHint": true,
        "openWorldHint": false
      }
    },
    {
      "name": "create_session",
      "title": "Create Execution Session",
      "description": "Create an explicit stateful execution session (for advanced use - most users should rely on automatic workspace sessions)",
      "inputSchema": {
        "type": "object",
        "properties": {
          "language": {"type": "string", "enum": ["python", "javascript"]},
          "memory_limit_mb": {"type": "integer", "minimum": 64, "maximum": 1024},
          "timeout_seconds": {"type": "integer", "minimum": 60, "maximum": 3600}
        },
        "required": ["language"]
      },
      "annotations": {
        "readOnlyHint": false,
        "destructiveHint": false,
        "idempotentHint": false,
        "openWorldHint": false
      }
    },
    {
      "name": "destroy_session",
      "title": "Destroy Execution Session",
      "description": "Destroy an explicit stateful execution session",
      "inputSchema": {
        "type": "object",
        "properties": {
          "session_id": {"type": "string"}
        },
        "required": ["session_id"]
      },
      "annotations": {
        "readOnlyHint": false,
        "destructiveHint": true,
        "idempotentHint": true,
        "openWorldHint": false
      }
    },
    {
      "name": "install_package",
      "title": "Install Python Package",
      "description": "Install a Python package in the current workspace session using micropip",
      "inputSchema": {
        "type": "object",
        "properties": {
          "package": {"type": "string"},
          "version": {"type": "string"},
          "session_id": {"type": "string", "description": "Optional explicit session ID (uses workspace by default)"}
        },
        "required": ["package"]
      },
      "annotations": {
        "readOnlyHint": false,
        "destructiveHint": false,
        "idempotentHint": true,
        "openWorldHint": false
      }
    },
    {
      "name": "cancel_execution",
      "title": "Cancel Execution",
      "description": "Cancel a currently running code execution",
      "inputSchema": {
        "type": "object",
        "properties": {
          "execution_id": {"type": "string"}
        },
        "required": ["execution_id"]
      },
      "annotations": {
        "readOnlyHint": false,
        "destructiveHint": true,
        "idempotentHint": true,
        "openWorldHint": false
      }
    }
  ]
}
```

---

**Document Prepared By:** Claude (Enterprise Architecture Assistant)  
**For:** ThomasRohde/llm-wasm-sandbox MCP Server Development  
**Status:** Ready for Development