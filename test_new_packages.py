"""Test new vendored packages in WASM environment.

This script tests each newly added package to ensure:
1. It can be imported in WASM
2. Basic functionality works
3. No C extensions are required
4. Operations complete within fuel budget
"""

from sandbox import create_sandbox, RuntimeType

# Test cases for each new package
test_cases = {
    "python-dateutil": """
import sys
sys.path.insert(0, '/app/site-packages')

from dateutil import parser
from dateutil.relativedelta import relativedelta
from datetime import datetime

# Test date parsing
date1 = parser.parse("2024-01-15 14:30:00")
print(f"Parsed date: {date1}")

# Test relative delta
date2 = date1 + relativedelta(months=2, days=5)
print(f"Date + 2 months 5 days: {date2}")

# Test fuzzy parsing
date3 = parser.parse("The meeting is on Jan 20, 2024 at 3pm", fuzzy=True)
print(f"Fuzzy parsed: {date3}")

print("✓ python-dateutil works")
""",
    "tabulate": """
import sys
sys.path.insert(0, '/app/site-packages')

from tabulate import tabulate

# Test basic table
data = [
    ["Alice", 24, "Engineer"],
    ["Bob", 19, "Student"],
    ["Charlie", 30, "Manager"]
]
headers = ["Name", "Age", "Role"]

# ASCII table
ascii_table = tabulate(data, headers=headers, tablefmt="grid")
print("ASCII Table:")
print(ascii_table)

# Markdown table
md_table = tabulate(data, headers=headers, tablefmt="github")
print("\\nMarkdown Table:")
print(md_table)

print("\\n✓ tabulate works")
""",
    "jinja2": """
import sys
sys.path.insert(0, '/app/site-packages')

from jinja2 import Template

# Test template rendering
template_str = '''
Hello {{ name }}!

Your tasks:
{% for task in tasks %}
  - {{ task }}
{% endfor %}

Total: {{ tasks|length }} tasks
'''

template = Template(template_str)
result = template.render(
    name="Alice",
    tasks=["Code review", "Write tests", "Deploy"]
)
print(result)

# Test with safe escaping
html_template = Template('<p>{{ content }}</p>')
result = html_template.render(content="<script>alert('xss')</script>")
print(f"Escaped HTML: {result}")

print("✓ jinja2 works")
""",
    "markdown": """
import sys
sys.path.insert(0, '/app/site-packages')

import markdown

# Test Markdown to HTML conversion
md_text = '''
# Hello World

This is a **test** with:
- Item 1
- Item 2

[Link](https://example.com)

```python
print("code block")
```
'''

html = markdown.markdown(md_text)
print("Converted HTML:")
print(html)
print("\\n✓ markdown works")
""",
    "jsonschema": """
import sys
sys.path.insert(0, '/app/site-packages')

from jsonschema import validate, ValidationError

# Test JSON schema validation
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "number", "minimum": 0}
    },
    "required": ["name", "age"]
}

# Valid data
valid_data = {"name": "Alice", "age": 25}
try:
    validate(instance=valid_data, schema=schema)
    print("✓ Valid data passed validation")
except ValidationError as e:
    print(f"✗ Validation failed: {e}")

# Invalid data
invalid_data = {"name": "Bob"}  # Missing age
try:
    validate(instance=invalid_data, schema=schema)
    print("✗ Invalid data should have failed")
except ValidationError as e:
    print(f"✓ Invalid data correctly rejected: {e.message}")

print("\\n✓ jsonschema works")
""",
    "tomli": """
import sys
sys.path.insert(0, '/app/site-packages')

try:
    import tomllib  # Python 3.11+
    print("Using stdlib tomllib")
except ImportError:
    import tomli as tomllib
    print("Using tomli backport")

# Test TOML parsing
toml_str = '''
[package]
name = "test"
version = "1.0.0"

[dependencies]
pytest = ">=7.0"
'''

data = tomllib.loads(toml_str)
print(f"Parsed TOML: {data}")
print(f"Package name: {data['package']['name']}")
print(f"Package version: {data['package']['version']}")

print("\\n✓ tomli works")
""",
}


def test_package(package_name: str, code: str):
    """Test a package in WASM sandbox."""
    print(f"\n{'=' * 60}")
    print(f"Testing {package_name}")
    print(f"{'=' * 60}")

    try:
        # jinja2 needs higher fuel budget for import
        from sandbox import ExecutionPolicy

        policy = ExecutionPolicy(
            fuel_budget=5_000_000_000 if package_name == "jinja2" else 2_000_000_000
        )
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
        result = sandbox.execute(code)

        if result.success:
            print(f"\n[PASS] {package_name} test PASSED")
            print(f"Fuel consumed: {result.fuel_consumed:,} instructions")
            print(f"Duration: {result.duration_ms:.1f}ms")
            print(f"\nOutput:\n{result.stdout}")
            return True
        else:
            print(f"\n[FAIL] {package_name} test FAILED")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"\n[FAIL] {package_name} test FAILED with exception")
        print(f"Exception: {e}")
        return False


def main():
    """Run all package tests."""
    print("Testing new vendored packages in WASM environment")
    print("=" * 60)

    results = {}
    for package_name, code in test_cases.items():
        success = test_package(package_name, code)
        results[package_name] = success

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for package_name, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {package_name}")

    print(f"\nTotal: {passed}/{total} packages passed")

    if passed == total:
        print("\nAll packages work in WASM environment!")
        return 0
    else:
        print(f"\n{total - passed} package(s) failed")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
