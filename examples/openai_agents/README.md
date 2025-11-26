# OpenAI Agents SDK Integration with LLM WASM Sandbox

Production-ready examples demonstrating secure code execution using [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) with the llm-wasm-sandbox.

## Features

- **Function Calling Tools**: Execute Python and JavaScript in isolated WASM sandboxes
- **Stateful Sessions**: Multi-turn conversations with file persistence
- **Error Recovery**: Agents automatically debug and retry failed executions
- **Security Boundaries**: Fuel limits, memory caps, filesystem isolation
- **Rich UI**: Beautiful console output with code highlighting and metrics

## Prerequisites

- Python 3.11+ (Python 3.13+ recommended)
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))
- WASM runtime binaries (instructions below)

## Installation

### 1. Install Dependencies

From the repository root:

```powershell
# Install with OpenAI example dependencies
pip install -e ".[openai-example]"

# OR install manually
pip install llm-wasm-sandbox agents-sdk python-dotenv rich
```

### 2. Download WASM Binaries

The sandbox requires WASM runtime binaries to execute code:

**Windows (PowerShell):**
```powershell
# From repository root
.\scripts\fetch_wlr_python.ps1   # CPython WASM (~50-100 MB)
.\scripts\fetch_quickjs.ps1       # QuickJS WASM (~1.4 MB, optional for JS demos)
```

**Linux/macOS:**
```bash
# From repository root
./scripts/fetch_wlr_python.sh
```

### 3. Configure API Key

Copy the example environment file and add your OpenAI API key:

```powershell
# From examples/openai_agents/ directory
cp .env.example .env
# Edit .env and set: OPENAI_API_KEY=sk-your-api-key-here
```

## Quick Start

### Basic Agent (Function Calling)

Execute Python and JavaScript code via agent function calls:

```powershell
cd examples/openai_agents
python basic_agent.py
```

**What it demonstrates:**
- ✅ Python code execution in WASM sandbox
- ✅ JavaScript code execution (QuickJS)
- ✅ Structured result handling with metrics
- ✅ Security policies (fuel budgets, memory limits)

### Stateful Agent (Multi-Turn Sessions)

Execute code with file persistence across conversation turns:

```powershell
cd examples/openai_agents
python stateful_agent.py
```

**What it demonstrates:**
- ✅ Session-based file persistence (`/app` directory)
- ✅ Multi-turn conversations with state
- ✅ Error recovery (syntax errors, fuel exhaustion)
- ✅ Automatic debugging and retry logic

### Shell Utils Agent (Advanced Features)

Execute data processing and file operations using shell-like utilities:

```powershell
cd examples/openai_agents
python shell_utils_agent.py
```

**What it demonstrates:**
- ✅ Shell-like file operations (find, tree, grep, ls, cat, etc.)
- ✅ Data manipulation (group_by, filter_by, sort_by, unique)
- ✅ Format conversions (CSV ↔ JSON, XML → dict)
- ✅ Text processing (sed, diff, head, tail, wc)
- ✅ Vendored packages (tabulate, python-dateutil, markdown)
- ✅ Complete workflows (log analysis, report generation, data transformation)

### MCP External Files Agent (NEW: MCP Integration)

Connect to the llm-wasm-mcp server via MCP protocol with external file access:

```powershell
cd examples/openai_agents
python mcp_external_files_agent.py
```

**What it demonstrates:**
- ✅ MCPServerStdio connection to llm-wasm-mcp
- ✅ External files mounted read-only at `/external/`
- ✅ Agent reading and processing external data files
- ✅ MCP tool discovery and invocation
- ✅ Read-only protection verification
- ✅ Full MCP protocol integration with OpenAI Agents SDK

## How It Works

### MCP Server Pattern (Recommended for External Files)

Use MCPServerStdio to connect to the llm-wasm-mcp server:

```python
from agents import Agent, ModelSettings, Runner
from agents.mcp import MCPServerStdio

async def main():
    # Start MCP server with external files
    async with MCPServerStdio(
        name="llm-wasm-sandbox",
        params={
            "command": "llm-wasm-mcp",
            "args": [
                "--external-files", "/path/to/data.json", "/path/to/config.yaml",
                "--max-external-file-size-mb", "50",
            ],
        },
    ) as mcp_server:
        # Create agent with MCP server access
        agent = Agent(
            name="Data Analysis Agent",
            instructions=(
                "You can execute code in a secure WASM sandbox.\n"
                "External files are available at /external/ (read-only).\n"
                "Use execute_code tool with language='python' or 'javascript'."
            ),
            model="gpt-4.1",
            mcp_servers=[mcp_server],  # Agent gets MCP tools automatically
        )
        
        result = await Runner.run(agent, input="Analyze /external/data.json")
        print(result.final_output)
```

**Key Points:**
- External files are copied to storage and mounted read-only at `/external/`
- All MCP tools (execute_code, create_session, etc.) are exposed automatically
- Agent can read external data but cannot modify it
- Works with Claude Desktop, Cursor, and other MCP-compatible clients

### Function Tool Pattern

The integration uses OpenAI's function calling to safely execute code:

```python
from agents import Agent, function_tool
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

@function_tool
def run_python_in_wasm(code: str) -> dict:
    """Execute Python code in WASM sandbox."""
    policy = ExecutionPolicy(
        fuel_budget=500_000_000,      # Instruction limit
        memory_bytes=32 * 1024 * 1024, # 32 MB
        stdout_max_bytes=100_000       # Truncate output
    )
    
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
    result = sandbox.execute(code)
    
    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "fuel_consumed": result.fuel_consumed,
        "duration_seconds": result.duration_seconds,
    }

# Define agent with tool
agent = Agent(
    name="WASM Sandbox Agent",
    instructions="Execute code using run_python_in_wasm tool",
    tools=[run_python_in_wasm],
)
```

### Session Management

For stateful multi-turn execution with file persistence:

```python
@function_tool
def run_python_in_wasm_session(
    code: str,
    session_id: str | None = None
) -> dict:
    """Execute code with session persistence."""
    if session_id:
        # Reuse existing session
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            session_id=session_id
        )
    else:
        # Create new session
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        session_id = sandbox.session_id
    
    result = sandbox.execute(code)
    
    return {
        "success": result.success,
        "stdout": result.stdout,
        "session_id": session_id,  # Return for reuse
        # ... other fields
    }
```

**Key Points:**
- Files written to `/app` persist across calls with the same `session_id`
- Agent must reuse `session_id` from previous responses to maintain state
- Each session has isolated workspace (no cross-contamination)

## Security Model

### Multi-Layered Defense

The sandbox provides production-grade security:

| Layer | Mechanism | Protection |
|-------|-----------|------------|
| **WASM Memory** | Bounds checking | No buffer overflows, type safety |
| **Filesystem** | WASI capabilities | Only `/app` accessible, no path traversal |
| **CPU** | Fuel metering | Deterministic instruction limits |
| **Memory** | Linear memory cap | Configurable size limits (default 32 MB) |
| **Output** | Truncation | Prevent DoS via stdout/stderr |
| **Network** | Zero capabilities | No socket access |

### ExecutionPolicy Configuration

Tune security boundaries for your use case:

```python
from sandbox import ExecutionPolicy

# Strict policy for untrusted LLM code
strict_policy = ExecutionPolicy(
    fuel_budget=500_000_000,          # ~500M instructions
    memory_bytes=32 * 1024 * 1024,    # 32 MB
    stdout_max_bytes=100_000,         # 100 KB output
)

# Relaxed policy for trusted operations
relaxed_policy = ExecutionPolicy(
    fuel_budget=5_000_000_000,        # ~5B instructions
    memory_bytes=128 * 1024 * 1024,   # 128 MB
    stdout_max_bytes=1_000_000,       # 1 MB output
)
```

### Production Hardening

For production deployments, combine with OS-level security:

- **Containers**: Run sandbox in Docker/Podman for additional isolation
- **OS Timeouts**: Use `subprocess.run(timeout=...)` to limit wall-clock time
- **Resource Limits**: Apply cgroups (Linux) for CPU/memory caps
- **Monitoring**: Log all executions with code hashes for audit trails
- **Rate Limiting**: Throttle agent requests to prevent abuse

## Example Workflows

### Shell-Like File Operations (NEW)

```python
# Agent explores project structure
user: "Show me the directory tree and find all Python files"
agent: [uses tree() and find("*.py") from sandbox_utils]
agent: "Found 5 Python files in /app/src and /app/tests directories"

# Agent analyzes log files
user: "Search for ERROR entries in app.log and count them"
agent: [uses grep(r'ERROR', files) and wc(file)]
agent: "Found 12 ERROR entries. Total log size: 1,234 lines"
```

### Data Processing with Vendored Packages (NEW)

```python
# Agent processes CSV data
user: "Load sales.csv, group by product, and show totals in a table"
agent: [uses csv_to_json(), group_by(), and tabulate package]
agent: [displays formatted table with product sales]

# Agent generates reports
user: "Create a Markdown report and convert to HTML"
agent: [uses markdown package to render HTML from Markdown]
agent: [saves report.md and report.html to /app]
```

### Data Processing Pipeline

```python
# Turn 1: Agent creates dataset
user: "Create a CSV file with sample sales data"
agent: [writes data.csv to /app via run_python_in_wasm_session]

# Turn 2: Agent analyzes data
user: "Calculate total sales and average transaction value"
agent: [reads /app/data.csv, computes stats, returns results]

# Turn 3: Agent generates report
user: "Create a summary report as JSON"
agent: [reads data, writes /app/report.json]
```

### Error Recovery Flow

```python
# Agent writes buggy code
agent: [executes code with syntax error]
sandbox: {success: false, stderr: "SyntaxError: invalid syntax"}

# Agent debugs and fixes
agent: [analyzes stderr, rewrites code]
sandbox: {success: true, stdout: "42"}

# Agent returns corrected result
agent: "The calculation completed successfully: 42"
```

## Troubleshooting

### Common Issues

#### `OPENAI_API_KEY not found`

**Solution:** Copy `.env.example` to `.env` and add your API key:

```powershell
cp .env.example .env
# Edit .env: OPENAI_API_KEY=sk-...
```

#### `python.wasm not found`

**Solution:** Download WASM binaries from repository root:

```powershell
.\scripts\fetch_wlr_python.ps1
```

Verify: `bin/python.wasm` should be ~50-100 MB

#### `OutOfFuel` errors

**Cause:** Code exceeded instruction budget

**Solutions:**
- Increase `fuel_budget` in ExecutionPolicy
- Simplify algorithm (agent can do this automatically)
- Use more efficient data structures

#### `Import "agents" could not be resolved`

**Cause:** agents-sdk package not installed

**Solution:**
```powershell
pip install agents-sdk
# OR from repo root:
pip install -e ".[openai-example]"
```

#### Agent doesn't reuse session_id

**Cause:** Agent instructions unclear about session persistence

**Solution:** Update agent instructions to emphasize:
```python
instructions=(
    "IMPORTANT: When you receive a session_id in a tool response, "
    "you MUST reuse it in subsequent calls to maintain state."
)
```

### Getting Help

- 🐞 **Report bugs**: [GitHub Issues](https://github.com/ThomasRohde/llm-wasm-sandbox/issues)
- 📖 **Main documentation**: [README.md](../../README.md)
- 💡 **More examples**: [demo.py](../../demo.py), [demo_session_workflow.py](../../demo_session_workflow.py)

## Advanced Usage

### Custom Storage Backends

Implement `StorageAdapter` for cloud storage (S3, Azure Blob):

```python
from sandbox import StorageAdapter, create_sandbox
from pathlib import Path

class S3StorageAdapter(StorageAdapter):
    def read(self, path: Path) -> bytes:
        # Implement S3 read
        pass
    
    def write(self, path: Path, content: bytes) -> None:
        # Implement S3 write
        pass
    
    # ... implement other methods

storage = S3StorageAdapter()
sandbox = create_sandbox(
    runtime=RuntimeType.PYTHON,
    storage_adapter=storage
)
```

### Session Pruning

Clean up old sessions automatically:

```python
from sandbox import prune_sessions

# Delete sessions older than 7 days
result = prune_sessions(max_age_days=7)
print(f"Deleted {result.deleted_count} sessions")
print(f"Freed {result.bytes_freed} bytes")
```

### Vendored Packages

Use pure-Python packages in the sandbox:

```powershell
# From repo root
uv run python scripts/manage_vendor.py install requests
uv run python scripts/manage_vendor.py copy
```

Then in sandboxed code:
```python
import sys
sys.path.insert(0, '/app/site-packages')
import requests  # Now available
```

## API Reference

### Function Tools

#### `run_python_in_wasm(code: str) -> dict`

Execute Python code in isolated WASM sandbox.

**Returns:**
- `success` (bool): Execution succeeded
- `stdout` (str): Standard output
- `stderr` (str): Standard error
- `fuel_consumed` (int): Instructions executed
- `duration_seconds` (float): Wall-clock time
- `mem_pages` (int): Memory pages used

#### `run_javascript_in_wasm(code: str) -> dict`

Execute JavaScript code in QuickJS WASM sandbox.

**Returns:** Same structure as `run_python_in_wasm`

#### `run_python_in_wasm_session(code: str, session_id: str | None) -> dict`

Execute Python code with session persistence.

**Returns:** Same as `run_python_in_wasm` plus:
- `session_id` (str): Session ID for reuse

### ExecutionPolicy Fields

```python
ExecutionPolicy(
    fuel_budget=2_000_000_000,      # Instruction limit (default: 2B)
    memory_bytes=128_000_000,       # Memory cap (default: 128 MB)
    stdout_max_bytes=2_000_000,     # Stdout limit (default: 2 MB)
    stderr_max_bytes=1_000_000,     # Stderr limit (default: 1 MB)
    timeout_seconds=None,           # Wall-clock timeout (optional)
    env={},                         # Environment variables (default: {})
    preserve_logs=False,            # Keep log files (default: False)
)
```

## License

MIT License - see [LICENSE](../../LICENSE)

## References

- [OpenAI Agents SDK Documentation](https://openai.github.io/openai-agents-python/)
- [LLM WASM Sandbox](https://github.com/ThomasRohde/llm-wasm-sandbox)
- [Wasmtime Security](https://docs.wasmtime.dev/security.html)
- [WASI Capabilities](https://github.com/bytecodealliance/wasmtime/blob/main/docs/WASI-capabilities.md)

---

<div align="center">

**Built for secure LLM code execution with OpenAI Agents**

[Report Bug](https://github.com/ThomasRohde/llm-wasm-sandbox/issues) •
[Main Documentation](../../README.md) •
[Examples](../../demo.py)

</div>
