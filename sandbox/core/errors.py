"""Exception classes for sandbox errors and validation failures.

Provides domain-specific exceptions for policy validation errors
and sandbox execution failures with clear error messages.
"""

from __future__ import annotations


class PolicyValidationError(Exception):
    """Raised when execution policy configuration is invalid.

    Indicates that a provided ExecutionPolicy or policy TOML file
    contains invalid values (e.g., negative limits, missing required
    fields, or validation constraint violations).

    This exception wraps Pydantic ValidationError with a clearer
    domain-specific name for sandbox consumers.
    """

    pass


class SandboxExecutionError(Exception):
    """Raised when sandbox execution fails unexpectedly.

    Indicates a failure in the sandbox runtime itself (not user code),
    such as WASM binary loading errors, WASI configuration failures,
    or runtime crashes. User code errors (syntax errors, exceptions)
    are captured in SandboxResult.stderr and do not raise this exception.
    """

    pass
