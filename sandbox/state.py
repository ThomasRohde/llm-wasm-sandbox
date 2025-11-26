"""State persistence utilities for maintaining Python globals across executions.

This module provides helpers for saving and restoring Python state between
sandbox executions using JSON serialization. State is automatically stored
in the session workspace and survives across multiple execute() calls.

Key Features:
- Automatic serialization of primitive types (int, str, list, dict, bool, float, None)
- Filtering of non-serializable objects (functions, modules, classes, file handles)
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
- File handles (TextIOWrapper, BufferedReader, etc.) are filtered automatically
- State file is workspace-scoped (no cross-session access)
- No code execution during deserialization (JSON.parse is safe)

Supported Types
--------------
- Primitives: int, str, float, bool, None
- Collections: list, dict, tuple, set (sets become lists)
- Paths: pathlib.Path, PosixPath, WindowsPath (converted to strings)
- Dates: datetime.datetime, date, time (converted to ISO format strings)
- Binary: bytes (converted to base64 with 'b64:' prefix)

Filtered Types (silently skipped)
---------------------------------
- Functions, modules, classes
- File handles: TextIOWrapper, BufferedReader, BufferedWriter, FileIO, etc.
- I/O objects with read/write/close/fileno methods

Limitations
----------
- Custom classes and numpy arrays not supported (use dicts/lists instead)
- Functions, modules, and classes are silently skipped
- Nested object depth limited by JSON serializer
- Large state may impact execution fuel consumption
- No automatic conflict resolution for concurrent executions
- Restored Path values will be strings (use Path(value) to convert back)
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
    - File handles and I/O objects
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

        # Skip I/O objects (file handles, etc.)
        if _is_io_object(value):
            continue

        # Only include serializable types
        if is_serializable(value):
            filtered[key] = value

    return filtered


def _is_io_object(obj: Any) -> bool:
    """Check if object is a file handle or I/O object.

    Detects file handles (TextIOWrapper, BufferedReader, etc.) and other
    I/O objects that cannot be serialized to JSON.

    Args:
        obj: Python object to check

    Returns:
        bool: True if obj is a file handle or I/O object
    """
    # Check common I/O type names
    io_type_names = (
        "TextIOWrapper",
        "BufferedReader",
        "BufferedWriter",
        "BufferedRandom",
        "FileIO",
        "BytesIO",
        "StringIO",
        "_IOBase",
    )
    type_name = type(obj).__name__
    if type_name in io_type_names:
        return True

    # Check for file-like duck typing (has read/write/close but isn't a common type)
    # Be careful not to catch dicts or other objects with these methods
    return hasattr(obj, "read") and hasattr(obj, "close") and hasattr(obj, "fileno")


def save_state_code(state_var: str = "globals()", filename: str = STATE_FILENAME) -> str:
    """Generate Python code to save state to JSON file.

    Returns a code snippet that serializes globals to a JSON file in the
    session workspace. This code should be appended to user code.

    Handles common non-JSON types by converting them:
    - pathlib.Path/PosixPath/WindowsPath → string
    - datetime.datetime/date/time → ISO format string
    - sets → lists
    - bytes → base64 string (prefixed with 'b64:')

    Filters out non-serializable types:
    - File handles (TextIOWrapper, BufferedReader, etc.)
    - Functions, classes, modules
    - Private variables (starting with _)

    Args:
        state_var: Python expression that returns dict to save (default: globals())
        filename: Target filename in /app/ (default: .session_state.json)

    Returns:
        str: Python code snippet to save state

    Examples:
        >>> code = save_state_code()
        >>> print(code)
        import json
        from pathlib import Path, PurePath
        import datetime
        import base64
        import io

        def _is_io_object(v):
            io_types = ('TextIOWrapper', 'BufferedReader', 'BufferedWriter',
                        'BufferedRandom', 'FileIO', 'BytesIO', 'StringIO')
            if type(v).__name__ in io_types:
                return True
            if hasattr(v, 'read') and hasattr(v, 'close') and hasattr(v, 'fileno'):
                return True
            return False

        def _serialize_value(v):
            if _is_io_object(v):
                return None  # Skip file handles
            if isinstance(v, PurePath):
                return str(v)
            elif isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
                return v.isoformat()
            elif isinstance(v, set):
                return list(v)
            elif isinstance(v, bytes):
                return 'b64:' + base64.b64encode(v).decode('ascii')
            elif isinstance(v, dict):
                return {k: _serialize_value(val) for k, val in v.items()}
            elif isinstance(v, (list, tuple)):
                return [_serialize_value(item) for item in v]
            return v

        _state = {}
        for k, v in globals().items():
            if k.startswith('_') or callable(v) or type(v).__name__ == 'module':
                continue
            if _is_io_object(v):
                continue
            try:
                _state[k] = _serialize_value(v)
            except:
                pass
        with open('/app/.session_state.json', 'w') as _f:
            json.dump(_state, _f)
        del _state, _f, _serialize_value, _is_io_object
    """
    return f"""
import json
from pathlib import Path, PurePath
import datetime
import base64

def _is_io_object(v):
    io_types = ('TextIOWrapper', 'BufferedReader', 'BufferedWriter',
                'BufferedRandom', 'FileIO', 'BytesIO', 'StringIO')
    if type(v).__name__ in io_types:
        return True
    if hasattr(v, 'read') and hasattr(v, 'close') and hasattr(v, 'fileno'):
        return True
    return False

def _serialize_value(v):
    if _is_io_object(v):
        return None  # Skip file handles
    if isinstance(v, PurePath):
        return str(v)
    elif isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    elif isinstance(v, set):
        return list(v)
    elif isinstance(v, bytes):
        return 'b64:' + base64.b64encode(v).decode('ascii')
    elif isinstance(v, dict):
        return {{k: _serialize_value(val) for k, val in v.items() if not _is_io_object(val)}}
    elif isinstance(v, (list, tuple)):
        return [_serialize_value(item) for item in v if not _is_io_object(item)]
    return v

_state = {{}}
for k, v in list({state_var}.items()):
    if k.startswith('_') or callable(v) or type(v).__name__ == 'module':
        continue
    if _is_io_object(v):
        continue
    try:
        _state[k] = _serialize_value(v)
    except:
        pass
with open('/app/{filename}', 'w') as _f:
    json.dump(_state, _f)
del _state, _f, _serialize_value, _is_io_object
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

Handles common non-JSON types by converting them:
- pathlib.Path/PosixPath/WindowsPath → string
- datetime.datetime/date/time → ISO format string
- sets → lists
- bytes → base64 string (prefixed with 'b64:')

Filters out non-serializable types:
- File handles (TextIOWrapper, BufferedReader, etc.)
- Functions, classes, modules
"""

import json
from typing import Any
from pathlib import PurePath
import datetime
import base64


def _is_io_object(v: Any) -> bool:
    """Check if value is a file handle or I/O object."""
    io_types = ('TextIOWrapper', 'BufferedReader', 'BufferedWriter',
                'BufferedRandom', 'FileIO', 'BytesIO', 'StringIO')
    if type(v).__name__ in io_types:
        return True
    if hasattr(v, 'read') and hasattr(v, 'close') and hasattr(v, 'fileno'):
        return True
    return False


def _serialize_value(v: Any) -> Any:
    """Convert non-JSON-serializable types to JSON-compatible values."""
    if _is_io_object(v):
        return None  # Skip file handles
    if isinstance(v, PurePath):
        return str(v)
    elif isinstance(v, (datetime.datetime, datetime.date, datetime.time)):
        return v.isoformat()
    elif isinstance(v, set):
        return list(v)
    elif isinstance(v, bytes):
        return 'b64:' + base64.b64encode(v).decode('ascii')
    elif isinstance(v, dict):
        return {k: _serialize_value(val) for k, val in v.items() if not _is_io_object(val)}
    elif isinstance(v, (list, tuple)):
        return [_serialize_value(item) for item in v if not _is_io_object(item)]
    return v


def save_state(state: dict[str, Any], filename: str = ".session_state.json") -> None:
    """Save state dictionary to session workspace.

    Automatically converts common non-JSON types:
    - pathlib.Path → string
    - datetime objects → ISO format string
    - sets → lists
    - bytes → base64 string

    Functions, classes, modules, and file handles are filtered out.

    Args:
        state: Dictionary with values to save
        filename: Target filename in /app/ (default: .session_state.json)

    Examples:
        >>> # Save variables for next execution
        >>> save_state({'counter': 42, 'data': [1, 2, 3]})

        >>> # Paths are automatically converted to strings
        >>> from pathlib import Path
        >>> save_state({'file': Path('/app/data.txt')})  # Saves as "/app/data.txt"

        >>> # Custom filename
        >>> save_state({'config': {'key': 'value'}}, 'mystate.json')
    """
    filtered = {}
    for k, v in state.items():
        if k.startswith('_') or callable(v) or type(v).__name__ == 'module':
            continue
        if _is_io_object(v):
            continue
        try:
            filtered[k] = _serialize_value(v)
        except:
            pass

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
