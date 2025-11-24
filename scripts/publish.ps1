#!/usr/bin/env pwsh
# Publish script for llm-wasm-sandbox using uv package manager
# Requires UV_PUBLISH_TOKEN environment variable to be set

param(
    [Parameter(Position=0)]
    [ValidateSet("testpypi", "pypi")]
    [string]$Target = "pypi",
    
    [Parameter()]
    [switch]$DryRun,
    
    [Parameter()]
    [switch]$SkipBuild,
    
    [Parameter()]
    [switch]$SkipTests,
    
    [Parameter()]
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Fail { Write-Host $args -ForegroundColor Red }

# Banner
Write-Info "`n==================================================================="
Write-Info "  llm-wasm-sandbox PyPI Publishing Script (using uv)"
Write-Info "==================================================================="

# Step 1: Check UV_PUBLISH_TOKEN
Write-Info "`n[1/7] Checking environment..."
if (-not $env:UV_PUBLISH_TOKEN) {
    Write-Fail "ERROR: UV_PUBLISH_TOKEN environment variable is not set!"
    Write-Warning "Please set it in your Windows environment or run:"
    Write-Warning '  $env:UV_PUBLISH_TOKEN = "<your-token>"'
    exit 1
}
Write-Success "✓ UV_PUBLISH_TOKEN is configured"

# Step 2: Check WASM binaries
Write-Info "`n[2/7] Checking WASM binaries..."
$wasmBinaries = @("bin/python.wasm", "bin/quickjs.wasm")
$missingBinaries = @()

foreach ($binary in $wasmBinaries) {
    if (-not (Test-Path $binary)) {
        $missingBinaries += $binary
    }
}

if ($missingBinaries.Count -gt 0) {
    Write-Fail "ERROR: Missing WASM binaries:"
    foreach ($binary in $missingBinaries) {
        Write-Fail "  - $binary"
    }
    Write-Warning "`nRun the fetch scripts first:"
    Write-Warning "  .\scripts\fetch_wlr_python.ps1"
    Write-Warning "  .\scripts\fetch_quickjs.ps1"
    exit 1
}
Write-Success "✓ All WASM binaries present"

# Step 3: Run tests
if (-not $SkipTests) {
    Write-Info "`n[3/7] Running test suite..."
    uv run pytest tests/ -v --tb=short
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "ERROR: Tests failed!"
        exit 1
    }
    Write-Success "✓ All tests passed"
} else {
    Write-Warning "`n[3/7] Skipping tests (--SkipTests flag)"
}

# Step 4: Build package
if (-not $SkipBuild) {
    Write-Info "`n[4/7] Building package..."
    
    # Clean previous builds
    if (Test-Path "dist") {
        Write-Info "Cleaning previous builds..."
        Remove-Item -Recurse -Force dist
    }
    
    # Build with uv (--no-sources ensures reproducible builds)
    Write-Info "Running: uv build --no-sources"
    uv build --no-sources
    
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "ERROR: Build failed!"
        exit 1
    }
    Write-Success "✓ Package built successfully"
} else {
    Write-Warning "`n[4/7] Skipping build (--SkipBuild flag)"
    if (-not (Test-Path "dist")) {
        Write-Fail "ERROR: No dist/ directory found and --SkipBuild specified!"
        exit 1
    }
}

# Step 5: Verify package contents
Write-Info "`n[5/7] Verifying package contents..."
$distFiles = Get-ChildItem dist -Filter "*.whl"
if ($distFiles.Count -eq 0) {
    Write-Fail "ERROR: No wheel files found in dist/"
    exit 1
}

foreach ($file in $distFiles) {
    Write-Info "Inspecting: $($file.Name)"
    
    # Use Python to list wheel contents
    $wheelContents = python -m zipfile -l "dist/$($file.Name)"
    
    # Check for critical files
    $hasWasm = $wheelContents -match "python\.wasm" -or $wheelContents -match "quickjs\.wasm"
    $hasSandbox = $wheelContents -match "sandbox/"
    $hasMcp = $wheelContents -match "mcp_server/"
    
    if (-not $hasWasm) {
        Write-Warning "  Warning: WASM binaries not found in wheel (may be in data directory)"
    }
    if (-not $hasSandbox) {
        Write-Fail "  ERROR: sandbox/ package not found in wheel!"
        exit 1
    }
    if (-not $hasMcp) {
        Write-Fail "  ERROR: mcp_server/ package not found in wheel!"
        exit 1
    }
}
Write-Success "✓ Package contents verified"

# Step 6: Determine publish target
Write-Info "`n[6/7] Publishing to $Target..."

if ($DryRun) {
    Write-Warning "DRY RUN MODE - No actual upload will occur"
    Write-Info "`nCommand that would be executed:"
    if ($Target -eq "testpypi") {
        Write-Info "  uv publish --index testpypi"
    } else {
        Write-Info "  uv publish"
    }
    Write-Success "`n✓ Dry run complete"
    exit 0
}

# Confirm before publishing to production PyPI
if ($Target -eq "pypi" -and -not $Force) {
    Write-Warning "`n⚠️  WARNING: You are about to publish to PRODUCTION PyPI!"
    Write-Warning "This action is IRREVERSIBLE. You cannot delete or re-upload the same version."
    Write-Info "`nPackages to be published:"
    Get-ChildItem dist | ForEach-Object { Write-Info "  - $($_.Name)" }
    
    $confirm = Read-Host "`nType 'publish' to confirm"
    if ($confirm -ne "publish") {
        Write-Warning "Publication cancelled."
        exit 0
    }
}

# Step 7: Publish
Write-Info "`n[7/7] Uploading to $Target..."

if ($Target -eq "testpypi") {
    # Publish to Test PyPI
    uv publish --index testpypi
} else {
    # Publish to production PyPI
    uv publish
}

if ($LASTEXITCODE -ne 0) {
    Write-Fail "`nERROR: Publication failed!"
    exit 1
}

Write-Success "`n==================================================================="
Write-Success "  ✓ Successfully published to $Target!"
Write-Success "==================================================================="

# Post-publication instructions
Write-Info "`nNext steps:"
if ($Target -eq "testpypi") {
    Write-Info "1. Test installation:"
    Write-Info "   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ llm-wasm-sandbox"
    Write-Info "2. If everything works, publish to production:"
    Write-Info "   .\scripts\publish.ps1 pypi"
} else {
    Write-Info "1. Tag the release:"
    Write-Info "   git tag -a v<version> -m 'Release version <version>'"
    Write-Info "   git push origin v<version>"
    Write-Info "2. Create GitHub Release"
    Write-Info "3. Test installation:"
    Write-Info "   pip install llm-wasm-sandbox"
    Write-Info "4. Bump version for next release:"
    Write-Info "   uv version --bump minor  # or patch/major"
}

Write-Info ""
