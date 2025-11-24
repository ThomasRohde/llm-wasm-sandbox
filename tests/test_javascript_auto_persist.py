"""Test JavaScript auto_persist_globals functionality.

This test verifies that the JavaScript sandbox correctly persists global
variables across multiple executions when auto_persist_globals=True.

⚠️ IMPORTANT: These tests are currently SKIPPED because they test the OLD API
(let/const variable persistence). The NEW API requires using _state object.
See tests/test_javascript_state.py for working state persistence tests.

Historical Note: Originally skipped because QuickJS-WASI file I/O was not integrated.
Now fully implemented using QuickJS std.open() APIs.
"""

import pytest

from sandbox import RuntimeType, create_sandbox


@pytest.mark.skip(
    reason="Old API (let/const persistence) not supported - use _state object instead (see test_javascript_state.py)"
)
def test_javascript_auto_persist_basic():
    """Test basic variable persistence across JavaScript executions."""
    # Create sandbox with auto_persist enabled
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # First execution - set variables
    result1 = sandbox.execute("let counter = 100; let data = [1, 2, 3];")
    assert result1.success, f"First execution failed: {result1.stderr}"

    # Second execution - variables should be restored
    result2 = sandbox.execute(
        "console.log('counter=' + counter + ', data=' + JSON.stringify(data));"
    )
    assert result2.success, f"Second execution failed: {result2.stderr}"
    assert "counter=100" in result2.stdout, f"Counter not restored. stdout: {result2.stdout}"
    assert "[1,2,3]" in result2.stdout or "[1, 2, 3]" in result2.stdout, (
        f"Data not restored. stdout: {result2.stdout}"
    )


@pytest.mark.skip(
    reason="Old API (let/const persistence) not supported - use _state object instead (see test_javascript_state.py)"
)
def test_javascript_auto_persist_mutation():
    """Test that mutated variables persist correctly."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # First execution - initialize
    result1 = sandbox.execute("let count = 0; let items = [];")
    assert result1.success

    # Second execution - mutate
    result2 = sandbox.execute("count += 10; items.push('apple');")
    assert result2.success

    # Third execution - verify mutations persisted
    result3 = sandbox.execute("console.log('count=' + count + ', items=' + JSON.stringify(items));")
    assert result3.success
    assert "count=10" in result3.stdout, f"Count mutation not persisted. stdout: {result3.stdout}"
    assert "apple" in result3.stdout, f"Array mutation not persisted. stdout: {result3.stdout}"


def test_javascript_auto_persist_disabled():
    """Test that variables do NOT persist when auto_persist_globals=False."""
    sandbox = create_sandbox(
        runtime=RuntimeType.JAVASCRIPT,
        auto_persist_globals=False,  # Explicitly disabled
    )

    # First execution - set variable
    result1 = sandbox.execute("let x = 42;")
    assert result1.success

    # Second execution - variable should NOT exist
    result2 = sandbox.execute("console.log(typeof x);")
    assert result2.success
    assert "undefined" in result2.stdout, (
        f"Variable persisted when it shouldn't. stdout: {result2.stdout}"
    )


@pytest.mark.skip(
    reason="Old API (let/const persistence) not supported - use _state object instead (see test_javascript_state.py)"
)
def test_javascript_auto_persist_objects():
    """Test that object variables persist correctly."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # First execution - create object
    result1 = sandbox.execute("""
        let user = {name: 'Alice', age: 30};
        let config = {debug: true, timeout: 5000};
    """)
    assert result1.success

    # Second execution - verify objects restored
    result2 = sandbox.execute("""
        console.log('user.name=' + user.name);
        console.log('config.debug=' + config.debug);
    """)
    assert result2.success
    assert "user.name=Alice" in result2.stdout, (
        f"Object property not restored. stdout: {result2.stdout}"
    )
    assert "config.debug=true" in result2.stdout, (
        f"Config object not restored. stdout: {result2.stdout}"
    )


@pytest.mark.skip(
    reason="Old API (let/const persistence) not supported - use _state object instead (see test_javascript_state.py)"
)
def test_javascript_auto_persist_multiple_types():
    """Test persistence of various JavaScript types."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # First execution - set various types
    result1 = sandbox.execute("""
        let num = 42;
        let str = 'hello';
        let bool = true;
        let arr = [1, 2, 3];
        let obj = {key: 'value'};
        let nil = null;
    """)
    assert result1.success

    # Second execution - verify all types restored
    result2 = sandbox.execute("""
        console.log('num=' + num);
        console.log('str=' + str);
        console.log('bool=' + bool);
        console.log('arr=' + JSON.stringify(arr));
        console.log('obj=' + JSON.stringify(obj));
        console.log('nil=' + nil);
    """)
    assert result2.success

    # Verify all values
    assert "num=42" in result2.stdout
    assert "str=hello" in result2.stdout
    assert "bool=true" in result2.stdout
    assert "[1,2,3]" in result2.stdout or "[1, 2, 3]" in result2.stdout
    assert '{"key":"value"}' in result2.stdout or "{'key':'value'}" in result2.stdout
    assert "nil=null" in result2.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
