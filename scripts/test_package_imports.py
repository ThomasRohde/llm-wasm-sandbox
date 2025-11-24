"""Test that all documented packages can be imported successfully.

This is the exact test case from the GitHub Copilot bug report (Nov 24, 2025).
Verifies that the list_available_packages tool documentation is accurate.
"""

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox

# Increase fuel budget for package imports (some like openpyxl need 8-10B)
policy = ExecutionPolicy(fuel_budget=10_000_000_000, memory_bytes=256 * 1024 * 1024)
sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

# Map package names to their import names
package_imports = {
    "openpyxl": "openpyxl",
    "xlsxwriter": "xlsxwriter",
    "PyPDF2": "PyPDF2",  # Correct capitalization
    "odfpy": "odf",  # Import name is 'odf'
    "mammoth": "mammoth",
    "tabulate": "tabulate",
    "jinja2": "jinja2",
    "markupsafe": "markupsafe",
    "markdown": "markdown",
    "dateutil": "dateutil",
    "attrs": "attr",  # Import name is 'attr'
    "certifi": "certifi",
    "charset_normalizer": "charset_normalizer",
    "idna": "idna",
    "urllib3": "urllib3",
    "six": "six",
    "tomli": "tomli",
}

# Test each package
results = {}
for pkg_name, import_name in package_imports.items():
    # Use the CORRECT path as documented
    code = f"""import sys
sys.path.insert(0, "/data/site-packages")
import {import_name}
print("PASS: {pkg_name}")
"""
    result = sandbox.execute(code)
    if result.success and "PASS" in result.stdout:
        results[pkg_name] = "PASS"
    else:
        results[pkg_name] = "FAIL"
        print(f"Failed to import {pkg_name} (as {import_name}):")
        if result.stderr:
            # Truncate long stderr
            stderr_preview = (
                result.stderr[:500] + "..." if len(result.stderr) > 500 else result.stderr
            )
            print(stderr_preview)

# Report results
failures = [k for k, v in results.items() if v == "FAIL"]
passes = [k for k, v in results.items() if v == "PASS"]

print(f"\n[PASS] Successfully imported {len(passes)}/{len(package_imports)} packages")
print(f"Passed: {passes}")

if failures:
    print(f"\n[FAIL] Failed to import {len(failures)} packages: {failures}")
    exit(1)
else:
    print("\n[SUCCESS] All documented packages are importable!")
    exit(0)
