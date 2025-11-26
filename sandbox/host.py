"""WASM sandbox host layer for executing untrusted Python code.

This module provides the core security sandbox using Wasmtime to run CPython
compiled to WASM (WLR AIO binary). It implements multi-layered defense through:
- WASM memory safety and sandboxing
- WASI capability-based filesystem isolation
- Deterministic execution limits via fuel budgeting
- Memory caps to prevent resource exhaustion

The sandbox is designed for LLM-generated code execution where untrusted
code must be isolated from the host system.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import tempfile
from pathlib import Path

from wasmtime import (
    Config,
    DirPerms,
    Engine,
    ExitTrap,
    FilePerms,
    Linker,
    Module,
    Store,
    Trap,
    WasiConfig,
)

from .core.errors import SandboxExecutionError
from .core.models import ExecutionPolicy


class SandboxResult:
    """Container for sandbox execution results and metrics.

    Attributes:
        stdout: Captured standard output from the guest (capped to policy limit)
        stderr: Captured standard error from the guest (capped to policy limit)
        fuel_consumed: Number of WASM instructions executed (None if unavailable)
        mem_pages: Number of 64 KiB WASM memory pages allocated
        mem_len: Total memory size in bytes
        logs_dir: Temporary directory containing full stdout/stderr logs (None if cleaned up)
    """

    def __init__(
        self,
        stdout: str,
        stderr: str,
        fuel_consumed: int | None,
        mem_pages: int,
        mem_len: int,
        logs_dir: str | None,
        exit_code: int | None = None,
        trapped: bool = False,
        trap_reason: str | None = None,
        trap_message: str | None = None,
        stdout_truncated: bool = False,
        stderr_truncated: bool = False,
    ):
        self.stdout = stdout
        self.stderr = stderr
        self.fuel_consumed = fuel_consumed
        self.mem_pages = mem_pages
        self.mem_len = mem_len
        self.logs_dir = logs_dir
        self.exit_code = exit_code
        self.trapped = trapped
        self.trap_reason = trap_reason
        self.trap_message = trap_message
        self.stdout_truncated = stdout_truncated
        self.stderr_truncated = stderr_truncated


def run_untrusted_python(
    wasm_path: str = "bin/python.wasm",
    workspace_dir: str | None = None,
    policy: ExecutionPolicy | None = None,
) -> SandboxResult:
    """Execute untrusted Python code in a WASM sandbox with security constraints.

    Creates a Wasmtime environment with WASI capabilities, loads the CPython WASM
    binary, and executes it with strict resource limits. The guest process sees only
    preopened directories (capability-based filesystem isolation) and is limited by
    fuel budget (instruction count) and memory caps.

    Security boundaries enforced:
    - Filesystem: Only preopened paths visible to guest (no ambient authority)
    - CPU: Fuel budget provides deterministic execution limit
    - Memory: Hard cap on WASM linear memory growth
    - I/O: Stdout/stderr captured with size limits to prevent DoS

    Args:
        wasm_path: Path to the CPython WASM binary (WLR AIO build).
        workspace_dir: Override for the writable workspace directory mounted at
            guest_mount_path. If None, uses policy default (mount_host_dir).
        policy: ExecutionPolicy to enforce for this execution. If None, uses
            the default ExecutionPolicy() values.

    Returns:
        SandboxResult containing captured outputs, resource consumption metrics,
        and path to full logs.

    Raises:
        FileNotFoundError: If wasm_path or required directories don't exist.
        wasmtime.WasmtimeError: If WASM module fails to load or link.
        OSError: If temporary directory creation fails.
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

    tmp = tempfile.mkdtemp(prefix="wasm-python-")
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

        # Handle additional read-only mounts (e.g., external files at /external)
        for mount_host_path, mount_guest_path in policy.additional_readonly_mounts:
            mount_abs_path = os.path.abspath(mount_host_path)
            if os.path.exists(mount_abs_path):
                readonly_mount_dir, temp_mount_root = _prepare_readonly_data_dir(mount_abs_path)
                cleanup_paths.append(temp_mount_root)
                wasi.preopen_dir(
                    readonly_mount_dir,
                    mount_guest_path,
                    DirPerms.READ_ONLY,
                    FilePerms.READ_ONLY,
                )

        wasi.argv = tuple(policy.argv)
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
            # Normal WASI proc_exit - use exit code to determine success
            exit_code = trap.code
            if trap.code != 0:
                trap_message = str(trap)
                trap_reason = "proc_exit"
        except Trap as trap:
            # OutOfFuel or other WASM traps
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
            # Ensure OutOfFuel is visible to callers even if the guest wrote nothing
            trap_notice = "Execution trapped: OutOfFuel"
            if trap_notice not in stderr:
                stderr = f"{stderr.rstrip()}\n{trap_notice}".strip()
        elif trap_reason is not None and trap_message:
            trap_notice = f"Execution trapped: {trap_message}"
            if trap_notice not in stderr:
                stderr = f"{stderr.rstrip()}\n{trap_notice}".strip()

        # Re-apply caps if we appended trap notices
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


def _classify_trap(message: str | None) -> str | None:
    """Classify trap reason based on message content for easier diagnostics."""
    if message is None:
        return None

    lowered = message.lower()
    if "fuel" in lowered or "out of fuel" in lowered or "exhausted fuel" in lowered:
        return "out_of_fuel"
    if "memory" in lowered:
        return "memory_limit"
    return "trap"


def _enforce_cap(text: str, cap: int, already_truncated: bool) -> tuple[str, bool]:
    """Ensure text does not exceed cap bytes while tracking truncation."""
    data = text.encode("utf-8", errors="replace")
    if len(data) <= cap:
        return text, already_truncated

    truncated_text = data[:cap].decode("utf-8", errors="replace")
    return truncated_text, True


def _prepare_readonly_data_dir(source_dir: str) -> tuple[str, str]:
    """Copy data directory to a temporary, read-only location for mounting."""
    source_path = Path(source_dir).resolve()
    if not source_path.exists() or not source_path.is_dir():
        raise FileNotFoundError(
            f"mount_data_dir '{source_dir}' does not exist or is not a directory"
        )

    temp_root = Path(tempfile.mkdtemp(prefix="sandbox-data-"))
    readonly_root = temp_root / "data"

    try:
        shutil.copytree(source_path, readonly_root)
        _make_tree_readonly(readonly_root)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise

    return str(readonly_root), str(temp_root)


def _make_tree_readonly(path: Path) -> None:
    """Recursively strip write permissions from a directory tree."""

    def _read_only_mode(mode: int) -> int:
        return mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH

    for root, _dirs, files in os.walk(path):
        root_path = Path(root)
        with contextlib.suppress(OSError):
            root_path.chmod(_read_only_mode(root_path.stat().st_mode))

        for name in files:
            file_path = root_path / name
            with contextlib.suppress(OSError):
                file_path.chmod(_read_only_mode(file_path.stat().st_mode))


def run_untrusted_javascript(
    wasm_path: str = "bin/quickjs.wasm",
    workspace_dir: str | None = None,
    policy: ExecutionPolicy | None = None,
) -> SandboxResult:
    """Execute untrusted JavaScript code in a WASM sandbox with security constraints.

    Creates a Wasmtime environment with WASI capabilities, loads the QuickJS WASM
    binary, and executes it with strict resource limits. The guest process sees only
    preopened directories (capability-based filesystem isolation) and is limited by
    fuel budget (instruction count) and memory caps.

    Security boundaries enforced:
    - Filesystem: Only preopened paths visible to guest (no ambient authority)
    - CPU: Fuel budget provides deterministic execution limit
    - Memory: Hard cap on WASM linear memory growth
    - I/O: Stdout/stderr captured with size limits to prevent DoS

    Args:
        wasm_path: Path to the QuickJS WASM binary (qjs-wasi.wasm).
        workspace_dir: Override for the writable workspace directory mounted at
            guest_mount_path. If None, uses policy default (mount_host_dir).
        policy: ExecutionPolicy to enforce for this execution. If None, uses
            the default ExecutionPolicy() values.

    Returns:
        SandboxResult containing captured outputs, resource consumption metrics,
        and path to full logs.

    Raises:
        FileNotFoundError: If wasm_path or required directories don't exist.
        wasmtime.WasmtimeError: If WASM module fails to load or link.
        OSError: If temporary directory creation fails.
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

    tmp = tempfile.mkdtemp(prefix="wasm-javascript-")
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

        # Handle additional read-only mounts (e.g., external files at /external)
        for mount_host_path, mount_guest_path in policy.additional_readonly_mounts:
            mount_abs_path = os.path.abspath(mount_host_path)
            if os.path.exists(mount_abs_path):
                readonly_mount_dir, temp_mount_root = _prepare_readonly_data_dir(mount_abs_path)
                cleanup_paths.append(temp_mount_root)
                wasi.preopen_dir(
                    readonly_mount_dir,
                    mount_guest_path,
                    DirPerms.READ_ONLY,
                    FilePerms.READ_ONLY,
                )

        # JavaScript-specific argv: ["qjs", "--std", "/app/user_code.js"]
        # --std: Initialize std and os modules as global objects
        # Note: We use global std/os instead of ES6 module imports because
        # the QuickJS-NG WASI binary's module loader doesn't resolve builtin
        # module names like "std" and "os" when using -m flag.
        js_argv = ["qjs", "--std", f"{policy.guest_mount_path}/user_code.js"]
        wasi.argv = tuple(js_argv)

        # Minimal env for JavaScript (no NODE_ENV needed for QuickJS)
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
            # Normal WASI proc_exit - use exit code to determine success
            exit_code = trap.code
            if trap.code != 0:
                trap_message = str(trap)
                trap_reason = "proc_exit"
        except Trap as trap:
            # OutOfFuel or other WASM traps
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
            # Ensure OutOfFuel is visible to callers even if the guest wrote nothing
            trap_notice = "Execution trapped: OutOfFuel"
            if trap_notice not in stderr:
                stderr = f"{stderr.rstrip()}\n{trap_notice}".strip()
        elif trap_reason is not None and trap_message:
            trap_notice = f"Execution trapped: {trap_message}"
            if trap_notice not in stderr:
                stderr = f"{stderr.rstrip()}\n{trap_notice}".strip()

        # Re-apply caps if we appended trap notices
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
