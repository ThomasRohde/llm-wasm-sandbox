#!/usr/bin/env pwsh
# Development helper script to run the MCP server
# This is equivalent to: uv run python -m mcp_server

param(
    [Parameter()]
    [switch]$Help
)

if ($Help) {
    Write-Host @"
run-mcp-dev.ps1 - Run MCP server in development mode

USAGE:
    .\scripts\run-mcp-dev.ps1

DESCRIPTION:
    Starts the MCP server using the local development environment.
    This script is a convenience wrapper for: uv run python -m mcp_server

REQUIREMENTS:
    - uv must be installed
    - WASM binaries must be present in bin/ directory
      Run fetch scripts if needed:
        .\scripts\fetch_wlr_python.ps1
        .\scripts\fetch_quickjs.ps1

NOTES:
    - In development, use this script or 'uv run python -m mcp_server'
    - After 'pip install llm-wasm-sandbox', use 'llm-wasm-mcp' command
    - Press Ctrl+C to stop the server

EXAMPLES:
    # Run MCP server in development
    .\scripts\run-mcp-dev.ps1

    # Use in Claude Desktop config (Windows):
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

"@
    exit 0
}

$ErrorActionPreference = "Stop"

# Check if uv is available
try {
    $null = Get-Command uv -ErrorAction Stop
} catch {
    Write-Host "ERROR: uv is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Install uv: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
    exit 1
}

# Check if WASM binaries exist
$wasmBinaries = @("bin/python.wasm", "bin/quickjs.wasm")
$missingBinaries = @()

foreach ($binary in $wasmBinaries) {
    if (-not (Test-Path $binary)) {
        $missingBinaries += $binary
    }
}

if ($missingBinaries.Count -gt 0) {
    Write-Host "WARNING: Missing WASM binaries:" -ForegroundColor Yellow
    foreach ($binary in $missingBinaries) {
        Write-Host "  - $binary" -ForegroundColor Yellow
    }
    Write-Host "`nRun fetch scripts first:" -ForegroundColor Cyan
    Write-Host "  .\scripts\fetch_wlr_python.ps1" -ForegroundColor Cyan
    Write-Host "  .\scripts\fetch_quickjs.ps1" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "Starting MCP server in development mode..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Cyan
Write-Host ""

# Run the MCP server
uv run python -m mcp_server
