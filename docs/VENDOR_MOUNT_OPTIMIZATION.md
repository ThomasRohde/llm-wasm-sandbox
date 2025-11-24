# Vendor Package Mount Optimization

## Overview

As of the recent optimization (November 2024), vendored packages are now mounted **read-only** at `/data/site-packages` instead of being copied to each session workspace. This provides significant disk space savings and improved session creation performance.

## Key Changes

### Before (Copying Approach)
- Each session workspace had `site-packages/` directory copied (~7.9 MB per session)
- With 456 sessions: ~3.6 GB of duplicated vendor packages
- Slower session creation due to file copying
- Path: `/app/site-packages`

### After (Read-Only Mount)
- Vendor packages mounted once at `/data/site-packages` (shared across all sessions)
- Zero disk space overhead per session
- Instant session creation (no copying)
- Read-only enforcement prevents cross-session pollution
- Path: `/data/site-packages`

## Implementation Details

### Automatic Path Injection

The `PythonSandbox` automatically injects this setup code at the start of every execution:

```python
import sys
if '/data/site-packages' not in sys.path:
    sys.path.insert(0, '/data/site-packages')
```

This means **user code does not need to manually configure sys.path** - vendored packages are automatically available.

### WASI Mount Configuration

The optimization uses WASI's read-only preopen capability:

```python
# In sandbox/host.py
wasi.preopen_dir(
    readonly_data_dir,
    policy.guest_data_path,  # /data
    DirPerms.READ_ONLY,
    FilePerms.READ_ONLY,
)
```

### Session Workspace Contents

**New sessions (after optimization):**
```
workspace/
  <session-id>/
    .metadata.json
    user_code.py
    # No site-packages directory!
```

**Old sessions (before optimization):**
```
workspace/
  <session-id>/
    .metadata.json
    user_code.py
    site-packages/  # ~7.9 MB of vendored packages
      tabulate/
      openpyxl/
      ...
```

## Usage Examples

### For LLM-Generated Code

**Before (manual path setup):**
```python
import sys
sys.path.insert(0, '/app/site-packages')

from tabulate import tabulate
print(tabulate([[1, 2], [3, 4]], headers=["A", "B"]))
```

**After (automatic):**
```python
# sys.path is already configured - just import!
from tabulate import tabulate
print(tabulate([[1, 2], [3, 4]], headers=["A", "B"]))
```

### Disabling Automatic Injection

If needed, you can disable the automatic sys.path injection:

```python
from sandbox import create_sandbox, RuntimeType

sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
result = sandbox.execute(code, inject_setup=False)
```

## Benefits

1. **Disk Space**: Saves ~7.9 MB per session (3.6 GB for 456 sessions)
2. **Performance**: Instant session creation (no file copying overhead)
3. **Security**: Read-only mount prevents accidental/malicious vendor modification
4. **Consistency**: All sessions use the same vendor package versions
5. **Simplicity**: Automatic path injection - no manual setup needed

## Migration Notes

### Existing Sessions

Old sessions with copied `site-packages/` directories will continue to work but can be cleaned up:

```python
from pathlib import Path
import shutil

workspace_root = Path("workspace")
for session_dir in workspace_root.iterdir():
    site_packages = session_dir / "site-packages"
    if site_packages.exists():
        print(f"Removing {site_packages}")
        shutil.rmtree(site_packages)
```

### Custom Policies

If you've configured a custom `mount_data_dir` in your `ExecutionPolicy`, ensure it doesn't conflict with the vendor mount:

```python
from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

# Custom data mount (in addition to vendor mount)
policy = ExecutionPolicy(
    mount_data_dir="/path/to/custom/data",  # Mounted at /data by default
    guest_data_path="/custom_data"  # Use different path to avoid conflict
)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
```

## Testing

Verify the optimization is working:

```python
from sandbox import create_sandbox, RuntimeType
from pathlib import Path

# Create sandbox and execute code using vendored packages
sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
result = sandbox.execute("""
from tabulate import tabulate
print(tabulate([[1, 2]], headers=["A", "B"]))
""")

# Verify no site-packages in session workspace
session_workspace = Path(sandbox.workspace)
has_site_packages = (session_workspace / "site-packages").exists()

print(f"Success: {result.success}")
print(f"Has site-packages: {has_site_packages}")  # Should be False
print(f"Files: {list(session_workspace.iterdir())}")
# Expected: [.metadata.json, user_code.py]
```

## See Also

- `sandbox/host.py`: WASI mount configuration
- `sandbox/core/factory.py`: Vendor path detection and policy configuration
- `sandbox/runtimes/python/sandbox.py`: Automatic sys.path injection
- `sandbox/core/models.py`: ExecutionPolicy mount configuration
