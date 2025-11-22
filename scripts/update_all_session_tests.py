"""Update all remaining session test files to use new create_sandbox API."""

import re
from pathlib import Path


def update_test_file(file_path: Path) -> None:
    """Update a single test file."""
    content = file_path.read_text()
    original = content

    # Update imports - handle various import patterns
    content = content.replace(
        'from sandbox import (\n    RuntimeType,\n    create_session_sandbox,\n    delete_session_workspace,\n    get_session_sandbox,\n    list_session_files,\n    read_session_file,\n    write_session_file,\n)',
        'from sandbox import (\n    RuntimeType,\n    create_sandbox,\n    delete_session_workspace,\n    list_session_files,\n    read_session_file,\n    write_session_file,\n)'
    )

    content = content.replace(
        'from sandbox import (\n    RuntimeType,\n    create_session_sandbox,\n    delete_session_workspace,\n    get_session_sandbox,\n)',
        'from sandbox import (\n    RuntimeType,\n    create_sandbox,\n    delete_session_workspace,\n)'
    )

    content = content.replace(
        '    create_session_sandbox,',
        '    create_sandbox,'
    )

    content = re.sub(r'    get_session_sandbox,\n', '', content)

    # Pattern 1: Simple case - session_id, sandbox = create_session_sandbox(runtime=..., workspace_root=...)
    content = re.sub(
        r'(\s+)session_id, sandbox = create_session_sandbox\(\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+)\s*\)',
        r'\1sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=\2)\n\1session_id = sandbox.session_id',
        content
    )

    # Pattern 2: With logger
    content = re.sub(
        r'(\s+)session_id, sandbox = create_session_sandbox\(\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+),\s*logger=(\w+)\s*\)',
        r'\1sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=\2, logger=\3)\n\1session_id = sandbox.session_id',
        content
    )

    # Pattern 3: Underscore assignment - session_id, _ = create_session_sandbox(...)
    content = re.sub(
        r'(\s+)session_id, _ = create_session_sandbox\(\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+)\s*\)',
        r'\1sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=\2)\n\1session_id = sandbox.session_id',
        content
    )

    # Pattern 4: With logger and underscore
    content = re.sub(
        r'(\s+)session_id, _ = create_session_sandbox\(\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+),\s*logger=(\w+)\s*\)',
        r'\1sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=\2, logger=\3)\n\1session_id = sandbox.session_id',
        content
    )

    # Pattern 5: Numbered variables - session_id_a, sandbox_a = create_session_sandbox(...)
    content = re.sub(
        r'(\s+)session_id_([a-z]), sandbox_([a-z]) = create_session_sandbox\(\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+)\s*\)',
        r'\1sandbox_\2 = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=\4)\n\1session_id_\2 = sandbox_\3.session_id',
        content
    )

    # Pattern 6: Just underscore - _, sandbox = create_session_sandbox(...)
    content = re.sub(
        r'(\s+)_, sandbox = create_session_sandbox\(\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+)\s*\)',
        r'\1sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=\2)',
        content
    )

    # Pattern 7: get_session_sandbox calls - sandbox = get_session_sandbox(session_id, runtime=..., workspace_root=...)
    content = re.sub(
        r'(\s+)sandbox = get_session_sandbox\(\s*session_id,\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+)\s*\)',
        r'\1sandbox = create_sandbox(runtime=RuntimeType.PYTHON, session_id=session_id, workspace_root=\2)',
        content
    )

    # Pattern 8: get_session_sandbox with logger
    content = re.sub(
        r'(\s+)sandbox = get_session_sandbox\(\s*session_id,\s*runtime=RuntimeType\.PYTHON,\s*workspace_root=(\w+),\s*logger=(\w+)\s*\)',
        r'\1sandbox = create_sandbox(runtime=RuntimeType.PYTHON, session_id=session_id, workspace_root=\2, logger=\3)',
        content
    )

    if content != original:
        file_path.write_text(content)
        print(f"✓ Updated: {file_path.name}")
    else:
        print(f"  No changes: {file_path.name}")


def main():
    """Update all session test files."""
    test_files = [
        'tests/test_session_logging.py',
        'tests/test_session_file_ops.py',
        'tests/test_session_file_roundtrip.py',
        'tests/test_session_path_validation.py',
        'tests/test_session_pruning.py',
    ]

    print("Updating session test files...")
    for file_name in test_files:
        file_path = Path(file_name)
        if file_path.exists():
            update_test_file(file_path)
        else:
            print(f"  Skipping: {file_name} (not found)")

    print("\nDone!")


if __name__ == "__main__":
    main()
