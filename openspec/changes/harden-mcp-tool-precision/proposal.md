# Change: Harden MCP Tool Precision & Error Guidance

## Why

Following extensive testing of the JavaScript runtime through MCP tools (20+ scenarios, 57 tool invocations, 0% error rate), we've identified critical opportunities to improve LLM decision-making and developer experience:

1. **Generic Tool Descriptions**: Current MCP tool descriptions are minimal and don't guide LLMs in making informed decisions about when/how to use tools
2. **Non-Actionable Errors**: Error messages are technically correct but lack guidance on resolution (e.g., "OutOfFuel" doesn't explain that heavy packages need higher budgets)
3. **Hidden Fuel Requirements**: Package fuel budgets are documented separately; LLMs and users don't know upfront which packages require budget increases
4. **Missing Usage Patterns**: Common patterns (session management, state persistence, QuickJS API quirks) aren't surfaced in tool interfaces
5. **No Proactive Guidance**: System doesn't warn when fuel utilization approaches limits or recommend budget adjustments

**Impact**: LLMs frequently select suboptimal patterns (e.g., creating sessions when defaults suffice, missing state persistence opportunities, hitting fuel limits unexpectedly).

## What Changes

### Phase 1: Enhanced Tool Descriptions (Quick Wins)
- **MODIFIED**: Enhance `execute_code` tool description with:
  - When to use (data processing, file manipulation) vs. when not to (network operations)
  - Runtime-specific capabilities (QuickJS std/os modules, Python vendored packages)
  - Common pitfalls (QuickJS tuple returns, /app path requirements, fuel limits)
  - Usage pattern examples (one-off calculation, file processing, stateful workflows)
  
- **MODIFIED**: Enhance `create_session` tool description with:
  - Decision tree: when to create new session vs. reuse default
  - Auto-persist guidelines: when to enable, what gets persisted, limitations
  - Session lifecycle management patterns
  - Fuel budget customization guidance

- **MODIFIED**: Enhance `list_runtimes` tool to include:
  - Runtime version details and ES2020+ feature availability
  - Vendored package counts and names
  - API pattern notes (QuickJS tuple returns, Python import paths)
  - Helper function availability

- **MODIFIED**: Update `list_available_packages` to include:
  - Per-package fuel requirements (e.g., "openpyxl: 5-7B first import")
  - Import pattern examples
  - Common use cases for each package
  - Performance notes (first import vs. cached)

### Phase 2: Actionable Error Guidance
- **ADDED**: `SandboxResult.structured_content.error_guidance` field containing:
  - `error_type`: Classified error category (OutOfFuel, PathRestriction, QuickJSTuple, etc.)
  - `actionable_guidance`: Array of concrete solution steps
  - `related_docs`: Links to relevant documentation sections
  - `code_examples`: Optional corrected code snippets

- **MODIFIED**: Error classification logic in `sandbox/host.py`:
  - Detect OutOfFuel and include fuel budget recommendations
  - Detect path violations and explain /app restriction
  - Detect QuickJS destructuring errors and show correct pattern
  - Detect missing imports and suggest sys.path configuration

### Phase 3: Fuel Budget Analysis & Recommendations
- **ADDED**: `SandboxResult.structured_content.fuel_analysis` field containing:
  - `consumed`: Instructions executed
  - `budget`: Total budget allocated
  - `utilization_percent`: Usage percentage
  - `status`: "efficient" | "moderate" | "warning" | "critical"
  - `recommendation`: Text guidance on budget adjustment
  - `likely_causes`: Array of detected patterns (heavy packages, loops, etc.)

- **ADDED**: Fuel utilization thresholds:
  - <50%: ✅ Efficient (no action)
  - 50-75%: ℹ️ Moderate (informational)
  - 75-90%: ⚠️ Warning (suggest increase for similar tasks)
  - 90-100%: 🚨 Critical (must increase for future runs)

## Impact

**Affected Capabilities**:
- `mcp-tool-descriptions` (NEW): Comprehensive tool metadata for LLM decision-making
- `error-guidance` (NEW): Structured error analysis and actionable solutions
- `fuel-budget-analysis` (NEW): Proactive resource monitoring and recommendations

**Affected Code**:
- `mcp_server/server.py`: Enhanced tool descriptions (execute_code, create_session, list_runtimes, list_available_packages)
- `sandbox/core/models.py`: Add `error_guidance` and `fuel_analysis` to `SandboxResult.metadata` field (preserves backward compatibility)
- `sandbox/host.py`: Error classification and fuel analysis logic
- `sandbox/runtimes/python/sandbox.py`: Populate error guidance in result
- `sandbox/runtimes/javascript/sandbox.py`: Populate error guidance in result
- `docs/MCP_INTEGRATION.md`: Document new structured_content fields
- `docs/PYTHON_CAPABILITIES.md`: Add fuel budget reference table
- `docs/JAVASCRIPT_CAPABILITIES.md`: Add QuickJS API pattern guide

**Breaking Changes**:
- ❌ None - all changes are additive
- New fields in `SandboxResult.metadata` are optional
- Existing tool calls work unchanged
- Enhanced descriptions don't alter API contracts

**Migration Path**:
- Existing clients continue to work without changes
- Clients can optionally consume new `structured_content.error_guidance` and `fuel_analysis` fields
- Enhanced tool descriptions improve LLM decision-making automatically (no code changes needed)

**Success Metrics**:
- LLM tool selection accuracy >95% (measure via A/B testing)
- Error resolution on first attempt >80% (track retry rates)
- Fuel exhaustion errors <5% of total executions
- Session creation appropriateness >90% (manual review sample)
