"""Pydantic models for type-safe sandbox configuration and results.

Provides validated data models for execution policies, runtime types,
and sandbox execution results with automatic field validation and
JSON serialization support.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from sandbox.core.errors import PolicyValidationError


class RuntimeType(str, Enum):
    """Supported WASM runtime types for sandbox execution.

    PYTHON: CPython compiled to WASM (WLR AIO binary)
    JAVASCRIPT: Future JavaScript runtime support
    """
    PYTHON = "python"
    JAVASCRIPT = "javascript"


class ExecutionPolicy(BaseModel):
    """Type-safe configuration model for sandbox execution limits and capabilities.

    Defines resource budgets (fuel, memory), output limits, filesystem mounts,
    and environment configuration. All fields have secure defaults and are
    validated at construction time to prevent invalid configurations.

    Attributes:
        fuel_budget: WASM instruction limit (prevents infinite loops)
        memory_bytes: Linear memory cap in bytes (prevents memory bombs)
        stdout_max_bytes: Maximum stdout capture size
        stderr_max_bytes: Maximum stderr capture size
        mount_host_dir: Host directory for WASI capability-based preopen
        guest_mount_path: Guest-visible mount point (typically /app)
        mount_data_dir: Optional secondary mount for read-only data
        guest_data_path: Mount point for optional data directory
        argv: Guest process command-line arguments
        env: Environment variables exposed to guest (whitelist pattern)
        timeout_seconds: Optional OS-level timeout (None = no timeout)
    """

    fuel_budget: int = Field(
        default=2_000_000_000,
        gt=0,
        description="WASM instruction limit for deterministic interruption"
    )

    memory_bytes: int = Field(
        default=128_000_000,
        gt=0,
        description="Linear memory cap in bytes"
    )

    stdout_max_bytes: int = Field(
        default=2_000_000,
        gt=0,
        description="Maximum stdout capture size"
    )

    stderr_max_bytes: int = Field(
        default=1_000_000,
        gt=0,
        description="Maximum stderr capture size"
    )

    mount_host_dir: str = Field(
        default="workspace",
        description="Host directory for WASI preopen"
    )

    guest_mount_path: str = Field(
        default="/app",
        description="Guest-visible mount point"
    )

    mount_data_dir: str | None = Field(
        default=None,
        description="Optional secondary mount for read-only data"
    )

    guest_data_path: str | None = Field(
        default=None,
        description="Mount point for optional data directory"
    )

    argv: list[str] = Field(
        default_factory=lambda: ["python", "-I", "/app/user_code.py", "-X", "utf8"],
        description="Guest process command-line arguments (Python-specific default; runtimes may override in host layer)"
    )

    env: dict[str, str] = Field(
        default_factory=lambda: {
            "PYTHONUTF8": "1",
            "LC_ALL": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
        },
        description="Environment variables exposed to guest (Python-specific defaults; can be customized per runtime)"
    )

    timeout_seconds: float | None = Field(
        default=None,
        ge=0,
        description="Optional OS-level timeout (None = no timeout)"
    )

    @model_validator(mode="before")
    @classmethod
    def set_guest_data_default(cls, values: Any) -> Any:
        """Ensure guest_data_path defaults to /data when mount_data_dir is provided."""
        if not isinstance(values, dict):
            return values

        mount_dir = values.get("mount_data_dir")
        guest_data = values.get("guest_data_path")
        if mount_dir is not None and guest_data is None:
            updated = dict(values)
            updated["guest_data_path"] = "/data"
            return updated
        return values

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as e:
            raise PolicyValidationError(f"Invalid execution policy: {e}") from e

    @classmethod
    def model_validate(cls, obj: Any, *, strict: bool | None = None, context: dict[str, Any] | None = None) -> "ExecutionPolicy":
        try:
            return super().model_validate(obj, strict=strict, context=context)  # type: ignore[arg-type]
        except ValidationError as e:
            raise PolicyValidationError(f"Invalid execution policy: {e}") from e

    @field_validator("fuel_budget", "memory_bytes", "stdout_max_bytes", "stderr_max_bytes")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Ensure resource limits are positive."""
        if v <= 0:
            raise ValueError("Resource limits must be positive")
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: float | None) -> float | None:
        """Ensure timeout is non-negative if provided."""
        if v is not None and v < 0:
            raise ValueError("Timeout must be non-negative")
        return v


class SandboxResult(BaseModel):
    """Type-safe execution result from sandbox with metrics and outputs.

    Captures all execution details including stdout/stderr, resource consumption,
    file system changes, and metadata for observability and debugging.

    Attributes:
        success: Whether execution completed without errors
        stdout: Captured stdout (may be truncated per policy)
        stderr: Captured stderr (may be truncated per policy)
        exit_code: Guest process exit code (0 = success)
        fuel_consumed: WASM instructions executed (None if not tracked)
        memory_used_bytes: Peak memory usage in bytes
        duration_ms: Wall-clock execution time in milliseconds
        files_created: List of new files in workspace (relative paths)
        files_modified: List of modified files in workspace (relative paths)
        workspace_path: Absolute path to workspace directory
        metadata: Additional runtime-specific or execution metadata
    """

    success: bool = Field(
        description="Whether execution completed without errors"
    )

    stdout: str = Field(
        default="",
        description="Captured stdout (may be truncated per policy)"
    )

    stderr: str = Field(
        default="",
        description="Captured stderr (may be truncated per policy)"
    )

    exit_code: int = Field(
        default=0,
        description="Guest process exit code (0 = success)"
    )

    fuel_consumed: int | None = Field(
        default=None,
        description="WASM instructions executed (None if not tracked)"
    )

    memory_used_bytes: int = Field(
        default=0,
        description="Peak memory usage in bytes"
    )

    duration_ms: float = Field(
        default=0.0,
        description="Wall-clock execution time in milliseconds"
    )

    files_created: list[str] = Field(
        default_factory=list,
        description="New files in workspace (relative paths)"
    )

    files_modified: list[str] = Field(
        default_factory=list,
        description="Modified files in workspace (relative paths)"
    )

    workspace_path: str = Field(
        description="Absolute path to workspace directory"
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional runtime-specific or execution metadata (e.g., logs_dir, trap_reason, stdout_truncated)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "stdout": "Hello from WASM\n",
                    "stderr": "",
                    "exit_code": 0,
                    "fuel_consumed": 1234567,
                    "memory_used_bytes": 8388608,
                    "duration_ms": 125.5,
                    "files_created": ["output.txt"],
                    "files_modified": [],
                    "workspace_path": "/workspace",
                    "metadata": {"runtime": "python"}
                }
            ]
        }
    }
