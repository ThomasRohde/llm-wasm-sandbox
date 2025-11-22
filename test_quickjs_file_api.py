"""Quick test to discover QuickJS file I/O capabilities."""

from sandbox import create_sandbox, RuntimeType

sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)

# Test 1: Try require('std')
code1 = """
try {
    const std = require('std');
    console.log('SUCCESS: require std works');
} catch (e) {
    console.error('FAILED: ' + e.name + ': ' + e.message);
}
"""

print("=== Test 1: require('std') ===")
result1 = sandbox.execute(code1)
print(f"stdout: {result1.stdout}")
print(f"stderr: {result1.stderr}")
print(f"exit_code: {result1.exit_code}")
print()

# Test 2: Try console.error
code2 = """
console.error('This is an error message');
"""

print("=== Test 2: console.error ===")
result2 = sandbox.execute(code2)
print(f"stdout: {result2.stdout}")
print(f"stderr: {result2.stderr}")
print(f"exit_code: {result2.exit_code}")
print()

# Test 3: Try native WASI file I/O (if available)
code3 = """
try {
    // Try to use WASI file descriptor API
    const fd = std.fdopen(1, 'w');
    console.log('FD API works');
} catch (e) {
    console.error('FD API failed: ' + e.message);
}
"""

print("=== Test 3: WASI FD API ===")
result3 = sandbox.execute(code3)
print(f"stdout: {result3.stdout}")
print(f"stderr: {result3.stderr}")
print(f"exit_code: {result3.exit_code}")
