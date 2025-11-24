# uv Publishing Quick Reference

This is a quick reference for publishing `llm-wasm-sandbox` to PyPI using uv.

## Prerequisites

Set `UV_PUBLISH_TOKEN` environment variable:

```powershell
# Current session only
$env:UV_PUBLISH_TOKEN = "pypi-AgEIcHl..."

# Permanent (run as admin or use User scope)
[System.Environment]::SetEnvironmentVariable('UV_PUBLISH_TOKEN', 'pypi-AgEIcHl...', 'User')
```

## Quick Publish Workflow

### Option 1: Using Publish Script (Recommended)

```powershell
# Test PyPI first (recommended)
.\scripts\publish.ps1 testpypi

# Production PyPI (with confirmation)
.\scripts\publish.ps1 pypi

# Skip confirmation
.\scripts\publish.ps1 pypi -Force

# Dry run
.\scripts\publish.ps1 pypi -DryRun
```

### Option 2: Manual Steps

```powershell
# 1. Ensure WASM binaries exist
.\scripts\fetch_wlr_python.ps1
.\scripts\fetch_quickjs.ps1

# 2. Run tests
uv run pytest tests/ -v

# 3. Build package
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
uv build --no-sources

# 4. Verify contents
python -m zipfile -l dist\*.whl

# 5. Publish to Test PyPI
uv publish --index testpypi

# 6. Test installation
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ llm-wasm-sandbox

# 7. Publish to production PyPI
uv publish
```

## Version Management

```powershell
# Check current version
uv version

# Bump version
uv version --bump patch   # 0.1.0 -> 0.1.1
uv version --bump minor   # 0.1.0 -> 0.2.0
uv version --bump major   # 0.1.0 -> 1.0.0

# Pre-release versions
uv version --bump patch --bump alpha   # 0.1.0 -> 0.1.1a1
uv version --bump minor --bump beta    # 0.1.0 -> 0.2.0b1
uv version --bump beta                 # 0.2.0b1 -> 0.2.0b2
uv version --bump stable               # 0.2.0b2 -> 0.2.0

# Dry run (preview without changing)
uv version --bump minor --dry-run

# Without syncing dependencies (faster)
uv version --bump minor --frozen
```

## Common Commands

```powershell
# Build only (no publish)
uv build --no-sources

# List built distributions
Get-ChildItem dist

# Inspect wheel contents
python -m zipfile -l dist\llm_wasm_sandbox-*.whl

# Inspect source dist
tar -tzf dist\llm_wasm_sandbox-*.tar.gz | Select-Object -First 30

# Check environment variable is set
echo $env:UV_PUBLISH_TOKEN

# Install from local build (for testing)
pip install dist\llm_wasm_sandbox-*.whl
```

## Troubleshooting

```powershell
# If publish fails with "already exists"
uv version --bump patch
uv build --no-sources
uv publish

# If UV_PUBLISH_TOKEN not found
$env:UV_PUBLISH_TOKEN = "pypi-AgEIcHl..."

# If build fails
uv sync
uv build --no-sources

# Skip tests or build in publish script
.\scripts\publish.ps1 pypi -SkipTests
.\scripts\publish.ps1 pypi -SkipBuild
```

## Post-Release Checklist

```powershell
# 1. Tag release
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0

# 2. Bump version for next development
uv version --bump minor

# 3. Commit version bump
git add pyproject.toml uv.lock
git commit -m "Bump version to $(uv version)"
git push

# 4. Verify installation
pip install llm-wasm-sandbox
python -c "from sandbox import create_sandbox; print('Success!')"
```

## Script Options

The `publish.ps1` script supports these options:

```powershell
# Target (positional parameter)
.\scripts\publish.ps1 testpypi   # Test PyPI
.\scripts\publish.ps1 pypi       # Production PyPI

# Flags
-DryRun          # Show what would happen without publishing
-Force           # Skip confirmation prompt
-SkipTests       # Don't run test suite
-SkipBuild       # Use existing dist/ files
```

## References

- Full guide: `docs/PUBLISHING.md`
- Checklist: `docs/PYPI_CHECKLIST.md`
- uv docs: https://docs.astral.sh/uv/guides/package/
