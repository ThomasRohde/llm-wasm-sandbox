"""Demo: State persistence across multiple sandbox executions.

This example demonstrates three approaches to maintaining Python state
between executions in the WASM sandbox:

1. Manual file-based persistence (JSON)
2. Automatic state wrapping with sandbox.state utilities
3. Using session workspace for data files

Each approach has different trade-offs:
- Manual: Full control, explicit, good for complex state
- Automatic: Convenient, transparent, good for simple variables
- Workspace files: Best for large data, supports any format
"""

from sandbox import RuntimeType, create_sandbox
from sandbox.state import wrap_stateful_code

print("=" * 70)
print("State Persistence Demo")
print("=" * 70)

# Create a persistent session
sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
session_id = sandbox.session_id
print(f"\n✓ Created session: {session_id}")

print("\n" + "=" * 70)
print("Approach 1: Manual JSON State Persistence")
print("=" * 70)

# Execution 1: Initialize state
code1 = """
import json

# Initialize state
state = {
    'counter': 0,
    'items': [],
    'config': {'name': 'Demo'}
}

# Save to file
with open('/app/state.json', 'w') as f:
    json.dump(state, f, indent=2)

print("✓ Initialized state:", state)
"""

result1 = sandbox.execute(code1)
print("\nExecution 1:")
print(result1.stdout)

# Execution 2: Load and modify state
code2 = """
import json

# Load previous state
with open('/app/state.json', 'r') as f:
    state = json.load(f)

# Modify state
state['counter'] += 1
state['items'].append('item-1')
state['config']['updated'] = True

# Save back
with open('/app/state.json', 'w') as f:
    json.dump(state, f, indent=2)

print("✓ Updated state:", state)
"""

result2 = sandbox.execute(code2)
print("\nExecution 2:")
print(result2.stdout)

# Execution 3: Continue with state
code3 = """
import json

# Load state
with open('/app/state.json', 'r') as f:
    state = json.load(f)

# More modifications
state['counter'] += 10
state['items'].append('item-2')

print("✓ Final state:", state)
print(f"  Counter: {state['counter']}")
print(f"  Items: {state['items']}")
"""

result3 = sandbox.execute(code3)
print("\nExecution 3:")
print(result3.stdout)

print("\n" + "=" * 70)
print("Approach 2: Automatic State Wrapping")
print("=" * 70)

# Create new session for clean demo
sandbox2 = create_sandbox(runtime=RuntimeType.PYTHON)
print(f"✓ Created session: {sandbox2.session_id}")

# Execution 1: Initialize variables (wrapped automatically)
wrapped_code1 = wrap_stateful_code("""
# Initialize variables
counter = 0
data = []
total = 100

print(f"Initialized: counter={counter}, data={data}, total={total}")
""")

result = sandbox2.execute(wrapped_code1)
print("\nExecution 1 (auto-wrapped):")
print(result.stdout)

# Execution 2: State is automatically restored!
wrapped_code2 = wrap_stateful_code("""
# Variables are automatically available
counter += 5
data.append("first")
total += 50

print(f"Updated: counter={counter}, data={data}, total={total}")
""")

result = sandbox2.execute(wrapped_code2)
print("\nExecution 2 (auto-wrapped):")
print(result.stdout)

# Execution 3: Continue using state
wrapped_code3 = wrap_stateful_code("""
# State persists across executions
counter += 10
data.append("second")
total *= 2

print(f"Final: counter={counter}, data={data}, total={total}")
""")

result = sandbox2.execute(wrapped_code3)
print("\nExecution 3 (auto-wrapped):")
print(result.stdout)

print("\n" + "=" * 70)
print("Approach 3: Helper Functions (LLM-friendly)")
print("=" * 70)

# Create new session
sandbox3 = create_sandbox(runtime=RuntimeType.PYTHON)
print(f"✓ Created session: {sandbox3.session_id}")

# Execution 1: Use helper functions
code_with_helpers = """
import json

# Helper functions for state management
def save_state(data, filename='.state.json'):
    with open(f'/app/{filename}', 'w') as f:
        json.dump(data, f)

def load_state(filename='.state.json', default=None):
    try:
        with open(f'/app/{filename}', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default or {}

# Initialize
state = load_state(default={'visits': 0, 'messages': []})
state['visits'] += 1
state['messages'].append('Hello!')
save_state(state)

print(f"Visit #{state['visits']}: {state['messages']}")
"""

result = sandbox3.execute(code_with_helpers)
print("\nExecution 1:")
print(result.stdout)

# Execution 2: Continue with helpers
result = sandbox3.execute(code_with_helpers)
print("\nExecution 2:")
print(result.stdout)

# Execution 3: One more time
result = sandbox3.execute(code_with_helpers)
print("\nExecution 3:")
print(result.stdout)

print("\n" + "=" * 70)
print("Performance Comparison")
print("=" * 70)

print("\nManual JSON (3 executions):")
print(f"  Total fuel: {sum([r.fuel_consumed or 0 for r in [result1, result2, result3]]):,}")

print("\nAuto-wrapped (3 executions):")
# Note: wrapped code includes save/load overhead
print("  Convenient but includes overhead from state serialization")

print("\n" + "=" * 70)
print("Summary")
print("=" * 70)

print("""
✓ State persistence is fully supported via file-based storage
✓ Three patterns available:
  1. Manual JSON - full control, explicit
  2. Auto-wrap - convenient for simple variables
  3. Helper functions - LLM-friendly, composable

Best practices:
- Use manual JSON for complex state or large data
- Use auto-wrap for interactive/iterative development
- Use helpers for LLM-generated code patterns
- All state is session-scoped and isolated

Security:
- Only JSON-serializable types (no pickle for safety)
- State files are workspace-scoped (/app directory)
- No cross-session access
""")
