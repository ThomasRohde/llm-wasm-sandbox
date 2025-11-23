"""Consolidated test suite for sandbox functionality using pytest."""
import os
import tempfile
from pathlib import Path

import pytest

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox
from sandbox.core.errors import SandboxExecutionError
from sandbox.host import SandboxResult, run_untrusted_python
from sandbox.policies import DEFAULT_POLICY, load_policy
from sandbox.utils import (
    FuelExhaustionError,
    MemoryLimitError,
    SandboxError,
    ensure_dir_exists,
    setup_logging,
)
from sandbox.vendor import (
    clean_vendor_dir,
    copy_vendor_to_workspace,
    list_vendored_packages,
    setup_vendor_dir,
)


def execute(code: str, inject_setup: bool = True, policy: ExecutionPolicy | None = None) -> dict:
    """Helper function to execute code using new API and return dict for compatibility."""
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
    result = sandbox.execute(code, inject_setup=inject_setup)
    # Convert SandboxResult to dict for backwards compatibility with existing tests
    # Map memory_used_bytes to both mem_pages (approximate) and mem_len for compatibility
    mem_pages = result.memory_used_bytes // 65536  # Approximate pages (64KB each)
    return {
        'stdout': result.stdout,
        'stderr': result.stderr,
        'fuel_consumed': result.fuel_consumed,
        'mem_pages': mem_pages,  # Backwards compat - approximate
        'mem_len': result.memory_used_bytes,  # Backwards compat
        'logs_dir': result.workspace_path,  # Use workspace as logs_dir equivalent
        'success': result.success,
        'exit_code': result.exit_code,
        'metadata': result.metadata,
    }


class TestBasicExecution:
    """Test basic sandbox execution."""

    def test_basic_smoke(self):
        """Test basic Python execution with env vars and file access."""
        policy = ExecutionPolicy(env={"DEMO_GREETING": "Hello from custom policy"})
        code = """
import os
print("Hello from WASM Python")
print("ENV:", os.getenv("DEMO_GREETING"))
try:
    with open("/app/input.txt", "r", encoding="utf-8") as f:
        print("File:", f.read().strip())
except Exception as e:
    print("Error reading file:", e)
"""
        result = execute(code, policy=policy)

        assert "Hello from WASM Python" in result['stdout']
        assert "Hello from custom policy" in result['stdout']
        assert result['fuel_consumed'] is not None
        assert result['mem_pages'] > 0
        assert result['logs_dir'] is not None


class TestFilesystemIsolation:
    """Test filesystem access controls via WASI capabilities."""

    def test_absolute_path_escape_blocked(self):
        """Test that absolute paths outside preopen are blocked."""
        code = r"""
try:
    # Attempt to read an absolute path (outside preopen) -> not permitted
    print(open("/etc/passwd", "r").read()[:50])
except Exception as e:
    print("FS sandbox caught:", type(e).__name__, str(e)[:80])
"""
        result = execute(code)
        assert "FS sandbox caught" in result['stdout']

    def test_parent_directory_escape_blocked(self):
        """Test that parent directory traversal is blocked."""
        code = r"""
try:
    # Attempt to escape via parent directory
    print(open("../README.md", "r").read()[:50])
except Exception as e:
    print("Parent escape caught:", type(e).__name__, str(e)[:80])
"""
        result = execute(code)
        assert "Parent escape caught" in result['stdout']

    def test_allowed_preopen_access(self):
        """Test that reads within /app preopen succeed."""
        # Use create_sandbox to get session-aware sandbox
        from pathlib import Path

        from sandbox import RuntimeType, create_sandbox, write_session_file

        workspace_root = Path("workspace")
        workspace_root.mkdir(parents=True, exist_ok=True)

        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, workspace_root=workspace_root)
        session_id = sandbox.session_id

        # Write input file using session-aware API
        write_session_file(session_id, "input.txt", "This text came from the host filesystem", workspace_root=workspace_root)

        code = """
try:
    with open("/app/input.txt", "r") as f:
        print("Allowed read:", f.read().strip())
except Exception as e:
    print("Unexpected error reading allowed file:", e)
"""
        result = sandbox.execute(code)
        assert "Allowed read:" in result.stdout
        assert "This text came from the host filesystem" in result.stdout


class TestFuelExhaustion:
    """Test that fuel limits prevent runaway execution."""

    def test_infinite_loop_exhausts_fuel(self):
        """Test that infinite loops are caught by fuel exhaustion."""
        policy = ExecutionPolicy(fuel_budget=100_000)
        code = """
i = 0
while True:
    i += 1
"""
        result = execute(code, policy=policy)

        # Fuel should be consumed (either fully exhausted or partially)
        assert result['fuel_consumed'] is not None
        assert result['success'] is False
        assert result['exit_code'] != 0
        assert "OutOfFuel" in result['stderr'] or "fuel" in result['stderr'].lower()


class TestMemoryLimits:
    """Test that memory limits are enforced."""

    def test_memory_blowup_caught(self):
        """Test that large allocations hit memory cap."""
        code = """
# Try to blow up memory (should be capped)
try:
    x = [0] * (50_000_000)   # adjust size to provoke MemoryError within cap
    print("Allocated len:", len(x))
except MemoryError as e:
    print("Memory limit hit:", str(e)[:100])
except Exception as e:
    print("Other error:", type(e).__name__, str(e)[:100])
"""
        result = execute(code)

        # Either Python catches MemoryError or trap occurs
        assert ("Memory limit" in result['stdout'] or
                "MemoryError" in result['stderr'] or
                "Other error" in result['stdout'])
        assert result['mem_pages'] is not None


class TestSandboxMetrics:
    """Test that sandbox returns expected metrics."""

    def test_result_structure(self):
        """Test that execute returns all expected fields."""
        code = "print('test')"
        result = execute(code)

        assert 'stdout' in result
        assert 'stderr' in result
        assert 'fuel_consumed' in result
        assert 'mem_pages' in result
        assert 'mem_len' in result
        assert 'logs_dir' in result

        assert isinstance(result['stdout'], str)
        assert isinstance(result['stderr'], str)
        assert result['logs_dir'] is not None


class TestPolicyManagement:
    """Test policy loading and configuration."""

    def test_default_policy_values(self):
        """Test that default policy has expected values."""
        assert DEFAULT_POLICY["fuel_budget"] > 0
        assert DEFAULT_POLICY["memory_bytes"] > 0
        assert DEFAULT_POLICY["stdout_max_bytes"] > 0
        assert DEFAULT_POLICY["stderr_max_bytes"] > 0
        assert "mount_host_dir" in DEFAULT_POLICY
        assert "guest_mount_path" in DEFAULT_POLICY
        assert "preserve_logs" in DEFAULT_POLICY
        assert "argv" in DEFAULT_POLICY
        assert "env" in DEFAULT_POLICY
        assert DEFAULT_POLICY["preserve_logs"] is False

    def test_load_policy_default(self):
        """Test loading policy when file doesn't exist."""
        from sandbox.core.models import ExecutionPolicy
        policy = load_policy("nonexistent/policy.toml")
        assert isinstance(policy, ExecutionPolicy)
        assert policy.fuel_budget == DEFAULT_POLICY["fuel_budget"]

    def test_load_policy_existing(self):
        """Test loading existing policy file."""
        from sandbox.core.models import ExecutionPolicy
        policy = load_policy("config/policy.toml")
        assert isinstance(policy, ExecutionPolicy)
        assert hasattr(policy, "fuel_budget")
        assert hasattr(policy, "memory_bytes")

    def test_policy_env_merge(self):
        """Test that environment variables are properly merged."""
        policy = load_policy()
        assert hasattr(policy, "env")
        assert isinstance(policy.env, dict)


class TestUtilities:
    """Test utility functions."""

    def test_setup_logging(self):
        """Test logging setup."""
        import logging
        logger = setup_logging(logging.DEBUG)
        assert logger is not None
        assert logger.name == "llm-wasm-sandbox"

    def test_ensure_dir_exists(self):
        """Test directory creation."""
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "test", "nested", "dir")
            result = ensure_dir_exists(test_path)
            assert result.exists()
            assert result.is_dir()

    def test_ensure_dir_exists_already_exists(self):
        """Test directory creation when dir already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = ensure_dir_exists(tmpdir)
            assert result.exists()

    def test_sandbox_error_hierarchy(self):
        """Test that custom exceptions work properly."""
        # Test base exception
        try:
            raise SandboxError("Test error")
        except SandboxError as e:
            assert str(e) == "Test error"

        # Test FuelExhaustionError
        try:
            raise FuelExhaustionError("Out of fuel")
        except SandboxError as e:
            assert isinstance(e, FuelExhaustionError)
            assert str(e) == "Out of fuel"

        # Test MemoryLimitError
        try:
            raise MemoryLimitError("Memory exceeded")
        except SandboxError as e:
            assert isinstance(e, MemoryLimitError)
            assert str(e) == "Memory exceeded"


class TestVendorManagement:
    """Test vendoring utilities."""

    def test_setup_vendor_dir(self):
        """Test vendor directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vendor_path = Path(tmpdir) / "test_vendor"
            result = setup_vendor_dir(vendor_path)
            assert result.exists()
            assert (result / "site-packages").exists()

    def test_list_vendored_packages_empty(self):
        """Test listing packages when vendor dir is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vendor_path = Path(tmpdir) / "empty_vendor"
            packages = list_vendored_packages(vendor_path)
            assert packages == []

    def test_list_vendored_packages_existing(self):
        """Test listing packages from existing vendor directory."""
        packages = list_vendored_packages("vendor")
        # Should return a list (may be empty or contain packages)
        assert isinstance(packages, list)
        # If vendor/site-packages exists with packages, check they're strings
        if packages:
            assert all(isinstance(pkg, str) for pkg in packages)

    def test_clean_vendor_dir(self):
        """Test cleaning vendor directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vendor_path = Path(tmpdir) / "clean_test"
            vendor_path.mkdir()
            (vendor_path / "test.txt").write_text("test")

            clean_vendor_dir(vendor_path)
            assert not vendor_path.exists()

    def test_copy_vendor_to_workspace_no_source(self):
        """Test copying when source doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vendor_path = Path(tmpdir) / "no_vendor"
            workspace_path = Path(tmpdir) / "workspace"
            workspace_path.mkdir()

            # Should not raise, just print warning
            copy_vendor_to_workspace(vendor_path, workspace_path)


class TestHostDirect:
    """Test host.py functionality directly."""

    def test_run_untrusted_python_basic(self):
        """Test direct execution via host."""
        # Write simple test code
        test_code = 'print("Direct host test")'
        workspace_path = Path("workspace")
        workspace_path.mkdir(exist_ok=True)
        (workspace_path / "user_code.py").write_text(test_code)

        # Check if WASM binary exists
        if os.path.exists("bin/python.wasm"):
            result = run_untrusted_python()
            assert "Direct host test" in result.stdout
            assert isinstance(result.fuel_consumed, (int, type(None)))
            assert result.mem_pages >= 0
            assert result.mem_len >= 0

    def test_sandbox_result_attributes(self):
        """Test SandboxResult has all expected attributes."""
        result = SandboxResult(
            stdout="test stdout",
            stderr="test stderr",
            fuel_consumed=1000,
            mem_pages=10,
            mem_len=65536,
            logs_dir="/tmp/test",
            exit_code=0,
            trapped=False,
            trap_reason=None,
            trap_message=None,
            stdout_truncated=False,
            stderr_truncated=True
        )

        assert result.stdout == "test stdout"
        assert result.stderr == "test stderr"
        assert result.fuel_consumed == 1000
        assert result.mem_pages == 10
        assert result.mem_len == 65536
        assert result.logs_dir == "/tmp/test"
        assert result.exit_code == 0
        assert result.trapped is False
        assert result.trap_reason is None
        assert result.trap_message is None
        assert result.stdout_truncated is False
        assert result.stderr_truncated is True

    def test_run_untrusted_python_raises_when_memory_limits_missing(self, monkeypatch, tmp_path: Path):
        """Memory limit enforcement should fail closed when set_limits is unavailable."""
        import sandbox.host as host_module

        class DummyConfig:
            def __init__(self):
                pass

        class DummyEngine:
            def __init__(self, cfg):
                pass

        class DummyLinker:
            def __init__(self, engine):
                pass

            def define_wasi(self):
                pass

        class DummyModule:
            @staticmethod
            def from_file(engine, path):
                return DummyModule()

        class DummyWasiConfig:
            def preopen_dir(self, host_dir, guest_path):
                pass

        class DummyStore:
            def __init__(self, engine):
                pass

            def set_wasi(self, wasi):
                pass

            def set_fuel(self, fuel):
                pass

        monkeypatch.setattr(host_module, "Config", DummyConfig)
        monkeypatch.setattr(host_module, "Engine", DummyEngine)
        monkeypatch.setattr(host_module, "Linker", DummyLinker)
        monkeypatch.setattr(host_module, "Module", DummyModule)
        monkeypatch.setattr(host_module, "WasiConfig", DummyWasiConfig)
        monkeypatch.setattr(host_module, "Store", DummyStore)

        with pytest.raises(SandboxExecutionError):
            run_untrusted_python(wasm_path=str(tmp_path / "python.wasm"))


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_code_execution(self):
        """Test executing empty code."""
        result = execute("")
        assert result['stdout'] == ""
        assert result['fuel_consumed'] is not None
        assert result['success'] is True

    def test_syntax_error_in_code(self):
        """Test executing code with syntax errors causes trap."""
        code = """
# Syntax error will cause Python to exit with non-zero status
if True
    print('missing colon')
"""
        result = execute(code)
        assert result['fuel_consumed'] is not None
        assert result['success'] is False
        assert result['exit_code'] != 0
        assert "traceback" in result['stderr'].lower() or "syntax" in result['stderr'].lower()

    def test_import_error_handling(self):
        """Test handling of import errors."""
        code = """
try:
    import nonexistent_module
except ImportError as e:
    print("Import error caught:", str(e)[:50])
"""
        result = execute(code)
        assert "Import error caught:" in result['stdout']

    def test_unicode_handling(self):
        """Test that unicode is handled correctly."""
        code = 'print("Unicode: 你好 мир 🌍")'
        result = execute(code)
        assert "Unicode:" in result['stdout']

    def test_multiline_output(self):
        """Test handling multiline output."""
        code = """
for i in range(5):
    print(f"Line {i}")
"""
        result = execute(code)
        assert "Line 0" in result['stdout']
        assert "Line 4" in result['stdout']

    def test_large_output_capped(self):
        """Test that large output is capped."""
        code = """
        # Try to generate large output (should be capped by policy)
for i in range(100000):
    print("x" * 100)
"""
        result = execute(code)
        # Output should exist but be capped
        assert len(result['stdout']) > 0
        assert result['fuel_consumed'] is not None
        assert result["metadata"].get("stdout_truncated") is True


class TestVendorBootstrap:
    """Test vendor bootstrapping and package management."""

    def test_recommended_packages_list(self):
        """Test that RECOMMENDED_PACKAGES is defined."""
        from sandbox.vendor import RECOMMENDED_PACKAGES
        assert isinstance(RECOMMENDED_PACKAGES, list)
        assert len(RECOMMENDED_PACKAGES) > 0

    def test_copy_vendor_to_workspace_with_files(self):
        """Test copying vendor to workspace when source exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vendor_path = Path(tmpdir) / "vendor"
            workspace_path = Path(tmpdir) / "workspace"

            # Create vendor structure with a test package
            (vendor_path / "site-packages" / "testpkg").mkdir(parents=True)
            (vendor_path / "site-packages" / "testpkg" / "__init__.py").write_text("# test")
            workspace_path.mkdir()

            copy_vendor_to_workspace(vendor_path, workspace_path)
            assert (workspace_path / "site-packages" / "testpkg" / "__init__.py").exists()

    def test_copy_vendor_replaces_existing(self):
        """Test that copying vendor replaces existing site-packages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vendor_path = Path(tmpdir) / "vendor"
            workspace_path = Path(tmpdir) / "workspace"

            # Create structures
            (vendor_path / "site-packages" / "newpkg").mkdir(parents=True)
            (vendor_path / "site-packages" / "newpkg" / "__init__.py").write_text("new")

            (workspace_path / "site-packages" / "oldpkg").mkdir(parents=True)
            (workspace_path / "site-packages" / "oldpkg" / "__init__.py").write_text("old")

            copy_vendor_to_workspace(vendor_path, workspace_path)

            # New package should exist, old should be gone
            assert (workspace_path / "site-packages" / "newpkg" / "__init__.py").exists()
            assert not (workspace_path / "site-packages" / "oldpkg").exists()


class TestPolicyEdgeCases:
    """Test policy loading edge cases."""

    def test_policy_with_custom_toml(self):
        """Test loading policy with custom values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_file = Path(tmpdir) / "custom_policy.toml"
            policy_file.write_text("""
fuel_budget = 5000000
memory_bytes = 32000000

[env]
CUSTOM_VAR = "test_value"
""")
            policy = load_policy(str(policy_file))
            assert policy.fuel_budget == 5000000
            assert policy.memory_bytes == 32000000
            assert policy.env["CUSTOM_VAR"] == "test_value"
            # Should still have defaults
            assert "PYTHONUTF8" in policy.env

    def test_policy_with_data_mount(self):
        """Test policy with optional data directory mount."""
        with tempfile.TemporaryDirectory() as tmpdir:
            policy_file = Path(tmpdir) / "data_policy.toml"
            policy_file.write_text("""
mount_data_dir = "/some/data/path"
guest_data_path = "/data"
""")
            policy = load_policy(str(policy_file))
            assert policy.mount_data_dir == "/some/data/path"
            assert policy.guest_data_path == "/data"

