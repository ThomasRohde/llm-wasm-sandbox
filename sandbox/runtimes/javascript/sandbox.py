"""JavaScriptSandbox: Type-safe orchestration layer for JavaScript WASM execution.

Provides JavaScriptSandbox class that wraps the low-level host.run_untrusted_javascript()
with type-safe inputs (ExecutionPolicy), structured logging, file change detection,
and Pydantic-based result models (SandboxResult).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sandbox.core.base import BaseSandbox
from sandbox.core.models import ExecutionPolicy, SandboxResult
from sandbox.host import run_untrusted_javascript


class JavaScriptSandbox(BaseSandbox):
    """Type-safe JavaScript sandbox implementation using QuickJS WASM runtime.

    Orchestrates JavaScript code execution by:
    1. Writing untrusted code to session workspace (user_code.js)
    2. Taking filesystem snapshots before execution (for delta detection)
    3. Delegating to low-level host.run_untrusted_javascript() for WASM execution
    4. Mapping raw results to typed SandboxResult with metrics and file changes
    5. Updating session metadata timestamps after execution
    6. Emitting structured log events for observability

    Security Model:
        - WASM memory isolation (bounds-checked linear memory)
        - WASI capability-based filesystem access (only /app directory)
        - Fuel metering for deterministic CPU limits
        - No network or subprocess capabilities
        - Environment variable whitelist only

    Attributes:
        wasm_binary_path: Path to QuickJS WASM binary (qjs-wasi.wasm)
        policy: ExecutionPolicy with validated resource limits
        session_id: UUIDv4 session identifier for workspace isolation
        workspace_root: Root directory containing all session workspaces
        workspace: Path to session-specific workspace directory (workspace_root / session_id)
        logger: SandboxLogger for structured event emission

    Example:
        Basic usage with default policy::

            from sandbox import create_sandbox, RuntimeType

            sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
            result = sandbox.execute('console.log("Hello, WASM!");')
            print(result.stdout)  # "Hello, WASM!\n"

        Custom resource limits::

            from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

            policy = ExecutionPolicy(
                fuel_budget=500_000_000,        # 500M instructions
                memory_bytes=32 * 1024 * 1024,  # 32 MB
                stdout_max_bytes=100_000        # 100 KB
            )
            sandbox = create_sandbox(
                runtime=RuntimeType.JAVASCRIPT,
                policy=policy
            )
            result = sandbox.execute('const x = 42; console.log(x);')

        Multi-turn session::

            # Turn 1: Generate data
            sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
            session_id = sandbox.session_id

            result1 = sandbox.execute('''
                const data = {count: 0};
                console.log(JSON.stringify(data));
            ''')

            # Turn 2: Reuse session (same workspace)
            sandbox = create_sandbox(
                session_id=session_id,
                runtime=RuntimeType.JAVASCRIPT
            )
            result2 = sandbox.execute('''
                const data = {count: 1};
                console.log(JSON.stringify(data));
            ''')
    """

    def __init__(
        self,
        wasm_binary_path: str,
        policy: ExecutionPolicy,
        session_id: str,
        workspace_root: Path,
        logger: Any = None
    ) -> None:
        """Initialize JavaScriptSandbox with WASM binary path and session config.

        Args:
            wasm_binary_path: Path to quickjs.wasm binary (e.g., "bin/quickjs.wasm")
            policy: ExecutionPolicy with validated limits
            session_id: UUIDv4 string identifying the session
            workspace_root: Root directory for all session workspaces
            logger: Optional SandboxLogger (created if None)
        """
        super().__init__(policy, session_id, workspace_root, logger)
        self.wasm_binary_path = wasm_binary_path

    def execute(self, code: str, **kwargs: Any) -> SandboxResult:
        """Execute untrusted JavaScript code in WASM sandbox with resource limits and session tracking.

        Workflow:
        1. Log execution start with policy details and session_id
        2. Write code to workspace/user_code.js
        3. Snapshot filesystem state for delta detection
        4. Execute via host.run_untrusted_javascript() with WASI isolation
        5. Measure execution duration and detect file changes
        6. Map raw result to typed SandboxResult with session_id in metadata
        7. Update session metadata timestamp
        8. Log execution complete with metrics

        Args:
            code: Untrusted JavaScript source code to execute
            **kwargs: Reserved for future extensions

        Returns:
            SandboxResult: Typed execution result with the following fields:
                - success (bool): Execution succeeded without errors
                - stdout (str): Standard output from console.log()
                - stderr (str): Standard error from exceptions/syntax errors
                - exit_code (int): Process exit code (0 = success)
                - duration_ms (float): Wall-clock execution time in milliseconds
                - fuel_consumed (int | None): WASM instruction count used
                - memory_used_bytes (int): Peak WASM linear memory usage
                - files_created (list[str]): Relative paths of files created during execution
                - files_modified (list[str]): Relative paths of files modified during execution
                - workspace_path (str): Absolute path to session workspace directory
                - metadata (dict): Additional execution details (runtime, limits, session_id, etc.)

        Raises:
            FileNotFoundError: If WASM binary not found at wasm_binary_path

        Example:
            Basic execution::

                result = sandbox.execute('console.log("test");')
                print(result.stdout)  # "test\n"
                print(result.success)  # True
                print(result.fuel_consumed)  # e.g., 1234567

            Error handling::

                result = sandbox.execute('throw new Error("fail");')
                print(result.success)  # False
                print(result.stderr)  # Contains error message
                print(result.exit_code)  # Non-zero

            Syntax error::

                result = sandbox.execute('const x = ;')
                print(result.success)  # False
                print(result.stderr)  # Contains parse error

            Fuel exhaustion::

                result = sandbox.execute('while(true) {}')
                print(result.success)  # False
                print(result.metadata['trapped'])  # True
                print(result.metadata['trap_reason'])  # "out_of_fuel"
        """
        wasm_path = Path(self.wasm_binary_path)
        if not wasm_path.is_file():
            raise FileNotFoundError(f"WASM binary not found at {wasm_path}")

        # Log execution start with session_id
        self.logger.log_execution_start(
            runtime="javascript",
            policy=self.policy,
            session_id=self.session_id
        )

        # Write code to workspace
        user_code_path = self._write_untrusted_code(code)

        # Snapshot filesystem before execution
        before_files = self._snapshot_workspace(exclude=user_code_path)

        # Measure execution duration
        start_time = time.perf_counter()

        # Delegate to low-level host execution
        try:
            raw_result = run_untrusted_javascript(
                wasm_path=str(wasm_path),
                workspace_dir=str(self.workspace),
                policy=self.policy
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
                logs_dir="",
                exit_code=1,
                trapped=True,
                trap_reason=trap_reason
            )

        duration_seconds = time.perf_counter() - start_time

        # Detect file changes
        files_created, files_modified = self._detect_file_delta(
            before_files,
            exclude=user_code_path
        )

        # Map to typed SandboxResult (always include session_id)
        result = self._map_to_sandbox_result(
            raw_result,
            duration_seconds,
            files_created,
            files_modified,
            session_id=self.session_id
        )

        # Update session timestamp after successful execution
        self._update_session_timestamp()

        # Log execution complete with session_id
        self.logger.log_execution_complete(result, runtime="javascript", session_id=self.session_id)

        return result

    def validate_code(self, code: str) -> bool:
        """Validate JavaScript code syntax without executing it.

        Note: This implementation defers validation to runtime execution.
        Adding a JavaScript parser (e.g., esprima) would enable syntax
        checking without execution, but is not critical for v1 since
        execution captures syntax errors in stderr.

        Args:
            code: JavaScript source code to validate

        Returns:
            bool: Always True (syntax validation deferred to runtime)

        Example:
            >>> sandbox.validate_code('console.log("valid");')
            True
            >>> sandbox.validate_code('const x = ;')  # Syntax error
            True  # Deferred to runtime - execute() will catch it

        Future Enhancement:
            Install esprima or similar parser for pre-execution validation::

                try:
                    import esprima
                    esprima.parseScript(code)
                    return True
                except esprima.Error:
                    return False
        """
        # TODO: Consider adding esprima or similar parser for pre-execution validation
        # For v1, we defer validation to runtime execution where syntax errors
        # will be caught and reported in stderr
        return True

    def _write_untrusted_code(self, code: str) -> Path:
        """Write untrusted JavaScript code to workspace/user_code.js.

        Args:
            code: JavaScript source code to write

        Returns:
            Path to written user_code.js file
        """
        self.workspace.mkdir(parents=True, exist_ok=True)

        user_code_path = self.workspace / "user_code.js"
        user_code_path.write_text(code, encoding="utf-8")
        return user_code_path

    def _snapshot_workspace(self, exclude: Path) -> dict[Path, tuple[float, int]]:
        """Take snapshot of workspace files before execution.

        Captures modification time and size for all files except the excluded
        user_code.js to enable file delta detection.

        Args:
            exclude: Path to user_code.js (don't track this file)

        Returns:
            Dict mapping file paths to (mtime, size) tuples
        """
        snapshot = {}

        if self.workspace.exists():
            for file_path in self.workspace.rglob('*'):
                if file_path.is_file() and file_path != exclude:
                    try:
                        stat = file_path.stat()
                        snapshot[file_path] = (stat.st_mtime, stat.st_size)
                    except (OSError, PermissionError):
                        pass

        return snapshot

    def _detect_file_delta(
        self,
        before_files: dict[Path, tuple[float, int]],
        exclude: Path
    ) -> tuple[list[str], list[str]]:
        """Detect files created or modified during execution.

        Compares post-execution filesystem state to pre-execution snapshot
        to identify new files and modified files. Useful for LLM feedback
        about what the code did.

        Args:
            before_files: Pre-execution snapshot from _snapshot_workspace()
            exclude: Path to user_code.js (don't report this file)

        Returns:
            Tuple of (files_created, files_modified) with relative paths
        """
        files_created = []
        files_modified = []

        if self.workspace.exists():
            for file_path in self.workspace.rglob('*'):
                if file_path.is_file() and file_path != exclude:
                    try:
                        rel_path = file_path.relative_to(self.workspace).as_posix()

                        if file_path not in before_files:
                            files_created.append(rel_path)
                        else:
                            old_mtime, old_size = before_files[file_path]
                            stat = file_path.stat()
                            if stat.st_mtime != old_mtime or stat.st_size != old_size:
                                files_modified.append(rel_path)
                    except (OSError, PermissionError):
                        pass

        return files_created, files_modified

    def _map_to_sandbox_result(
        self,
        raw_result: Any,
        duration_seconds: float,
        files_created: list[str],
        files_modified: list[str],
        session_id: str | None = None
    ) -> SandboxResult:
        """Map host.SandboxResult to core.SandboxResult Pydantic model.

        Converts the raw dict-like result from host.run_untrusted_javascript()
        to the typed Pydantic SandboxResult model with additional fields
        for duration, file changes, and workspace path.

        Args:
            raw_result: Result from host.run_untrusted_javascript()
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

        metadata = {
            "runtime": "javascript",
            "fuel_budget": self.policy.fuel_budget,
            "memory_limit_bytes": self.policy.memory_bytes,
            "memory_pages": raw_result.mem_pages,
            "logs_dir": raw_result.logs_dir,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "exit_code": exit_code,
            "trapped": trapped,
        }

        # Include session_id in metadata if provided
        if session_id is not None:
            metadata["session_id"] = session_id

        if trap_reason is not None:
            metadata["trap_reason"] = trap_reason
        if trap_message is not None:
            metadata["trap_message"] = trap_message

        # Determine success based on exit code, traps, and stderr contents
        success = self._determine_success(
            exit_code=exit_code,
            trapped=trapped,
            stderr=raw_result.stderr
        )

        return SandboxResult(
            success=success,
            stdout=raw_result.stdout,
            stderr=raw_result.stderr,
            exit_code=exit_code,
            duration_ms=duration_seconds * 1000,  # Convert to milliseconds
            fuel_consumed=raw_result.fuel_consumed,
            memory_used_bytes=raw_result.mem_len,
            files_created=files_created,
            files_modified=files_modified,
            workspace_path=str(self.workspace),
            metadata=metadata
        )

    @staticmethod
    def _determine_success(exit_code: int, trapped: bool, stderr: str) -> bool:
        """Determine execution success based on exit codes, traps, and stderr content."""
        if trapped:
            return False

        if exit_code != 0:
            return False

        # JavaScript-specific error patterns
        lowered = (stderr or "").lower()
        failure_tokens = (
            "error",
            "exception",
            "outoffuel",
            "referenceerror",
            "syntaxerror",
            "typeerror",
            "rangeerror"
        )
        return not any(token in lowered for token in failure_tokens)

    def _update_session_timestamp(self) -> None:
        """Update the updated_at timestamp in session metadata after execution.

        Reads the .metadata.json file in the session workspace, updates the
        updated_at field to current UTC time, and writes it back. This tracks
        session activity for automated pruning. Handles missing/corrupted
        metadata gracefully to avoid execution failures.
        """
        import json
        from datetime import UTC, datetime

        metadata_path = self.workspace / ".metadata.json"

        if not metadata_path.exists():
            # Legacy session without metadata - skip silently
            return

        try:
            data = json.loads(metadata_path.read_text())
            data["updated_at"] = datetime.now(UTC).isoformat()
            metadata_path.write_text(json.dumps(data, indent=2))

            # Log structured event
            self.logger.log_session_metadata_updated(
                session_id=self.session_id,
                timestamp=data["updated_at"]
            )
        except (json.JSONDecodeError, OSError) as e:
            # Log warning but don't fail execution
            import sys
            print(
                f"Warning: Failed to update session timestamp for {self.session_id}: {e}",
                file=sys.stderr
            )
