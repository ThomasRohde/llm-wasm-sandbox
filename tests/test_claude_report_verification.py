"""
Verification Tests for Claude Desktop Report Issues
===================================================

This test suite verifies the specific claims made in the Claude Desktop testing report:
1. Package system availability (/data/site-packages)
2. JavaScript session persistence with auto_persist_globals
3. File system capabilities
4. Success flag behavior with exception handling
5. Timeout parameter functionality

Run with: uv run pytest tests/test_claude_report_verification.py -v
"""

import pytest

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox


class TestPackageSystem:
    """Verify package availability claims from Claude report."""

    def test_data_site_packages_exists(self):
        """Test if /data/site-packages directory exists in sandbox."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
import os
import sys

# Check if /data/site-packages exists
exists = os.path.exists('/data/site-packages')
is_dir = os.path.isdir('/data/site-packages') if exists else False

# Check if it's in sys.path
in_sys_path = '/data/site-packages' in sys.path

print(f"exists={exists}")
print(f"is_dir={is_dir}")
print(f"in_sys_path={in_sys_path}")

# List contents if it exists
if exists and is_dir:
    try:
        contents = os.listdir('/data/site-packages')
        print(f"contents_count={len(contents)}")
        print(f"first_10={contents[:10]}")
    except Exception as e:
        print(f"error_listing={e}")
""")
        print("\n=== /data/site-packages Test ===")
        print(result.stdout)
        print(result.stderr)

        # Parse results
        assert "exists=True" in result.stdout, "/data/site-packages should exist"
        assert "is_dir=True" in result.stdout, "/data/site-packages should be a directory"

    def test_tabulate_import(self):
        """Test if tabulate package can be imported (as advertised in README)."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')

try:
    import tabulate
    print(f"SUCCESS: tabulate imported, version={getattr(tabulate, '__version__', 'unknown')}")
    print(f"tabulate.tabulate exists: {hasattr(tabulate, 'tabulate')}")
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"ERROR: {e}")
""")
        print("\n=== tabulate Import Test ===")
        print(result.stdout)
        print(result.stderr)

        assert "SUCCESS" in result.stdout, "tabulate should be importable"

    def test_openpyxl_import(self):
        """Test if openpyxl package can be imported (as advertised in README)."""
        from sandbox.core.models import ExecutionPolicy
        policy = ExecutionPolicy(fuel_budget=10_000_000_000)  # 10B required for openpyxl
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
        result = sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')

try:
    import openpyxl
    print(f"SUCCESS: openpyxl imported, version={getattr(openpyxl, '__version__', 'unknown')}")
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"ERROR: {e}")
""")
        print("\n=== openpyxl Import Test ===")
        print(result.stdout)
        print(result.stderr)

        assert "SUCCESS" in result.stdout, "openpyxl should be importable"

    def test_markdown_import(self):
        """Test if markdown package can be imported (as advertised in README)."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')

try:
    import markdown
    print(f"SUCCESS: markdown imported, version={getattr(markdown, '__version__', 'unknown')}")
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"ERROR: {e}")
""")
        print("\n=== markdown Import Test ===")
        print(result.stdout)
        print(result.stderr)

        assert "SUCCESS" in result.stdout, "markdown should be importable"

    def test_dateutil_import(self):
        """Test if python-dateutil package can be imported (as advertised in README)."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')

try:
    import dateutil
    from dateutil import parser
    print(f"SUCCESS: dateutil imported, version={getattr(dateutil, '__version__', 'unknown')}")
    print(f"parser.parse exists: {hasattr(parser, 'parse')}")
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"ERROR: {e}")
""")
        print("\n=== dateutil Import Test ===")
        print(result.stdout)
        print(result.stderr)

        assert "SUCCESS" in result.stdout, "dateutil should be importable"

    def test_pypdf2_import(self):
        """Test if PyPDF2 package can be imported (as advertised in README)."""
        from sandbox.core.models import ExecutionPolicy
        policy = ExecutionPolicy(fuel_budget=10_000_000_000)  # 10B required for PyPDF2
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
        result = sandbox.execute("""
import sys
sys.path.insert(0, '/data/site-packages')

try:
    import PyPDF2
    print(f"SUCCESS: PyPDF2 imported, version={getattr(PyPDF2, '__version__', 'unknown')}")
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"ERROR: {e}")
""")
        print("\n=== PyPDF2 Import Test ===")
        print(result.stdout)
        print(result.stderr)

        assert "SUCCESS" in result.stdout, "PyPDF2 should be importable"


class TestJavaScriptSessionPersistence:
    """Verify JavaScript session persistence with auto_persist_globals."""

    @pytest.mark.skip(reason="JavaScript auto_persist_globals not yet supported - QuickJS-WASI lacks file I/O APIs")
    def test_javascript_auto_persist_basic(self):
        """Test if JavaScript variables persist with auto_persist_globals=True."""
        sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

        # Execution 1: Set variables
        result1 = sandbox.execute("""
let counter = 100;
let data = [1, 2, 3];
let obj = {name: "test", value: 42};
console.log("Set: counter=" + counter + ", data=" + JSON.stringify(data));
""")

        print("\n=== JavaScript Session Test - Execution 1 ===")
        print(result1.stdout)
        assert result1.success, "First execution should succeed"

        # Execution 2: Access variables (should persist)
        result2 = sandbox.execute("""
console.log("Got: counter=" + counter + ", data=" + JSON.stringify(data) + ", obj=" + JSON.stringify(obj));
""")

        print("\n=== JavaScript Session Test - Execution 2 ===")
        print(result2.stdout)
        print(result2.stderr)

        # Check if variables persisted
        if "ReferenceError" in result2.stderr or "not defined" in result2.stderr:
            pytest.fail("JavaScript auto_persist_globals does NOT work - variables not persisted")

        assert "counter=100" in result2.stdout, "counter variable should persist"
        assert "[1,2,3]" in result2.stdout, "data array should persist"

    @pytest.mark.skip(reason="JavaScript auto_persist_globals not yet supported - QuickJS-WASI lacks file I/O APIs")
    def test_javascript_auto_persist_modification(self):
        """Test if JavaScript variable modifications persist."""
        sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

        # Set initial value
        sandbox.execute("let count = 0;")

        # Increment 3 times
        for i in range(3):
            result = sandbox.execute("count++; console.log('count=' + count);")
            print(f"\n=== Iteration {i + 1} ===")
            print(result.stdout)

        # Final check
        result = sandbox.execute("console.log('final=' + count);")

        if "final=3" not in result.stdout:
            pytest.fail(
                f"JavaScript auto_persist_globals NOT working - expected final=3, got: {result.stdout}"
            )


class TestSuccessFlagBehavior:
    """Verify success flag behavior with exception handling."""

    def test_success_with_caught_exception(self):
        """Test if success=True when exception is caught with try/except."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
try:
    x = 1 / 0
except ZeroDivisionError:
    print("Caught division by zero")
print("Execution completed")
""")

        print("\n=== Success Flag with Caught Exception ===")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        print(f"success: {result.success}")
        print(f"exit_code: {result.exit_code}")

        # According to Claude's report: exit_code=0 but success=False (inconsistent)
        assert result.exit_code == 0, "Exit code should be 0 for caught exception"

        if not result.success:
            pytest.fail(
                "SUCCESS FLAG INCONSISTENCY: exit_code=0 but success=False when exception is caught. "
                "This contradicts normal behavior - caught exceptions should result in success=True."
            )

    def test_success_with_uncaught_exception(self):
        """Test if success=False when exception is uncaught."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
x = 1 / 0
print("This should not print")
""")

        print("\n=== Success Flag with Uncaught Exception ===")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        print(f"success: {result.success}")
        print(f"exit_code: {result.exit_code}")

        assert not result.success, "Success should be False for uncaught exception"
        assert result.exit_code != 0, "Exit code should be non-zero for uncaught exception"


class TestTimeoutParameter:
    """Verify timeout parameter functionality."""

    def test_timeout_parameter_accepted(self):
        """Test if timeout parameter is accepted without error."""
        # Try with timeout in policy
        policy = ExecutionPolicy(
            fuel_budget=1_000_000_000,
            timeout_seconds=5,  # This might not be a valid parameter
        )

        try:
            sandbox_with_timeout = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
            result = sandbox_with_timeout.execute("print('hello')")
            print("\n=== Timeout Parameter Test ===")
            print("Timeout parameter accepted: YES")
            print(f"Result: {result.stdout}")
        except Exception as e:
            print("\n=== Timeout Parameter Test ===")
            print("Timeout parameter accepted: NO")
            print(f"Error: {e}")
            # This is expected based on Claude's report


class TestFileSystemCapabilities:
    """Verify file system capabilities and limitations."""

    def test_file_write_capability(self):
        """Test if file writing is supported within /app."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
try:
    with open('/app/test.txt', 'w') as f:
        f.write('Hello, World!')
    print("SUCCESS: File write works")
except Exception as e:
    print(f"FAILED: {e}")
""")

        print("\n=== File Write Test ===")
        print(result.stdout)
        print(result.stderr)

        # Check if file I/O is supported
        if "FAILED" in result.stdout or "Permission denied" in result.stderr:
            print("NOTE: File I/O not supported (expected WASM limitation)")

    def test_file_read_after_write(self):
        """Test if files persist within a session."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)

        # Write file
        result1 = sandbox.execute("""
try:
    with open('/app/data.txt', 'w') as f:
        f.write('test data')
    print("Write: SUCCESS")
except Exception as e:
    print(f"Write: FAILED - {e}")
""")

        # Read file
        result2 = sandbox.execute("""
try:
    with open('/app/data.txt', 'r') as f:
        content = f.read()
    print(f"Read: SUCCESS - {content}")
except Exception as e:
    print(f"Read: FAILED - {e}")
""")

        print("\n=== File Persistence Test ===")
        print("Write result:", result1.stdout)
        print("Read result:", result2.stdout)


class TestSandboxUtilsAvailability:
    """Verify sandbox_utils library availability."""

    def test_sandbox_utils_import(self):
        """Test if sandbox_utils can be imported (as advertised in README)."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("""
try:
    from sandbox_utils import find, tree, grep, ls
    print("SUCCESS: sandbox_utils imported")
    print(f"Available functions: {dir(sandbox_utils)[:10]}")
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"ERROR: {e}")
""")

        print("\n=== sandbox_utils Import Test ===")
        print(result.stdout)
        print(result.stderr)

        # This might fail if sandbox_utils is not actually available


if __name__ == "__main__":
    # Run with detailed output
    pytest.main([__file__, "-v", "-s"])
