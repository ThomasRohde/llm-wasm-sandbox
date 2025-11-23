# MCP Server Design

## Context

The LLM WASM Sandbox provides secure code execution but lacks standardized interfaces for LLM integration. MCP (Model Context Protocol) is the emerging standard for tool use in AI applications. We need to add MCP server support while maintaining the project's security-first architecture and type-safe patterns.

## Goals / Non-Goals

### Goals
- Full MCP 2025-06-18 protocol compliance
- Seamless integration with existing sandbox architecture
- Automatic workspace session management for stateful execution
- Support for both stdio (local) and HTTP (remote) transports
- Production-ready error handling and logging
- Comprehensive test coverage including security tests

### Non-Goals
- MCP client implementation (only server)
- Custom MCP protocol extensions
- Non-FastMCP server frameworks
- Breaking changes to existing sandbox APIs

## Decisions

### Framework: FastMCP 2.0
**Decision**: Use FastMCP 2.0 as the MCP server framework.

**Rationale**:
- Official Python MCP framework with active maintenance
- Type-safe tool definitions with automatic schema generation
- Built-in support for stdio and HTTP transports
- Structured error handling and context injection
- Aligns with project's Pydantic/type-safe patterns

**Alternatives Considered**:
- Raw MCP protocol implementation: Too complex, error-prone
- Other MCP libraries: FastMCP is the most mature and feature-complete

### Architecture: Layered Design
**Decision**: Implement MCP server as a separate layer on top of existing sandbox.

```
MCP Layer (new)
├── server.py (FastMCP app)
├── tools.py (Tool definitions)
├── sessions.py (Workspace manager)
└── transports.py (Transport config)

Sandbox Layer (existing)
├── core/ (Type-safe models)
├── runtimes/ (Python/JS execution)
└── host.py (WASM host)
```

**Rationale**:
- Clean separation of concerns
- Minimal changes to existing sandbox code
- Easy to test MCP layer independently
- Allows future MCP versions without touching sandbox

### Session Management: Automatic Binding
**Decision**: Automatically bind MCP client sessions to workspace sessions.

**Rationale**:
- Simplifies LLM integration (no manual session management)
- Maintains state across tool calls naturally
- Per-client isolation prevents interference
- Graceful fallback to stateless execution

**Implementation**:
- stdio transport: Single workspace per process
- HTTP transport: Workspace per `Mcp-Session-Id` header
- Automatic cleanup on session timeout/disconnect

### Tool Design: Direct Sandbox Mapping
**Decision**: Map MCP tools directly to sandbox operations with minimal abstraction.

**Rationale**:
- Transparency: MCP tools mirror sandbox capabilities
- Maintainability: Changes to sandbox automatically benefit MCP
- Performance: No additional processing layers
- Security: MCP validation layers on top of existing sandbox security

### Error Handling: Structured Responses
**Decision**: Use FastMCP's structured error handling with custom error types.

**Rationale**:
- Consistent error reporting across tools
- Type-safe error schemas
- Proper MCP error classification
- Integration with existing sandbox error handling

## Risks / Trade-offs

### Performance Overhead
**Risk**: MCP protocol adds ~50-100ms overhead per tool call.

**Mitigation**:
- Optimize session lookup and binding
- Use async execution where possible
- Cache frequently accessed data
- Monitor and profile performance

### Complexity
**Risk**: Adding MCP layer increases overall system complexity.

**Mitigation**:
- Keep MCP layer thin and focused
- Comprehensive testing of integration points
- Clear separation between layers
- Extensive documentation

### Security Surface
**Risk**: MCP server expands attack surface.

**Mitigation**:
- Input validation on all MCP inputs
- Rate limiting and timeout controls
- Audit logging of all tool calls
- Sandbox security remains primary defense

## Migration Plan

### Phase 1: Core Implementation
1. Implement basic MCP server with execute_code tool
2. Add session management
3. Test with stdio transport

### Phase 2: Full Tool Set
1. Implement remaining tools (list_runtimes, create_session, etc.)
2. Add HTTP transport support
3. Comprehensive testing

### Phase 3: Production Readiness
1. Performance optimization
2. Security hardening
3. Documentation and examples

### Rollback
- Remove MCP package and dependencies
- No changes to existing sandbox functionality

## Open Questions

- Should we support MCP resource subscriptions for execution results?
- How to handle long-running executions with MCP's synchronous model?
- What level of customization should we expose for MCP server configuration?