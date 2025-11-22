"""Python runtime sandbox implementation using CPython compiled to WASM.

Provides PythonSandbox class that extends BaseSandbox to execute untrusted
Python code in a WebAssembly sandbox with fuel-based resource limits,
capability-based filesystem isolation, and memory caps.
"""

from .sandbox import PythonSandbox

__all__ = ["PythonSandbox"]
