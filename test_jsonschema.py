from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

code = """
import sys
sys.path.insert(0, '/app/site-packages')
from jsonschema import validate
schema = {"type": "object", "properties": {"name": {"type": "string"}}}
validate(instance={"name": "test"}, schema=schema)
print("OK")
"""

sandbox = create_sandbox(
    runtime=RuntimeType.PYTHON, policy=ExecutionPolicy(fuel_budget=5_000_000_000)
)
result = sandbox.execute(code)

if result.success and "OK" in result.stdout:
    print(f"PASS - Fuel: {result.fuel_consumed / 1e9:.2f}B")
else:
    print(f"FAIL: {result.stderr}")
