# Using JavaScript Runtime via MCP

## Summary

**All JavaScript features documented for the Python API are fully functional via MCP**, including:
- ✅ std module (file I/O with `std.open()`, `std.loadFile()`, etc.)
- ✅ os module (environment variables, file stats, directory operations)
- ✅ requireVendor() function for loading vendored packages
- ✅ Helper functions (readJson, writeJson, readText, listFiles, etc.)
- ✅ _state object for automatic state persistence (requires auto_persist_globals=True)

## Correct Usage Patterns

### 1. One-Shot Code Execution (No Session Persistence)

Use the `execute_code` tool without creating an explicit session:

```javascript
// This works immediately - all features are available
const data = {message: "Hello, MCP!"};
writeJson('/app/output.json', data);

const result = readJson('/app/output.json');
console.log("Data:", JSON.stringify(result));

// std module is available
const f = std.open('/app/example.txt', 'w');
f.puts("Created via MCP!");
f.close();
```

**Features Available:**
- ✅ std, os modules
- ✅ requireVendor()
- ✅ Helper functions (readJson, writeJson, etc.)
- ❌ _state (not available without auto_persist_globals)

### 2. Persistent Session with State Management (Recommended)

**Step 1:** Create a session with `auto_persist_globals=True`:

```json
{
  "tool": "create_session",
  "arguments": {
    "language": "javascript",
    "session_id": "my-session",
    "auto_persist_globals": true
  }
}
```

**Step 2:** Execute code with state persistence:

```javascript
// First execution - initialize state
_state.counter = (_state.counter || 0) + 1;
_state.data = {name: "MCP Test"};
console.log("Counter:", _state.counter);
```

Output: `Counter: 1`

**Step 3:** Execute more code in the same session:

```javascript
// Second execution - state persists!
_state.counter = (_state.counter || 0) + 1;
console.log("Counter:", _state.counter);
console.log("Data:", JSON.stringify(_state.data));
```

Output:
```
Counter: 2
Data: {"name":"MCP Test"}
```

**Features Available:**
- ✅ std, os modules
- ✅ requireVendor()
- ✅ Helper functions
- ✅ _state object with automatic persistence across executions

### 3. Using Vendored Packages

All vendored packages are available via `requireVendor()`:

```javascript
// Load CSV parser
const csv = requireVendor('csv');

const data = csv.parse("name,age\nAlice,30\nBob,25");
console.log("Parsed:", JSON.stringify(data));

// Load JSONPath for complex queries
const jsonpath = requireVendor('json_path');
const users = {
  users: [
    {name: "Alice", age: 30},
    {name: "Bob", age: 25}
  ]
};
const result = jsonpath.query(users, '$.users[?(@.age > 26)]');
console.log("Query result:", JSON.stringify(result));
```

**Available Packages:**
- `csv.js` - CSV parsing/generation
- `json_path.js` - JSONPath queries
- `json_utils.js` - JSON schema validation
- `string_utils.js` - String manipulation utilities
- `sandbox-utils.js` - File I/O helpers (auto-loaded globally)

### 4. File I/O with std Module

Direct access to QuickJS std module:

```javascript
// Write file
const f = std.open('/app/data.txt', 'w');
f.puts("Line 1");
f.puts("Line 2");
f.close();

// Read file
const f2 = std.open('/app/data.txt', 'r');
const content = f2.readAsString();
f2.close();
console.log("Content:", content);

// Or use helpers for JSON/text
writeJson('/app/config.json', {setting: "value"});
const config = readJson('/app/config.json');
```

## Common Pitfalls

### ❌ Pitfall 1: Expecting _state without auto_persist_globals

```javascript
// This will FAIL if session created without auto_persist_globals=true
_state.counter = 1;  // ❌ ReferenceError: _state is not defined
```

**Fix:** Create session with `auto_persist_globals: true`

### ❌ Pitfall 2: Using Node.js-specific APIs

```javascript
// These will FAIL - QuickJS != Node.js
const fs = require('fs');           // ❌ Not available
const http = require('http');       // ❌ Not available
process.exit(0);                    // ❌ Not available
```

**Fix:** Use QuickJS std/os modules and vendored packages instead

### ❌ Pitfall 3: Not reusing sessions for stateful workflows

```javascript
// Calling execute_code without session_id each time
// means each execution gets a NEW session (no state persistence)
```

**Fix:** Create an explicit session and pass `session_id` to all `execute_code` calls

## MCP Tool Parameters

### create_session
```typescript
{
  language: "javascript",
  session_id?: string,            // Optional: provide your own ID
  auto_persist_globals?: boolean  // Default: false. Set true for _state
}
```

### execute_code
```typescript
{
  code: string,                   // JavaScript source code
  language: "javascript",
  timeout?: number,               // Optional: execution timeout in seconds
  session_id?: string            // Optional: reuse existing session
}
```

**Returns:**
```typescript
{
  content: string,                 // Primary output (stdout)
  success: boolean,
  structured_content: {
    stdout: string,
    stderr: string,
    exit_code: number,
    execution_time_ms: number,
    fuel_consumed: number,
    success: boolean
  }
}
```

## Resource Limits

MCP sessions use increased limits for document processing:

- **Fuel Budget:** 10B instructions (supports heavy vendored packages)
- **Memory:** 256 MB
- **Stdout:** 2 MB
- **Stderr:** 1 MB

## Feature Parity Matrix

| Feature | Python API | MCP Server | Notes |
|---------|-----------|-----------|-------|
| std module | ✅ | ✅ | Full file I/O |
| os module | ✅ | ✅ | Env vars, file stats |
| requireVendor() | ✅ | ✅ | Auto-injected |
| Helper functions | ✅ | ✅ | readJson, writeJson, etc. |
| _state persistence | ✅ | ✅ | Requires auto_persist_globals=True |
| Vendored packages | ✅ | ✅ | csv, json_path, string_utils, etc. |
| Session reuse | ✅ | ✅ | Pass session_id |
| Fuel metering | ✅ | ✅ | 10B budget for MCP |
| Memory limits | ✅ | ✅ | 256 MB for MCP |

**Conclusion:** The JavaScript runtime has **100% feature parity** between Python API and MCP Server.

## Testing Verification

Run the following tests to verify all features work:

```python
# From the repository root:
uv run python temp_test_mcp_directly.py
```

Expected output:
- ✅ All globals available (std, os, requireVendor, helpers)
- ✅ File I/O works via std module
- ✅ Helper functions work
- ✅ State persistence works (counter increments across executions)

## Further Reading

- [JAVASCRIPT.md](../JAVASCRIPT.md) - Complete JavaScript runtime documentation
- [JAVASCRIPT_CAPABILITIES.md](./JAVASCRIPT_CAPABILITIES.md) - Detailed capability reference
- [JAVASCRIPT_STATE_PERSISTENCE.md](./JAVASCRIPT_STATE_PERSISTENCE.md) - State management guide
- [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) - General MCP integration documentation
