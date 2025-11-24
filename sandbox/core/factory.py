"""Factory function for creating sandbox instances based on runtime type.

Provides create_sandbox() factory that maps RuntimeType enum values to
concrete sandbox implementations (PythonSandbox, future JavaScriptSandbox).
All sandboxes are session-aware with auto-generated session IDs.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sandbox.core.logging import SandboxLogger
from sandbox.core.models import ExecutionPolicy, RuntimeType
from sandbox.core.storage import DiskStorageAdapter
from sandbox.runtime_paths import get_python_wasm_path, get_quickjs_wasm_path
from sandbox.sessions import _validate_session_workspace

if TYPE_CHECKING:
    from sandbox.core.storage import StorageAdapter


def create_sandbox(
    runtime: RuntimeType = RuntimeType.PYTHON,
    policy: ExecutionPolicy | None = None,
    session_id: str | None = None,
    workspace_root: Path | None = None,
    storage_adapter: StorageAdapter | None = None,
    logger: SandboxLogger | None = None,
    allow_non_uuid: bool = True,
    auto_persist_globals: bool = False,
    **kwargs: Any,
) -> Any:  # Returns BaseSandbox but avoid circular import in type hint
    """Create a session-aware sandbox instance for the specified runtime type.

    Factory function that instantiates the appropriate sandbox implementation
    based on the requested runtime. All sandboxes are session-aware with
    auto-generated UUIDv4 session IDs (or explicit session_id if provided).
    Creates session workspace and metadata automatically.

    Args:
        runtime: RuntimeType enum value (PYTHON or JAVASCRIPT)
        policy: Optional ExecutionPolicy. If None, uses default policy.
        session_id: Optional explicit session identifier. If None, auto-generates UUIDv4.
        workspace_root: Optional root directory for session workspaces. Default: Path("workspace")
                       Ignored if storage_adapter is provided.
        storage_adapter: Optional StorageAdapter for workspace operations.
                        If None, creates DiskStorageAdapter with workspace_root.
        logger: Optional SandboxLogger. If None, runtime creates default logger.
        allow_non_uuid: If False, session_id must be a valid UUID string.
        auto_persist_globals: If True, automatically save/restore Python globals between
                             executions using JSON serialization. Only serializable types
                             (int, str, list, dict, bool, float, None) are persisted.
                             Functions, modules, and classes are filtered out.
        **kwargs: Additional runtime-specific arguments passed to constructor.
                  For PythonSandbox: wasm_binary_path (default: auto-detected bundled binary)
                  For JavaScriptSandbox: wasm_binary_path (default: auto-detected bundled binary)

    Returns:
        BaseSandbox: Concrete sandbox instance (PythonSandbox or JavaScriptSandbox)
                     with session_id attribute accessible

    Raises:
        ValueError: If runtime is not a valid RuntimeType enum value

    Examples:
        >>> # Create sandbox with auto-generated session ID
        >>> sandbox = create_sandbox()
        >>> print(sandbox.session_id)
        '550e8400-e29b-41d4-a716-446655440000'

        >>> # Create with explicit session ID (for resuming session)
        >>> sandbox = create_sandbox(session_id="my-session-123")
        >>> print(sandbox.session_id)
        'my-session-123'

        >>> # Create with custom policy
        >>> policy = ExecutionPolicy(fuel_budget=1_000_000_000)
        >>> sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

        >>> # Create JavaScript sandbox
        >>> sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
        >>> print(sandbox.session_id)
        '550e8400-e29b-41d4-a716-446655440001'

        >>> # Create with custom workspace root
        >>> sandbox = create_sandbox(workspace_root=Path("/var/lib/sandbox/sessions"))

        >>> # Create with custom storage adapter
        >>> from sandbox.core.storage import DiskStorageAdapter
        >>> adapter = DiskStorageAdapter(Path("/custom/path"))
        >>> sandbox = create_sandbox(storage_adapter=adapter)
    """
    # Validate runtime type
    if not isinstance(runtime, RuntimeType):
        raise ValueError(
            f"Invalid runtime type: {runtime}. "
            f"Must be a RuntimeType enum value (PYTHON or JAVASCRIPT)."
        )

    # Set defaults
    if policy is None:
        policy = ExecutionPolicy()

    # Create storage adapter if not provided
    if storage_adapter is None:
        workspace_root = Path("workspace") if workspace_root is None else Path(workspace_root)
        workspace_root = workspace_root.resolve()
        storage_adapter = DiskStorageAdapter(workspace_root)
    else:
        # If storage_adapter provided, use its workspace_root
        # (only for DiskStorageAdapter backward compatibility)
        if hasattr(storage_adapter, "workspace_root") and isinstance(
            storage_adapter.workspace_root, Path
        ):
            workspace_root = storage_adapter.workspace_root
        elif workspace_root is None:
            workspace_root = Path("workspace")
        else:
            workspace_root = Path(workspace_root)

    # Auto-generate session_id if not provided
    if session_id is None:
        session_id = str(uuid.uuid4())

    # Validate workspace path (for DiskStorageAdapter only)
    if isinstance(storage_adapter, DiskStorageAdapter):
        session_workspace = _validate_session_workspace(
            session_id=session_id,
            workspace_root=storage_adapter.workspace_root,
            allow_non_uuid=allow_non_uuid,
        )
        session_id = session_workspace.name

    # Create session via storage adapter
    if not storage_adapter.session_exists(session_id):
        storage_adapter.create_session(session_id)

        # Copy shared packages into session (if using DiskStorageAdapter)
        if isinstance(storage_adapter, DiskStorageAdapter):
            try:
                # Try multiple vendor locations in order of preference
                vendor_candidates = [
                    storage_adapter.workspace_root,  # For tests that put site-packages directly in workspace_root
                    storage_adapter.workspace_root.parent / "vendor",  # Standard location
                    Path("vendor"),  # Fallback to project root
                ]
                vendor_path = None
                for candidate in vendor_candidates:
                    if (candidate / "site-packages").exists():
                        vendor_path = candidate
                        break

                if vendor_path is not None:
                    storage_adapter.copy_vendor_packages(session_id, vendor_path)
            except (FileNotFoundError, OSError):
                # Vendor packages not available - not an error
                pass

        # Log session creation
        if logger is not None:
            metadata = storage_adapter.read_metadata(session_id)
            logger.log_session_metadata_created(
                session_id=session_id, created_at=metadata.created_at
            )
            logger.log_session_created(session_id, str(session_id))
    else:
        # Existing session - ensure metadata exists (legacy session support)
        try:
            storage_adapter.read_metadata(session_id)
        except (FileNotFoundError, json.JSONDecodeError):
            # Legacy session without metadata - create it now
            from datetime import UTC, datetime

            from sandbox.sessions import SessionMetadata

            now = datetime.now(UTC).isoformat()
            metadata = SessionMetadata(
                session_id=session_id, created_at=now, updated_at=now, version=1
            )
            try:
                storage_adapter.write_metadata(session_id, metadata)
                if logger is not None:
                    logger.log_session_metadata_created(session_id=session_id, created_at=now)
            except OSError:
                # If we can't write metadata, continue anyway
                pass

        # Update timestamp for existing session
        storage_adapter.update_session_timestamp(session_id)

        # Log session retrieval
        if logger is not None:
            logger.log_session_retrieved(session_id, str(session_id))

    # Dispatch to runtime-specific implementation
    if runtime == RuntimeType.PYTHON:
        from sandbox.runtimes.python.sandbox import PythonSandbox

        # Use bundled binary by default, allow override via kwargs
        if "wasm_binary_path" not in kwargs:
            try:
                wasm_binary_path = str(get_python_wasm_path())
            except FileNotFoundError:
                # Fallback for backward compatibility (development without downloaded binaries)
                wasm_binary_path = "bin/python.wasm"
        else:
            wasm_binary_path = kwargs.pop("wasm_binary_path")

        return PythonSandbox(
            wasm_binary_path=wasm_binary_path,
            policy=policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
            logger=logger,
            auto_persist_globals=auto_persist_globals,
            **kwargs,
        )

    elif runtime == RuntimeType.JAVASCRIPT:
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox

        # Use bundled binary by default, allow override via kwargs
        if "wasm_binary_path" not in kwargs:
            try:
                wasm_binary_path = str(get_quickjs_wasm_path())
            except FileNotFoundError:
                # Fallback for backward compatibility (development without downloaded binaries)
                wasm_binary_path = "bin/quickjs.wasm"
        else:
            wasm_binary_path = kwargs.pop("wasm_binary_path")

        return JavaScriptSandbox(
            wasm_binary_path=wasm_binary_path,
            policy=policy,
            session_id=session_id,
            storage_adapter=storage_adapter,
            logger=logger,
            **kwargs,
        )

    else:
        # Should never reach here due to enum validation, but be defensive
        raise ValueError(f"Unsupported runtime type: {runtime}")
