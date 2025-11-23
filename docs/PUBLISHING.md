# Publishing to PyPI

This document provides step-by-step instructions for publishing the `llm-wasm-sandbox` package to PyPI.

## Pre-Release Checklist

- [x] All tests passing (`uv run pytest tests/ -v`)
- [x] Version number updated in `pyproject.toml`
- [x] CHANGELOG.md updated with release notes
- [x] README.md reflects current features and installation
- [x] All GitHub URLs point to correct repository
- [x] Package metadata complete (classifiers, keywords, urls)
- [x] License file present and referenced in `pyproject.toml`
- [x] Type hints marker (`py.typed`) included
- [x] Build succeeds without errors (`uv build`)

## Prerequisites

1. **PyPI Account**: Create accounts on both [Test PyPI](https://test.pypi.org/account/register/) and [PyPI](https://pypi.org/account/register/)
2. **API Tokens**: Generate API tokens for both platforms:
   - Test PyPI: https://test.pypi.org/manage/account/#api-tokens
   - PyPI: https://pypi.org/manage/account/#api-tokens
3. **Install Tools**: Ensure you have `uv` or `build` and `twine` installed

## Build the Package

```powershell
# Clean previous builds
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue

# Build the package
uv build
```

This creates:
- `dist/llm_wasm_sandbox-0.1.0.tar.gz` (source distribution)
- `dist/llm_wasm_sandbox-0.1.0-py3-none-any.whl` (wheel)

## Verify Package Contents

### Inspect the Wheel
```powershell
python -m zipfile -l dist\llm_wasm_sandbox-0.1.0-py3-none-any.whl
```

Verify it includes:
- All `sandbox/` package files
- `sandbox/py.typed` (type hints marker)
- `sandbox/core/` and `sandbox/runtimes/` subdirectories
- `METADATA` with correct classifiers and dependencies

### Inspect the Source Distribution
```powershell
tar -tzf dist\llm_wasm_sandbox-0.1.0.tar.gz | Select-Object -First 20
```

Verify it includes:
- All source files
- `tests/` directory
- `scripts/` for WASM binary fetching
- `config/policy.toml`
- `LICENSE` and `README.md`

## Test on Test PyPI (Recommended)

```powershell
# Install twine if not using uv
pip install twine

# Upload to Test PyPI
twine upload --repository testpypi dist/*

# When prompted, enter:
# Username: __token__
# Password: <your-test-pypi-token>
```

### Test Installation from Test PyPI

```powershell
# Create a fresh virtual environment
python -m venv test_env
.\test_env\Scripts\Activate.ps1

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ llm-wasm-sandbox

# Verify import works
python -c "from sandbox import create_sandbox, RuntimeType; print('Import successful')"

# Deactivate and cleanup
deactivate
Remove-Item -Recurse -Force test_env
```

## Publish to PyPI

**⚠️ WARNING: This is irreversible! You cannot delete or re-upload the same version.**

```powershell
# Upload to production PyPI
twine upload dist/*

# When prompted, enter:
# Username: __token__
# Password: <your-pypi-token>
```

### Alternative: Using uv

```powershell
# Configure PyPI credentials (one-time setup)
uv publish --token <your-pypi-token>
```

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
   python -c "from sandbox import create_sandbox; print('Success')"
   ```

4. **Update Documentation**
   - Ensure README badges are accurate
   - Update any links that reference "upcoming release"

## Version Bumping for Next Release

After publishing, immediately bump the version for development:

```toml
# In pyproject.toml
version = "0.2.0-dev"  # or "0.1.1-dev" for patch
```

Commit this change:
```powershell
git add pyproject.toml
git commit -m "Bump version to 0.2.0-dev"
git push
```

## Troubleshooting

### Build Fails
- Check `pyproject.toml` syntax (especially TOML arrays and tables)
- Ensure all referenced files exist
- Run `uv sync` to update dependencies

### Upload Rejected (Version Conflict)
- You cannot reuse version numbers
- Bump the version in `pyproject.toml` and rebuild
- Consider using pre-release versions (e.g., `0.1.1a1`, `0.1.1rc1`)

### Import Fails After Install
- Check that `sandbox/__init__.py` exports all public APIs
- Verify `py.typed` is included in the wheel
- Ensure dependencies are correctly specified in `pyproject.toml`

### Missing Files in Distribution
- Update `[tool.hatch.build.targets.sdist]` in `pyproject.toml`
- For wheels, ensure files are in `packages = ["sandbox"]` directory

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

- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI Publishing Documentation](https://packaging.python.org/tutorials/packaging-projects/)
- [Hatchling Build System](https://hatch.pypa.io/latest/config/build/)
- [Semantic Versioning](https://semver.org/)
