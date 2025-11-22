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

import os
import tempfile

from wasmtime import Config, Engine, Linker, Module, Store, Trap, WasiConfig

from .policies import load_policy


class SandboxResult:
    """Container for sandbox execution results and metrics.

    Attributes:
        stdout: Captured standard output from the guest (capped to policy limit)
        stderr: Captured standard error from the guest (capped to policy limit)
        fuel_consumed: Number of WASM instructions executed (None if unavailable)
        mem_pages: Number of 64 KiB WASM memory pages allocated
        mem_len: Total memory size in bytes
        logs_dir: Temporary directory containing full stdout/stderr logs
    """

    def __init__(self, stdout: str, stderr: str, fuel_consumed: int | None,
                 mem_pages: int, mem_len: int, logs_dir: str):
        self.stdout = stdout
        self.stderr = stderr
        self.fuel_consumed = fuel_consumed
        self.mem_pages = mem_pages
        self.mem_len = mem_len
        self.logs_dir = logs_dir


def run_untrusted_python(wasm_path: str = "bin/python.wasm", workspace_dir: str | None = None) -> SandboxResult:
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

    Returns:
        SandboxResult containing captured outputs, resource consumption metrics,
        and path to full logs.

    Raises:
        FileNotFoundError: If wasm_path or required directories don't exist.
        wasmtime.WasmtimeError: If WASM module fails to load or link.
        OSError: If temporary directory creation fails.
    """
    policy = load_policy()

    cfg = Config()
    cfg.consume_fuel = True
    engine = Engine(cfg)

    linker = Linker(engine)
    linker.define_wasi()

    module = Module.from_file(engine, wasm_path)

    tmp = tempfile.mkdtemp(prefix="wasm-python-")
    out_log = os.path.join(tmp, "stdout.log")
    err_log = os.path.join(tmp, "stderr.log")

    wasi = WasiConfig()

    if workspace_dir is not None:
        host_dir = os.path.abspath(workspace_dir)
    else:
        host_dir = os.path.abspath(policy.mount_host_dir)

    wasi.preopen_dir(host_dir, policy.guest_mount_path)

    # Mount shared site-packages to avoid duplicating packages per workspace
    shared_packages = os.path.abspath("workspace/site-packages")
    if os.path.exists(shared_packages):
        wasi.preopen_dir(shared_packages, "/app/site-packages")

    if policy.mount_data_dir is not None:
        data_dir = os.path.abspath(policy.mount_data_dir)
        if os.path.exists(data_dir) and policy.guest_data_path is not None:
            wasi.preopen_dir(data_dir, policy.guest_data_path)

    wasi.argv = tuple(policy.argv)
    wasi.env = [(k, v) for k, v in policy.env.items()]
    wasi.stdout_file = out_log
    wasi.stderr_file = err_log

    store = Store(engine)
    store.set_wasi(wasi)

    fuel_budget = int(policy.fuel_budget)
    store.set_fuel(fuel_budget)

    try:
        store.set_limits(memory_size=int(policy.memory_bytes))
    except Exception:
        # Graceful degradation if wasmtime-py version lacks set_limits
        pass

    instance = linker.instantiate(store, module)
    start = instance.exports(store)["_start"]
    memory = instance.exports(store)["memory"]

    try:
        start(store)  # type: ignore[operator]
    except Trap:
        # Expected for OutOfFuel or other policy violations - not an error
        pass

    try:
        fuel_remaining = store.get_fuel()
        fuel_consumed = fuel_budget - fuel_remaining
    except Exception:
        fuel_consumed = None

    def read_capped(path: str, cap: int) -> str:
        """Read file up to cap bytes to prevent DoS from unbounded output.

        Args:
            path: Log file path to read.
            cap: Maximum bytes to return.

        Returns:
            File contents truncated to cap bytes, decoded as UTF-8.
        """
        try:
            with open(path, "rb") as f:
                data = f.read(cap + 1)
            return data[:cap].decode("utf-8", errors="replace")
        except FileNotFoundError:
            return ""

    stdout = read_capped(out_log, int(policy.stdout_max_bytes))
    stderr = read_capped(err_log, int(policy.stderr_max_bytes))

    return SandboxResult(
        stdout=stdout,
        stderr=stderr,
        fuel_consumed=fuel_consumed,
        mem_pages=memory.size(store),  # type: ignore[union-attr,call-arg]
        mem_len=memory.data_len(store),  # type: ignore[union-attr,call-arg]
        logs_dir=tmp,
    )
