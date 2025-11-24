# Spec: MCP Tool Descriptions

## ADDED Requirements

### Requirement: Comprehensive Tool Metadata

MCP tools SHALL provide comprehensive metadata including usage patterns, runtime-specific capabilities, common pitfalls, and decision guidance to enable LLMs to make informed tool selection decisions.

#### Scenario: execute_code Tool Enhancement

- **WHEN** an LLM needs to execute code via MCP
- **THEN** the `execute_code` tool description SHALL include:
  - When to use vs. when not to use (e.g., "Best for: data processing, file manipulation. Limitations: No network access")
  - Runtime-specific capabilities (JavaScript: QuickJS std/os modules, Python: 30+ vendored packages)
  - Common pitfalls with solutions (QuickJS tuple returns, /app path requirements, fuel limits)
  - Usage pattern examples (one-off calculation, file processing, stateful workflows)
  - Parameter descriptions explaining impact (e.g., `session_id`: "Omit to use default workspace. Create dedicated session for multi-turn workflows")

#### Scenario: create_session Tool Enhancement

- **WHEN** an LLM needs to create a session
- **THEN** the `create_session` tool description SHALL include:
  - Decision tree: "Use default session when: one-off execution, no state needed. Create new session when: multi-turn workflows, heavy packages requiring >10B fuel"
  - Auto-persist guidelines: when to enable, what data structures are supported, performance implications
  - Session lifecycle patterns (creation, reuse, cleanup)
  - Custom configuration guidance (fuel_budget for heavy packages, memory_bytes for large data)

#### Scenario: list_runtimes Tool Enhancement

- **WHEN** an LLM queries available runtimes
- **THEN** the `list_runtimes` response SHALL include:
  - Runtime version and language feature support (e.g., "ES2020+" for JavaScript)
  - Vendored package counts and notable package names
  - API pattern notes (e.g., "QuickJS functions return [result, error] tuples")
  - Available helper functions (JavaScript: readJson, writeJson; Python: automatic sys.path config)

#### Scenario: list_available_packages Tool Enhancement

- **WHEN** an LLM queries available packages
- **THEN** the response SHALL include for each package:
  - Fuel requirement estimate (e.g., "openpyxl: 5-7B instructions first import, <100M cached")
  - Import pattern example (e.g., "import openpyxl" for Python, "requireVendor('csv-simple')" for JavaScript)
  - Common use cases (e.g., "openpyxl: Excel file creation, spreadsheet data extraction")
  - Performance characteristics (first import vs. subsequent cached imports)

### Requirement: Usage Pattern Documentation

MCP tool descriptions SHALL include concrete usage pattern examples for common scenarios to demonstrate correct tool invocation patterns.

#### Scenario: One-Off Calculation Pattern

- **WHEN** tool description includes usage patterns
- **THEN** it SHALL provide example for one-off calculations:
  ```json
  {
    "code": "print(sum(range(1, 101)))",
    "language": "python"
  }
  ```

#### Scenario: Stateful Session Pattern

- **WHEN** tool description includes usage patterns
- **THEN** it SHALL provide example for stateful workflows:
  - Step 1: Create session with `auto_persist_globals=True`
  - Step 2: Execute code referencing persistent state (e.g., Python: `counter = globals().get('counter', 0) + 1`)
  - Step 3: Subsequent executions access persisted state

#### Scenario: File Processing Pattern

- **WHEN** tool description includes usage patterns
- **THEN** it SHALL provide examples demonstrating:
  - Correct file path usage (absolute paths with `/app` prefix)
  - JavaScript helper functions (readJson, writeJson)
  - Python file I/O with context managers

### Requirement: Common Pitfall Documentation

MCP tool descriptions SHALL document common errors with their causes and solutions to reduce error rates.

#### Scenario: QuickJS Tuple Return Pattern

- **WHEN** tool description documents JavaScript pitfalls
- **THEN** it SHALL explain:
  - Error: `TypeError: value is not iterable`
  - Cause: "QuickJS functions return [result, error] tuples"
  - Solution: "Use destructuring: `const [files, err] = os.readdir('/app')`"

#### Scenario: Path Restriction Pitfall

- **WHEN** tool description documents file I/O pitfalls
- **THEN** it SHALL explain:
  - Error: `FileNotFoundError: data.txt`
  - Cause: "File path missing /app prefix"
  - Solution: "Use absolute path: '/app/data.txt'"

#### Scenario: Fuel Exhaustion Pitfall

- **WHEN** tool description documents execution pitfalls
- **THEN** it SHALL explain:
  - Error: "OutOfFuel"
  - Cause: "Code exceeded 10B instruction budget (heavy packages or complex processing)"
  - Solution: "Create session with higher fuel: create_session(fuel_budget=20_000_000_000)"

### Requirement: Decision Tree Guidance

Tool descriptions SHALL provide decision trees for common choices (e.g., when to create sessions, when to enable auto-persist) to guide LLM decision-making.

#### Scenario: Session Creation Decision

- **WHEN** LLM evaluates whether to create a session
- **THEN** tool description SHALL provide criteria:
  - Create new session when: multi-turn conversation, processing related files, heavy packages, isolated testing
  - Use default session when: one-off execution, independent calculations, quick prototyping, default resources sufficient

#### Scenario: Auto-Persist Decision

- **WHEN** LLM evaluates whether to enable auto-persist
- **THEN** tool description SHALL provide criteria:
  - Enable when: LLM agent workflows, incremental processing, state machines
  - Don't enable when: one-off executions, fresh environment needed, large objects, complex class instances
