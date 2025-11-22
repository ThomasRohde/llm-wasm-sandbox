"""JavaScript runtime sandbox implementation using QuickJS compiled to WASM.

Provides JavaScriptSandbox class that extends BaseSandbox to execute untrusted
JavaScript code in a WebAssembly sandbox with fuel-based resource limits,
capability-based filesystem isolation, and memory caps.
"""

from .sandbox import JavaScriptSandbox

__all__ = ["JavaScriptSandbox"]
