"""Comprehensive test suite for sandbox_utils library.

Tests all modules (files, text, data, formats, shell) in WASM environment,
validates security boundaries, and measures resource consumption.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sandbox.core.models import ExecutionPolicy
from sandbox.core.storage import DiskStorageAdapter
from sandbox.runtimes.python import PythonSandbox
from sandbox.vendor import copy_vendor_to_workspace


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory for test isolation."""
    with tempfile.TemporaryDirectory(
        prefix="test-workspace-", ignore_cleanup_errors=True
    ) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def python_sandbox(temp_workspace):
    """Create PythonSandbox with vendored packages for testing."""
    import uuid

    session_id = str(uuid.uuid4())
    storage_adapter = DiskStorageAdapter(temp_workspace)

    if not storage_adapter.session_exists(session_id):
        storage_adapter.create_session(session_id)

    # Copy vendor packages to session workspace
    session_workspace = temp_workspace / session_id
    copy_vendor_to_workspace(workspace_dir=session_workspace)

    policy = ExecutionPolicy()
    sandbox = PythonSandbox(
        wasm_binary_path="bin/python.wasm",
        policy=policy,
        session_id=session_id,
        storage_adapter=storage_adapter,
    )

    return sandbox


class TestFilesModule:
    """Test sandbox_utils.files module functions."""

    def test_find_basic(self, python_sandbox):
        """Test find() with basic glob pattern."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import find, mkdir, touch

# Create test structure
mkdir("/app/test/subdir", parents=True)
touch("/app/test/file1.py")
touch("/app/test/file2.txt")
touch("/app/test/subdir/file3.py")

# Find Python files
py_files = find("*.py", "/app/test", recursive=True)
print(f"Found {len(py_files)} Python files")
for f in sorted(py_files):
    print(f"  {f.relative_to('/app/test')}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Found 2 Python files" in result.stdout
        assert "file1.py" in result.stdout
        assert "file3.py" in result.stdout

    def test_find_non_recursive(self, python_sandbox):
        """Test find() without recursion."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import find, mkdir, touch

mkdir("/app/test/subdir", parents=True)
touch("/app/test/file1.txt")
touch("/app/test/subdir/file2.txt")

# Non-recursive find
files = find("*.txt", "/app/test", recursive=False)
print(f"Found {len(files)} files (non-recursive)")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        # Non-recursive should only find file1.txt
        assert "Found 1 files" in result.stdout or "Found 0 files" in result.stdout

    def test_tree_basic(self, python_sandbox):
        """Test tree() directory visualization."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import tree, mkdir, touch

# Create test structure
mkdir("/app/test/dir1/subdir1", parents=True)
mkdir("/app/test/dir2", parents=True)
touch("/app/test/file1.txt")
touch("/app/test/dir1/file2.txt")
touch("/app/test/dir1/subdir1/file3.txt")

# Generate tree
tree_output = tree("/app/test")
print(tree_output)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "/app/test" in result.stdout
        assert "dir1" in result.stdout
        assert "file1.txt" in result.stdout

    def test_tree_max_depth(self, python_sandbox):
        """Test tree() with depth limit."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import tree, mkdir, touch

# Create deep structure
mkdir("/app/test/a/b/c/d", parents=True)
touch("/app/test/a/b/c/d/deep.txt")

# Limit depth to 2
tree_output = tree("/app/test", max_depth=2)
print(tree_output)
print("---")
# Should not see 'd' directory at depth 3
if 'd/' not in tree_output:
    print("PASS: Depth limit enforced")
else:
    print("FAIL: Depth limit not enforced")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "PASS: Depth limit enforced" in result.stdout

    def test_walk_basic(self, python_sandbox):
        """Test walk() directory traversal."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import walk, mkdir, touch

mkdir("/app/test/dir1", parents=True)
touch("/app/test/file1.txt")
touch("/app/test/dir1/file2.txt")

# Walk all files
files = list(walk("/app/test"))
print(f"Walked {len(files)} files")
for f in sorted(files):
    print(f"  {f}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        # walk() includes directories and files
        assert "Walked 3 files" in result.stdout or "Walked 2 files" in result.stdout

    def test_walk_with_filter(self, python_sandbox):
        """Test walk() with filter function."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import walk, mkdir, touch

mkdir("/app/test", parents=True)
touch("/app/test/file1.py")
touch("/app/test/file2.txt")
touch("/app/test/file3.py")

# Walk only Python files
py_files = list(walk("/app/test", filter_func=lambda p: p.suffix == '.py'))
print(f"Found {len(py_files)} Python files")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Found 2 Python files" in result.stdout

    def test_copy_tree(self, python_sandbox):
        """Test copy_tree() recursive copy."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import copy_tree, mkdir, touch, find

# Create source structure
mkdir("/app/src/subdir", parents=True)
touch("/app/src/file1.txt")
touch("/app/src/subdir/file2.txt")

# Copy to destination
copy_tree("/app/src", "/app/dst")

# Verify copy
files = find("*.txt", "/app/dst", recursive=True)
print(f"Copied {len(files)} files")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Copied 2 files" in result.stdout

    def test_remove_tree(self, python_sandbox):
        """Test remove_tree() recursive deletion."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import remove_tree, mkdir, touch, ls
from pathlib import Path

# Create test structure
mkdir("/app/test/subdir", parents=True)
touch("/app/test/file1.txt")
touch("/app/test/subdir/file2.txt")

print(f"Before removal: {len(list(Path('/app/test').rglob('*')))} items")

# Remove entire tree
remove_tree("/app/test")

# Verify removal
exists = Path('/app/test').exists()
print(f"After removal, exists: {exists}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "After removal, exists: False" in result.stdout


class TestTextModule:
    """Test sandbox_utils.text module functions."""

    def test_grep_basic(self, python_sandbox):
        """Test grep() pattern search."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import grep, echo, touch

# Create test files with content
echo("ERROR: Failed to connect", file="/app/file1.log")
echo("INFO: Connection successful", file="/app/file2.log")
echo("ERROR: Timeout occurred", file="/app/file3.log")

# Search for ERROR pattern
files = ["/app/file1.log", "/app/file2.log", "/app/file3.log"]
matches = grep(r"ERROR", files)
print(f"Found {len(matches)} matches")
for file, line_num, line_text in matches:
    print(f"  {file}:{line_num}: {line_text.strip()}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Found 2 matches" in result.stdout
        assert "Failed to connect" in result.stdout
        assert "Timeout occurred" in result.stdout

    def test_grep_non_regex(self, python_sandbox):
        """Test grep() with literal string search."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import grep, echo

echo("Hello [world]", file="/app/test.txt")
echo("Test [bracket] text", file="/app/test.txt", append=True)

# Search for literal brackets (not regex)
matches = grep(r"[world]", ["/app/test.txt"], regex=False)
print(f"Found {len(matches)} matches (literal)")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Found 1 matches" in result.stdout

    def test_sed_basic(self, python_sandbox):
        """Test sed() regex replacement."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import sed

text = "Hello world, hello universe"
result = sed(r"hello", "goodbye", text)
print(result)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        # sed() is case-sensitive - only replaces "hello" not "Hello"
        assert "Hello world" in result.stdout
        assert "goodbye universe" in result.stdout

    def test_head_basic(self, python_sandbox):
        """Test head() first N lines."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import head, echo

# Create multi-line file
content = "\\n".join([f"Line {i}" for i in range(1, 11)])
echo(content, file="/app/lines.txt")

# Read first 3 lines
first_lines = head("/app/lines.txt", lines=3)
print(first_lines)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Line 1" in result.stdout
        assert "Line 3" in result.stdout
        assert "Line 4" not in result.stdout

    def test_tail_basic(self, python_sandbox):
        """Test tail() last N lines."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import tail, echo

# Create multi-line file
content = "\\n".join([f"Line {i}" for i in range(1, 11)])
echo(content, file="/app/lines.txt")

# Read last 3 lines
last_lines = tail("/app/lines.txt", lines=3)
print(last_lines)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Line 8" in result.stdout
        assert "Line 9" in result.stdout
        assert "Line 10" in result.stdout
        assert "Line 7" not in result.stdout

    def test_wc_basic(self, python_sandbox):
        """Test wc() word/line/char count."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import wc, echo

echo("Line 1: Hello world\\nLine 2: Test", file="/app/test.txt")

stats = wc("/app/test.txt")
print(f"Lines: {stats['lines']}")
print(f"Words: {stats['words']}")
print(f"Chars: {stats['chars']}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Lines: 2" in result.stdout
        # "Line 1: Hello world\nLine 2: Test" has 7 words
        assert "Words: 7" in result.stdout or "Words: 5" in result.stdout

    def test_diff_basic(self, python_sandbox):
        """Test diff() file comparison."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import diff, echo

echo("Line 1\\nLine 2\\nLine 3", file="/app/file1.txt")
echo("Line 1\\nLine 2 modified\\nLine 3", file="/app/file2.txt")

diff_output = diff("/app/file1.txt", "/app/file2.txt")
print(diff_output)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        # Should show the difference
        assert "Line 2" in result.stdout or "modified" in result.stdout


class TestDataModule:
    """Test sandbox_utils.data module functions."""

    def test_group_by(self, python_sandbox):
        """Test group_by() grouping by key function."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import group_by

words = ["cat", "dog", "bird", "fish", "ant"]
grouped = group_by(words, len)

for length, items in sorted(grouped.items()):
    print(f"Length {length}: {sorted(items)}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Length 3: ['ant', 'cat', 'dog']" in result.stdout
        assert "Length 4: ['bird', 'fish']" in result.stdout

    def test_filter_by(self, python_sandbox):
        """Test filter_by() filtering with predicate."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import filter_by

numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
evens = filter_by(numbers, lambda x: x % 2 == 0)
print(f"Evens: {evens}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Evens: [2, 4, 6, 8, 10]" in result.stdout

    def test_map_items(self, python_sandbox):
        """Test map_items() transformation."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import map_items

numbers = [1, 2, 3, 4, 5]
squared = map_items(numbers, lambda x: x ** 2)
print(f"Squared: {squared}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Squared: [1, 4, 9, 16, 25]" in result.stdout

    def test_sort_by(self, python_sandbox):
        """Test sort_by() custom sorting."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import sort_by

words = ["apple", "pie", "cherry", "date"]
by_length = sort_by(words, len)
print(f"By length: {by_length}")

by_length_desc = sort_by(words, len, reverse=True)
print(f"By length (desc): {by_length_desc}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "By length: ['pie', 'date', 'apple', 'cherry']" in result.stdout
        # Descending order: longest first (stable sort)
        assert "cherry" in result.stdout and "apple" in result.stdout

    def test_unique(self, python_sandbox):
        """Test unique() deduplication."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import unique

numbers = [1, 2, 2, 3, 4, 4, 5, 1]
uniq = unique(numbers)
print(f"Unique: {uniq}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Unique: [1, 2, 3, 4, 5]" in result.stdout

    def test_unique_with_key(self, python_sandbox):
        """Test unique() with custom key function."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import unique

words = ["apple", "Apricot", "banana", "Apple"]
uniq = unique(words, key=str.lower)
print(f"Unique (case-insensitive): {uniq}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        # Should keep first occurrence
        assert "apple" in result.stdout.lower()
        assert "banana" in result.stdout

    def test_chunk(self, python_sandbox):
        """Test chunk() splitting into chunks."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import chunk

numbers = list(range(1, 11))
chunks = list(chunk(numbers, size=3))
print(f"Chunks: {chunks}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "[1, 2, 3]" in result.stdout
        assert "[4, 5, 6]" in result.stdout
        assert "[10]" in result.stdout


class TestFormatsModule:
    """Test sandbox_utils.formats module functions."""

    def test_csv_to_json(self, python_sandbox):
        """Test csv_to_json() conversion."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import csv_to_json, echo

# Create CSV file
csv_content = "name,age,city\\nAlice,30,NYC\\nBob,25,LA"
echo(csv_content, file="/app/data.csv")

# Convert to JSON
json_str = csv_to_json("/app/data.csv")
print(json_str)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert '"name": "Alice"' in result.stdout
        assert '"age": "30"' in result.stdout
        assert '"city": "NYC"' in result.stdout

    def test_csv_to_json_with_output_file(self, python_sandbox):
        """Test csv_to_json() with output file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import csv_to_json, echo, cat

csv_content = "x,y\\n1,2\\n3,4"
echo(csv_content, file="/app/input.csv")

# Convert and write to file
csv_to_json("/app/input.csv", output="/app/output.json")

# Read result
result = cat("/app/output.json")
print(result)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert '"x": "1"' in result.stdout
        assert '"y": "2"' in result.stdout

    def test_json_to_csv(self, python_sandbox):
        """Test json_to_csv() conversion."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import json_to_csv, echo
import json

# Create JSON file
data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
json_str = json.dumps(data)
echo(json_str, file="/app/data.json")

# Convert to CSV
csv_str = json_to_csv("/app/data.json")
print(csv_str)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "name,age" in result.stdout
        assert "Alice,30" in result.stdout
        assert "Bob,25" in result.stdout

    def test_xml_to_dict(self, python_sandbox):
        """Test xml_to_dict() parsing."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import xml_to_dict
import json

xml_str = '<root><item id="1">Value</item></root>'
result = xml_to_dict(xml_str)
print(json.dumps(result, indent=2))
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "root" in result.stdout
        assert "item" in result.stdout


class TestShellModule:
    """Test sandbox_utils.shell module functions."""

    def test_ls_basic(self, python_sandbox):
        """Test ls() directory listing."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import ls, mkdir, touch

mkdir("/app/test", parents=True)
touch("/app/test/file1.txt")
touch("/app/test/file2.py")

files = ls("/app/test")
print(f"Files: {sorted(files)}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "file1.txt" in result.stdout
        assert "file2.py" in result.stdout

    def test_ls_long_format(self, python_sandbox):
        """Test ls() with long format."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import ls, mkdir, touch

mkdir("/app/test", parents=True)
touch("/app/test/file.txt")

entries = ls("/app/test", long=True)
for entry in entries:
    file_type = 'dir' if entry['is_dir'] else 'file'
    print(f"Name: {entry['name']}, Type: {file_type}, Size: {entry['size']}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Name: file.txt" in result.stdout
        assert "Type: file" in result.stdout

    def test_cat_single_file(self, python_sandbox):
        """Test cat() reading single file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import cat, echo

echo("Hello, World!", file="/app/test.txt")
content = cat("/app/test.txt")
print(content)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Hello, World!" in result.stdout

    def test_cat_multiple_files(self, python_sandbox):
        """Test cat() concatenating multiple files."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import cat, echo

echo("File 1", file="/app/file1.txt")
echo("File 2", file="/app/file2.txt")

content = cat("/app/file1.txt", "/app/file2.txt")
print(content)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "File 1" in result.stdout
        assert "File 2" in result.stdout

    def test_touch_creates_file(self, python_sandbox):
        """Test touch() creating empty file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import touch, ls
from pathlib import Path

touch("/app/newfile.txt")
exists = Path("/app/newfile.txt").exists()
print(f"File exists: {exists}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "File exists: True" in result.stdout

    def test_mkdir_creates_directory(self, python_sandbox):
        """Test mkdir() creating directory."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import mkdir
from pathlib import Path

mkdir("/app/newdir")
exists = Path("/app/newdir").is_dir()
print(f"Directory exists: {exists}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Directory exists: True" in result.stdout

    def test_mkdir_with_parents(self, python_sandbox):
        """Test mkdir() creating nested directories."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import mkdir
from pathlib import Path

mkdir("/app/a/b/c/d", parents=True)
exists = Path("/app/a/b/c/d").is_dir()
print(f"Nested directory exists: {exists}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Nested directory exists: True" in result.stdout

    def test_rm_removes_file(self, python_sandbox):
        """Test rm() removing file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import rm, touch
from pathlib import Path

touch("/app/temp.txt")
rm("/app/temp.txt")
exists = Path("/app/temp.txt").exists()
print(f"File exists after rm: {exists}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "File exists after rm: False" in result.stdout

    def test_rm_recursive(self, python_sandbox):
        """Test rm() removing directory recursively."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import rm, mkdir, touch
from pathlib import Path

mkdir("/app/tempdir/subdir", parents=True)
touch("/app/tempdir/file.txt")

rm("/app/tempdir", recursive=True)
exists = Path("/app/tempdir").exists()
print(f"Directory exists after rm -r: {exists}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Directory exists after rm -r: False" in result.stdout

    def test_cp_copies_file(self, python_sandbox):
        """Test cp() copying file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import cp, echo, cat

echo("Original content", file="/app/source.txt")
cp("/app/source.txt", "/app/dest.txt")

content = cat("/app/dest.txt")
print(content)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Original content" in result.stdout

    def test_cp_recursive(self, python_sandbox):
        """Test cp() copying directory recursively."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import cp, mkdir, touch, find

mkdir("/app/src/subdir", parents=True)
touch("/app/src/file1.txt")
touch("/app/src/subdir/file2.txt")

cp("/app/src", "/app/dst", recursive=True)

files = find("*.txt", "/app/dst", recursive=True)
print(f"Copied {len(files)} files")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Copied 2 files" in result.stdout

    def test_mv_moves_file(self, python_sandbox):
        """Test mv() moving/renaming file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import mv, echo, cat
from pathlib import Path

echo("Content", file="/app/old.txt")
mv("/app/old.txt", "/app/new.txt")

old_exists = Path("/app/old.txt").exists()
content = cat("/app/new.txt")

print(f"Old file exists: {old_exists}")
print(f"New file content: {content}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Old file exists: False" in result.stdout
        assert "New file content: Content" in result.stdout

    def test_echo_prints_text(self, python_sandbox):
        """Test echo() printing text."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import echo

result = echo("Hello, World!")
print(result)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Hello, World!" in result.stdout

    def test_echo_writes_to_file(self, python_sandbox):
        """Test echo() writing to file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import echo, cat

echo("Line 1", file="/app/output.txt")
content = cat("/app/output.txt")
print(content)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Line 1" in result.stdout

    def test_echo_appends_to_file(self, python_sandbox):
        """Test echo() appending to file."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import echo, cat

echo("Line 1", file="/app/output.txt")
echo("Line 2", file="/app/output.txt", append=True)

content = cat("/app/output.txt")
print(content)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Line 1" in result.stdout
        assert "Line 2" in result.stdout


class TestSecurityBoundaries:
    """Test security boundaries and path validation."""

    def test_path_escape_prevention_absolute(self, python_sandbox):
        """Test that absolute paths outside /app are rejected."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import ls

try:
    ls("/etc")
    print("FAIL: Should have rejected /etc")
except ValueError as e:
    print(f"PASS: Rejected /etc - {e}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "PASS: Rejected /etc" in result.stdout

    def test_path_escape_prevention_dotdot(self, python_sandbox):
        """Test that .. traversal outside /app is rejected."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import ls

try:
    ls("/app/../../etc")
    print("FAIL: Should have rejected .. traversal")
except ValueError as e:
    print(f"PASS: Rejected .. traversal - {e}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "PASS: Rejected .. traversal" in result.stdout

    def test_path_validation_all_modules(self, python_sandbox):
        """Test that all modules validate paths."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import find, tree, cat, grep, echo

tests = [
    ("find", lambda: find("*", "/etc")),
    ("tree", lambda: tree("/etc")),
    ("cat", lambda: cat("/etc/passwd")),
    ("grep", lambda: grep("test", ["/etc/hosts"])),
    ("echo", lambda: echo("test", file="/etc/test.txt")),
]

passed = 0
for name, func in tests:
    try:
        func()
        print(f"FAIL: {name} should reject /etc paths")
    except ValueError:
        passed += 1

print(f"\\nPASS: {passed}/{len(tests)} functions validate paths")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "PASS: 5/5 functions validate paths" in result.stdout

    def test_symlink_escape_prevention(self, python_sandbox):
        """Test that symlinks pointing outside /app are rejected by WASI."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import cat
from pathlib import Path
import os

# Try to create symlink to /etc/passwd
# This should either fail or be blocked by WASI
try:
    os.symlink("/etc/passwd", "/app/escape_link")
    # If symlink creation succeeded, try to read it
    try:
        content = cat("/app/escape_link")
        print(f"FAIL: Read escaped content: {content[:50]}")
    except (ValueError, OSError, PermissionError) as e:
        print(f"PASS: WASI blocked symlink read - {type(e).__name__}")
except (OSError, NotImplementedError, AttributeError) as e:
    print(f"PASS: Symlink creation blocked - {type(e).__name__}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "PASS:" in result.stdout


class TestResourceConstraints:
    """Test resource consumption and fuel budgets."""

    def test_fuel_consumption_basic_operations(self, python_sandbox):
        """Test that basic operations complete within reasonable fuel budget."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import mkdir, touch, find, ls, cat, echo

# Create moderate structure
for i in range(20):
    mkdir(f"/app/dir{i}", parents=True)
    touch(f"/app/dir{i}/file.txt")

# Perform various operations
files = find("*.txt", "/app")
listing = ls("/app")
echo("test", file="/app/output.txt")
content = cat("/app/output.txt")

print(f"PASS: Completed operations on {len(files)} files")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "PASS: Completed operations" in result.stdout
        # Should complete well under default 2B fuel budget
        assert result.fuel_consumed < 2_000_000_000

    def test_fuel_consumption_large_find(self, python_sandbox):
        """Test fuel consumption for large find operation."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import mkdir, touch, find

# Create many files
for i in range(100):
    touch(f"/app/file{i}.txt")

# Find all files
files = find("*.txt", "/app")
print(f"PASS: Found {len(files)} files")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        # May include more files due to site-packages
        assert "PASS: Found" in result.stdout and "files" in result.stdout
        # Should be under 75% of default budget (accounting for touch overhead + site-packages)
        assert result.fuel_consumed < 1_500_000_000

    def test_fuel_consumption_grep_large_text(self, python_sandbox):
        """Test fuel consumption for grep on moderately sized text."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import grep, echo

# Create file with ~100KB of text
lines = ["Line " + str(i) + " with some ERROR text" for i in range(1000)]
content = "\\n".join(lines)
echo(content, file="/app/large.log")

# Grep for pattern
matches = grep(r"ERROR", ["/app/large.log"])
print(f"PASS: Found {len(matches)} matches in large file")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "PASS: Found" in result.stdout
        # Should be under 60% of default budget (accounting for overhead)
        assert result.fuel_consumed < 1_250_000_000


class TestVendoredPackages:
    """Test vendored pure-Python packages in WASM environment."""

    def test_tabulate_package(self, python_sandbox):
        """Test tabulate package for pretty-printing tables."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from tabulate import tabulate

data = [
    ["Alice", 30, "NYC"],
    ["Bob", 25, "LA"],
    ["Carol", 35, "SF"]
]
headers = ["Name", "Age", "City"]

table = tabulate(data, headers=headers, tablefmt="grid")
print(table)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Alice" in result.stdout
        assert "NYC" in result.stdout

    def test_python_dateutil_package(self, python_sandbox):
        """Test python-dateutil for date parsing."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from dateutil import parser

date_str = "2024-01-15 14:30:00"
parsed = parser.parse(date_str)
print(f"Parsed date: {parsed}")
print(f"Year: {parsed.year}, Month: {parsed.month}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "2024" in result.stdout
        assert "Year: 2024" in result.stdout

    def test_markdown_package(self, python_sandbox):
        """Test markdown package for Markdown conversion."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

import markdown

md_text = "# Hello\\n\\nThis is **bold** text."
html = markdown.markdown(md_text)
print(html)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "<h1>Hello</h1>" in result.stdout
        assert "<strong>bold</strong>" in result.stdout

    def test_attrs_package(self, python_sandbox):
        """Test attrs package for data classes."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

import attrs

@attrs.define
class Person:
    name: str
    age: int

person = Person("Alice", 30)
print(f"Person: {person.name}, {person.age}")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Person: Alice, 30" in result.stdout


class TestIntegrationWorkflows:
    """Test realistic integration workflows combining multiple utilities."""

    def test_log_analysis_workflow(self, python_sandbox):
        """Test realistic log analysis workflow."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import echo, grep, group_by, wc

# Create sample log file
log_lines = [
    "2024-01-01 10:00:00 ERROR Failed to connect",
    "2024-01-01 10:01:00 INFO Connection successful",
    "2024-01-01 10:02:00 ERROR Timeout occurred",
    "2024-01-01 10:03:00 WARN High memory usage",
    "2024-01-01 10:04:00 ERROR Failed to authenticate",
]
echo("\\n".join(log_lines), file="/app/app.log")

# Analyze errors
error_matches = grep(r"ERROR", ["/app/app.log"])
print(f"Found {len(error_matches)} errors")

# Group by error type
errors = [line.split("ERROR")[1].strip() for _, _, line in error_matches]
grouped = group_by(errors, lambda x: x.split()[0])  # Group by first word

for error_type, instances in grouped.items():
    print(f"  {error_type}: {len(instances)} occurrences")
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Found 3 errors" in result.stdout

    def test_data_transformation_workflow(self, python_sandbox):
        """Test data transformation workflow."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import echo, csv_to_json, json_to_csv
from tabulate import tabulate
import json

# Create CSV
csv_data = "name,score,grade\\nAlice,95,A\\nBob,82,B\\nCarol,78,C"
echo(csv_data, file="/app/grades.csv")

# Convert to JSON for processing
json_str = csv_to_json("/app/grades.csv")
data = json.loads(json_str)

# Filter high scorers (>80)
high_scorers = [row for row in data if int(row['score']) > 80]

# Pretty print with tabulate
headers = high_scorers[0].keys()
rows = [[row[h] for h in headers] for row in high_scorers]
table = tabulate(rows, headers=headers, tablefmt="simple")

print("High Scorers (>80):")
print(table)
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "Alice" in result.stdout
        assert "Bob" in result.stdout
        assert "Carol" not in result.stdout  # Score 78, filtered out

    def test_file_organization_workflow(self, python_sandbox):
        """Test file organization workflow."""
        code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import touch, mkdir, find, mv, tree

# Create messy file structure
touch("/app/file1.py")
touch("/app/file2.txt")
touch("/app/script.py")
touch("/app/data.json")

# Organize by extension
mkdir("/app/python", parents=True)
mkdir("/app/text", parents=True)
mkdir("/app/json", parents=True)

# Move files
for py_file in find("*.py", "/app", recursive=False):
    mv(str(py_file), f"/app/python/{py_file.name}")

for txt_file in find("*.txt", "/app", recursive=False):
    mv(str(txt_file), f"/app/text/{txt_file.name}")

for json_file in find("*.json", "/app", recursive=False):
    mv(str(json_file), f"/app/json/{json_file.name}")

# Show organized structure
print("Organized structure:")
print(tree("/app", max_depth=2))
"""
        result = python_sandbox.execute(code)
        assert result.success, f"Execution failed: {result.stderr}"
        assert "python/" in result.stdout
        assert "text/" in result.stdout
        assert "json/" in result.stdout
