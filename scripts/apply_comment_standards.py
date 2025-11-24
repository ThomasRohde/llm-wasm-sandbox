#!/usr/bin/env python3
"""Apply comment best practices to all Python source files using Copilot CLI.

This script iterates through all Python files in ./sandbox
and applies comment best practices using the copilot command with Claude Sonnet 4.5.
"""

import subprocess
import sys
from pathlib import Path

# Best practices prompt for commenting
COMMENT_PROMPT = """Review and improve the comments in this Python file according to these best practices:

1. **Module-level docstrings**: Ensure the file has a clear module docstring explaining its purpose
2. **Function/method docstrings**: All public functions should have docstrings with:
   - Brief description of what it does
   - Args: parameter descriptions with types
   - Returns: return value description with type
   - Raises: any exceptions that might be raised
3. **Class docstrings**: Classes should have docstrings explaining their purpose and responsibility
4. **Inline comments**: Add inline comments for complex logic, but only when the *why* isn't obvious from the code itself
5. **Remove redundant comments**: Remove comments that just restate what the code obviously does
6. **Type hints**: Ensure type hints are present and accurate (Python 3.12+ style)
7. **TODO/FIXME**: If you find any, ensure they're actionable and properly formatted

Focus on clarity and maintainability. Explain *why*, not *what* the code does.
DO NOT change the functionality of the code, only improve documentation and comments.
"""


def main() -> None:
    """Main entry point for the script."""
    # Get all Python files in sandbox directory
    sandbox_dir = Path("./sandbox").resolve()
    all_python_files = list(sandbox_dir.rglob("*.py"))

    if not all_python_files:
        print("No Python files found to process.")
        return

    # Get list of uncommitted files using git
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, check=True
        )
        uncommitted_files = set(result.stdout.strip().split("\n"))
    except subprocess.CalledProcessError:
        print("Error: Failed to get git status. Are you in a git repository?")
        sys.exit(1)

    # Filter out uncommitted files (already commented)
    python_files = [
        f
        for f in all_python_files
        if str(f.relative_to(Path.cwd())).replace("\\", "/") not in uncommitted_files
    ]

    if not python_files:
        print("No Python files to process (all files are uncommitted/already commented).")
        return

    print(f"Found {len(all_python_files)} total Python file(s)")
    uncommitted_count = len(
        uncommitted_files
        & {str(f.relative_to(Path.cwd())).replace("\\", "/") for f in all_python_files}
    )
    print(f"Skipping {uncommitted_count} uncommitted file(s)")
    print(f"Processing {len(python_files)} file(s)\n")

    success_count = 0
    failure_count = 0
    failed_files = []

    for file_path in python_files:
        relative_path = file_path.relative_to(Path.cwd())
        print(f"Processing: {relative_path}")

        try:
            # Build prompt with file path for Copilot to update in place
            prompt = f"""{COMMENT_PROMPT}

Please review and improve the comments in the file: {relative_path}

Update the file directly with your improvements."""

            # Call GitHub Copilot CLI - it will update the file in place
            copilot_cmd = r"C:\Users\E29667\AppData\Roaming\npm\copilot.cmd"

            result = subprocess.run(
                [copilot_cmd, "--model", "claude-sonnet-4.5", "--allow-all-tools"],
                input=prompt,
                capture_output=False,
                text=True,
                shell=True,
            )

            if result.returncode == 0:
                print("  ✓ Success\n")
                success_count += 1
            else:
                print(f"  ✗ Failed (exit code: {result.returncode})\n")
                failure_count += 1
                failed_files.append(str(relative_path))
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
            failure_count += 1
            failed_files.append(str(relative_path))

    # Summary
    print("=" * 60)
    print("Summary:")
    print(f"  Total files: {len(python_files)}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failure_count}")

    if failed_files:
        print("\nFailed files:")
        for file in failed_files:
            print(f"  - {file}")
        sys.exit(1)

    print("\nAll files processed successfully!")


if __name__ == "__main__":
    main()
