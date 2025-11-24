"""State persistence utilities for maintaining Python globals across executions.

This module provides helpers for saving and restoring Python state between
sandbox executions using JSON serialization. State is automatically stored
in the session workspace and survives across multiple execute() calls.

Key Features:
- Automatic serialization of primitive types (int, str, list, dict, bool, float, None)
- Filtering of non-serializable objects (functions, modules, classes)
- Session-aware storage (state isolated per session)
- Helper functions that can be injected into sandbox code

State Persistence Patterns
--------------------------

Pattern 1: Auto-save/restore with wrapper code
    >>> from sandbox import create_sandbox
    >>> from sandbox.state import wrap_stateful_code
    >>>
    >>> sandbox = create_sandbox()
    >>> session_id = sandbox.session_id
    >>>
    >>> # First execution saves state
    >>> code1 = "counter = 0\\ndata = []"
    >>> wrapped1 = wrap_stateful_code(code1)
    >>> result1 = sandbox.execute(wrapped1)
    >>>
    >>> # Second execution restores and uses state
    >>> code2 = "counter += 10\\ndata.append('item')\\nprint(counter, data)"
    >>> wrapped2 = wrap_stateful_code(code2)
    >>> result2 = sandbox.execute(wrapped2)
    >>> print(result2.stdout)
    10 ['item']

Pattern 2: Manual state management
    >>> from sandbox import create_sandbox
    >>> from sandbox.state import save_state_code, load_state_code
    >>>
    >>> sandbox = create_sandbox()
    >>>
    >>> # Save state explicitly
    >>> code_with_save = '''
    ... counter = 42
    ... data = {"key": "value"}
    ... ''' + save_state_code()
    >>> sandbox.execute(code_with_save)
    >>>
    >>> # Load state in next execution
    >>> code_with_load = load_state_code() + '''
    ... print(f"Counter: {counter}")
    ... print(f"Data: {data}")
    ... '''
    >>> result = sandbox.execute(code_with_load)
    >>>
    >>> # Load state in next execution
    >>> code_with_load = load_state_code() + '''
    ... print(f"Counter: {counter}")
    ... print(f"Data: {data}")
    ... '''
    >>> result = sandbox.execute(code_with_load)

Pattern 3: LLM-friendly utilities (via sandbox_utils)
    >>> # Inside sandbox execution
    >>> code = '''
    ... from sandbox_utils import save_state, load_state
    ...
    ... # Load previous state if exists
    ... state = load_state()
    ... counter = state.get('counter', 0)
    ...
    ... # Do work
    ... counter += 1
    ...
    ... # Save for next execution
    ... save_state({'counter': counter})
    ... '''

Security Considerations
----------------------
- Only JSON-serializable types are persisted (no arbitrary pickle)
- Functions, modules, classes are filtered out automatically
- State file is workspace-scoped (no cross-session access)
- No code execution during deserialization (JSON.parse is safe)

Limitations
----------
- Complex objects (custom classes, numpy arrays) not supported
- Nested object depth limited by JSON serializer
- Large state may impact execution fuel consumption
- No automatic conflict resolution for concurrent executions
"""

from __future__ import annotations

from typing import Any

# Default filename for state storage in session workspace
STATE_FILENAME = ".session_state.json"


def is_serializable(obj: Any) -> bool:
    """Check if object is JSON-serializable primitive type.

    Args:
        obj: Python object to check

    Returns:
        bool: True if obj is int, str, float, bool, list, dict, or None

    Examples:
        >>> is_serializable(42)
        True
        >>> is_serializable("text")
        True
        >>> is_serializable([1, 2, 3])
        True
        >>> is_serializable(lambda x: x)
        False
        >>> is_serializable(open)
        False
    """
    type_name = type(obj).__name__
    allowed_types = ("int", "str", "float", "bool", "list", "dict", "NoneType")
    return type_name in allowed_types


def filter_serializable_globals(globals_dict: dict[str, Any]) -> dict[str, Any]:
    """Filter globals dict to only JSON-serializable values.

    Removes:
    - Private variables (starting with _)
    - Functions, classes, modules
    - Built-in objects
    - Non-serializable types

    Args:
        globals_dict: Dictionary of global variables (from globals())

    Returns:
        dict: Filtered dictionary with only serializable key-value pairs

    Examples:
        >>> test_globals = {
        ...     'counter': 42,
        ...     'data': [1, 2, 3],
        ...     '_private': 'hidden',
        ...     'func': lambda: None,
        ...     '__builtins__': {},
        ... }
        >>> filtered = filter_serializable_globals(test_globals)
        >>> filtered
        {'counter': 42, 'data': [1, 2, 3]}
    """
    filtered = {}

    for key, value in globals_dict.items():
        # Skip private/dunder variables
        if key.startswith("_"):
            continue

        # Skip callables (functions, classes)
        if callable(value):
            continue

        # Skip modules
        if type(value).__name__ == "module":
            continue

        # Only include serializable types
        if is_serializable(value):
            filtered[key] = value

    return filtered


def save_state_code(state_var: str = "globals()", filename: str = STATE_FILENAME) -> str:
    """Generate Python code to save state to JSON file.

    Returns a code snippet that serializes globals to a JSON file in the
    session workspace. This code should be appended to user code.

    Args:
        state_var: Python expression that returns dict to save (default: globals())
        filename: Target filename in /app/ (default: .session_state.json)

    Returns:
        str: Python code snippet to save state

    Examples:
        >>> code = save_state_code()
        >>> print(code)
        import json
        _state = {k: v for k, v in globals().items()
                  if not k.startswith('_') and not callable(v) and
                  type(v).__name__ in ('int', 'str', 'list', 'dict', 'float', 'bool', 'NoneType')}
        with open('/app/.session_state.json', 'w') as _f:
            json.dump(_state, _f)
        del _state, _f
    """
    return f"""
import json
_state = {{k: v for k, v in {state_var}.items()
          if not k.startswith('_') and not callable(v) and
          type(v).__name__ in ('int', 'str', 'list', 'dict', 'float', 'bool', 'NoneType')}}
with open('/app/{filename}', 'w') as _f:
    json.dump(_state, _f)
del _state, _f
""".strip()


def load_state_code(filename: str = STATE_FILENAME) -> str:
    """Generate Python code to load state from JSON file.

    Returns a code snippet that deserializes state from JSON file and
    restores variables into globals. This code should be prepended to user code.

    Args:
        filename: Source filename in /app/ (default: .session_state.json)

    Returns:
        str: Python code snippet to load state

    Examples:
        >>> code = load_state_code()
        >>> print(code)
        import json
        try:
            with open('/app/.session_state.json', 'r') as _f:
                _loaded = json.load(_f)
                globals().update(_loaded)
                del _loaded
        except FileNotFoundError:
            pass
    """
    return f"""
import json
try:
    with open('/app/{filename}', 'r') as _f:
        _loaded = json.load(_f)
        globals().update(_loaded)
        del _loaded
except FileNotFoundError:
    pass
""".strip()


def wrap_stateful_code(code: str, filename: str = STATE_FILENAME) -> str:
    """Wrap user code with automatic state save/restore logic.

    Generates code that:
    1. Loads previous state from JSON (if exists)
    2. Executes user code
    3. Saves updated state to JSON

    This provides transparent state persistence across executions.

    Args:
        code: User's Python code to execute
        filename: State filename (default: .session_state.json)

    Returns:
        str: Wrapped code with state management

    Examples:
        >>> user_code = "counter = counter + 1 if 'counter' in dir() else 0"
        >>> wrapped = wrap_stateful_code(user_code)
        >>> # Execution 1: counter becomes 0
        >>> # Execution 2: counter becomes 1
        >>> # Execution 3: counter becomes 2
    """
    load_code = load_state_code(filename)
    save_code = save_state_code(filename=filename)

    return f"""{load_code}

# User code
{code}

# Auto-save state
{save_code}
"""


def create_state_helpers() -> str:
    """Generate helper functions for LLM-friendly state management.

    Returns Python code defining save_state() and load_state() functions
    that can be used directly in sandbox code without imports.

    Returns:
        str: Python code defining state helper functions

    Examples:
        >>> helpers = create_state_helpers()
        >>> # Now can use in sandbox:
        >>> code = '''
        ... state = load_state()
        ... counter = state.get('counter', 0) + 1
        ... save_state({'counter': counter})
        ... print(f"Counter: {counter}")
        ... '''
    """
    return f'''
def save_state(state_dict, filename="{STATE_FILENAME}"):
    """Save state dictionary to session workspace.

    Args:
        state_dict: Dictionary with JSON-serializable values
        filename: Target filename (default: {STATE_FILENAME})
    """
    import json
    with open(f'/app/{{filename}}', 'w') as f:
        json.dump(state_dict, f)

def load_state(filename="{STATE_FILENAME}", default=None):
    """Load state dictionary from session workspace.

    Args:
        filename: Source filename (default: {STATE_FILENAME})
        default: Return value if file not found (default: {{}})

    Returns:
        dict: Loaded state or default
    """
    import json
    try:
        with open(f'/app/{{filename}}', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {{}}
'''.strip()


# Example integration with sandbox_utils
SANDBOX_UTILS_STATE_MODULE = '''
"""State persistence helpers for sandbox_utils package.

These functions provide simple state management for LLM-generated code
that needs to preserve variables across multiple executions.
"""

import json
from typing import Any

def save_state(state: dict[str, Any], filename: str = ".session_state.json") -> None:
    """Save state dictionary to session workspace.

    Only JSON-serializable values are saved. Functions, classes, and modules
    are automatically filtered out.

    Args:
        state: Dictionary with serializable values
        filename: Target filename in /app/ (default: .session_state.json)

    Examples:
        >>> # Save variables for next execution
        >>> save_state({'counter': 42, 'data': [1, 2, 3]})

        >>> # Custom filename
        >>> save_state({'config': {'key': 'value'}}, 'mystate.json')
    """
    filtered = {
        k: v for k, v in state.items()
        if not k.startswith('_') and not callable(v) and
        type(v).__name__ in ('int', 'str', 'list', 'dict', 'float', 'bool', 'NoneType')
    }

    with open(f'/app/{filename}', 'w') as f:
        json.dump(filtered, f, indent=2)


def load_state(filename: str = ".session_state.json", default: dict | None = None) -> dict:
    """Load state dictionary from session workspace.

    Args:
        filename: Source filename in /app/ (default: .session_state.json)
        default: Return value if file not found (default: {})

    Returns:
        dict: Loaded state or default

    Examples:
        >>> # Load previous state
        >>> state = load_state()
        >>> counter = state.get('counter', 0)
        >>> print(f"Counter: {counter}")

        >>> # With custom default
        >>> state = load_state(default={'counter': 0, 'items': []})
    """
    try:
        with open(f'/app/{filename}', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}


def update_state(updates: dict[str, Any], filename: str = ".session_state.json") -> None:
    """Update existing state with new values (merge operation).

    Loads current state, merges with updates, and saves back. Useful for
    incrementally updating state without overwriting everything.

    Args:
        updates: Dictionary with values to merge into state
        filename: State filename (default: .session_state.json)

    Examples:
        >>> # First execution
        >>> update_state({'counter': 1, 'total': 100})

        >>> # Second execution (only updates counter)
        >>> update_state({'counter': 2})
        >>> # State is now {'counter': 2, 'total': 100}
    """
    current = load_state(filename)
    current.update(updates)
    save_state(current, filename)
'''
