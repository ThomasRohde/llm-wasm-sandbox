"""PythonSandbox: Type-safe orchestration layer for Python WASM execution.

Provides PythonSandbox class that wraps the low-level host.run_untrusted_python()
with type-safe inputs (ExecutionPolicy), structured logging, file change detection,
and Pydantic-based result models (SandboxResult).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sandbox.core.base import BaseSandbox
from sandbox.core.models import ExecutionPolicy, SandboxResult
from sandbox.host import run_untrusted_python

if TYPE_CHECKING:
    from sandbox.core.storage import StorageAdapter

# Prepended to user code so LLM-generated code can use vendored packages
# without needing to know about the /data/site-packages read-only WASI mount point
INJECTED_SETUP = """import sys
if '/data/site-packages' not in sys.path:
    sys.path.insert(0, '/data/site-packages')

"""


class PythonSandbox(BaseSandbox):
    """Type-safe Python sandbox implementation using CPython WASM runtime.

    Orchestrates Python code execution by:
    1. Writing untrusted code to session workspace with optional package setup injection
    2. Taking filesystem snapshots before execution (for delta detection)
    3. Delegating to low-level host.run_untrusted_python() for WASM execution
    4. Mapping raw results to typed SandboxResult with metrics and file changes
    5. Updating session metadata timestamps after execution
    6. Emitting structured log events for observability

    Attributes:
        wasm_binary_path: Path to CPython WASM binary (WLR AIO artifact)
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
        auto_persist_globals: bool = False,
    ) -> None:
        """Initialize PythonSandbox with WASM binary path and session config.

        Args:
            wasm_binary_path: Path to python.wasm binary (e.g., "bin/python.wasm")
            policy: ExecutionPolicy with validated limits
            session_id: UUIDv4 string identifying the session
            storage_adapter: StorageAdapter for workspace operations
            logger: Optional SandboxLogger (created if None)
            auto_persist_globals: If True, automatically wrap code with state save/restore
        """
        super().__init__(policy, session_id, storage_adapter, logger)
        self.wasm_binary_path = wasm_binary_path
        self.auto_persist_globals = auto_persist_globals

    def execute(self, code: str, inject_setup: bool = True, **kwargs: Any) -> SandboxResult:
        """Execute untrusted Python code in WASM sandbox with resource limits and session tracking.

        Workflow:
        1. Log execution start with policy details and session_id
        2. Write code to workspace/user_code.py (with optional sys.path setup)
        3. Snapshot filesystem state for delta detection
        4. Execute via host.run_untrusted_python() with WASI isolation
        5. Measure execution duration and detect file changes
        6. Map raw result to typed SandboxResult with session_id in metadata
        7. Update session metadata timestamp
        8. Log execution complete with metrics

        Args:
            code: Untrusted Python source code to execute
            inject_setup: If True, prepend sys.path setup for vendored packages
            **kwargs: Reserved for future extensions

        Returns:
            SandboxResult with outputs, metrics, file deltas, logs path, and session_id
        """
        wasm_path = Path(self.wasm_binary_path)
        if not wasm_path.is_file():
            raise FileNotFoundError(f"WASM binary not found at {wasm_path}")

        # Log execution start with session_id
        self.logger.log_execution_start(
            runtime="python",
            policy=self.policy,
            session_id=self.session_id,
            inject_setup=inject_setup,
        )

        # Auto-wrap code with state persistence if enabled
        if self.auto_persist_globals:
            from sandbox.state import wrap_stateful_code

            code = wrap_stateful_code(code)

        # Write code to workspace
        user_code_path = self._write_untrusted_code(code, inject_setup)

        # Snapshot filesystem before execution
        before_files = self._snapshot_workspace(exclude=user_code_path)

        # Measure execution duration
        start_time = time.perf_counter()

        # Delegate to low-level host execution
        try:
            raw_result = run_untrusted_python(
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
        self.logger.log_execution_complete(result, runtime="python", session_id=self.session_id)

        return result

    def validate_code(self, code: str) -> bool:
        """Validate Python code syntax without executing it.

        Uses Python's compile() builtin to parse code and check for syntax
        errors. Does not execute the code or import any modules, making this
        safe for untrusted input.

        Args:
            code: Python source code to validate

        Returns:
            True if syntax is valid, False if syntax errors exist
        """
        try:
            compile(code, "<sandbox>", "exec")
            return True
        except SyntaxError:
            return False

    def _write_untrusted_code(self, code: str, inject_setup: bool) -> str:
        """Write untrusted Python code to workspace via storage adapter.

        Args:
            code: Python source code to write
            inject_setup: If True, prepend sys.path setup for vendored packages

        Returns:
            Relative path to written user_code.py file
        """
        final_code = INJECTED_SETUP + code if inject_setup else code

        filename = self.storage_adapter.PYTHON_CODE_FILENAME
        self.storage_adapter.write_file(self.session_id, filename, final_code.encode("utf-8"))
        return filename

    def _snapshot_workspace(self, exclude: str) -> dict[str, float]:
        """Take snapshot of workspace files before execution.

        Uses storage adapter's get_workspace_snapshot for optimal performance
        (disk: stat all files, memory: track dict, cloud: use versioning).

        Args:
            exclude: Relative path to user_code.py (don't track this file)

        Returns:
            Dict mapping relative paths to modification timestamps
        """
        snapshot = self.storage_adapter.get_workspace_snapshot(self.session_id)
        # Remove excluded file from snapshot
        snapshot.pop(exclude, None)
        return snapshot

    def _detect_file_delta(
        self, before_files: dict[str, float], exclude: str
    ) -> tuple[list[str], list[str]]:
        """Detect files created or modified during execution.

        Uses storage adapter's detect_file_changes to compare snapshots.
        Each adapter can optimize this (disk: compare mtimes, memory: track
        changes, cloud: use versioning).

        Args:
            before_files: Pre-execution snapshot from _snapshot_workspace()
            exclude: Relative path to user_code.py (don't report this file)

        Returns:
            Tuple of (files_created, files_modified) with relative paths
        """
        # Get current snapshot
        after_files = self.storage_adapter.get_workspace_snapshot(self.session_id)

        # Detect changes via adapter
        files_created, files_modified = self.storage_adapter.detect_file_changes(
            self.session_id, before_files, after_files
        )

        # Filter out excluded file
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

        Converts the raw dict-like result from host.run_untrusted_python()
        to the typed Pydantic SandboxResult model with additional fields
        for duration, file changes, and workspace path.

        Args:
            raw_result: Result from host.run_untrusted_python()
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

        # Default exit_code if not provided by host
        if exit_code is None:
            exit_code = 1 if trapped else 0

        # Enhance stderr with helpful package import error messages
        enhanced_stderr = self._enhance_package_error_message(raw_result.stderr)

        metadata = {
            "memory_pages": raw_result.mem_pages,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "exit_code": exit_code,
            "trapped": trapped,
        }

        if raw_result.logs_dir:
            metadata["logs_dir"] = raw_result.logs_dir

        # Include session_id in metadata if provided
        if session_id is not None:
            metadata["session_id"] = session_id

        if trap_reason is not None:
            metadata["trap_reason"] = trap_reason
        if trap_message is not None:
            metadata["trap_message"] = trap_message

        # Add error guidance if execution failed
        if exit_code != 0 or trapped:
            from sandbox.core.error_templates import get_error_guidance

            error_guidance = get_error_guidance(
                trap_message=trap_message,
                stderr=enhanced_stderr,
                language="python",
                fuel_consumed=raw_result.fuel_consumed,
                fuel_budget=int(self.policy.fuel_budget),
                memory_used=raw_result.mem_len,
                memory_limit=int(self.policy.memory_bytes),
            )
            if error_guidance:
                metadata["error_guidance"] = error_guidance

        # Add fuel analysis for all executions
        if raw_result.fuel_consumed is not None:
            from sandbox.core.fuel_patterns import analyze_fuel_usage

            fuel_analysis = analyze_fuel_usage(
                consumed=raw_result.fuel_consumed,
                budget=int(self.policy.fuel_budget),
                stderr=enhanced_stderr,
                is_cached_import=False,
            )
            metadata["fuel_analysis"] = fuel_analysis

        # Determine success based on exit code, traps, and stderr contents
        success = self._determine_success(
            exit_code=exit_code, trapped=trapped, stderr=enhanced_stderr
        )

        return SandboxResult(
            success=success,
            stdout=raw_result.stdout,
            stderr=enhanced_stderr,
            exit_code=exit_code,
            duration_ms=duration_seconds * 1000,  # Convert to milliseconds
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

        lowered = (stderr or "").lower()
        failure_tokens = ("traceback", "exception", "outoffuel", "memoryerror")
        return not any(token in lowered for token in failure_tokens)

    @staticmethod
    def _enhance_package_error_message(stderr: str) -> str:
        """Enhance ModuleNotFoundError messages with helpful vendor package guidance.

        Detects import errors for packages that exist in vendor/site-packages and
        provides actionable feedback about correct sys.path setup.

        Args:
            stderr: Original stderr output from code execution

        Returns:
            Enhanced stderr with helpful hints appended (or original if no relevant errors)
        """
        if not stderr or "ModuleNotFoundError" not in stderr:
            return stderr

        # List of vendored packages (matches what's in vendor/site-packages)
        vendored_packages = {
            "openpyxl",
            "xlsxwriter",
            "pypdf2",
            "pdfminer",
            "odfpy",
            "mammoth",
            "tabulate",
            "jinja2",
            "markupsafe",
            "markdown",
            "dateutil",
            "attr",
            "attrs",
            "certifi",
            "charset_normalizer",
            "idna",
            "urllib3",
            "six",
            "tomli",
        }

        # Extract module name from error message
        # Pattern: "ModuleNotFoundError: No module named 'package_name'"
        import re

        match = re.search(r"No module named '([^']+)'", stderr)
        if not match:
            return stderr

        module_name = match.group(1).split(".")[0].lower()  # Get base package name

        # Check if this is a vendored package
        if module_name not in vendored_packages:
            return stderr

        # Check if user tried the wrong path
        wrong_path_used = (
            "/app/site-packages" in stderr or "sys.path.insert(0, '/app/site-packages')" in stderr
        )

        # Build helpful message
        hint = "\n\n" + "=" * 70 + "\n"
        hint += "📦 PACKAGE IMPORT HELP\n"
        hint += "=" * 70 + "\n"
        hint += f"The package '{module_name}' IS available in the sandbox!\n\n"

        if wrong_path_used:
            hint += "❌ ERROR: You used the WRONG path: /app/site-packages\n\n"
            hint += "✅ SOLUTION: Use the CORRECT path: /data/site-packages\n\n"
        else:
            hint += "It looks like you forgot to add vendored packages to sys.path.\n\n"

        hint += "Add this at the START of your code:\n"
        hint += "    import sys\n"
        hint += "    sys.path.insert(0, '/data/site-packages')\n\n"
        hint += "Then your import will work:\n"
        hint += f"    import {module_name}\n"
        hint += "=" * 70 + "\n"

        return stderr + hint

    def _update_session_timestamp(self) -> None:
        """Update the updated_at timestamp in session metadata after execution.

        Uses storage adapter's update_session_timestamp method to refresh the
        updated_at field to current UTC time. This tracks session activity for
        automated pruning. Handles missing/corrupted metadata gracefully.
        """
        try:
            self.storage_adapter.update_session_timestamp(self.session_id)

            # Log structured event
            metadata = self.storage_adapter.read_metadata(self.session_id)
            self.logger.log_session_metadata_updated(
                session_id=self.session_id, timestamp=metadata.updated_at
            )
        except Exception as e:
            # Log warning but don't fail execution
            import sys

            print(
                f"Warning: Failed to update session timestamp for {self.session_id}: {e}",
                file=sys.stderr,
            )
