# Development vs Production: Running the MCP Server

This document clarifies how to run the MCP server in different environments.

## Quick Answer

### Development (from source)
```powershell
# Easiest: Use the convenience script
.\scripts\run-mcp-dev.ps1

# Or directly
uv run python -m mcp_server
```

### Production (installed package)
```powershell
# After: pip install llm-wasm-sandbox
llm-wasm-mcp

# Or
python -m mcp_server
```

## The Issue

The `llm-wasm-mcp` command is registered as a console script in `pyproject.toml`:

```toml
[project.scripts]
llm-wasm-mcp = "mcp_server.__main__:main"
```

This command is only available **after the package is installed** via `pip install`. It won't work in development mode because:
1. The script isn't in your system PATH
2. The console script wrapper isn't created until installation

## Development Workflow

When developing the project, you have three options:

### Option 1: Convenience Script (Recommended)
```powershell
.\scripts\run-mcp-dev.ps1
```

This script:
- Checks uv is installed
- Verifies WASM binaries exist
- Runs `uv run python -m mcp_server`
- Shows helpful error messages

Get help:
```powershell
.\scripts\run-mcp-dev.ps1 -Help
```

### Option 2: Direct Module Execution
```powershell
uv run python -m mcp_server
```

This runs the `mcp_server` package as a module using the uv-managed environment.

### Option 3: Example Scripts
```powershell
# Promiscuous mode (all code allowed)
uv run python examples/llm_wasm_mcp.py

# With security filters
uv run python examples/mcp_stdio_example.py
```

## Claude Desktop Configuration

### Development Setup

Use this configuration when working from source:

```json
{
  "mcpServers": {
    "llm-wasm-sandbox-dev": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\Users\\YourName\\Projects\\llm-wasm-sandbox",
        "run",
        "python",
        "-m",
        "mcp_server"
      ]
    }
  }
}
```

**Important**: 
- Use `--directory` (not `cwd`) for uv to resolve dependencies correctly
- Replace `YourName` with your actual Windows username
- Use forward slashes or escaped backslashes in paths

### Production Setup

After installing via `pip install llm-wasm-sandbox`:

```json
{
  "mcpServers": {
    "llm-wasm-sandbox": {
      "command": "python",
      "args": ["-m", "mcp_server"]
    }
  }
}
```

Or using the console script:

```json
{
  "mcpServers": {
    "llm-wasm-sandbox": {
      "command": "llm-wasm-mcp"
    }
  }
}
```

## Why This Distinction Exists

### Console Scripts
When you define a console script in `pyproject.toml`:

```toml
[project.scripts]
llm-wasm-mcp = "mcp_server.__main__:main"
```

The build process creates a wrapper executable that:
1. Activates the correct Python environment
2. Imports the specified module and function
3. Calls the function as the entry point

This wrapper is only created during **installation** (`pip install`), not during development with `uv run`.

### Development with uv
When using `uv run`, you're executing Python in a managed virtual environment, but no console scripts are installed. You need to use:
- `uv run python -m module_name` to run a module
- `uv run python script.py` to run a script file

### Module vs Script
- `python -m mcp_server` runs the `__main__.py` file inside the `mcp_server` package
- This works whether the package is installed or just in your source tree
- It's the most reliable way to run the MCP server in development

## Troubleshooting

### "llm-wasm-mcp: The term 'llm-wasm-mcp' is not recognized"

**Problem**: You're in development mode and trying to use the installed command.

**Solution**: Use one of the development options instead:
```powershell
.\scripts\run-mcp-dev.ps1
# or
uv run python -m mcp_server
```

### "No module named 'mcp_server.__main__'"

**Problem**: The package isn't properly installed or synced.

**Solution**: 
```powershell
# Ensure dependencies are synced
uv sync

# Then run
uv run python -m mcp_server
```

### "WASM binaries not found"

**Problem**: The WASM runtime binaries aren't downloaded.

**Solution**:
```powershell
.\scripts\fetch_wlr_python.ps1
.\scripts\fetch_quickjs.ps1
```

## Testing Your Setup

### Quick Test
```powershell
# Should show MCP server startup messages
uv run python -m mcp_server
# Press Ctrl+C to stop

# Or use the convenience script
.\scripts\run-mcp-dev.ps1
```

### Verify in Claude Desktop
1. Update your `claude_desktop_config.json` with development settings
2. Restart Claude Desktop
3. Look for "llm-wasm-sandbox-dev" in available tools
4. Test with: "Execute this Python code: print('Hello from WASM!')"

## Summary

| Environment | Command | When to Use |
|-------------|---------|-------------|
| **Development** | `.\scripts\run-mcp-dev.ps1` | Local development (easiest) |
| **Development** | `uv run python -m mcp_server` | Local development (direct) |
| **Development** | `uv run python examples/llm_wasm_mcp.py` | Testing examples |
| **Production** | `llm-wasm-mcp` | After `pip install` |
| **Production** | `python -m mcp_server` | After `pip install` (alternative) |

**Key Takeaway**: The `llm-wasm-mcp` console script only exists after installation. In development, use `uv run python -m mcp_server` or the convenience script.
