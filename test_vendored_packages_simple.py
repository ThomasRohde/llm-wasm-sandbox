"""Simple test of new vendored packages without unicode."""

from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

tests = [
    (
        "python-dateutil",
        2_000_000_000,
        """
import sys
sys.path.insert(0, '/app/site-packages')
from dateutil import parser
date = parser.parse("2024-01-15 14:30:00")
print(f"OK: {date}")
""",
    ),
    (
        "tabulate",
        2_000_000_000,
        """
import sys
sys.path.insert(0, '/app/site-packages')
from tabulate import tabulate
data = [["Alice", 24], ["Bob", 19]]
print(tabulate(data, headers=["Name", "Age"], tablefmt="grid"))
print("OK")
""",
    ),
    (
        "jinja2",
        5_000_000_000,
        """
import sys
sys.path.insert(0, '/app/site-packages')
from jinja2 import Template
t = Template("Hello {{ name }}!")
print(t.render(name="World"))
print("OK")
""",
    ),
    (
        "markdown",
        2_000_000_000,
        """
import sys
sys.path.insert(0, '/app/site-packages')
import markdown
html = markdown.markdown("# Hello")
print(html)
print("OK")
""",
    ),
    (
        "jsonschema",
        5_000_000_000,
        """
import sys
sys.path.insert(0, '/app/site-packages')
from jsonschema import validate
schema = {"type": "object", "properties": {"name": {"type": "string"}}}
validate(instance={"name": "test"}, schema=schema)
print("OK")
""",
    ),
    (
        "tomli",
        2_000_000_000,
        """
import sys
sys.path.insert(0, '/app/site-packages')
try:
    import tomllib
    print("Using stdlib tomllib")
except ImportError:
    import tomli as tomllib
    print("Using tomli backport")
data = tomllib.loads('[package]\\nname = "test"')
print(f"OK: {data}")
""",
    ),
]

for name, fuel, code in tests:
    print(f"\n=== {name} ===")
    policy = ExecutionPolicy(fuel_budget=fuel)
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
    result = sandbox.execute(code)

    if result.success and "OK" in result.stdout:
        print(f"PASS - Fuel: {result.fuel_consumed / 1e9:.2f}B")
    else:
        print(f"FAIL - {result.stderr[:200]}")
