"""Policy management for WASM sandbox execution.

Provides default security policies and TOML-based configuration loading
for controlling WASM guest resource limits, filesystem capabilities,
and environment isolation.
"""

from __future__ import annotations

import os
import tomllib

from pydantic import ValidationError

from sandbox.core.errors import PolicyValidationError
from sandbox.core.models import ExecutionPolicy

DEFAULT_POLICY = {
    # WASM instruction limit - prevents infinite loops and excessive computation
    "fuel_budget": 2_000_000_000,

    # Linear memory cap - prevents memory bombs
    "memory_bytes": 128_000_000,

    # Output size caps - prevents log flooding attacks
    "stdout_max_bytes": 2_000_000,
    "stderr_max_bytes": 1_000_000,

    # WASI filesystem preopen for capability-based isolation
    "mount_host_dir": "workspace",
    "guest_mount_path": "/app",

    # Guest argv - "-I" isolates from user site-packages for predictability
    "argv": ["python", "-I", "/app/user_code.py", "-X", "utf8"],

    # Environment whitelist - only expose explicitly required variables
    "env": {
        "PYTHONUTF8": "1",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONHASHSEED": "0",  # Deterministic hash seeds for reproducibility
        "DEMO_GREETING": "Hej fra WASM 👋",
    },
}

def load_policy(path: str = "config/policy.toml") -> ExecutionPolicy:
    """Load and merge user policy configuration with secure defaults.

    Performs a shallow merge of user-provided TOML settings with DEFAULT_POLICY,
    ensuring all required security parameters have safe fallback values. The env
    dict is deep-merged to allow adding environment variables without replacing
    the entire default set.

    Returns a validated ExecutionPolicy Pydantic model that enforces type safety
    and field constraints (e.g., positive resource limits).

    Args:
        path: Path to the policy TOML file. If file doesn't exist, returns
              ExecutionPolicy with defaults.

    Returns:
        ExecutionPolicy: Validated policy model with merged configuration.

    Raises:
        PolicyValidationError: If policy contains invalid values (negative limits,
                               invalid types, etc.)
        tomllib.TOMLDecodeError: If TOML file is malformed
        OSError: If file exists but cannot be read
    """
    if not os.path.exists(path):
        try:
            return ExecutionPolicy(**DEFAULT_POLICY)  # type: ignore[arg-type]
        except PolicyValidationError:
            raise
        except ValidationError as e:
            raise PolicyValidationError(f"Default policy validation failed: {e}") from e

    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Merge top-level keys, with user overrides taking precedence
    policy = DEFAULT_POLICY | data

    # Deep merge env dict to preserve default environment variables
    policy["env"] = DEFAULT_POLICY["env"] | data.get("env", {})

    # Support optional secondary mount for read-only data access
    if "mount_data_dir" in data:
        policy["mount_data_dir"] = data["mount_data_dir"]
        policy["guest_data_path"] = data.get("guest_data_path", "/data")

    try:
        return ExecutionPolicy(**policy)  # type: ignore[arg-type]
    except PolicyValidationError:
        raise
    except ValidationError as e:
        raise PolicyValidationError(f"Policy validation failed: {e}") from e
