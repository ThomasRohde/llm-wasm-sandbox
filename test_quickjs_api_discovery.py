"""Discover what APIs QuickJS actually exposes."""

from sandbox import create_sandbox, RuntimeType

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

# Test what global objects are available
code = """
console.log('typeof console:', typeof console);
console.log('typeof console.log:', typeof console.log);
console.log('typeof console.error:', typeof console.error);
console.log('typeof require:', typeof require);
console.log('typeof global:', typeof global);
console.log('typeof globalThis:', typeof globalThis);

// List all global properties
const props = Object.getOwnPropertyNames(globalThis);
console.log('Global properties count:', props.length);
console.log('Globals:', props.slice(0, 20).join(', '));
"""

print("=== Discovering QuickJS globals ===")
result = sandbox.execute(code)
print(f"Success: {result.success}")
print(f"stdout:\\n{result.stdout}")
print(f"stderr:\\n{result.stderr}")
