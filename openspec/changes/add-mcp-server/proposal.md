# Change: Add MCP Server for Sandbox Execution

## Why

Large Language Models (LLMs) need secure, sandboxed code execution capabilities to safely run generated code. While the core sandbox provides excellent security isolation, it lacks standardized protocols for LLM integration. The Model Context Protocol (MCP) is the emerging standard for tool use in AI applications, providing:

- **Standardized API**: Consistent interface across different MCP clients (Claude Desktop, custom agents)
- **Stateful Sessions**: Automatic persistence of variables and execution context across tool calls
- **Streaming Support**: Real-time execution feedback for long-running code
- **Security Boundaries**: MCP layer enforces additional validation on top of WASM isolation
- **Enterprise Integration**: Fits into existing MCP ecosystems and tooling

Without MCP support, each LLM integration requires custom adapters and loses the benefits of standardized tool calling.

## What Changes

- **NEW**: MCP server implementation using FastMCP 2.0 framework
  - Full MCP 2025-06-18 protocol compliance
  - stdio transport for local MCP clients
  - Streamable HTTP transport for remote/web clients
  - Automatic workspace session management per MCP client

- **NEW**: Core MCP tools exposing sandbox functionality
  - `execute_code`: Execute Python/JavaScript with automatic session binding
  - `list_runtimes`: Enumerate available language runtimes
  - `create_session`: Explicit session management for advanced use cases
  - `destroy_session`: Clean up explicit sessions
  - `install_package`: Python package installation in sessions
  - `cancel_execution`: Interrupt running executions
  - `get_workspace_info`: Inspect current session state
  - `reset_workspace`: Clear session state while maintaining MCP connection

- **NEW**: Workspace session manager for automatic state persistence
  - Binds MCP client sessions to WASM sandbox sessions
  - Automatic session creation and cleanup
  - Per-language session isolation
  - Session timeout and resource management

- **NEW**: FastMCP-based server architecture
  - Type-safe tool definitions with Pydantic schemas
  - Structured error handling and logging
  - Progress reporting and context injection
  - Production-ready async support

- **UPDATE**: Project structure to accommodate MCP server
  - New `mcp/` package with server implementation
  - Updated dependencies (FastMCP 2.0, additional MCP-related packages)
  - Configuration for MCP server settings
  - Documentation for MCP integration

## Impact

**Affected Specs**:
- `mcp-protocol`: New capability for MCP 2025-06-18 compliance
- `mcp-tools`: New capability for sandbox tool exposure
- `mcp-transports`: New capability for stdio/HTTP transport support
- `mcp-session-management`: New capability for workspace session binding

**Affected Code**:
- `mcp/` (new package)
  - `server.py`: Main FastMCP server implementation
  - `tools.py`: Tool definitions and handlers
  - `sessions.py`: Workspace session manager
  - `transports.py`: Transport implementations
- `pyproject.toml`: New dependencies (fastmcp, uvicorn for HTTP)
- `config/`: MCP-specific configuration
- `tests/test_mcp_*.py`: Comprehensive MCP integration tests
- `examples/mcp_*.py`: MCP usage examples
- `docs/MCP_INTEGRATION.md`: Integration guide

**User Impact**:
- **Before**: Custom integration code required for each LLM/client
- **After**: Standard MCP interface - works with Claude Desktop, custom MCP clients out of the box

**Breaking Changes**: None (purely additive feature)

**Migration**: Not applicable (new feature)

## Success Metrics

- Full MCP 2025-06-18 protocol compliance verified
- All 8 core tools implemented and tested
- Automatic session management working across tool calls
- Both stdio and HTTP transports functional
- Comprehensive test coverage (unit, integration, security)
- Performance: Tool calls complete within 100ms overhead
- Documentation covers setup, configuration, and integration examples
- Compatible with Claude Desktop and custom MCP clients