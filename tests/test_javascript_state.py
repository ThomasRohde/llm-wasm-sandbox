"""Tests for JavaScript state persistence functionality.

Verifies that auto_persist_globals works correctly for JavaScript runtime,
including state save/restore, session isolation, error handling, and
complex object serialization.
"""

from __future__ import annotations

from sandbox import RuntimeType, create_sandbox


def test_basic_state_persistence():
    """Test basic state persistence across multiple executions."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # Execution 1: Initialize counter
    code1 = """
    _state.counter = (_state.counter || 0) + 1;
    console.log("counter=" + _state.counter);
    """
    result1 = sandbox.execute(code1)
    assert result1.success
    assert "counter=1" in result1.stdout

    # Execution 2: Counter should persist
    code2 = """
    _state.counter = (_state.counter || 0) + 1;
    console.log("counter=" + _state.counter);
    """
    result2 = sandbox.execute(code2)
    assert result2.success
    assert "counter=2" in result2.stdout

    # Execution 3: Counter should still persist
    code3 = """
    _state.counter = (_state.counter || 0) + 1;
    console.log("counter=" + _state.counter);
    """
    result3 = sandbox.execute(code3)
    assert result3.success
    assert "counter=3" in result3.stdout


def test_state_isolation_between_sessions():
    """Test that different sessions have independent state."""
    # Session 1
    sandbox1 = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)
    session1_id = sandbox1.session_id

    code1 = """
    _state.value = "session1";
    console.log("value=" + _state.value);
    """
    result1 = sandbox1.execute(code1)
    assert result1.success
    assert "value=session1" in result1.stdout

    # Session 2 (different session)
    sandbox2 = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)
    session2_id = sandbox2.session_id

    # Verify sessions are different
    assert session1_id != session2_id

    code2 = """
    _state.value = "session2";
    console.log("value=" + _state.value);
    """
    result2 = sandbox2.execute(code2)
    assert result2.success
    assert "value=session2" in result2.stdout

    # Verify session 1 state is unchanged
    code3 = """
    console.log("value=" + _state.value);
    """
    result3 = sandbox1.execute(code3)
    assert result3.success
    assert "value=session1" in result3.stdout


def test_state_with_complex_objects():
    """Test state persistence with arrays and nested objects."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # Execution 1: Create complex state
    code1 = """
    _state.user = {
        name: "Alice",
        age: 30,
        tags: ["developer", "python"]
    };
    _state.items = [1, 2, 3];
    console.log("initialized");
    """
    result1 = sandbox.execute(code1)
    assert result1.success
    assert "initialized" in result1.stdout

    # Execution 2: Modify and verify persistence
    code2 = """
    _state.user.age += 1;
    _state.user.tags.push("javascript");
    _state.items.push(4);
    console.log("name=" + _state.user.name);
    console.log("age=" + _state.user.age);
    console.log("tags=" + _state.user.tags.join(","));
    console.log("items=" + _state.items.join(","));
    """
    result2 = sandbox.execute(code2)
    assert result2.success
    assert "name=Alice" in result2.stdout
    assert "age=31" in result2.stdout
    assert "tags=developer,python,javascript" in result2.stdout
    assert "items=1,2,3,4" in result2.stdout

    # Execution 3: Verify persistence again
    code3 = """
    console.log("age=" + _state.user.age);
    console.log("tags_count=" + _state.user.tags.length);
    console.log("items_count=" + _state.items.length);
    """
    result3 = sandbox.execute(code3)
    assert result3.success
    assert "age=31" in result3.stdout
    assert "tags_count=3" in result3.stdout
    assert "items_count=4" in result3.stdout


def test_state_corruption_handling():
    """Test graceful handling of corrupted JSON state file."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # Execution 1: Create valid state
    code1 = """
    _state.counter = 42;
    console.log("counter=" + _state.counter);
    """
    result1 = sandbox.execute(code1)
    assert result1.success
    assert "counter=42" in result1.stdout

    # Manually corrupt the state file
    state_file = sandbox.workspace / ".session_state.json"
    state_file.write_text("{invalid json content")

    # Execution 2: Should handle corruption gracefully
    code2 = """
    _state.counter = (_state.counter || 0) + 1;
    console.log("counter=" + _state.counter);
    """
    result2 = sandbox.execute(code2)
    assert result2.success
    # Should start from 0 + 1 = 1 due to corrupted state
    assert "counter=1" in result2.stdout


def test_state_without_auto_persist():
    """Test that state does NOT persist when auto_persist_globals is False."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=False)

    # Execution 1
    code1 = """
    if (typeof _state === 'undefined') {
        var _state = {};
    }
    _state.counter = (_state.counter || 0) + 1;
    console.log("counter=" + _state.counter);
    """
    result1 = sandbox.execute(code1)
    assert result1.success
    assert "counter=1" in result1.stdout

    # Execution 2: Should NOT persist (starts from 1 again)
    code2 = """
    if (typeof _state === 'undefined') {
        var _state = {};
    }
    _state.counter = (_state.counter || 0) + 1;
    console.log("counter=" + _state.counter);
    """
    result2 = sandbox.execute(code2)
    assert result2.success
    assert "counter=1" in result2.stdout  # Not 2!


def test_state_filtering_functions():
    """Test that functions are filtered out during serialization."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # Execution 1: Try to persist a function (should be filtered)
    code1 = """
    _state.data = "persists";
    _state.func = function() { return 42; };
    _state.value = 123;
    console.log("set");
    """
    result1 = sandbox.execute(code1)
    assert result1.success

    # Execution 2: Verify function was not persisted
    code2 = """
    console.log("data=" + _state.data);
    console.log("value=" + _state.value);
    console.log("func_type=" + typeof _state.func);
    """
    result2 = sandbox.execute(code2)
    assert result2.success
    assert "data=persists" in result2.stdout
    assert "value=123" in result2.stdout
    # Function should not persist (JSON.stringify filters it)
    assert "func_type=undefined" in result2.stdout


def test_state_with_null_and_boolean():
    """Test state persistence with null and boolean values."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # Execution 1
    code1 = """
    _state.enabled = true;
    _state.disabled = false;
    _state.nothing = null;
    console.log("set");
    """
    result1 = sandbox.execute(code1)
    assert result1.success

    # Execution 2: Verify persistence
    code2 = """
    console.log("enabled=" + _state.enabled);
    console.log("disabled=" + _state.disabled);
    console.log("nothing=" + _state.nothing);
    console.log("enabled_type=" + typeof _state.enabled);
    console.log("nothing_type=" + typeof _state.nothing);
    """
    result2 = sandbox.execute(code2)
    assert result2.success
    assert "enabled=true" in result2.stdout
    assert "disabled=false" in result2.stdout
    assert "nothing=null" in result2.stdout
    assert "enabled_type=boolean" in result2.stdout
    assert "nothing_type=object" in result2.stdout  # null is object type in JS


def test_state_file_created():
    """Test that state file is created in workspace."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # Execute code with state
    code = """
    _state.test = "value";
    console.log("done");
    """
    result = sandbox.execute(code)
    assert result.success

    # Verify state file exists
    state_file = sandbox.workspace / ".session_state.json"
    assert state_file.exists()
    assert state_file.is_file()

    # Verify file contains valid JSON
    import json

    content = json.loads(state_file.read_text())
    assert content["test"] == "value"


def test_resuming_session_with_state():
    """Test resuming a session restores state correctly."""
    # Create session and set state
    sandbox1 = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)
    session_id = sandbox1.session_id

    code1 = """
    _state.message = "Hello from first sandbox";
    _state.count = 100;
    console.log("set");
    """
    result1 = sandbox1.execute(code1)
    assert result1.success

    # Resume same session with new sandbox instance
    sandbox2 = create_sandbox(
        runtime=RuntimeType.JAVASCRIPT, session_id=session_id, auto_persist_globals=True
    )

    code2 = """
    console.log("message=" + _state.message);
    console.log("count=" + _state.count);
    """
    result2 = sandbox2.execute(code2)
    assert result2.success
    assert "message=Hello from first sandbox" in result2.stdout
    assert "count=100" in result2.stdout


def test_state_with_empty_object():
    """Test state persistence with empty objects and arrays."""
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    # Execution 1
    code1 = """
    _state.emptyObj = {};
    _state.emptyArr = [];
    _state.normalValue = 42;
    console.log("set");
    """
    result1 = sandbox.execute(code1)
    assert result1.success

    # Execution 2: Verify persistence
    code2 = """
    console.log("emptyObj_type=" + typeof _state.emptyObj);
    console.log("emptyArr_type=" + typeof _state.emptyArr);
    console.log("emptyArr_is_array=" + Array.isArray(_state.emptyArr));
    console.log("normalValue=" + _state.normalValue);
    """
    result2 = sandbox.execute(code2)
    assert result2.success
    assert "emptyObj_type=object" in result2.stdout
    assert "emptyArr_type=object" in result2.stdout
    assert "emptyArr_is_array=true" in result2.stdout
    assert "normalValue=42" in result2.stdout
