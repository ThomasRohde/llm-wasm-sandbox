"""
File Processing Examples with sandbox_utils

This module demonstrates file processing workflows using shell-like utilities
from the sandbox_utils library. All operations run within the /app sandbox.

Examples include:
- Recursive file search and filtering
- Batch file renaming
- Directory tree generation
- File organization by type
"""

from sandbox import RuntimeType, create_sandbox


def demo_recursive_file_search():
    """Example: Find all files matching patterns across directory tree."""
    print("\n" + "=" * 60)
    print("DEMO: Recursive File Search")
    print("=" * 60)

    code = """
from sandbox_utils import find, mkdir, touch, echo

# Create sample directory structure with various file types
mkdir("/app/project/src", parents=True)
mkdir("/app/project/tests", parents=True)
mkdir("/app/project/docs", parents=True)
mkdir("/app/project/build", parents=True)

# Create source files
touch("/app/project/src/main.py")
touch("/app/project/src/utils.py")
touch("/app/project/src/config.py")

# Create test files
touch("/app/project/tests/test_main.py")
touch("/app/project/tests/test_utils.py")

# Create documentation
touch("/app/project/docs/README.md")
touch("/app/project/docs/API.md")

# Create build artifacts
touch("/app/project/build/output.log")
touch("/app/project/build/report.txt")

# Create config files
echo("debug=true", "/app/project/.env")
echo("name: MyProject", "/app/project/config.yaml")

print("Created project structure\\n")

# Example 1: Find all Python files
print("1. All Python files (.py):")
py_files = find("*.py", "/app/project", recursive=True)
for f in sorted(py_files):
    print(f"   {f}")

# Example 2: Find all markdown files
print("\\n2. All Markdown files (.md):")
md_files = find("*.md", "/app/project", recursive=True)
for f in sorted(md_files):
    print(f"   {f}")

# Example 3: Find files in specific directory
print("\\n3. Files in /app/project/src:")
src_files = find("*", "/app/project/src", recursive=False)
for f in sorted(src_files):
    print(f"   {f}")

# Example 4: Find test files specifically
print("\\n4. Test files (test_*.py):")
test_files = find("test_*.py", "/app/project", recursive=True)
for f in sorted(test_files):
    print(f"   {f}")

# Example 5: Count files by extension
print("\\n5. File count by extension:")
all_files = find("*", "/app/project", recursive=True)
extensions = {}
for f in all_files:
    ext = Path(f).suffix or "(no extension)"
    extensions[ext] = extensions.get(ext, 0) + 1

for ext in sorted(extensions.keys()):
    print(f"   {ext:15s}: {extensions[ext]} files")
"""

    # Execute in sandbox
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_batch_file_operations():
    """Example: Batch rename and organize files."""
    print("\n" + "=" * 60)
    print("DEMO: Batch File Operations")
    print("=" * 60)

    code = """
from sandbox_utils import find, mkdir, cp, ls, echo
from pathlib import Path

# Create files with inconsistent naming
mkdir("/app/uploads", parents=True)
echo("content1", "/app/uploads/IMG_001.jpg")
echo("content2", "/app/uploads/photo-2023-01.jpg")
echo("content3", "/app/uploads/scan_old.pdf")
echo("content4", "/app/uploads/document.pdf")
echo("content5", "/app/uploads/IMG_002.jpg")

print("Original files:")
for item in sorted(ls("/app/uploads")):
    print(f"  {item}")

# Organize files by type into subdirectories
mkdir("/app/organized/images", parents=True)
mkdir("/app/organized/documents", parents=True)

# Find and copy images
jpg_files = find("*.jpg", "/app/uploads")
print(f"\\nOrganizing {len(jpg_files)} images...")
for idx, img in enumerate(sorted(jpg_files), start=1):
    # Rename to consistent format: image_001.jpg, image_002.jpg, etc.
    new_name = f"image_{idx:03d}.jpg"
    cp(img, f"/app/organized/images/{new_name}")
    print(f"  {Path(img).name:25s} → {new_name}")

# Find and copy PDFs
pdf_files = find("*.pdf", "/app/uploads")
print(f"\\nOrganizing {len(pdf_files)} documents...")
for idx, pdf in enumerate(sorted(pdf_files), start=1):
    new_name = f"document_{idx:03d}.pdf"
    cp(pdf, f"/app/organized/documents/{new_name}")
    print(f"  {Path(pdf).name:25s} → {new_name}")

print("\\nOrganized structure:")
print("  /app/organized/")
print("    images/")
for item in sorted(ls("/app/organized/images")):
    print(f"      {item}")
print("    documents/")
for item in sorted(ls("/app/organized/documents")):
    print(f"      {item}")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_directory_tree_visualization():
    """Example: Generate and display directory trees."""
    print("\n" + "=" * 60)
    print("DEMO: Directory Tree Visualization")
    print("=" * 60)

    code = """
from sandbox_utils import tree, mkdir, touch, echo

# Create a complex project structure
mkdir("/app/myapp/src/components", parents=True)
mkdir("/app/myapp/src/utils", parents=True)
mkdir("/app/myapp/tests/unit", parents=True)
mkdir("/app/myapp/tests/integration", parents=True)
mkdir("/app/myapp/docs/api", parents=True)
mkdir("/app/myapp/config", parents=True)

# Add files
touch("/app/myapp/README.md")
touch("/app/myapp/setup.py")
touch("/app/myapp/.gitignore")

touch("/app/myapp/src/__init__.py")
touch("/app/myapp/src/main.py")
touch("/app/myapp/src/components/button.py")
touch("/app/myapp/src/components/form.py")
touch("/app/myapp/src/utils/helpers.py")

touch("/app/myapp/tests/__init__.py")
touch("/app/myapp/tests/unit/test_utils.py")
touch("/app/myapp/tests/integration/test_app.py")

touch("/app/myapp/docs/README.md")
touch("/app/myapp/docs/api/endpoints.md")

echo("DEBUG=true", "/app/myapp/config/dev.env")
echo("DEBUG=false", "/app/myapp/config/prod.env")

# Display full tree
print("Full Project Tree:")
print(tree("/app/myapp"))

# Display limited depth
print("\\nTop 2 Levels:")
print(tree("/app/myapp", max_depth=2))

# Display specific subtree
print("\\nSource Code Structure:")
print(tree("/app/myapp/src"))
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def demo_file_filtering_and_cleanup():
    """Example: Filter and clean up files based on patterns."""
    print("\n" + "=" * 60)
    print("DEMO: File Filtering and Cleanup")
    print("=" * 60)

    code = """
from sandbox_utils import find, rm, mkdir, touch, echo, ls
from pathlib import Path

# Create mixed files
mkdir("/app/workspace", parents=True)

# Source files (keep)
touch("/app/workspace/app.py")
touch("/app/workspace/utils.py")
touch("/app/workspace/config.py")

# Build artifacts (remove)
touch("/app/workspace/output.pyc")
touch("/app/workspace/__pycache__/app.cpython-311.pyc")
touch("/app/workspace/dist/app-1.0.tar.gz")

# Log files (old ones to remove)
echo("old logs", "/app/workspace/app.log")
echo("old logs", "/app/workspace/debug.log")

# Config (keep)
echo("config", "/app/workspace/.env")
touch("/app/workspace/settings.json")

print("Files before cleanup:")
all_files = find("*", "/app/workspace", recursive=True)
for f in sorted(all_files):
    print(f"  {f}")

# Clean up build artifacts
print("\\nRemoving build artifacts...")
pyc_files = find("*.pyc", "/app/workspace", recursive=True)
for f in pyc_files:
    print(f"  Removing: {Path(f).name}")
    rm(f)

# Remove cache directories
cache_dirs = ["/app/workspace/__pycache__", "/app/workspace/dist"]
for d in cache_dirs:
    if Path(d).exists():
        print(f"  Removing: {Path(d).name}/")
        rm(d, recursive=True)

# Remove log files
print("\\nRemoving log files...")
log_files = find("*.log", "/app/workspace", recursive=True)
for f in log_files:
    print(f"  Removing: {Path(f).name}")
    rm(f)

print("\\nFiles after cleanup:")
remaining = find("*", "/app/workspace", recursive=True)
for f in sorted(remaining):
    print(f"  {f}")

print(f"\\nCleaned up {len(all_files) - len(remaining)} files")
"""

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    result = sandbox.execute(code)

    print(result.stdout)
    print(f"\n[Fuel consumed: {result.fuel_consumed:,} instructions]")


def main():
    """Run all file processing examples."""
    print("\n" + "=" * 60)
    print("FILE PROCESSING EXAMPLES")
    print("Demonstrating sandbox_utils shell-like file operations")
    print("=" * 60)

    demo_recursive_file_search()
    demo_batch_file_operations()
    demo_directory_tree_visualization()
    demo_file_filtering_and_cleanup()

    print("\n" + "=" * 60)
    print("✓ All file processing examples completed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
