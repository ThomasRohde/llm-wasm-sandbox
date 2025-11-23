"""Abstract base class for sandbox runtime implementations.

Provides BaseSandbox ABC that defines the contract for all sandbox runtimes
(Python, JavaScript, etc.). Each runtime must implement execute() and validate_code()
methods while sharing common initialization, logging, and metrics tracking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sandbox.core.logging import SandboxLogger
    from sandbox.core.models import ExecutionPolicy, SandboxResult
    from sandbox.core.storage import StorageAdapter


class BaseSandbox(ABC):
    """Abstract base class for sandbox runtime implementations.

    Defines the contract that all sandbox runtimes must implement, providing
    common initialization logic for policy, workspace, logging, and session
    management. All sandboxes are session-aware with auto-generated session IDs.

    Attributes:
        policy: ExecutionPolicy containing resource limits and configuration
        session_id: UUIDv4 session identifier for workspace isolation
        storage_adapter: StorageAdapter for workspace file operations
        logger: SandboxLogger for structured event logging
    """

    def __init__(
        self,
        policy: ExecutionPolicy,
        session_id: str,
        storage_adapter: StorageAdapter,
        logger: SandboxLogger | None = None
    ) -> None:
        """Initialize BaseSandbox with policy, session, storage, and logger.

        Args:
            policy: ExecutionPolicy with validated resource limits
            session_id: UUIDv4 string identifying the session
            storage_adapter: StorageAdapter for workspace operations
            logger: Optional SandboxLogger for structured events.
                    If None, creates default logger named 'sandbox'.
        """
        self.policy = policy
        self.session_id = session_id
        self.storage_adapter = storage_adapter

        if logger is None:
            # Import here to avoid circular dependency
            from sandbox.core.logging import SandboxLogger
            self.logger = SandboxLogger()
        else:
            self.logger = logger

    @property
    def workspace_root(self) -> Path:
        """Get workspace root from storage adapter.

        For backward compatibility with code expecting Path object.
        Only works with DiskStorageAdapter.

        Returns:
            Path to workspace root directory

        Raises:
            AttributeError: If storage adapter doesn't have workspace_root Path
        """
        if hasattr(self.storage_adapter, 'workspace_root') and isinstance(
            self.storage_adapter.workspace_root, Path
        ):
            return self.storage_adapter.workspace_root
        raise AttributeError(
            "workspace_root property only available with DiskStorageAdapter"
        )

    @property
    def workspace(self) -> Path:
        """Get session workspace path from storage adapter.

        For backward compatibility with code expecting Path object.
        Only works with DiskStorageAdapter.

        Returns:
            Path to session workspace directory

        Raises:
            AttributeError: If storage adapter doesn't support Path-based access
        """
        if hasattr(self.storage_adapter, 'workspace_root') and isinstance(
            self.storage_adapter.workspace_root, Path
        ):
            return self.storage_adapter.workspace_root / self.session_id
        raise AttributeError(
            "workspace property only available with DiskStorageAdapter"
        )

    @abstractmethod
    def execute(self, code: str, **kwargs: Any) -> SandboxResult:
        """Execute untrusted code in sandbox with resource limits and session tracking.

        Runtime-specific implementation must:
        1. Log execution start via self.logger.log_execution_start()
        2. Write code to workspace (or pass to WASM runtime)
        3. Execute code with fuel, memory, and filesystem limits
        4. Capture stdout/stderr with policy-defined size caps
        5. Collect execution metrics (fuel consumed, memory used, duration)
        6. Update session timestamp via _update_session_timestamp()
        7. Log execution complete via self.logger.log_execution_complete()
        8. Return SandboxResult with all captured data

        Args:
            code: Untrusted code to execute (language-specific syntax)
            **kwargs: Runtime-specific options (e.g., inject_setup for Python)

        Returns:
            SandboxResult with execution status, outputs, metrics, and session_id

        Raises:
            SandboxExecutionError: If execution fails due to sandbox error
            (not for guest code errors - those are captured in SandboxResult)
        """
        pass

    @abstractmethod
    def validate_code(self, code: str) -> bool:
        """Validate code syntax without executing it.

        Runtime-specific implementation must perform syntax-only validation
        (e.g., Python compile(), JavaScript parser) without side effects.
        This allows early rejection of syntactically invalid code before
        expensive WASM initialization.

        Args:
            code: Code to validate (language-specific syntax)

        Returns:
            True if syntax is valid, False otherwise
        """
        pass

    def _log_execution_metrics(
        self,
        result: SandboxResult,
        runtime: str
    ) -> None:
        """Helper method to log execution completion with metrics.

        Convenience method for runtime implementations to emit structured
        execution.complete events with consistent formatting.

        Args:
            result: SandboxResult containing execution metrics
            runtime: Runtime type identifier (e.g., "python", "javascript")
        """
        self.logger.log_execution_complete(result, runtime)
