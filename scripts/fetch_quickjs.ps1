# Fetch QuickJS WASM Binary for JavaScript Runtime
# This script downloads the QuickJS-NG WASI binary (standalone JavaScript runtime)
# from the QuickJS-NG project releases.
#
# QuickJS-NG is the "next generation" fork of QuickJS that provides official WASI builds
# with a standard _start entry point, enabling direct execution under Wasmtime/Wasmer.
#
# Usage:
#   .\scripts\fetch_quickjs.ps1
#
# The binary will be downloaded to: bin/quickjs.wasm
# Size: ~1.36 MB (standalone WASI module)
# Source: https://github.com/quickjs-ng/quickjs

param(
    [string]$Version = "v0.11.0",
    [string]$BinDir = "bin",
    [string]$OutputFile = "quickjs.wasm"
)

$ErrorActionPreference = "Stop"

# Configuration
$wasmAssetName = "qjs-wasi.wasm"
$downloadUrl = "https://github.com/quickjs-ng/quickjs/releases/download/$Version/$wasmAssetName"
$binPath = Join-Path $PSScriptRoot ".." $BinDir
$downloadPath = Join-Path $binPath $wasmAssetName
$outputPath = Join-Path $binPath $OutputFile

Write-Host "==> Fetching QuickJS WASM Binary (QuickJS-NG $Version)" -ForegroundColor Cyan
Write-Host ""

# Create bin directory if it doesn't exist
if (-not (Test-Path $binPath)) {
    Write-Host "Creating directory: $binPath" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $binPath -Force | Out-Null
}

# Check if binary already exists
if (Test-Path $outputPath) {
    $response = Read-Host "Binary already exists at $outputPath. Overwrite? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Host "Aborted." -ForegroundColor Yellow
        exit 0
    }
    Remove-Item $outputPath -Force
}

# Download the WASM binary
Write-Host "Downloading from: $downloadUrl" -ForegroundColor Green
try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $downloadPath -ErrorAction Stop
    Write-Host "Downloaded to: $downloadPath" -ForegroundColor Green
}
catch {
    Write-Host "Error: Failed to download QuickJS binary" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

# Rename to standard name if different
if ($downloadPath -ne $outputPath) {
    Write-Host "Renaming to: $outputPath" -ForegroundColor Green
    Move-Item -Path $downloadPath -Destination $outputPath -Force
}

# Verify the WASM binary
if (Test-Path $outputPath) {
    $fileSize = (Get-Item $outputPath).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    Write-Host ""
    Write-Host "==> Success!" -ForegroundColor Green
    Write-Host "QuickJS WASM binary downloaded to: $outputPath" -ForegroundColor Green
    Write-Host "File size: $fileSizeMB MB" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Run tests: uv run python tests/test_javascript_sandbox.py" -ForegroundColor White
    Write-Host "  2. Try demo: uv run python demo_javascript.py" -ForegroundColor White
}
else {
    Write-Host "Error: Binary file not found after extraction" -ForegroundColor Red
    exit 1
}
