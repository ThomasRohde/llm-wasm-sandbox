# Publishing to PyPI

This document provides step-by-step instructions for publishing the `llm-wasm-sandbox` package to PyPI using the **uv package manager**.

> **Note**: This project uses `uv` for all packaging operations. The traditional `twine` workflow is no longer used.

---

## Quick Reference

### One-Command Publish

```powershell
# Test PyPI first (recommended)
.\scripts\publish.ps1 testpypi

# Production PyPI
.\scripts\publish.ps1 pypi
```

### Manual Quick Workflow

```powershell
# 1. Ensure WASM binaries exist
.\scripts\fetch_wlr_python.ps1
.\scripts\fetch_quickjs.ps1

# 2. Run tests
uv run pytest tests/ -v

# 3. Build package  
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
uv build --no-sources

# 4. Publish
uv publish --index testpypi    # Test first
uv publish                      # Production
```

### Version Bumping

```powershell
uv version --bump patch   # 0.1.0 -> 0.1.1
uv version --bump minor   # 0.1.0 -> 0.2.0
uv version --bump major   # 0.1.0 -> 1.0.0
```

---

## Pre-Release Checklist

- [x] All tests passing (`uv run pytest tests/ -v`)
- [x] Version number updated in `pyproject.toml`
- [x] CHANGELOG.md updated with release notes
- [x] README.md reflects current features and installation
- [x] All GitHub URLs point to correct repository
- [x] Package metadata complete (classifiers, keywords, urls)
- [x] License file present and referenced in `pyproject.toml`
- [x] Type hints marker (`py.typed`) included
- [x] **WASM binaries present in `bin/` directory** (`python.wasm`, `quickjs.wasm`)
- [x] Build succeeds without errors (`uv build`)

## Prerequisites

1. **PyPI Account**: Create accounts on both [Test PyPI](https://test.pypi.org/account/register/) and [PyPI](https://pypi.org/account/register/)
2. **API Tokens**: Generate API tokens for both platforms:
   - Test PyPI: https://test.pypi.org/manage/account/#api-tokens
   - PyPI: https://pypi.org/manage/account/#api-tokens
3. **Environment Variable**: Set `UV_PUBLISH_TOKEN` in Windows environment variables with your PyPI API token
   ```powershell
   # Set for current session
   $env:UV_PUBLISH_TOKEN = "pypi-AgEIcHl..."
   
   # Or set permanently (requires admin)
   [System.Environment]::SetEnvironmentVariable('UV_PUBLISH_TOKEN', 'pypi-AgEIcHl...', 'User')
   ```
4. **uv Package Manager**: Already installed if you've been developing this project
5. **WASM Binaries**: Ensure `bin/python.wasm` and `bin/quickjs.wasm` exist (run fetch scripts if needed)

## Build the Package

```powershell
# Ensure WASM binaries are present (required for bundling)
if (-not (Test-Path "bin/python.wasm")) {
    .\scripts\fetch_wlr_python.ps1
}
if (-not (Test-Path "bin/quickjs.wasm")) {
    .\scripts\fetch_quickjs.ps1
}

# Clean previous builds
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue

# Build the package with uv (--no-sources ensures reproducible builds)
uv build --no-sources
```

> **Why `--no-sources`?** This flag ensures the package builds correctly without `tool.uv.sources` overrides, which is required for compatibility with other build tools and PyPI's build infrastructure.

This creates:
- `dist/llm_wasm_sandbox-0.1.0.tar.gz` (source distribution with WASM binaries)
- `dist/llm_wasm_sandbox-0.1.0-py3-none-any.whl` (wheel with WASM binaries)

## Verify Package Contents

### Inspect the Wheel
```powershell
python -m zipfile -l dist\llm_wasm_sandbox-0.1.0-py3-none-any.whl
```

Verify it includes:
- All `sandbox/` package files
- `sandbox/py.typed` (type hints marker)
- `sandbox/core/` and `sandbox/runtimes/` subdirectories
- **`bin/python.wasm` and `bin/quickjs.wasm`** (bundled WASM runtimes)
- `METADATA` with correct classifiers and dependencies

### Inspect the Source Distribution
```powershell
tar -tzf dist\llm_wasm_sandbox-0.1.0.tar.gz | Select-Object -First 20
```

Verify it includes:
- All source files
- `tests/` directory
- `scripts/` for WASM binary fetching (for development)
- **`bin/python.wasm` and `bin/quickjs.wasm`** (bundled WASM runtimes)
- `config/policy.toml`
- `LICENSE` and `README.md`

## Test on Test PyPI (Recommended)

### Quick Method: Using the Publish Script

```powershell
# Publish to Test PyPI (includes build, tests, and verification)
.\scripts\publish.ps1 testpypi
```

### Manual Method: Using uv directly

First, configure Test PyPI in your `pyproject.toml` (already done):

```toml
[[tool.uv.index]]
name = "testpypi"
url = "https://test.pypi.org/simple/"
publish-url = "https://test.pypi.org/legacy/"
explicit = true
```

Then publish:

```powershell
# Publish to Test PyPI
uv publish --index testpypi

# Or with explicit token (not recommended, use UV_PUBLISH_TOKEN instead)
uv publish --index testpypi --token pypi-AgEIcHl...
```

### Test Installation from Test PyPI

```powershell
# Create a fresh virtual environment
python -m venv test_env
.\test_env\Scripts\Activate.ps1

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ llm-wasm-sandbox

# Verify import works and WASM binaries are accessible
python -c "from sandbox import create_sandbox, RuntimeType; sandbox = create_sandbox(runtime=RuntimeType.PYTHON); print('Package and runtimes successfully installed!')"

# Deactivate and cleanup
deactivate
Remove-Item -Recurse -Force test_env
```

## Publish to PyPI

**⚠️ WARNING: This is irreversible! You cannot delete or re-upload the same version.**

### Quick Method: Using the Publish Script (Recommended)

```powershell
# Publish to production PyPI (with confirmation prompt)
.\scripts\publish.ps1 pypi

# Skip confirmation prompt (use with caution!)
.\scripts\publish.ps1 pypi -Force

# Dry run to see what would happen
.\scripts\publish.ps1 pypi -DryRun
```

The script will:
1. Check `UV_PUBLISH_TOKEN` is set
2. Verify WASM binaries exist
3. Run full test suite
4. Build package with `--no-sources`
5. Verify package contents
6. Prompt for confirmation (unless `-Force`)
7. Publish to PyPI

### Manual Method: Using uv directly

```powershell
# Publish to production PyPI
uv publish

# Or with explicit token (not recommended, use UV_PUBLISH_TOKEN instead)
uv publish --token pypi-AgEIcHl...
```

> **Note**: When using `uv publish` with environment variable `UV_PUBLISH_TOKEN`, you don't need to specify the token explicitly. This is the recommended and secure approach.

## Post-Release Tasks

1. **Tag the Release in Git**
   ```powershell
   git tag -a v0.1.0 -m "Release version 0.1.0"
   git push origin v0.1.0
   ```

2. **Create GitHub Release**
   - Go to https://github.com/ThomasRohde/llm-wasm-sandbox/releases
   - Click "Create a new release"
   - Select the tag `v0.1.0`
   - Copy release notes from CHANGELOG.md
   - Attach the wheel and tar.gz files as release assets

3. **Verify Installation**
   ```powershell
   pip install llm-wasm-sandbox
   python -c "from sandbox import create_sandbox, RuntimeType; sandbox = create_sandbox(); print('Success - runtimes bundled!')"
   ```

4. **Update Documentation**
   - Ensure README badges are accurate
   - Update any links that reference "upcoming release"

## Version Bumping for Next Release

After publishing, immediately bump the version for development using uv's built-in version management:

```powershell
# Bump to next minor version (e.g., 0.1.0 -> 0.2.0)
uv version --bump minor

# Bump to next patch version (e.g., 0.1.0 -> 0.1.1)
uv version --bump patch

# Bump to next major version (e.g., 0.1.0 -> 1.0.0)
uv version --bump major

# Preview changes without modifying pyproject.toml
uv version --bump minor --dry-run

# Bump without syncing dependencies (faster)
uv version --bump minor --frozen
```

Common version bump patterns:

```powershell
# Move to pre-release
uv version --bump patch --bump alpha   # 1.0.0 -> 1.0.1a1
uv version --bump minor --bump beta    # 1.0.0 -> 1.1.0b1

# Increment pre-release
uv version --bump beta                 # 1.1.0b1 -> 1.1.0b2

# Move from pre-release to stable
uv version --bump stable               # 1.1.0b2 -> 1.1.0
```

Commit the version change:
```powershell
git add pyproject.toml uv.lock
git commit -m "Bump version to $(uv version)"
git push
```

## Troubleshooting

### Build Fails
- Check `pyproject.toml` syntax (especially TOML arrays and tables)
- Ensure all referenced files exist
- Run `uv sync` to update dependencies
- Try `uv build --no-sources` to ensure reproducible builds

### Upload Rejected (Version Conflict)
- You cannot reuse version numbers
- Bump the version using `uv version --bump patch` and rebuild
- Consider using pre-release versions (e.g., `0.1.1a1`, `0.1.1rc1`)

### UV_PUBLISH_TOKEN Not Found
```powershell
# Set for current session
$env:UV_PUBLISH_TOKEN = "pypi-AgEIcHl..."

# Set permanently (run as admin)
[System.Environment]::SetEnvironmentVariable('UV_PUBLISH_TOKEN', 'pypi-AgEIcHl...', 'User')

# Verify it's set
echo $env:UV_PUBLISH_TOKEN
```

### Import Fails After Install
- Check that `sandbox/__init__.py` exports all public APIs
- Verify `py.typed` is included in the wheel
- Ensure dependencies are correctly specified in `pyproject.toml`

### Missing Files in Distribution
- Update `[tool.hatch.build.targets.sdist]` in `pyproject.toml`
- For wheels, ensure files are in `packages = ["sandbox"]` directory
- Check `include` directives in build configuration

### Publish Script Fails
```powershell
# Skip tests if they're already passing
.\scripts\publish.ps1 pypi -SkipTests

# Skip build if you've already built
.\scripts\publish.ps1 pypi -SkipBuild

# See what would happen without publishing
.\scripts\publish.ps1 pypi -DryRun
```

## Dependency Management

Current pinned dependencies:
- `pydantic>=2.0.0,<3.0.0` - Type-safe models (major version pinned)
- `rich>=14.2.0` - Pretty console output (minor version floor)
- `structlog==25.5.0` - Structured logging (exact pin, may need updating)
- `wasmtime>=38.0.0,<39.0.0` - WASM runtime (tightly pinned due to API changes)

**Before releasing**, consider:
- Updating `structlog` to use `>=25.5.0` for flexibility
- Testing against latest `wasmtime` 38.x patch versions
- Verifying compatibility with Python 3.13

## Security Considerations

- **Never commit API tokens** to version control
- Use environment variables or secure credential storage
- Review `twine check dist/*` before uploading
- Scan dependencies for vulnerabilities: `pip-audit`

## References

- [uv Package Publishing Guide](https://docs.astral.sh/uv/guides/package/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI Publishing Documentation](https://packaging.python.org/tutorials/packaging-projects/)
- [Hatchling Build System](https://hatch.pypa.io/latest/config/build/)
- [Semantic Versioning](https://semver.org/)
