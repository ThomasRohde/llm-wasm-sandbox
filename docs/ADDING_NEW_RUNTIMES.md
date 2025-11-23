# Adding New Runtimes to LLM WASM Sandbox

**Last Updated**: November 23, 2025

This guide provides comprehensive instructions for adding new language runtimes (e.g., Ruby, Lua, PHP) to the LLM WASM sandbox alongside the existing Python and JavaScript runtimes. It covers WASM binary requirements, architecture patterns, integration points, testing strategies, and best practices.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Layers](#architecture-layers)
3. [WASM Binary Requirements](#wasm-binary-requirements)
4. [Step-by-Step Integration Guide](#step-by-step-integration-guide)
5. [Testing Strategy](#testing-strategy)
6. [Performance Tuning](#performance-tuning)
7. [Security Validation Checklist](#security-validation-checklist)
8. [Real-World Examples](#real-world-examples)
9. [Troubleshooting](#troubleshooting)
10. [References](#references)

---

## Overview

### What is a Runtime?

In this sandbox, a **runtime** is a complete language interpreter compiled to WebAssembly that executes untrusted code with security isolation. Each runtime implements:

- **Code execution**: Parse and execute user-provided source code
- **I/O operations**: Read/write files via WASI capability-based filesystem
- **Resource management**: Respect fuel budgets and memory limits
- **Error handling**: Capture and report syntax/runtime errors

### Supported Runtimes (Current)

| Runtime | Language | Binary Size | WASM Source | Notes |
|---------|----------|-------------|-------------|-------|
| **Python** | Python 3.11+ | ~50-100 MB | [WLR AIO](https://github.com/webassemblylabs/webassembly-language-runtimes) | Full CPython with stdlib |
| **JavaScript** | ECMAScript 2020+ | ~1.4 MB | [QuickJS-NG](https://github.com/quickjs-ng/quickjs) | Minimal ES runtime |

### Why Add New Runtimes?

- **Multi-language LLM support**: Allow LLMs to generate code in Ruby, Lua, PHP, etc.
- **Specialized use cases**: Enable domain-specific languages (DSLs) for financial modeling, data analysis
- **Ecosystem integration**: Run popular libraries only available in specific languages

---

## Architecture Layers

The sandbox uses a **three-layer architecture** for clean separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                   User-Facing API                       │
│  create_sandbox(runtime=RuntimeType.YOUR_LANG)          │
└─────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│               Runtime Layer (Custom Code)               │
│  sandbox/runtimes/your_lang/sandbox.py                  │
│  - YourLangSandbox(BaseSandbox)                         │
│  - execute(), validate_code()                           │
│  - _write_untrusted_code(), _map_to_sandbox_result()    │
└─────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│               Host Layer (Shared WASM Logic)            │
│  sandbox/host.py                                        │
│  - run_untrusted_YOUR_LANG() function                   │
│  - Wasmtime engine, fuel, memory setup                  │
│  - WASI preopen configuration                           │
└─────────────────────────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│               Core Layer (Type-Safe Models)             │
│  sandbox/core/                                          │
│  - ExecutionPolicy (Pydantic)                           │
│  - SandboxResult (Pydantic)                             │
│  - BaseSandbox (ABC)                                    │
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

1. **Core Layer**: Define contracts, validation, type safety
2. **Host Layer**: Low-level WASM execution, WASI configuration, fuel/memory enforcement
3. **Runtime Layer**: Language-specific orchestration, code writing, result mapping
4. **API Layer**: Factory function for runtime selection

---

## WASM Binary Requirements

### Critical Requirements

Your WASM binary **MUST**:

1. ✅ **Target WASI** (`wasm32-wasi` or `wasm32-wasip1`)
   - Provides POSIX-like file I/O, command-line args, environment variables
   - No browser-specific APIs (DOM, Web APIs)

2. ✅ **Export `_start` function**
   - Standard WASI entry point invoked by Wasmtime
   - Should accept command-line args via WASI argv

3. ✅ **Export `memory` object**
   - Linear memory visible to host for inspection/limits
   - Used for fuel metering and memory tracking

4. ✅ **Support fuel metering** (Wasmtime-specific)
   - Binary must tolerate fuel consumption tracking
   - No infinite host calls that bypass fuel (e.g., blocking sleep)

5. ✅ **Statically linked or bundle dependencies**
   - Cannot dynamically load `.so`/`.dll` files (WASI has no dynamic linker)
   - Embed all required libraries in WASM module

6. ✅ **Deterministic execution**
   - Same input → same output (no ambient timestamps, randomness from host)
   - Use WASI-provided randomness/clock if needed

### Desirable Features

- **Minimal size**: Smaller binaries load faster (<10 MB ideal, <100 MB acceptable)
- **Standard library**: Include common language features (file I/O, JSON, regex)
- **No networking**: Should not call `socket()`, `connect()` (WASI baseline doesn't expose these)
- **UTF-8 friendly**: Handle non-ASCII input/output correctly

### Binary Sources

#### Option 1: Pre-Built Community Binaries

- **WLR (WebAssembly Language Runtimes)**: Python, Ruby, PHP
  - Repository: https://github.com/webassemblylabs/webassembly-language-runtimes
  - Pros: Production-ready, actively maintained, AIO (All-In-One) bundles
  - Cons: Large binaries (~50-100 MB), limited language versions

- **wasi-sdk Toolchain**: Compile C/C++ to WASI
  - Repository: https://github.com/WebAssembly/wasi-sdk
  - Pros: Official toolchain, flexible
  - Cons: Requires building from source

- **Wasmer/Wasmtime Registries**: Search existing packages
  - WAPM: https://wapm.io/
  - WIT Packages: https://github.com/bytecodealliance/wasmtime/tree/main/crates/wasi

#### Option 2: Build from Source

**Example: Compiling Lua to WASI**

```bash
# Install wasi-sdk
wget https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-22/wasi-sdk-22.0-linux.tar.gz
tar -xzf wasi-sdk-22.0-linux.tar.gz

# Clone Lua
git clone https://github.com/lua/lua.git
cd lua

# Compile with wasi-sdk
export CC=/path/to/wasi-sdk-22.0/bin/clang
export CFLAGS="--target=wasm32-wasi -O2"
make generic

# Output: lua.wasm
```

**Verification Checklist**:

```bash
# Check WASI imports/exports
wasm-objdump -x your_lang.wasm | grep "wasi"

# Verify _start export
wasm-objdump -x your_lang.wasm | grep "_start"

# Verify memory export
wasm-objdump -x your_lang.wasm | grep "export.*memory"

# Test basic execution
wasmtime run your_lang.wasm -- -e "print('hello')"
```

---

## Step-by-Step Integration Guide

### Step 1: Add Runtime Type to Enum

**File**: `sandbox/core/models.py`

```python
class RuntimeType(str, Enum):
    """Supported WASM runtime types for sandbox execution."""
    
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    YOUR_LANG = "your_lang"  # Add your runtime here
```

### Step 2: Create Runtime Directory Structure

```bash
mkdir -p sandbox/runtimes/your_lang
touch sandbox/runtimes/your_lang/__init__.py
touch sandbox/runtimes/your_lang/sandbox.py
```

**File**: `sandbox/runtimes/your_lang/__init__.py`

```python
"""Your Language runtime implementation for LLM WASM sandbox.

Provides YourLangSandbox class for executing untrusted Your Language code
with WASM isolation, fuel limits, and file change tracking.
"""

from sandbox.runtimes.your_lang.sandbox import YourLangSandbox

__all__ = ["YourLangSandbox"]
```

### Step 3: Implement Sandbox Class

**File**: `sandbox/runtimes/your_lang/sandbox.py`

```python
"""YourLangSandbox: Type-safe orchestration layer for Your Language WASM execution.

Provides YourLangSandbox class that wraps the low-level host.run_untrusted_your_lang()
with type-safe inputs (ExecutionPolicy), structured logging, file change detection,
and Pydantic-based result models (SandboxResult).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sandbox.core.base import BaseSandbox
from sandbox.core.models import ExecutionPolicy, SandboxResult
from sandbox.host import run_untrusted_your_lang

if TYPE_CHECKING:
    from sandbox.core.storage import StorageAdapter


class YourLangSandbox(BaseSandbox):
    """Type-safe Your Language sandbox implementation using WASM runtime.

    Orchestrates Your Language code execution by:
    1. Writing untrusted code to session workspace (user_code.YOUR_EXTENSION)
    2. Taking filesystem snapshots before execution (for delta detection)
    3. Delegating to low-level host.run_untrusted_your_lang() for WASM execution
    4. Mapping raw results to typed SandboxResult with metrics and file changes
    5. Updating session metadata timestamps after execution
    6. Emitting structured log events for observability

    Attributes:
        wasm_binary_path: Path to your_lang.wasm binary
        policy: ExecutionPolicy with validated resource limits
        session_id: UUIDv4 session identifier for workspace isolation
        storage_adapter: StorageAdapter for workspace file operations
        logger: SandboxLogger for structured event emission
    """

    def __init__(
        self,
        wasm_binary_path: str,
        policy: ExecutionPolicy,
        session_id: str,
        storage_adapter: StorageAdapter,
        logger: Any = None,
    ) -> None:
        """Initialize YourLangSandbox with WASM binary path and session config.

        Args:
            wasm_binary_path: Path to your_lang.wasm binary (e.g., "bin/your_lang.wasm")
            policy: ExecutionPolicy with validated limits
            session_id: UUIDv4 string identifying the session
            storage_adapter: StorageAdapter for workspace operations
            logger: Optional SandboxLogger (created if None)
        """
        super().__init__(policy, session_id, storage_adapter, logger)
        self.wasm_binary_path = wasm_binary_path

    def execute(self, code: str, **kwargs: Any) -> SandboxResult:
        """Execute untrusted Your Language code in WASM sandbox with resource limits.

        Workflow:
        1. Log execution start with policy details and session_id
        2. Write code to workspace/user_code.YOUR_EXTENSION
        3. Snapshot filesystem state for delta detection
        4. Execute via host.run_untrusted_your_lang() with WASI isolation
        5. Measure execution duration and detect file changes
        6. Map raw result to typed SandboxResult with session_id in metadata
        7. Update session metadata timestamp
        8. Log execution complete with metrics

        Args:
            code: Untrusted Your Language source code to execute
            **kwargs: Runtime-specific options

        Returns:
            SandboxResult with outputs, metrics, file deltas, and session_id
        """
        wasm_path = Path(self.wasm_binary_path)
        if not wasm_path.is_file():
            raise FileNotFoundError(f"WASM binary not found at {wasm_path}")

        # Log execution start with session_id
        self.logger.log_execution_start(
            runtime="your_lang", policy=self.policy, session_id=self.session_id
        )

        # Write code to workspace
        user_code_path = self._write_untrusted_code(code)

        # Snapshot filesystem before execution
        before_files = self._snapshot_workspace(exclude=user_code_path)

        # Measure execution duration
        start_time = time.perf_counter()

        # Delegate to low-level host execution
        try:
            raw_result = run_untrusted_your_lang(
                wasm_path=str(wasm_path), workspace_dir=str(self.workspace), policy=self.policy
            )
        except Exception as e:
            duration_seconds = time.perf_counter() - start_time
            msg = f"WASM runtime error: {type(e).__name__}: {e!s}"
            trap_reason = "memory_limit" if "memory" in msg.lower() else "host_error"
            mem_len = int(self.policy.memory_bytes)
            mem_pages = max(1, mem_len // 65536)

            from sandbox.host import SandboxResult as HostSandboxResult

            raw_result = HostSandboxResult(
                stdout="",
                stderr=msg,
                fuel_consumed=None,
                mem_pages=mem_pages,
                mem_len=mem_len,
                logs_dir=None,
                exit_code=1,
                trapped=True,
                trap_reason=trap_reason,
            )

        duration_seconds = time.perf_counter() - start_time

        # Detect file changes
        files_created, files_modified = self._detect_file_delta(
            before_files, exclude=user_code_path
        )

        # Map to typed SandboxResult (always include session_id)
        result = self._map_to_sandbox_result(
            raw_result, duration_seconds, files_created, files_modified, session_id=self.session_id
        )

        # Update session timestamp after successful execution
        self._update_session_timestamp()

        # Log execution complete with session_id
        self.logger.log_execution_complete(result, runtime="your_lang", session_id=self.session_id)

        return result

    def validate_code(self, code: str) -> bool:
        """Validate Your Language code syntax without executing it.

        Args:
            code: Your Language source code to validate

        Returns:
            True if syntax is valid, False otherwise
        """
        # Option 1: Use language-specific parser (preferred)
        # try:
        #     import your_lang_parser
        #     your_lang_parser.parse(code)
        #     return True
        # except your_lang_parser.SyntaxError:
        #     return False
        
        # Option 2: Defer to runtime (acceptable for v1)
        return True

    def _write_untrusted_code(self, code: str) -> str:
        """Write untrusted Your Language code to workspace via storage adapter.

        Args:
            code: Your Language source code to write

        Returns:
            Relative path to written user_code file
        """
        filename = "user_code.YOUR_EXTENSION"  # e.g., "user_code.rb", "user_code.lua"
        self.storage_adapter.write_file(self.session_id, filename, code.encode("utf-8"))
        return filename

    def _snapshot_workspace(self, exclude: str) -> dict[str, float]:
        """Take snapshot of workspace files before execution.

        Args:
            exclude: Relative path to user code file (don't track this file)

        Returns:
            Dict mapping relative paths to modification timestamps
        """
        snapshot = self.storage_adapter.get_workspace_snapshot(self.session_id)
        snapshot.pop(exclude, None)
        return snapshot

    def _detect_file_delta(
        self, before_files: dict[str, float], exclude: str
    ) -> tuple[list[str], list[str]]:
        """Detect files created or modified during execution.

        Args:
            before_files: Pre-execution snapshot from _snapshot_workspace()
            exclude: Relative path to user code file (don't report this file)

        Returns:
            Tuple of (files_created, files_modified) with relative paths
        """
        after_files = self.storage_adapter.get_workspace_snapshot(self.session_id)
        files_created, files_modified = self.storage_adapter.detect_file_changes(
            self.session_id, before_files, after_files
        )
        files_created = [f for f in files_created if f != exclude]
        files_modified = [f for f in files_modified if f != exclude]
        return (files_created, files_modified)

    def _map_to_sandbox_result(
        self,
        raw_result: Any,
        duration_seconds: float,
        files_created: list[str],
        files_modified: list[str],
        session_id: str | None = None,
    ) -> SandboxResult:
        """Map host.SandboxResult to core.SandboxResult Pydantic model.

        Args:
            raw_result: Result from host.run_untrusted_your_lang()
            duration_seconds: Measured execution time
            files_created: List of relative paths to created files
            files_modified: List of relative paths to modified files
            session_id: Optional session identifier to include in metadata

        Returns:
            SandboxResult Pydantic model with all fields populated
        """
        exit_code = getattr(raw_result, "exit_code", None)
        trapped = bool(getattr(raw_result, "trapped", False))
        trap_reason = getattr(raw_result, "trap_reason", None)
        trap_message = getattr(raw_result, "trap_message", None)
        stdout_truncated = bool(getattr(raw_result, "stdout_truncated", False))
        stderr_truncated = bool(getattr(raw_result, "stderr_truncated", False))

        if exit_code is None:
            exit_code = 1 if trapped else 0

        metadata = {
            "runtime": "your_lang",
            "fuel_budget": self.policy.fuel_budget,
            "memory_limit_bytes": self.policy.memory_bytes,
            "memory_pages": raw_result.mem_pages,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "exit_code": exit_code,
            "trapped": trapped,
        }

        if raw_result.logs_dir:
            metadata["logs_dir"] = raw_result.logs_dir

        if session_id is not None:
            metadata["session_id"] = session_id

        if trap_reason is not None:
            metadata["trap_reason"] = trap_reason
        if trap_message is not None:
            metadata["trap_message"] = trap_message

        success = self._determine_success(
            exit_code=exit_code, trapped=trapped, stderr=raw_result.stderr
        )

        return SandboxResult(
            success=success,
            stdout=raw_result.stdout,
            stderr=raw_result.stderr,
            exit_code=exit_code,
            duration_ms=duration_seconds * 1000,
            fuel_consumed=raw_result.fuel_consumed,
            memory_used_bytes=raw_result.mem_len,
            files_created=files_created,
            files_modified=files_modified,
            workspace_path=str(self.workspace),
            metadata=metadata,
        )

    @staticmethod
    def _determine_success(exit_code: int, trapped: bool, stderr: str) -> bool:
        """Determine execution success based on exit codes, traps, and stderr content."""
        if trapped:
            return False

        if exit_code != 0:
            return False

        # Language-specific error patterns
        lowered = (stderr or "").lower()
        failure_tokens = (
            "error",
            "exception",
            "outoffuel",
            # Add language-specific patterns:
            # "syntaxerror",  # Your Language syntax error
            # "runtimeerror", # Your Language runtime error
        )
        return not any(token in lowered for token in failure_tokens)

    def _update_session_timestamp(self) -> None:
        """Update the updated_at timestamp in session metadata after execution."""
        try:
            self.storage_adapter.update_session_timestamp(self.session_id)
            metadata = self.storage_adapter.read_metadata(self.session_id)
            self.logger.log_session_metadata_updated(
                session_id=self.session_id, timestamp=metadata.updated_at
            )
        except Exception as e:
            import sys
            print(
                f"Warning: Failed to update session timestamp for {self.session_id}: {e}",
                file=sys.stderr,
            )
```

### Step 4: Add Host Function

**File**: `sandbox/host.py`

Add a new function following the `run_untrusted_python` pattern:

```python
def run_untrusted_your_lang(
    wasm_path: str = "bin/your_lang.wasm",
    workspace_dir: str | None = None,
    policy: ExecutionPolicy | None = None,
) -> SandboxResult:
    """Execute untrusted Your Language code in a WASM sandbox with security constraints.

    Creates a Wasmtime environment with WASI capabilities, loads the Your Language WASM
    binary, and executes it with strict resource limits. The guest process sees only
    preopened directories (capability-based filesystem isolation) and is limited by
    fuel budget (instruction count) and memory caps.

    Args:
        wasm_path: Path to the your_lang.wasm binary.
        workspace_dir: Override for the writable workspace directory mounted at
            guest_mount_path. If None, uses policy default (mount_host_dir).
        policy: ExecutionPolicy to enforce for this execution. If None, uses
            the default ExecutionPolicy() values.

    Returns:
        SandboxResult containing captured outputs, resource consumption metrics,
        and path to full logs.
    """
    policy = policy or ExecutionPolicy()
    preserve_logs = bool(getattr(policy, "preserve_logs", False))
    cleanup_paths: list[str] = []

    cfg = Config()
    cfg.consume_fuel = True
    engine = Engine(cfg)

    linker = Linker(engine)
    linker.define_wasi()

    module = Module.from_file(engine, wasm_path)

    tmp = tempfile.mkdtemp(prefix="wasm-your-lang-")
    out_log = os.path.join(tmp, "stdout.log")
    err_log = os.path.join(tmp, "stderr.log")

    logs_dir: str | None = tmp if preserve_logs else None

    try:
        wasi = WasiConfig()

        if workspace_dir is not None:
            host_dir = os.path.abspath(workspace_dir)
        else:
            host_dir = os.path.abspath(policy.mount_host_dir)

        wasi.preopen_dir(host_dir, policy.guest_mount_path)

        if policy.mount_data_dir is not None:
            data_dir = os.path.abspath(policy.mount_data_dir)
            if os.path.exists(data_dir) and policy.guest_data_path is not None:
                readonly_data_dir, temp_copy_root = _prepare_readonly_data_dir(data_dir)
                cleanup_paths.append(temp_copy_root)
                wasi.preopen_dir(
                    readonly_data_dir,
                    policy.guest_data_path,
                    DirPerms.READ_ONLY,
                    FilePerms.READ_ONLY,
                )

        # Language-specific argv (adjust for your runtime)
        your_lang_argv = ["your_lang", f"{policy.guest_mount_path}/user_code.YOUR_EXTENSION"]
        wasi.argv = tuple(your_lang_argv)

        # Language-specific environment variables
        wasi.env = [(k, v) for k, v in policy.env.items()]
        wasi.stdout_file = out_log
        wasi.stderr_file = err_log

        store = Store(engine)
        store.set_wasi(wasi)

        fuel_budget = int(policy.fuel_budget)
        store.set_fuel(fuel_budget)

        if not hasattr(store, "set_limits"):
            raise SandboxExecutionError(
                "Memory limit enforcement is unavailable: wasmtime.Store.set_limits is missing"
            )

        try:
            store.set_limits(memory_size=int(policy.memory_bytes))
        except Exception as e:
            raise SandboxExecutionError(
                f"Failed to enforce memory limit of {policy.memory_bytes} bytes"
            ) from e

        instance = linker.instantiate(store, module)
        start = instance.exports(store)["_start"]
        memory = instance.exports(store)["memory"]

        trapped = False
        trap_reason: str | None = None
        trap_message: str | None = None
        exit_code: int | None = None

        try:
            start(store)  # type: ignore[operator]
            exit_code = 0
        except ExitTrap as trap:
            exit_code = trap.code
            if trap.code != 0:
                trap_message = str(trap)
                trap_reason = "proc_exit"
        except Trap as trap:
            trapped = True
            trap_message = str(trap)
            trap_reason = _classify_trap(trap_message)
            exit_code = 1

        try:
            fuel_remaining = store.get_fuel()
            fuel_consumed = fuel_budget - fuel_remaining
        except Exception:
            fuel_consumed = None

        def read_capped(path: str, cap: int) -> tuple[str, bool]:
            """Read file up to cap bytes to prevent DoS from unbounded output."""
            try:
                with open(path, "rb") as f:
                    data = f.read(cap + 1)
                truncated = len(data) > cap
                return data[:cap].decode("utf-8", errors="replace"), truncated
            except FileNotFoundError:
                return "", False

        stdout, stdout_truncated = read_capped(out_log, int(policy.stdout_max_bytes))
        stderr, stderr_truncated = read_capped(err_log, int(policy.stderr_max_bytes))

        if trap_reason == "out_of_fuel":
            trap_notice = "Execution trapped: OutOfFuel"
            if trap_notice not in stderr:
                stderr = f"{stderr.rstrip()}\n{trap_notice}".strip()
        elif trap_reason is not None and trap_message:
            trap_notice = f"Execution trapped: {trap_message}"
            if trap_notice not in stderr:
                stderr = f"{stderr.rstrip()}\n{trap_notice}".strip()

        stdout, stdout_truncated = _enforce_cap(
            stdout, int(policy.stdout_max_bytes), stdout_truncated
        )
        stderr, stderr_truncated = _enforce_cap(
            stderr, int(policy.stderr_max_bytes), stderr_truncated
        )

    finally:
        for path in cleanup_paths:
            shutil.rmtree(path, ignore_errors=True)
        if not preserve_logs:
            shutil.rmtree(tmp, ignore_errors=True)

    return SandboxResult(
        stdout=stdout,
        stderr=stderr,
        fuel_consumed=fuel_consumed,
        mem_pages=memory.size(store),  # type: ignore[union-attr,call-arg]
        mem_len=memory.data_len(store),  # type: ignore[union-attr,call-arg]
        logs_dir=logs_dir,
        exit_code=exit_code,
        trapped=trapped,
        trap_reason=trap_reason,
        trap_message=trap_message,
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
    )
```

### Step 5: Update Factory Function

**File**: `sandbox/core/factory.py`

Add runtime dispatch in `create_sandbox()`:

```python
def create_sandbox(
    runtime: RuntimeType = RuntimeType.PYTHON,
    # ... existing args ...
) -> Any:
    # ... existing validation and setup ...

    # Add your runtime dispatch
    if runtime == RuntimeType.YOUR_LANG:
        from sandbox.runtimes.your_lang.sandbox import YourLangSandbox

        wasm_binary_path = kwargs.pop("wasm_binary_path", "bin/your_lang.wasm")
        return YourLangSandbox(
            wasm_binary_path=wasm_binary_path,
            policy=policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
            logger=logger,
            **kwargs,
        )

    else:
        raise ValueError(f"Unsupported runtime type: {runtime}")
```

### Step 6: Add StorageAdapter Constants

**File**: `sandbox/core/storage.py`

If using DiskStorageAdapter, add filename constant:

```python
class DiskStorageAdapter(StorageAdapter):
    PYTHON_CODE_FILENAME = "user_code.py"
    JAVASCRIPT_CODE_FILENAME = "user_code.js"
    YOUR_LANG_CODE_FILENAME = "user_code.YOUR_EXTENSION"  # Add this
```

### Step 7: Create Binary Fetch Script

**File**: `scripts/fetch_your_lang.ps1` (Windows) or `.sh` (Linux/macOS)

**PowerShell Example**:

```powershell
# Download Your Language WASM binary from official source

$BINARY_URL = "https://github.com/your-org/your-lang-wasm/releases/download/v1.0.0/your_lang.wasm"
$OUTPUT_PATH = "bin/your_lang.wasm"

Write-Host "Fetching Your Language WASM binary from $BINARY_URL"

# Create bin directory if it doesn't exist
if (!(Test-Path "bin")) {
    New-Item -ItemType Directory -Path "bin" | Out-Null
}

# Download binary
Invoke-WebRequest -Uri $BINARY_URL -OutFile $OUTPUT_PATH

# Verify download
if (Test-Path $OUTPUT_PATH) {
    $size = (Get-Item $OUTPUT_PATH).Length / 1MB
    Write-Host "✓ Downloaded $OUTPUT_PATH ($([math]::Round($size, 2)) MB)"
} else {
    Write-Error "✗ Failed to download Your Language WASM binary"
    exit 1
}

# Optional: Verify WASM structure
Write-Host "Verifying WASM binary exports..."
# Add wasm-objdump checks if available
```

**Bash Example**:

```bash
#!/usr/bin/env bash
set -euo pipefail

BINARY_URL="https://github.com/your-org/your-lang-wasm/releases/download/v1.0.0/your_lang.wasm"
OUTPUT_PATH="bin/your_lang.wasm"

echo "Fetching Your Language WASM binary from $BINARY_URL"

mkdir -p bin
curl -L -o "$OUTPUT_PATH" "$BINARY_URL"

if [ -f "$OUTPUT_PATH" ]; then
    size=$(du -h "$OUTPUT_PATH" | cut -f1)
    echo "✓ Downloaded $OUTPUT_PATH ($size)"
else
    echo "✗ Failed to download Your Language WASM binary"
    exit 1
fi

# Optional: Verify WASM structure
echo "Verifying WASM binary exports..."
wasm-objdump -x "$OUTPUT_PATH" | grep "_start" || echo "Warning: _start not found"
wasm-objdump -x "$OUTPUT_PATH" | grep "export.*memory" || echo "Warning: memory export not found"
```

---

## Testing Strategy

### Test File Structure

Create comprehensive test coverage for your runtime:

```
tests/
├── test_your_lang_sandbox.py      # Basic functionality tests
├── test_your_lang_security.py     # Security boundary tests
├── test_your_lang_binary.py       # Binary validation tests
└── conftest.py                    # Shared fixtures
```

### Basic Functionality Tests

**File**: `tests/test_your_lang_sandbox.py`

```python
"""Tests for YourLangSandbox runtime implementation."""

import pytest
from pathlib import Path
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

@pytest.fixture
def your_lang_sandbox():
    """Create YourLangSandbox instance for testing."""
    return create_sandbox(runtime=RuntimeType.YOUR_LANG)

def test_hello_world_execution(your_lang_sandbox):
    """Verify basic code execution and stdout capture."""
    code = 'print("Hello from Your Language")'
    result = your_lang_sandbox.execute(code)
    
    assert result.success
    assert "Hello from Your Language" in result.stdout
    assert result.exit_code == 0
    assert result.fuel_consumed is not None
    assert result.fuel_consumed > 0

def test_stderr_capture(your_lang_sandbox):
    """Verify error output is captured in stderr."""
    code = 'raise "Intentional error"'
    result = your_lang_sandbox.execute(code)
    
    assert not result.success
    assert "error" in result.stderr.lower()
    assert result.exit_code != 0

def test_file_creation_detection(your_lang_sandbox):
    """Verify file delta tracking works."""
    code = '''
    file = File.open("/app/test.txt", "w")
    file.write("content")
    file.close()
    '''
    result = your_lang_sandbox.execute(code)
    
    assert result.success
    assert "test.txt" in result.files_created

def test_syntax_error_handling(your_lang_sandbox):
    """Verify syntax errors are reported gracefully."""
    code = "this is not valid syntax {"
    result = your_lang_sandbox.execute(code)
    
    assert not result.success
    assert result.stderr  # Should contain error message
```

### Security Tests

**File**: `tests/test_your_lang_security.py`

```python
"""Security boundary tests for YourLangSandbox."""

import pytest
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

class TestFuelExhaustion:
    """Verify fuel limits prevent infinite loops."""
    
    def test_infinite_loop_trapped(self):
        """Infinite loop should hit fuel limit."""
        policy = ExecutionPolicy(fuel_budget=1_000_000)  # Low limit
        sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG, policy=policy)
        
        code = "while true do end"
        result = sandbox.execute(code)
        
        assert not result.success
        assert result.metadata.get("trapped") is True
        assert result.metadata.get("trap_reason") == "out_of_fuel"

class TestFilesystemIsolation:
    """Verify WASI capability isolation."""
    
    def test_etc_passwd_access_denied(self):
        """Guest cannot read /etc/passwd outside preopen."""
        sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG)
        
        code = '''
        begin
            File.read("/etc/passwd")
        rescue => e
            puts "Access denied: #{e.message}"
        end
        '''
        result = sandbox.execute(code)
        
        # Should fail gracefully (no host compromise)
        assert "Access denied" in result.stdout or result.stderr
    
    def test_app_directory_access_allowed(self):
        """Guest can read/write files in /app mount."""
        sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG)
        
        code = '''
        File.write("/app/allowed.txt", "success")
        puts File.read("/app/allowed.txt")
        '''
        result = sandbox.execute(code)
        
        assert result.success
        assert "success" in result.stdout

class TestMemoryLimits:
    """Verify memory caps prevent exhaustion."""
    
    def test_memory_limit_enforced(self):
        """Large allocations should respect memory cap."""
        policy = ExecutionPolicy(memory_bytes=8 * 1024 * 1024)  # 8 MB
        sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG, policy=policy)
        
        code = 'data = "x" * (100 * 1024 * 1024)'  # Try to allocate 100 MB
        result = sandbox.execute(code)
        
        # Should either trap or handle gracefully
        assert result.memory_used_bytes <= policy.memory_bytes * 1.1  # 10% tolerance

class TestOutputCapping:
    """Verify stdout/stderr size limits prevent DoS."""
    
    def test_stdout_truncated_at_limit(self):
        """Large stdout should be capped per policy."""
        policy = ExecutionPolicy(stdout_max_bytes=1000)
        sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG, policy=policy)
        
        code = '10000.times { puts "x" * 100 }'
        result = sandbox.execute(code)
        
        assert len(result.stdout) <= 1000
        assert result.metadata.get("stdout_truncated") is True
```

### Binary Validation Tests

**File**: `tests/test_your_lang_binary.py`

```python
"""Tests for Your Language WASM binary integrity."""

import pytest
import subprocess
from pathlib import Path

def test_binary_exists():
    """Verify WASM binary is present."""
    binary_path = Path("bin/your_lang.wasm")
    assert binary_path.exists(), "Run scripts/fetch_your_lang.ps1 first"
    assert binary_path.stat().st_size > 1024, "Binary seems corrupted (too small)"

def test_binary_has_wasi_exports():
    """Verify binary exports required WASI symbols."""
    result = subprocess.run(
        ["wasm-objdump", "-x", "bin/your_lang.wasm"],
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode == 0:
        output = result.stdout
        assert "_start" in output, "Missing _start export"
        assert "memory" in output, "Missing memory export"

def test_binary_imports_wasi():
    """Verify binary imports WASI functions."""
    result = subprocess.run(
        ["wasm-objdump", "-x", "bin/your_lang.wasm"],
        capture_output=True,
        text=True,
        check=False
    )
    
    if result.returncode == 0:
        output = result.stdout
        assert "wasi_snapshot_preview1" in output, "Binary not targeting WASI"
```

---

## Performance Tuning

### Fuel Budget Calibration

**Goal**: Find optimal fuel budget that:
- Allows legitimate code to complete
- Prevents infinite loops within acceptable time
- Balances cost (WASM overhead) vs safety

**Methodology**:

```python
import time
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

# Benchmark suite: realistic workloads
benchmarks = {
    "hello_world": 'puts "Hello"',
    "loop_1k": "1000.times { |i| i * 2 }",
    "file_io": 'File.write("/app/test.txt", "data"); File.read("/app/test.txt")',
    "json_parse": 'require "json"; JSON.parse(\'{"key": "value"}\')',
}

for name, code in benchmarks.items():
    # Test with high fuel budget to measure actual consumption
    policy = ExecutionPolicy(fuel_budget=10_000_000_000)
    sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG, policy=policy)
    
    result = sandbox.execute(code)
    print(f"{name}: {result.fuel_consumed:,} instructions ({result.duration_ms:.2f} ms)")

# Output example:
# hello_world: 1,234,567 instructions (125.50 ms)
# loop_1k: 45,678,901 instructions (450.25 ms)
# file_io: 23,456,789 instructions (234.10 ms)
# json_parse: 12,345,678 instructions (123.45 ms)

# Set default budget: max(benchmark consumptions) * 10 (safety margin)
# Recommended: 500M - 2B instructions for general purpose code
```

### Memory Optimization

**Tuning Strategy**:

1. **Profile baseline usage**: Run empty code to measure runtime overhead
2. **Test typical workloads**: Measure peak memory for expected use cases
3. **Add safety margin**: 2-3x peak usage to prevent false positives

```python
from sandbox import create_sandbox, RuntimeType, ExecutionPolicy

# Profile baseline memory
policy = ExecutionPolicy(memory_bytes=256 * 1024 * 1024)  # 256 MB
sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG, policy=policy)

result = sandbox.execute("")  # Empty code
print(f"Baseline memory: {result.memory_used_bytes / 1024 / 1024:.2f} MB")

# Profile typical workload
code = """
data = Array.new(10000) { |i| i * 2 }
puts data.sum
"""
result = sandbox.execute(code)
print(f"Typical workload: {result.memory_used_bytes / 1024 / 1024:.2f} MB")

# Set limit: baseline + workload + margin
# Example: 8 MB (baseline) + 16 MB (workload) + 40 MB (margin) = 64 MB default
```

---

## Security Validation Checklist

Before releasing your runtime integration, verify all security boundaries:

### ✅ Filesystem Isolation

- [ ] Guest cannot read `/etc/passwd`, `/proc`, `/sys`, or other host paths
- [ ] Guest can only access files under `/app` (policy.guest_mount_path)
- [ ] Path traversal (`../../../etc/passwd`) is blocked
- [ ] Absolute paths outside `/app` are denied
- [ ] Symlinks cannot escape `/app` boundary

**Test**: `tests/test_your_lang_security.py::TestFilesystemIsolation`

### ✅ CPU Limits (Fuel)

- [ ] Infinite loops trigger OutOfFuel trap
- [ ] Fuel consumption is tracked and reported
- [ ] Trap reason is correctly classified
- [ ] Normal code completes within fuel budget

**Test**: `tests/test_your_lang_security.py::TestFuelExhaustion`

### ✅ Memory Limits

- [ ] Large allocations respect memory cap
- [ ] Memory exhaustion doesn't crash host
- [ ] Peak memory usage is reported accurately

**Test**: `tests/your_lang_security.py::TestMemoryLimits`

### ✅ I/O Limits

- [ ] Stdout truncated at `policy.stdout_max_bytes`
- [ ] Stderr truncated at `policy.stderr_max_bytes`
- [ ] Truncation flag is set in metadata
- [ ] Large output doesn't cause DoS

**Test**: `tests/test_your_lang_security.py::TestOutputCapping`

### ✅ Environment Isolation

- [ ] Host environment variables are not leaked
- [ ] Only whitelisted vars in `policy.env` are visible
- [ ] Sensitive vars (PATH, HOME) are sanitized

**Test**: `tests/test_your_lang_security.py::TestEnvironmentIsolation`

### ✅ Network Isolation

- [ ] No socket creation (WASI baseline doesn't expose networking)
- [ ] HTTP requests fail gracefully
- [ ] DNS lookups are unavailable

**Test**: `tests/test_your_lang_security.py::TestNetworkIsolation`

---

## Real-World Examples

### Example 1: Adding Ruby Runtime

**Binary Source**: WLR Ruby (https://github.com/webassemblylabs/webassembly-language-runtimes)

**Key Configuration**:
- File extension: `.rb`
- Argv: `["ruby", "/app/user_code.rb"]`
- Default fuel: 1.5B instructions (Ruby is slower than Python)
- Memory: 128 MB (includes stdlib overhead)

**Special Considerations**:
- Ruby `require` needs vendored gems in `/app/vendor/bundle`
- ENV vars: `RUBY_VERSION`, `GEM_PATH`

### Example 2: Adding Lua Runtime

**Binary Source**: Build from lua.org using wasi-sdk

**Key Configuration**:
- File extension: `.lua`
- Argv: `["lua", "/app/user_code.lua"]`
- Default fuel: 800M instructions (Lua is fast)
- Memory: 32 MB (minimal runtime)

**Special Considerations**:
- Lua C modules not supported (WASI limitation)
- Use pure-Lua libraries only

### Example 3: Adding PHP Runtime

**Binary Source**: WLR PHP (https://github.com/webassemblylabs/webassembly-language-runtimes)

**Key Configuration**:
- File extension: `.php`
- Argv: `["php", "/app/user_code.php"]`
- Default fuel: 2B instructions
- Memory: 256 MB (PHP is memory-hungry)

**Special Considerations**:
- Disable `dl()`, `exec()`, `system()` functions via php.ini
- Mount read-only php.ini in `/app/.php.ini`

---

## Troubleshooting

### Problem: WASM binary loads but immediately traps

**Symptoms**:
- `trapped=True` with `trap_reason="trap"`
- Empty stdout/stderr
- Fuel consumption is 0 or very low

**Diagnosis**:
```python
result = sandbox.execute("")  # Empty code
print(result.metadata)
# Look for trap_message
```

**Common Causes**:
1. **Missing WASI imports**: Binary expects WASI functions not provided by Wasmtime
   - **Fix**: Use newer wasi-sdk or update binary source
2. **Incompatible memory model**: Binary uses multi-memory (not supported)
   - **Fix**: Recompile with single linear memory
3. **Stack overflow on startup**: Binary's `_start` exceeds stack
   - **Fix**: Increase Wasmtime stack size or simplify initialization

### Problem: Fuel exhaustion on simple code

**Symptoms**:
- Hello world triggers OutOfFuel
- Fuel budget seems unreasonably low

**Diagnosis**:
```python
policy = ExecutionPolicy(fuel_budget=100_000_000_000)  # Very high
result = sandbox.execute('print("hi")')
print(f"Consumed: {result.fuel_consumed:,}")
```

**Common Causes**:
1. **Runtime initialization overhead**: Some languages load large stdlibs
   - **Fix**: Increase default budget or use stripped runtime
2. **Fuel accounting bug**: Wasmtime version mismatch
   - **Fix**: Update wasmtime-py to latest version
3. **Incorrect fuel units**: Mixing instructions with gas
   - **Fix**: Review Wasmtime fuel documentation

### Problem: Files not detected in delta

**Symptoms**:
- `result.files_created` is empty even though code creates files
- Manual inspection shows files exist in workspace

**Diagnosis**:
```python
# Check if file is excluded
print(sandbox.storage_adapter.PYTHON_CODE_FILENAME)  # Should match user code filename

# Check if file is actually created
import os
workspace_path = result.workspace_path
print(os.listdir(workspace_path))
```

**Common Causes**:
1. **Wrong filename**: Code writes to different path than expected
   - **Fix**: Update `_write_untrusted_code()` filename
2. **Timing issue**: File created after snapshot
   - **Fix**: Ensure snapshot happens before execution
3. **Permission issue**: File created but not readable by host
   - **Fix**: Check WASI directory permissions

### Problem: Memory limit not enforced

**Symptoms**:
- Code allocates more than `policy.memory_bytes`
- No trap or error

**Diagnosis**:
```python
policy = ExecutionPolicy(memory_bytes=1024 * 1024)  # 1 MB
sandbox = create_sandbox(runtime=RuntimeType.YOUR_LANG, policy=policy)
result = sandbox.execute('data = "x" * (10 * 1024 * 1024)')  # 10 MB
print(f"Used: {result.memory_used_bytes / 1024 / 1024} MB")
```

**Common Causes**:
1. **Wasmtime version doesn't support `set_limits`**:
   - **Fix**: Upgrade to wasmtime-py >= 24.0.0
2. **Runtime uses host allocator**: Language runtime bypasses WASM memory
   - **Fix**: Ensure runtime is pure WASM (no host FFI)
3. **Memory measured incorrectly**: Reporting module size instead of heap
   - **Fix**: Use `memory.data_len()` not `memory.size()`

---

## References

### Official Documentation

- **Wasmtime Python API**: https://docs.wasmtime.dev/api/wasmtime/
- **WASI Specification**: https://github.com/WebAssembly/WASI
- **wasi-sdk Toolchain**: https://github.com/WebAssembly/wasi-sdk
- **WLR Runtimes**: https://github.com/webassemblylabs/webassembly-language-runtimes

### Community Resources

- **WAPM Registry** (pre-built binaries): https://wapm.io/
- **Awesome WASM Runtimes**: https://github.com/appcypher/awesome-wasm-runtimes
- **WASI Tutorial**: https://github.com/bytecodealliance/wasmtime/blob/main/docs/WASI-tutorial.md

### LLM WASM Sandbox Internals

- **Architecture Overview**: `WASM_SANDBOX.md`
- **Project Conventions**: `.github/copilot-instructions.md`
- **Testing Guide**: `tests/README.md`
- **API Reference**: `README.md`

---

## Conclusion

Adding a new runtime to the LLM WASM sandbox requires:

1. **WASM Binary** with WASI support, `_start` export, fuel compatibility
2. **Runtime Sandbox Class** implementing `BaseSandbox` contract
3. **Host Function** following `run_untrusted_*` pattern in `host.py`
4. **Factory Integration** dispatching to your runtime in `create_sandbox()`
5. **Comprehensive Tests** covering functionality and security boundaries
6. **Performance Tuning** for fuel/memory defaults
7. **Security Validation** against filesystem, CPU, memory, I/O limits

By following this guide, your runtime will integrate seamlessly with the existing architecture while maintaining the sandbox's defense-in-depth security model.

For questions or contributions, see `CONTRIBUTING.md` or open a GitHub issue.
