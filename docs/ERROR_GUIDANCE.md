# Error Guidance Catalog

Comprehensive reference for all error types detected by the LLM WASM Sandbox and their actionable solutions.

## Overview

The sandbox automatically analyzes execution failures and provides structured error guidance in `SandboxResult.metadata['error_guidance']`. This document catalogs all error types, their causes, and recommended solutions.

**Error Guidance Structure:**
```python
{
    "error_type": str,           # Error classification
    "actionable_guidance": list,  # Step-by-step solutions
    "related_docs": list,         # Documentation references
    "code_examples": list         # Optional corrected code snippets
}
```

## Error Classification

### 1. OutOfFuel

**Trigger:** WASM execution exceeds fuel budget (instruction count limit).

**Common Causes:**
- First-time import of heavy packages (openpyxl, jinja2, PyPDF2)
- Complex algorithms or tight loops
- Large dataset processing
- Recursive operations without base case

**Error Guidance Provided:**
```python
{
    "error_type": "OutOfFuel",
    "actionable_guidance": [
        "Code execution exceeded fuel budget (X billion instructions)",
        "Likely cause: Heavy package imports or complex computation",
        "Solution 1: Simplify code or break into smaller chunks",
        "Solution 2: Create session with higher fuel budget",
        "Example: create_session(fuel_budget=20_000_000_000, language='python')"
    ],
    "related_docs": [
        "docs/PYTHON_CAPABILITIES.md#fuel-requirements",
        "docs/FUEL_BUDGETING.md"
    ]
}
```

**Quick Fixes:**
```python
# ❌ BAD: Using default 10B budget for heavy packages
from sandbox import create_sandbox, RuntimeType
sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
result = sandbox.execute("import openpyxl")  # Will fail with OutOfFuel

# ✅ GOOD: Pre-allocate sufficient fuel
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy
policy = ExecutionPolicy(fuel_budget=20_000_000_000)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
result = sandbox.execute("import openpyxl")  # Success
```

**Package-Specific Fuel Requirements:**
| Package | First Import | Cached Import | Notes |
|---------|-------------|---------------|-------|
| openpyxl | 5-7B | <100M | Excel file handling |
| PyPDF2 | 5-6B | <100M | PDF processing |
| jinja2 | 5-10B | <100M | Template rendering |
| tabulate | 2-3B | <50M | Table formatting |
| markdown | 2-3B | <50M | Markdown parsing |

**Prevention:**
- Use `fuel_analysis` metadata to monitor utilization before hitting limits
- Create persistent sessions for heavy packages (imports are cached)
- Profile code complexity before execution

---

### 2. PathRestriction

**Trigger:** Code attempts to access files outside `/app` directory.

**Common Causes:**
- Using absolute paths like `/etc/passwd`, `/home/user/file.txt`
- Relative paths that traverse outside workspace (`../../../etc/passwd`)
- Missing `/app` prefix on absolute paths
- Environment variables pointing to host paths

**Error Guidance Provided:**
```python
{
    "error_type": "PathRestriction",
    "actionable_guidance": [
        "Security violation: Cannot access 'PATH' outside /app directory",
        "All file operations restricted to sandbox workspace (/app)",
        "Use absolute paths with /app prefix: '/app/data.txt'",
        "Or use relative paths (auto-prefixed): 'data.txt' → '/app/data.txt'"
    ],
    "related_docs": [
        "WASM_SANDBOX.md#filesystem-isolation",
        "docs/MCP_INTEGRATION.md#file-operations"
    ]
}
```

**Quick Fixes:**
```python
# ❌ BAD: Absolute paths without /app prefix
open("/data/file.txt")           # FileNotFoundError
open("../../../etc/passwd")      # Security violation

# ✅ GOOD: Use /app prefix for absolute paths
open("/app/data/file.txt")

# ✅ GOOD: Use relative paths (auto-prefixed in many contexts)
open("data/file.txt")            # Becomes /app/data/file.txt
```

**JavaScript Example:**
```javascript
// ❌ BAD: Missing /app prefix
const data = std.loadFile("config.json")  // FileNotFoundError

// ✅ GOOD: Explicit /app path
const data = std.loadFile("/app/config.json")

// ✅ GOOD: Use helper functions (auto-prefix)
const data = readJson("config.json")  // Helper adds /app prefix
```

**Prevention:**
- Always use `/app/` prefix for absolute paths
- Test file operations with non-existent files first to catch path issues
- Review environment variables - they may contain host paths

---

### 3. QuickJSTupleDestructuring

**Trigger:** JavaScript code tries to use QuickJS function return values without proper destructuring.

**Common Causes:**
- Treating QuickJS std/os function results as direct values
- Forgetting QuickJS functions return `[result, error]` tuples
- Not checking error values from tuple returns

**Error Guidance Provided:**
```python
{
    "error_type": "QuickJSTupleDestructuring",
    "actionable_guidance": [
        "TypeError: QuickJS std/os functions return [result, error] tuples",
        "Must use destructuring: const [result, err] = functionCall()",
        "Always check err before using result",
        "See docs/JAVASCRIPT_CAPABILITIES.md for API patterns"
    ],
    "related_docs": [
        "docs/JAVASCRIPT_CAPABILITIES.md#quickjs-api-patterns"
    ],
    "code_examples": [
        "// ❌ BAD: Direct assignment",
        "const files = os.readdir('/app')",
        "",
        "// ✅ GOOD: Tuple destructuring",
        "const [files, err] = os.readdir('/app')",
        "if (err) throw new Error(err)",
        "console.log(files)"
    ]
}
```

**Quick Fixes:**
```javascript
// ❌ BAD: Assuming direct return value
const content = std.loadFile("/app/data.txt")
console.log(content)  // TypeError: value is not iterable

// ✅ GOOD: Proper tuple destructuring
const [content, err] = std.loadFile("/app/data.txt")
if (err !== null) {
    throw new Error(`Failed to load file: ${err}`)
}
console.log(content)

// ✅ BETTER: Use helper functions (no tuples)
const content = readText("/app/data.txt")  // Throws on error
console.log(content)
```

**Common QuickJS Tuple Functions:**
| Function | Signature | Notes |
|----------|-----------|-------|
| `os.readdir()` | `(path) -> [[files], err]` | Returns array of filenames |
| `std.loadFile()` | `(path) -> [content, err]` | Returns file content as string |
| `os.stat()` | `(path) -> [stats, err]` | Returns file metadata |
| `std.open()` | `(path, mode) -> [file, err]` | Returns file handle |

**Prevention:**
- Use helper functions (`readJson`, `writeJson`, `fileExists`) - they handle tuples internally
- Always destructure QuickJS std/os function calls
- Enable TypeScript for type checking (if using tsc)

---

### 4. MissingVendoredPackage

**Trigger:** Python code imports a vendored package without setting sys.path.

**Common Causes:**
- Importing openpyxl, PyPDF2, tabulate without sys.path setup
- Forgetting to add `/data/site-packages` to import path
- Typo in package name

**Error Guidance Provided:**
```python
{
    "error_type": "MissingVendoredPackage",
    "actionable_guidance": [
        "ModuleNotFoundError: Package 'PKG' is vendored but not in sys.path",
        "Add to code: import sys; sys.path.insert(0, '/data/site-packages')",
        "Then import normally: import PKG",
        "Note: First import requires 5-7B fuel for heavy packages"
    ],
    "related_docs": [
        "docs/PYTHON_CAPABILITIES.md#vendored-packages",
        "docs/PYTHON_CAPABILITIES.md#fuel-requirements"
    ],
    "code_examples": [
        "# ❌ BAD: Direct import without sys.path",
        "import openpyxl  # ModuleNotFoundError",
        "",
        "# ✅ GOOD: Set sys.path first",
        "import sys",
        "sys.path.insert(0, '/data/site-packages')",
        "import openpyxl  # Success (requires 5-7B fuel)"
    ]
}
```

**Quick Fixes:**
```python
# ❌ BAD: Missing sys.path setup
import openpyxl  # ModuleNotFoundError: No module named 'openpyxl'

# ✅ GOOD: Add sys.path setup
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl

# ✅ BETTER: Check if already in path
import sys
if '/data/site-packages' not in sys.path:
    sys.path.insert(0, '/data/site-packages')
import openpyxl
```

**Available Vendored Packages:**
- Document processing: openpyxl, XlsxWriter, PyPDF2, odfpy, mammoth
- Text/data: tabulate, jinja2, markdown, python-dateutil
- Utilities: certifi, charset-normalizer, idna, attrs, tomli

**Check Package Availability:**
```python
# List all vendored packages via MCP tool
list_available_packages()

# Or programmatically
import sys
sys.path.insert(0, '/data/site-packages')
import pkg_resources
print([pkg.key for pkg in pkg_resources.working_set])
```

**Prevention:**
- Always set sys.path at the start of code
- Use `list_available_packages` tool to verify package availability
- Consider fuel budget when importing heavy packages

---

### 5. MemoryExhausted

**Trigger:** WASM linear memory exceeds configured limit.

**Common Causes:**
- Large in-memory data structures (arrays, dictionaries)
- Loading entire large files into memory
- Memory leaks in loops
- Image or binary data processing

**Error Guidance Provided:**
```python
{
    "error_type": "MemoryExhausted",
    "actionable_guidance": [
        "Execution exceeded memory limit (X MB)",
        "Likely cause: Large data structures or file loading",
        "Solution 1: Process data in chunks/streams",
        "Solution 2: Increase memory limit via ExecutionPolicy",
        "Example: ExecutionPolicy(memory_bytes=256*1024*1024)  # 256 MB"
    ],
    "related_docs": [
        "WASM_SANDBOX.md#memory-limits"
    ]
}
```

**Quick Fixes:**
```python
# ❌ BAD: Loading entire file into memory
data = open('/app/large_file.txt').read()  # May exceed memory limit

# ✅ GOOD: Stream processing
with open('/app/large_file.txt') as f:
    for line in f:  # Process line by line
        process(line)

# ✅ GOOD: Increase memory limit for legitimate needs
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy
policy = ExecutionPolicy(memory_bytes=256*1024*1024)  # 256 MB
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
```

**Memory Budget Guidelines:**
| Use Case | Recommended Memory | Notes |
|----------|-------------------|-------|
| Default | 128 MB | Most code |
| Excel processing | 256 MB | Large spreadsheets |
| PDF manipulation | 256 MB | Multi-page PDFs |
| Image processing | 512 MB | High-resolution images |

**Prevention:**
- Use streaming APIs for large files
- Clear variables after use (`del large_var`)
- Monitor memory usage in `fuel_analysis` metadata

---

### 6. InvalidSessionState

**Trigger:** Session state persistence fails due to non-serializable objects.

**Common Causes:**
- Storing class instances in auto-persisted globals
- File handles, sockets, or other resources
- Lambda functions or closures
- Circular references

**Error Guidance Provided:**
```python
{
    "error_type": "InvalidSessionState",
    "actionable_guidance": [
        "Session state persistence failed: Cannot serialize TYPE",
        "auto_persist_globals only supports JSON-serializable types",
        "Supported: int, float, str, list, dict, bool, None",
        "Not supported: class instances, file handles, lambdas",
        "Convert to dict or disable auto_persist_globals"
    ],
    "related_docs": [
        "docs/JAVASCRIPT_CAPABILITIES.md#state-persistence",
        "docs/MCP_INTEGRATION.md#session-management"
    ]
}
```

**Quick Fixes:**
```python
# ❌ BAD: Non-serializable objects
class Counter:
    def __init__(self):
        self.count = 0

counter = Counter()  # Cannot persist - will error

# ✅ GOOD: Use JSON-serializable structures
counter = {"count": 0}  # Simple dict - persists fine

# ✅ GOOD: Convert objects to dicts
class Counter:
    def to_dict(self):
        return {"count": self.count}

counter = Counter().to_dict()  # Serializes successfully
```

**JavaScript Example:**
```javascript
// ❌ BAD: Complex objects
_state.fileHandle = std.open("/app/data.txt", "r")  // Cannot serialize

// ✅ GOOD: Primitives and simple structures
_state.lastFilePath = "/app/data.txt"
_state.processedCount = 42
_state.results = [1, 2, 3]
```

**Prevention:**
- Use simple data structures (dicts, arrays, primitives)
- Serialize complex objects manually
- Consider disabling auto_persist if storing resources

---

## Error Detection Mechanism

The sandbox uses multi-layered error detection:

### 1. Trap-Based Detection
```python
# In sandbox/host.py
def _classify_error(trap_reason: str, trap_message: str) -> dict | None:
    if trap_reason == "out of fuel":
        return ERROR_TEMPLATES["OutOfFuel"]
    # ...
```

### 2. Stderr Pattern Matching
```python
# In sandbox/host.py
def _analyze_stderr(stderr: str, language: str) -> dict | None:
    if "FileNotFoundError" in stderr and "/app" not in stderr:
        return ERROR_TEMPLATES["PathRestriction"]
    # ...
```

### 3. Runtime-Specific Analysis
```python
# In sandbox/runtimes/javascript/sandbox.py
if "TypeError: value is not iterable" in stderr:
    return ERROR_TEMPLATES["QuickJSTupleDestructuring"]
```

## Using Error Guidance

### Programmatic Access
```python
from sandbox import create_sandbox, RuntimeType

sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
result = sandbox.execute("while True: pass")  # OutOfFuel

if not result.success and 'error_guidance' in result.metadata:
    guidance = result.metadata['error_guidance']
    print(f"Error Type: {guidance['error_type']}")
    print("Solutions:")
    for step in guidance['actionable_guidance']:
        print(f"  - {step}")
```

### MCP Client Access
```json
{
  "tool": "execute_code",
  "result": {
    "success": false,
    "stderr": "...",
    "structured_content": {
      "error_guidance": {
        "error_type": "OutOfFuel",
        "actionable_guidance": [...],
        "related_docs": [...],
        "code_examples": [...]
      }
    }
  }
}
```

## Troubleshooting Flowchart

```
Execution Failed?
│
├─ Trap: "out of fuel"
│  └─> OutOfFuel error guidance
│     ├─ Check fuel_analysis for utilization
│     ├─ Identify heavy packages in code
│     └─ Increase fuel_budget or simplify code
│
├─ Stderr: "FileNotFoundError"
│  └─> Check path format
│     ├─ Missing /app prefix? → PathRestriction
│     └─ File doesn't exist? → Regular FileNotFoundError
│
├─ Stderr: "TypeError: value is not iterable" (JS)
│  └─> QuickJSTupleDestructuring
│     └─ Use [result, err] = functionCall() pattern
│
├─ Stderr: "ModuleNotFoundError"
│  └─> Check if package is vendored
│     ├─ Yes → MissingVendoredPackage
│     │  └─ Add sys.path.insert(0, '/data/site-packages')
│     └─ No → Package not available (use alternative)
│
└─ Trap: memory limit exceeded
   └─> MemoryExhausted
      ├─ Process data in chunks
      └─ Increase memory_bytes in ExecutionPolicy
```

## Adding New Error Types

To add new error classifications:

1. **Define template** in `sandbox/core/error_templates.py`:
   ```python
   ERROR_TEMPLATES["NewErrorType"] = {
       "error_type": "NewErrorType",
       "actionable_guidance": [...],
       "related_docs": [...],
       "code_examples": [...]
   }
   ```

2. **Add detection logic** in `sandbox/host.py` or runtime-specific sandbox:
   ```python
   def _classify_error(trap_reason: str, trap_message: str) -> dict | None:
       if "pattern" in trap_message:
           return ERROR_TEMPLATES["NewErrorType"]
   ```

3. **Document here** in this catalog

4. **Add test case** in `tests/test_error_guidance.py`:
   ```python
   def test_new_error_type():
       result = sandbox.execute(code_that_triggers_error)
       assert "error_guidance" in result.metadata
       assert result.metadata["error_guidance"]["error_type"] == "NewErrorType"
   ```

## Related Documentation

- [MCP Integration Guide](MCP_INTEGRATION.md) - Error guidance in MCP responses
- [Python Capabilities](PYTHON_CAPABILITIES.md) - Package fuel requirements
- [JavaScript Capabilities](JAVASCRIPT_CAPABILITIES.md) - QuickJS API patterns
- [Fuel Budgeting Guide](FUEL_BUDGETING.md) - Planning fuel budgets
- [WASM Sandbox Architecture](../WASM_SANDBOX.md) - Security model and isolation

## Metrics & Monitoring

Track error resolution effectiveness:

```python
# MCP server automatically logs errors
# Check metrics via get_metrics tool:
{
    "tool_executions": {
        "error_count": 42,
        "errors_by_tool": {
            "execute_code": 38
        }
    }
}
```

**Success Metrics:**
- Error resolution on first retry: Target >80%
- Error guidance present: Target >80% of failures
- Pattern classification coverage: Target >80% of errors

## FAQ

**Q: Why doesn't every error have guidance?**  
A: Some errors (syntax errors, logical bugs) are user-specific and can't be generically classified. We focus on sandbox-specific errors that have actionable solutions.

**Q: Can I customize error templates?**  
A: Not directly, but you can wrap the sandbox and transform error_guidance in your application layer.

**Q: Do errors with guidance still fail?**  
A: Yes - guidance helps fix the code, but the original execution still failed. Use the guidance to modify and re-run.

**Q: How accurate is pattern detection?**  
A: ~95%+ for trap-based detection (deterministic). ~80-90% for stderr pattern matching (heuristic).

---

**Last Updated:** November 24, 2025  
**Related Change Proposal:** `openspec/changes/harden-mcp-tool-precision/`
