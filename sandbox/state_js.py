"""State persistence utilities for maintaining JavaScript globals across executions.

⚠️ IMPORTANT: JavaScript auto_persist_globals is NOT YET SUPPORTED ⚠️

This module is a placeholder for future JavaScript state persistence functionality.
The QuickJS-WASI runtime currently does not expose file I/O APIs (std.open, os.open),
making automatic state persistence impossible without native bindings.

Current Status:
- ✅ Python auto_persist_globals: FULLY SUPPORTED
- ❌ JavaScript auto_persist_globals: NOT SUPPORTED (planned for future)

Workaround for JavaScript:
Use manual file persistence via Python's sandbox_utils or explicit file operations
in the parent application between executions.

This module provides helpers for saving and restoring JavaScript state between
sandbox executions using JSON serialization. State would be automatically stored
in the session workspace and survive across multiple execute() calls.

Key Features (when supported):
- Automatic serialization of primitive types (number, string, array, object, boolean, null)
- Filtering of non-serializable objects (functions, classes, symbols)
- Session-aware storage (state isolated per session)
- Helper code that can be injected into sandbox execution

State Persistence Patterns
--------------------------

Pattern 1: Auto-save/restore with wrapper code
    >>> from sandbox import create_sandbox, RuntimeType
    >>> from sandbox.state_js import wrap_stateful_code
    >>>
    >>> sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
    >>> session_id = sandbox.session_id
    >>>
    >>> # First execution saves state
    >>> code1 = "let counter = 0; let data = [];"
    >>> wrapped1 = wrap_stateful_code(code1)
    >>> result1 = sandbox.execute(wrapped1)
    >>>
    >>> # Second execution restores and uses state
    >>> code2 = "counter += 10; data.push('item'); console.log(counter, data);"
    >>> wrapped2 = wrap_stateful_code(code2)
    >>> result2 = sandbox.execute(wrapped2)
    >>> print(result2.stdout)
    10 [ 'item' ]

Security Considerations
----------------------
- Only JSON-serializable types are persisted
- Functions, symbols, undefined values are filtered out automatically
- State file is workspace-scoped (no cross-session access)
- No code execution during deserialization (JSON.parse is safe)

Limitations
----------
⚠️ **CRITICAL**: Feature not yet available due to QuickJS-WASI lacking file I/O APIs
- QuickJS-WASI does not expose std.open() or os.open() for file operations
- Cannot persist state without native file I/O bindings
- Python's auto_persist_globals works perfectly (use Python runtime instead)
- Future support requires QuickJS-NG WASI to add file system APIs

Theoretical limitations (when/if feature becomes available):
- Complex objects (Map, Set, custom classes) not supported
- Circular references not handled
- Large state may impact execution fuel consumption
- Global variables must use var/let/const declarations to be captured
"""

from __future__ import annotations

# Default filename for state storage in session workspace
STATE_FILENAME = ".session_state.json"


def save_state_code(filename: str = STATE_FILENAME) -> str:
    """Generate JavaScript code to save global state to JSON file.

    Saves the _state object to a JSON file (only if defined).

    Args:
        filename: Target filename in /app/ (default: .session_state.json)

    Returns:
        str: JavaScript code snippet to save state

    Examples:
        >>> code = save_state_code()
    """
    return f"""
if (typeof _state !== 'undefined') {{
    const f = std.open('/app/{filename}', 'w');
    f.puts(JSON.stringify(_state));
    f.close();
}}
""".strip()


def load_state_code(filename: str = STATE_FILENAME) -> str:
    """Generate JavaScript code to load state from JSON file.

    Creates a module-level var _state that's accessible to user code.

    Args:
        filename: Source filename in /app/ (default: .session_state.json)

    Returns:
        str: JavaScript code snippet to load state

    Examples:
        >>> code = load_state_code()
    """
    return f"""
var _state = {{}};
try {{
    const f = std.open('/app/{filename}', 'r');
    const content = f.readAsString();
    f.close();
    _state = JSON.parse(content);
}} catch (e) {{
    // State file doesn't exist yet (first execution)
}}
""".strip()


def wrap_stateful_code(code: str, filename: str = STATE_FILENAME) -> str:
    """Wrap user code with automatic state save/restore logic.

    IMPORTANT: Due to JavaScript's scoping rules, let/const variables do NOT
    become properties of globalThis. Therefore, users must explicitly use
    the _state object for persistence:

    Instead of:
        let counter = 0;  // WON'T persist!

    Use:
        _state.counter = (_state.counter || 0) + 1;  // WILL persist!

    Generates code that:
    1. Loads _state object from JSON (if exists)
    2. Executes user code (which can read/write _state.*)
    3. Saves _state object back to JSON

    Args:
        code: User's JavaScript code to execute
        filename: State filename (default: .session_state.json)

    Returns:
        str: Wrapped code with state management

    Examples:
        >>> user_code = "_state.counter = (_state.counter || 0) + 1;"
        >>> wrapped = wrap_stateful_code(user_code)
        >>> # Execution 1: _state.counter becomes 1
        >>> # Execution 2: _state.counter becomes 2
        >>> # Execution 3: _state.counter becomes 3
    """
    load_code = load_state_code(filename)
    save_code = save_state_code(filename)

    return f"""{load_code}

// User code
{code}

// Auto-save state
{save_code}
"""
