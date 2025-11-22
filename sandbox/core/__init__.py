"""Core sandbox abstractions and models.

This module provides the foundational types and interfaces for the
enterprise-grade WASM sandbox, including Pydantic models for type-safe
configuration and results, base sandbox abstractions, and error types.
"""

from __future__ import annotations

from .base import BaseSandbox
from .errors import PolicyValidationError, SandboxExecutionError
from .models import ExecutionPolicy, RuntimeType, SandboxResult

__all__ = [
    "BaseSandbox",
    "ExecutionPolicy",
    "PolicyValidationError",
    "RuntimeType",
    "SandboxExecutionError",
    "SandboxResult",
]
