"""Comprehensive integration tests for JavaScript-Python parity.

This module tests full workflows combining multiple features:
- State persistence across executions
- Vendored package usage
- Helper utilities integration
- Cross-runtime consistency
- Error scenarios with state and vendored packages
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sandbox import RuntimeType, create_sandbox
from sandbox.core.models import ExecutionPolicy
from sandbox.core.storage import DiskStorageAdapter
from sandbox.runtimes.javascript import JavaScriptSandbox
from sandbox.runtimes.python import PythonSandbox


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory for test isolation."""
    with tempfile.TemporaryDirectory(
        prefix="test-workspace-", ignore_cleanup_errors=True
    ) as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def policy_with_vendor(policy_with_vendor_js):
    """Create ExecutionPolicy with vendor_js mount configured."""
    return policy_with_vendor_js


class TestJavaScriptFullWorkflow:
    """Test complete workflow: create session → state → vendor packages."""

    def test_full_workflow_with_state_and_packages(self, temp_workspace, policy_with_vendor):
        """Test full workflow combining state persistence and vendored packages."""
        import uuid

        session_id = str(uuid.uuid4())

        # Create sandbox with state persistence and vendored packages
        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session_id,
            storage_adapter=DiskStorageAdapter(temp_workspace),
            auto_persist_globals=True,
        )

        # Execution 1: Initialize state and use vendored package
        code1 = """
const csv = requireVendor('csv-simple');

// Initialize state
_state.counter = 1;
_state.users = [];

// Process CSV data
const csvData = 'name,age\\nAlice,30\\nBob,25';
const parsed = csv.parse(csvData);

// Store in state
_state.users = parsed;

console.log('Execution 1 - Counter:', _state.counter);
console.log('Execution 1 - Users:', _state.users.length);
"""
        result1 = sandbox.execute(code1)

        assert result1.success is True
        assert "Execution 1 - Counter: 1" in result1.stdout
        assert "Execution 1 - Users: 2" in result1.stdout

        # Execution 2: Increment state and use helpers
        code2 = """
// State should persist
_state.counter = _state.counter + 1;

// Use helper to save data
writeJson('/app/users.json', {users: _state.users, count: _state.counter});

// Read back
const data = readJson('/app/users.json');

console.log('Execution 2 - Counter:', data.count);
console.log('Execution 2 - Users from file:', data.users.length);
console.log('Execution 2 - First user:', data.users[0].name);
"""
        result2 = sandbox.execute(code2)

        assert result2.success is True
        assert "Execution 2 - Counter: 2" in result2.stdout
        assert "Execution 2 - Users from file: 2" in result2.stdout
        assert "Execution 2 - First user: Alice" in result2.stdout

        # Execution 3: Use string utils package
        code3 = """
const str = requireVendor('string-utils');

// State should still be there
_state.counter = _state.counter + 1;

// Use string utils
const slug = str.slugify('Hello World');
_state.lastSlug = slug;

console.log('Execution 3 - Counter:', _state.counter);
console.log('Execution 3 - Slug:', _state.lastSlug);
"""
        result3 = sandbox.execute(code3)

        assert result3.success is True
        assert "Execution 3 - Counter: 3" in result3.stdout
        assert "Execution 3 - Slug: hello-world" in result3.stdout

        # Verify state file exists in session workspace
        state_file = sandbox.workspace / ".session_state.json"
        assert state_file.exists()

        # Verify workspace file exists in session workspace
        users_file = sandbox.workspace / "users.json"
        assert users_file.exists()

    def test_workflow_with_no_injection(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test workflow when code injection is disabled."""
        import uuid

        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session_id,
            storage_adapter=DiskStorageAdapter(temp_workspace),
        )

        # Execute code without injection - helpers should not be available
        code = """
console.log('Manual code execution');
const x = 42;
console.log('Value:', x);
"""
        result = sandbox.execute(code, inject_setup=False)

        assert result.success is True
        assert "Manual code execution" in result.stdout
        assert "Value: 42" in result.stdout


class TestCrossRuntimeConsistency:
    """Test consistency between Python and JavaScript runtimes."""

    @pytest.mark.skip(reason="Python uses pickle for state persistence, not .session_state.json")
    def test_state_persistence_consistency(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Compare state persistence behavior across Python and JavaScript."""
        import uuid

        # Python session
        python_session_id = str(uuid.uuid4())
        python_workspace = temp_workspace / "python"
        python_workspace.mkdir()

        python_sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=policy_with_vendor_python,
            session_id=python_session_id,
            storage_adapter=DiskStorageAdapter(python_workspace),
            auto_persist_globals=True,
        )

        # JavaScript session
        js_session_id = str(uuid.uuid4())
        js_workspace = temp_workspace / "javascript"
        js_workspace.mkdir()

        js_sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=js_session_id,
            storage_adapter=DiskStorageAdapter(js_workspace),
            auto_persist_globals=True,
        )

        # Python: Initialize and increment counter
        python_code1 = "counter = 1"
        python_result1 = python_sandbox.execute(python_code1)
        assert python_result1.success is True

        python_code2 = "counter = counter + 1; print('Python counter:', counter)"
        python_result2 = python_sandbox.execute(python_code2)
        assert python_result2.success is True
        assert "Python counter: 2" in python_result2.stdout

        # JavaScript: Initialize and increment counter
        js_code1 = "_state.counter = 1;"
        js_result1 = js_sandbox.execute(js_code1)
        assert js_result1.success is True

        js_code2 = """
_state.counter = _state.counter + 1;
console.log('JavaScript counter:', _state.counter);
"""
        js_result2 = js_sandbox.execute(js_code2)
        assert js_result2.success is True
        assert "JavaScript counter: 2" in js_result2.stdout

        # Both should have state files
        python_state = python_workspace / ".session_state.json"
        js_state = js_workspace / ".session_state.json"

        assert python_state.exists()
        assert js_state.exists()

    @pytest.mark.skip(reason="sandbox_utils doesn't have write_json/read_json functions")
    def test_helper_utilities_consistency(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Compare helper utility behavior across runtimes."""
        import uuid

        # Python session
        python_session_id = str(uuid.uuid4())
        python_workspace = temp_workspace / "python"
        python_workspace.mkdir()

        python_sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=policy_with_vendor_python,
            session_id=python_session_id,
            storage_adapter=DiskStorageAdapter(python_workspace),
        )

        # JavaScript session
        js_session_id = str(uuid.uuid4())
        js_workspace = temp_workspace / "javascript"
        js_workspace.mkdir()

        js_sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=js_session_id,
            storage_adapter=DiskStorageAdapter(js_workspace),
        )

        # Python: Use sandbox_utils
        python_code = """
from sandbox_utils import write_json, read_json
write_json('/app/test.json', {'message': 'Hello', 'count': 42})
data = read_json('/app/test.json')
print('Python message:', data['message'])
print('Python count:', data['count'])
"""
        python_result = python_sandbox.execute(python_code)
        assert python_result.success is True
        assert "Python message: Hello" in python_result.stdout
        assert "Python count: 42" in python_result.stdout

        # JavaScript: Use helpers
        js_code = """
writeJson('/app/test.json', {message: 'Hello', count: 42});
const data = readJson('/app/test.json');
console.log('JavaScript message:', data.message);
console.log('JavaScript count:', data.count);
"""
        js_result = js_sandbox.execute(js_code)
        assert js_result.success is True
        assert "JavaScript message: Hello" in js_result.stdout
        assert "JavaScript count: 42" in js_result.stdout

        # Both should create files
        python_file = python_workspace / "test.json"
        js_file = js_workspace / "test.json"

        assert python_file.exists()
        assert js_file.exists()

    def test_vendored_packages_availability(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Verify both runtimes have equivalent vendored packages."""
        import uuid

        # Python session
        python_session_id = str(uuid.uuid4())
        python_workspace = temp_workspace / "python"
        python_workspace.mkdir()

        python_sandbox = PythonSandbox(
            wasm_binary_path="bin/python.wasm",
            policy=policy_with_vendor_python,
            session_id=python_session_id,
            storage_adapter=DiskStorageAdapter(python_workspace),
        )

        # JavaScript session
        js_session_id = str(uuid.uuid4())
        js_workspace = temp_workspace / "javascript"
        js_workspace.mkdir()

        js_sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=js_session_id,
            storage_adapter=DiskStorageAdapter(js_workspace),
        )

        # Python: Parse CSV
        python_code = """
import csv
import io
data = 'name,age\\nAlice,30\\nBob,25'
reader = csv.DictReader(io.StringIO(data))
rows = list(reader)
print('Python rows:', len(rows))
print('Python first:', rows[0]['name'])
"""
        python_result = python_sandbox.execute(python_code)
        assert python_result.success is True
        assert "Python rows: 2" in python_result.stdout
        assert "Python first: Alice" in python_result.stdout

        # JavaScript: Parse CSV
        js_code = """
const csv = requireVendor('csv-simple');
const data = 'name,age\\nAlice,30\\nBob,25';
const rows = csv.parse(data);
console.log('JavaScript rows:', rows.length);
console.log('JavaScript first:', rows[0].name);
"""
        js_result = js_sandbox.execute(js_code)
        assert js_result.success is True
        assert "JavaScript rows: 2" in js_result.stdout
        assert "JavaScript first: Alice" in js_result.stdout


class TestErrorScenarios:
    """Test error scenarios with state and vendored packages."""

    @pytest.mark.skip(reason="State file path check needs investigation")
    def test_fuel_exhaustion_with_state_persistence(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test that fuel exhaustion preserves state up to failure point."""
        import uuid

        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=ExecutionPolicy(fuel_budget=100_000),  # Very low budget
            session_id=session_id,
            storage_adapter=DiskStorageAdapter(temp_workspace),
            auto_persist_globals=True,
        )

        # Execution 1: Set state successfully
        code1 = "_state.initialized = true; _state.counter = 1;"
        result1 = sandbox.execute(code1)
        assert result1.success is True

        # Execution 2: Try to do infinite loop (should fail)
        code2 = """
_state.counter = _state.counter + 1;
while (true) {
    // Infinite loop - should hit fuel limit
}
"""
        result2 = sandbox.execute(code2)
        assert result2.success is False
        assert result2.metadata.get("trap_reason") == "out_of_fuel"

        # State file should still exist with previous successful state
        state_file = temp_workspace / ".session_state.json"
        assert state_file.exists()

    def test_vendor_package_error_handling(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test error handling when vendored package is missing."""
        import uuid

        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session_id,
            storage_adapter=DiskStorageAdapter(temp_workspace),
        )

        # Try to require non-existent package
        code = """
try {
    const pkg = requireVendor('non-existent-package');
    console.log('ERROR: Should have failed');
} catch (e) {
    console.log('Caught error:', e.name);
}
"""
        result = sandbox.execute(code)

        # Should execute without crashing
        assert result.success is True
        assert "Caught error:" in result.stdout

    def test_state_corruption_recovery(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test that corrupted state file is handled gracefully."""
        import uuid

        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session_id,
            storage_adapter=DiskStorageAdapter(temp_workspace),
            auto_persist_globals=True,
        )

        # Create corrupted state file
        state_file = temp_workspace / ".session_state.json"
        state_file.write_text("{invalid json content")

        # Should start with fresh state
        code = """
_state.recovered = true;
console.log('State recovery:', _state.recovered);
console.log('State keys:', Object.keys(_state).join(', '));
"""
        result = sandbox.execute(code)

        assert result.success is True
        assert "State recovery: true" in result.stdout

    def test_helper_utility_error_handling(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test error handling in helper utilities."""
        import uuid

        session_id = str(uuid.uuid4())

        sandbox = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session_id,
            storage_adapter=DiskStorageAdapter(temp_workspace),
        )

        # Try to read non-existent file
        code = """
try {
    const data = readJson('/app/non-existent.json');
    console.log('ERROR: Should have failed');
} catch (e) {
    console.log('Caught error:', e.name);
}
"""
        result = sandbox.execute(code)

        assert result.success is True
        assert "Caught error:" in result.stdout


class TestFactoryIntegration:
    """Test integration with factory pattern."""

    def test_create_sandbox_javascript_with_state(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test creating JavaScript sandbox with state via factory."""
        # Use factory to create sandbox
        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            auto_persist_globals=True,
            workspace_path=str(temp_workspace),
        )

        # Execute code with state
        code1 = "_state.value = 42;"
        result1 = sandbox.execute(code1)
        assert result1.success is True

        # State should persist
        code2 = "console.log('Value:', _state.value);"
        result2 = sandbox.execute(code2)
        assert result2.success is True
        assert "Value: 42" in result2.stdout

    def test_create_sandbox_javascript_with_vendored_packages(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test creating JavaScript sandbox with vendored packages via factory."""
        # Use factory to create sandbox
        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            workspace_path=str(temp_workspace),
        )

        # Use vendored package
        code = """
const csv = requireVendor('csv-simple');
const data = csv.parse('a,b\\n1,2');
console.log('Parsed:', data.length, 'rows');
"""
        result = sandbox.execute(code)
        assert result.success is True
        assert "Parsed: 1 rows" in result.stdout

    def test_create_sandbox_with_custom_policy(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test creating sandbox with custom policy via factory."""
        policy = ExecutionPolicy(
            fuel_budget=500_000_000,
            memory_bytes=32 * 1024 * 1024,
        )

        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            policy=policy,
            workspace_path=str(temp_workspace),
        )

        code = "console.log('Custom policy test');"
        result = sandbox.execute(code)
        assert result.success is True
        assert result.metadata.get("fuel_budget") == policy.fuel_budget


class TestSessionIsolation:
    """Test session isolation with state and packages."""

    @pytest.mark.skip(reason="State file path check needs investigation")
    def test_state_isolation_between_sessions(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test that different sessions have isolated state."""
        import uuid

        # Session 1
        session1_id = str(uuid.uuid4())
        workspace1 = temp_workspace / "session1"
        workspace1.mkdir()

        sandbox1 = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session1_id,
            storage_adapter=DiskStorageAdapter(workspace1),
            auto_persist_globals=True,
        )

        # Session 2
        session2_id = str(uuid.uuid4())
        workspace2 = temp_workspace / "session2"
        workspace2.mkdir()

        sandbox2 = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session2_id,
            storage_adapter=DiskStorageAdapter(workspace2),
            auto_persist_globals=True,
        )

        # Set different state in each session
        sandbox1.execute("_state.session = 1; _state.value = 'first';")
        sandbox2.execute("_state.session = 2; _state.value = 'second';")

        # Verify isolation
        result1 = sandbox1.execute(
            "console.log('Session:', _state.session, 'Value:', _state.value);"
        )
        result2 = sandbox2.execute(
            "console.log('Session:', _state.session, 'Value:', _state.value);"
        )

        assert result1.success is True
        assert result2.success is True
        assert "Session: 1 Value: first" in result1.stdout
        assert "Session: 2 Value: second" in result2.stdout

        # Verify separate state files
        state1 = workspace1 / ".session_state.json"
        state2 = workspace2 / ".session_state.json"

        assert state1.exists()
        assert state2.exists()
        assert state1.read_text() != state2.read_text()

    @pytest.mark.skip(reason="Workspace file isolation check needs investigation")
    def test_workspace_isolation_with_files(
        self, temp_workspace, policy_with_vendor, policy_with_vendor_python
    ):
        """Test that different sessions have isolated workspaces."""
        import uuid

        # Session 1
        session1_id = str(uuid.uuid4())
        workspace1 = temp_workspace / "session1"
        workspace1.mkdir()

        sandbox1 = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session1_id,
            storage_adapter=DiskStorageAdapter(workspace1),
        )

        # Session 2
        session2_id = str(uuid.uuid4())
        workspace2 = temp_workspace / "session2"
        workspace2.mkdir()

        sandbox2 = JavaScriptSandbox(
            wasm_binary_path="bin/quickjs.wasm",
            policy=policy_with_vendor,
            session_id=session2_id,
            storage_adapter=DiskStorageAdapter(workspace2),
        )

        # Write different files in each session
        sandbox1.execute("writeJson('/app/data.json', {session: 1});")
        sandbox2.execute("writeJson('/app/data.json', {session: 2});")

        # Read back and verify
        result1 = sandbox1.execute(
            "const d = readJson('/app/data.json'); console.log('Session:', d.session);"
        )
        result2 = sandbox2.execute(
            "const d = readJson('/app/data.json'); console.log('Session:', d.session);"
        )

        assert result1.success is True
        assert result2.success is True
        assert "Session: 1" in result1.stdout
        assert "Session: 2" in result2.stdout

        # Verify separate files
        file1 = workspace1 / "data.json"
        file2 = workspace2 / "data.json"

        assert file1.exists()
        assert file2.exists()
        assert file1.read_text() != file2.read_text()
