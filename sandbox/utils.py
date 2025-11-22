"""Utility functions and exception types for the WASM sandbox.

Provides common helper functions for logging setup and filesystem operations,
as well as a hierarchy of sandbox-specific exceptions for fine-grained error handling.
"""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure centralized logging for the sandbox with timestamp formatting.

    Creates a logger named "llm-wasm-sandbox" that captures execution events,
    security violations, and resource consumption metrics during WASM execution.

    Args:
        level: Logging verbosity level. Use logging.DEBUG for fuel/memory traces,
            logging.INFO for execution summaries (default: logging.INFO).

    Returns:
        logging.Logger: Configured logger instance for the sandbox subsystem.
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("llm-wasm-sandbox")


def ensure_dir_exists(path: str | Path) -> Path:
    """Ensure a directory exists, creating parent directories as needed.

    Idempotent operation used to prepare workspace directories for untrusted code
    execution. Does not raise if directory already exists.

    Args:
        path: Target directory path as string or Path object.

    Returns:
        Path: Resolved Path object for the directory.

    Raises:
        OSError: If directory creation fails due to permissions or filesystem errors.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


class SandboxError(Exception):
    """Base exception for all sandbox execution failures.

    Catch this type to handle any sandbox-related error (fuel exhaustion,
    memory limits, WASI violations). Subclasses provide granular error types
    for specific failure modes.
    """
    pass


class FuelExhaustionError(SandboxError):
    """Raised when WASM guest exhausts its instruction fuel budget.

    Indicates the untrusted code exceeded the deterministic execution limit
    configured in the policy. Typically caused by infinite loops or excessive
    computation. Maps to Wasmtime's OutOfFuel trap.
    """
    pass


class MemoryLimitError(SandboxError):
    """Raised when WASM guest exceeds allocated linear memory.

    Indicates the untrusted code attempted to grow memory beyond the cap
    configured in the policy. Typically caused by unbounded allocations
    or memory bombs. Maps to Wasmtime's memory limit violation.
    """
    pass
