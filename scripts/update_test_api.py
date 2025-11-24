"""Helper script to update test files from old session API to new unified API.

OLD API:
    session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    sandbox = get_session_sandbox(session_id, runtime=RuntimeType.PYTHON, workspace_root=tmp_path)

NEW API:
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=tmp_path)
    session_id = sandbox.session_id

    # For existing session
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, session_id=session_id, workspace_root=tmp_path)
"""

from __future__ import annotations

import re
from pathlib import Path


def update_file(file_path: Path) -> None:
    """Update a single test file to use new API."""
    content = file_path.read_text()
    original = content

    # Update imports
    content = content.replace(
        "from sandbox import (\n    RuntimeType,\n    create_session_sandbox,\n    delete_session_workspace,\n    get_session_sandbox,\n)",
        "from sandbox import (\n    RuntimeType,\n    create_sandbox,\n    delete_session_workspace,\n)",
    )

    content = content.replace(
        "from sandbox import (\n    RuntimeType,\n    create_session_sandbox,\n    get_session_sandbox,\n)",
        "from sandbox import (\n    RuntimeType,\n    create_sandbox,\n)",
    )

    content = content.replace(
        "from sandbox import RuntimeType, create_session_sandbox",
        "from sandbox import RuntimeType, create_sandbox",
    )

    # Pattern 1: session_id, sandbox = create_session_sandbox(...)
    # Replace with: sandbox = create_sandbox(...) followed by session_id = sandbox.session_id
    # This is complex because we need to preserve indentation and parameters

    # For single-line calls
    pattern1 = r"(\s+)session_id, sandbox = create_session_sandbox\((.*?)\)"

    def replace_create(match):
        indent = match.group(1)
        params = match.group(2)
        return (
            f"{indent}sandbox = create_sandbox({params})\n{indent}session_id = sandbox.session_id"
        )

    content = re.sub(pattern1, replace_create, content)

    # For multi-line calls (harder - need to find closing paren)
    # Pattern: session_id, sandbox = create_session_sandbox(\n
    # We'll do a simple approach - look for these patterns
    lines = content.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if line has create_session_sandbox with newline after (
        if "session_id, sandbox = create_session_sandbox(" in line and not line.rstrip().endswith(
            ")"
        ):
            # Multi-line call - find the closing )
            indent = len(line) - len(line.lstrip())
            indent_str = " " * indent

            # Replace the assignment
            line = line.replace(
                "session_id, sandbox = create_session_sandbox(", "sandbox = create_sandbox("
            )
            new_lines.append(line)
            i += 1

            # Copy parameter lines until we find the closing )
            while i < len(lines) and ")" not in lines[i]:
                new_lines.append(lines[i])
                i += 1

            # Add the closing ) line
            if i < len(lines):
                new_lines.append(lines[i])
                i += 1
                # Add session_id extraction
                new_lines.append(f"{indent_str}session_id = sandbox.session_id")
        else:
            new_lines.append(line)
            i += 1

    content = "\n".join(new_lines)

    # Pattern 2: sandbox = get_session_sandbox(session_id, runtime=..., workspace_root=...)
    # Replace with: sandbox = create_sandbox(runtime=..., session_id=session_id, workspace_root=...)
    # The key is to add session_id as a parameter

    # Single-line version
    pattern2 = r"(\s+)sandbox(\w*) = get_session_sandbox\(\s*session_id,\s*"
    replacement2 = r"\1sandbox\2 = create_sandbox(session_id=session_id, "
    content = re.sub(pattern2, replacement2, content)

    # Also handle: sandbox = get_session_sandbox(\n    session_id,\n    runtime=...
    # This is trickier - let's do line-by-line
    lines = content.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check for multi-line get_session_sandbox
        if "sandbox" in line and "= get_session_sandbox(" in line:
            # Extract variable name
            var_match = re.search(r"(\s+)(sandbox\w*) = get_session_sandbox\(", line)
            if var_match:
                indent_str = var_match.group(1)
                var_match.group(2)

                # Replace the function call
                line = line.replace("get_session_sandbox(", "create_sandbox(")
                new_lines.append(line)
                i += 1

                # Look for session_id parameter line and modify it
                while i < len(lines):
                    param_line = lines[i]
                    if "session_id," in param_line or "session_id" in param_line:
                        # Convert positional to keyword arg
                        param_line = re.sub(
                            r"(\s+)session_id,", r"\1session_id=session_id,", param_line
                        )
                        new_lines.append(param_line)
                        i += 1
                        break
                    elif ")" in param_line:
                        # Reached end without finding session_id param
                        new_lines.append(param_line)
                        i += 1
                        break
                    else:
                        new_lines.append(param_line)
                        i += 1

                # Continue copying remaining lines
                continue

        new_lines.append(line)
        i += 1

    content = "\n".join(new_lines)

    # Write back if changed
    if content != original:
        file_path.write_text(content)
        print(f"Updated: {file_path}")
    else:
        print(f"No changes: {file_path}")


def main():
    """Update all test files."""
    test_dir = Path("tests")

    test_files = [
        "test_session_security.py",
        "test_session_metadata.py",
        "test_session_lifecycle.py",
        "test_session_file_ops.py",
        "test_session_file_roundtrip.py",
        "test_session_logging.py",
        "test_session_path_validation.py",
        "test_session_pruning.py",
    ]

    for test_file in test_files:
        file_path = test_dir / test_file
        if file_path.exists():
            print(f"\nProcessing {test_file}...")
            update_file(file_path)
        else:
            print(f"Skipping {test_file} (not found)")


if __name__ == "__main__":
    main()
