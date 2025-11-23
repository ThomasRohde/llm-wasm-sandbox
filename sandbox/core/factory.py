"""Factory function for creating sandbox instances based on runtime type.

Provides create_sandbox() factory that maps RuntimeType enum values to
concrete sandbox implementations (PythonSandbox, future JavaScriptSandbox).
All sandboxes are session-aware with auto-generated session IDs.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sandbox.core.logging import SandboxLogger
from sandbox.core.models import ExecutionPolicy, RuntimeType
from sandbox.sessions import _validate_session_workspace


def _hydrate_session_site_packages(session_workspace: Path, workspace_root: Path) -> None:
    """Copy shared site-packages into the session workspace if available.

    This ensures guest-visible packages are isolated per session to prevent
    cross-session tampering. If the session already has a site-packages
    directory, it is left untouched to preserve session-local state.
    """
    shared_packages = workspace_root / "site-packages"
    if not shared_packages.exists():
        return

    target = session_workspace / "site-packages"
    if target.exists():
        return

    try:
        shutil.copytree(shared_packages, target)
    except OSError as exc:
        raise ValueError(
            f"Failed to prepare session site-packages for {session_workspace}: {exc}"
        ) from exc


def create_sandbox(
    runtime: RuntimeType = RuntimeType.PYTHON,
    policy: ExecutionPolicy | None = None,
    session_id: str | None = None,
    workspace_root: Path | None = None,
    logger: SandboxLogger | None = None,
    allow_non_uuid: bool = True,
    **kwargs: Any
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
        logger: Optional SandboxLogger. If None, runtime creates default logger.
        allow_non_uuid: If False, session_id must be a valid UUID string.
        **kwargs: Additional runtime-specific arguments passed to constructor.
                  For PythonSandbox: wasm_binary_path (default: "bin/python.wasm")
                  For JavaScriptSandbox: wasm_binary_path (default: "bin/quickjs.wasm")

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

    if workspace_root is None:
        workspace_root = Path("workspace")
    else:
        workspace_root = Path(workspace_root)

    workspace_root = workspace_root.resolve()

    # Auto-generate session_id if not provided
    if session_id is None:
        session_id = str(uuid.uuid4())

    # Validate workspace path and ensure it remains under workspace_root
    session_workspace = _validate_session_workspace(
        session_id=session_id,
        workspace_root=workspace_root,
        allow_non_uuid=allow_non_uuid
    )
    session_id = session_workspace.name
    session_workspace.mkdir(parents=True, exist_ok=True)

    # Copy shared packages into the session workspace to isolate mutations
    _hydrate_session_site_packages(session_workspace, workspace_root)

    # Create or update session metadata
    metadata_path = session_workspace / ".metadata.json"
    metadata_existed = metadata_path.exists()
    now_utc = datetime.now(UTC).isoformat()

    if metadata_existed:
        # Existing session - update timestamp only
        try:
            data = json.loads(metadata_path.read_text())
            data["updated_at"] = now_utc
            metadata_path.write_text(json.dumps(data, indent=2))
        except (json.JSONDecodeError, OSError) as e:
            # Log warning but continue
            import sys
            print(
                f"Warning: Failed to update session metadata for {session_id}: {e}",
                file=sys.stderr
            )
    else:
        # New session - create metadata
        metadata = {
            "session_id": session_id,
            "created_at": now_utc,
            "updated_at": now_utc,
            "version": 1
        }
        try:
            metadata_path.write_text(json.dumps(metadata, indent=2))

            # Log structured event if logger provided
            if logger is not None:
                logger.log_session_metadata_created(
                    session_id=session_id,
                    created_at=now_utc
                )
        except OSError as e:
            # Log warning but continue - metadata write failure shouldn't prevent creation
            import sys
            print(
                f"Warning: Failed to write session metadata for {session_id}: {e}",
                file=sys.stderr
            )

    # Log session creation/retrieval
    if logger is not None:
        if metadata_existed:
            logger.log_session_retrieved(session_id, str(session_workspace))
        else:
            logger.log_session_created(session_id, str(session_workspace))

    # Dispatch to runtime-specific implementation
    if runtime == RuntimeType.PYTHON:
        from sandbox.runtimes.python.sandbox import PythonSandbox

        wasm_binary_path = kwargs.pop("wasm_binary_path", "bin/python.wasm")
        return PythonSandbox(
            wasm_binary_path=wasm_binary_path,
            policy=policy,
            session_id=session_id,
            workspace_root=workspace_root,
            logger=logger,
            **kwargs
        )

    elif runtime == RuntimeType.JAVASCRIPT:
        from sandbox.runtimes.javascript.sandbox import JavaScriptSandbox

        wasm_binary_path = kwargs.pop("wasm_binary_path", "bin/quickjs.wasm")
        return JavaScriptSandbox(
            wasm_binary_path=wasm_binary_path,
            policy=policy,
            session_id=session_id,
            workspace_root=workspace_root,
            logger=logger,
            **kwargs
        )

    else:
        # Should never reach here due to enum validation, but be defensive
        raise ValueError(f"Unsupported runtime type: {runtime}")
