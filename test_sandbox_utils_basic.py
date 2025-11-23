"""Basic test of sandbox_utils library in WASM sandbox.

This script tests core functionality of the sandbox_utils library
by running it in the actual WASM sandbox environment.
"""

from sandbox import create_sandbox, RuntimeType
from sandbox.vendor import copy_vendor_to_workspace

# First, copy vendor packages to workspace so they're available in WASM
print("Copying vendor packages to workspace...")
copy_vendor_to_workspace()
print("Vendor packages copied.\n")

# Test code to run in WASM
test_code = """
import sys
sys.path.insert(0, '/app/site-packages')

from sandbox_utils import (
    find, tree, ls, cat, echo, touch, mkdir,
    grep, head, tail, wc, sed,
    group_by, filter_by, unique, chunk,
    csv_to_json
)

# Test 1: Create test directory structure
print("=== Test 1: Directory Operations ===")
mkdir("/app/test_dir/subdir")
touch("/app/test_dir/file1.txt")
touch("/app/test_dir/file2.py")
touch("/app/test_dir/subdir/file3.txt")

# Test 2: List files
print("\\n=== Test 2: List Files ===")
files = ls("/app/test_dir")
print(f"Files in test_dir: {files}")

# Test 3: Find files
print("\\n=== Test 3: Find Operations ===")
txt_files = find("*.txt", "/app/test_dir")
print(f"Found .txt files: {[str(f) for f in txt_files]}")

# Test 4: Write and read files
print("\\n=== Test 4: File I/O ===")
echo("Hello, World!", file="/app/test_dir/hello.txt")
echo("This is line 2", file="/app/test_dir/hello.txt", append=True)
content = cat("/app/test_dir/hello.txt")
print(f"File content: {content}")

# Test 5: Text processing
print("\\n=== Test 5: Text Processing ===")
echo("Line 1\\nLine 2\\nLine 3\\nLine 4\\nLine 5", file="/app/test_dir/lines.txt")
first_3 = head("/app/test_dir/lines.txt", lines=3)
print(f"First 3 lines: {first_3}")

last_2 = tail("/app/test_dir/lines.txt", lines=2)
print(f"Last 2 lines: {last_2}")

stats = wc("/app/test_dir/lines.txt")
print(f"Line count: {stats}")

# Test 6: Data manipulation
print("\\n=== Test 6: Data Manipulation ===")
numbers = [1, 2, 2, 3, 4, 4, 5]
unique_nums = unique(numbers)
print(f"Unique numbers: {unique_nums}")

words = ["cat", "dog", "bird", "fish"]
grouped = group_by(words, len)
print(f"Words grouped by length: {grouped}")

evens = filter_by(numbers, lambda x: x % 2 == 0)
print(f"Even numbers: {evens}")

# Test 7: CSV to JSON conversion
print("\\n=== Test 7: Format Conversion ===")
csv_content = "name,age,city\\nAlice,30,NYC\\nBob,25,LA"
echo(csv_content, file="/app/test_dir/data.csv")
json_result = csv_to_json("/app/test_dir/data.csv")
print(f"CSV to JSON: {json_result}")

# Test 8: Security - path validation
print("\\n=== Test 8: Security Validation ===")
try:
    # This should fail - path outside /app
    ls("/etc")
    print("ERROR: Should have rejected /etc path")
except ValueError as e:
    print(f"Successfully rejected invalid path: {e}")

print("\\n=== All Tests Completed Successfully! ===")
"""

# Run the test in WASM sandbox
print("Running sandbox_utils tests in WASM environment...\n")
sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
result = sandbox.execute(test_code)

if result.success:
    print(result.stdout)
    print(f"\n✓ Tests passed! Fuel consumed: {result.fuel_consumed:,}")
else:
    print("✗ Tests failed!")
    print(f"Error: {result.stderr}")
