"""Error guidance templates for actionable error resolution.

Provides structured error analysis and actionable solutions for common
sandbox execution errors. Templates are parameterized to include context-
specific information (e.g., detected package names, file paths).
"""

from __future__ import annotations

from typing import TypedDict


class CodeExample(TypedDict, total=False):
    """Structure for before/after code examples in error guidance."""

    before: str
    after: str
    explanation: str


class ErrorGuidance(TypedDict):
    """Structure for error guidance metadata in SandboxResult."""

    error_type: str
    actionable_guidance: list[str]
    related_docs: list[str]
    code_examples: list[CodeExample] | None


# Error type constants
ERROR_OUT_OF_FUEL = "OutOfFuel"
ERROR_PATH_RESTRICTION = "PathRestriction"
ERROR_QUICKJS_TUPLE_DESTRUCTURING = "QuickJSTupleDestructuring"
ERROR_MISSING_VENDORED_PACKAGE = "MissingVendoredPackage"
ERROR_MEMORY_EXHAUSTED = "MemoryExhausted"
ERROR_TIMEOUT = "Timeout"
ERROR_INVALID_PATH = "InvalidPath"
ERROR_MISSING_REQUIRE_VENDOR = "MissingRequireVendor"


def get_outoffuel_guidance(
    fuel_consumed: int | None = None,
    fuel_budget: int | None = None,
    detected_packages: list[str] | None = None,
) -> ErrorGuidance:
    """Generate guidance for OutOfFuel errors.

    Args:
        fuel_consumed: Fuel consumed before trap (if available)
        fuel_budget: Original fuel budget (if available)
        detected_packages: Heavy packages detected in stderr (e.g., ["openpyxl"])

    Returns:
        Structured error guidance with actionable solutions
    """
    guidance: list[str] = [
        "Code execution exceeded the fuel budget (instruction limit).",
        "This typically occurs with:",
        "  - Heavy package imports (openpyxl: 5-7B, PyPDF2: 5-6B, jinja2: 5-10B fuel on first import)",
        "  - Large dataset processing (loops over big files/arrays)",
        "  - Infinite loops or very deep recursion",
    ]

    if detected_packages:
        pkg_list = ", ".join(detected_packages)
        guidance.append(f"\nDetected heavy package(s): {pkg_list}")
        guidance.append("These packages require higher fuel budgets on first import (5-10B).")
        guidance.append(
            "Subsequent imports in the same session are cached and use minimal fuel (<100M)."
        )

    guidance.extend(
        [
            "\nSolutions:",
            "1. Increase fuel_budget when creating session or calling execute_code:",
            "   - For heavy packages: Use 10B+ for first import, 2B+ for subsequent executions",
            "   - For large datasets: Estimate ~1B fuel per 100K loop iterations",
            "2. Use persistent sessions (auto_persist_globals=True) to cache imports across executions",
            "3. Optimize code: reduce loop iterations, use generators instead of loading full datasets",
        ]
    )

    if fuel_budget and fuel_consumed:
        suggestion = int(fuel_budget * 2)  # 100% safety margin
        guidance.append(
            f"\nConcrete recommendation: Increase fuel_budget from {fuel_budget:,} to {suggestion:,} instructions"
        )
    elif fuel_budget:
        suggestion = int(fuel_budget * 2)
        guidance.append(
            f"\nConcrete recommendation: Increase fuel_budget to {suggestion:,} instructions"
        )

    return ErrorGuidance(
        error_type=ERROR_OUT_OF_FUEL,
        actionable_guidance=guidance,
        related_docs=[
            "docs/PYTHON_CAPABILITIES.md#fuel-requirements",
            "docs/MCP_INTEGRATION.md#fuel-budgeting",
        ],
        code_examples=[
            CodeExample(
                before="sandbox.execute(code)  # Uses default 5B fuel",
                after="sandbox.execute(code, fuel_budget=10_000_000_000)  # 10B for heavy packages",
                explanation="Increase fuel budget for package imports or large computations",
            )
        ],
    )


def get_path_restriction_guidance(detected_path: str | None = None) -> ErrorGuidance:
    """Generate guidance for path restriction errors.

    Args:
        detected_path: Invalid path detected in error message

    Returns:
        Structured error guidance
    """
    guidance: list[str] = [
        "File access failed due to WASI capability-based isolation.",
        "The sandbox only has access to files within the /app directory (workspace).",
        "Absolute paths and attempts to access parent directories (..) are blocked.",
    ]

    if detected_path:
        guidance.append(f"\nDetected invalid path: {detected_path}")

    guidance.extend(
        [
            "\nSolutions:",
            "1. Use relative paths within /app (e.g., 'data.txt' instead of '/etc/passwd')",
            "2. Place input files in the workspace directory before execution",
            "3. Use /app/ prefix for absolute paths: '/app/data.txt' (not '/data.txt')",
            "4. For secondary data mounts, use the configured guest_data_path (default: /data)",
        ]
    )

    code_example = (
        CodeExample(
            before=f"with open('{detected_path}', 'r') as f:",
            after="with open('/app/data.txt', 'r') as f:",
            explanation="Use /app prefix or relative paths within workspace",
        )
        if detected_path
        else CodeExample(
            before="with open('/etc/passwd', 'r') as f:",
            after="with open('/app/data.txt', 'r') as f:",
            explanation="Use /app prefix or relative paths within workspace",
        )
    )

    return ErrorGuidance(
        error_type=ERROR_PATH_RESTRICTION,
        actionable_guidance=guidance,
        related_docs=[
            "docs/MCP_INTEGRATION.md#filesystem-isolation",
            "HARDENING.md#capability-based-isolation",
        ],
        code_examples=[code_example],
    )


def get_quickjs_tuple_guidance(detected_line: str | None = None) -> ErrorGuidance:
    """Generate guidance for QuickJS tuple destructuring errors.

    Args:
        detected_line: Code line that caused the error (if available)

    Returns:
        Structured error guidance
    """
    guidance: list[str] = [
        "QuickJS helper functions return arrays, not JavaScript destructuring-compatible tuples.",
        "JavaScript array destructuring syntax works, but Python-style tuple unpacking does not.",
        "This is a known limitation of the QuickJS std/os modules.",
    ]

    if detected_line:
        guidance.append(f"\nProblematic code: {detected_line}")

    guidance.extend(
        [
            "\nSolutions:",
            "1. Use array destructuring: const [key, value] = readJson('data.json');",
            "2. Use array indexing: const result = readJson('data.json'); const key = result[0];",
            "3. Avoid Python-style tuple unpacking: NO: (key, value) = func(); YES: [key, value] = func();",
        ]
    )

    return ErrorGuidance(
        error_type=ERROR_QUICKJS_TUPLE_DESTRUCTURING,
        actionable_guidance=guidance,
        related_docs=[
            "docs/JAVASCRIPT_CAPABILITIES.md#quickjs-api-patterns",
            "docs/MCP_JAVASCRIPT_USAGE.md#common-pitfalls",
        ],
        code_examples=[
            CodeExample(
                before="const (status, data) = os.stat('/app/file.txt');  // ❌ Invalid",
                after="const [status, data] = os.stat('/app/file.txt');  // ✅ Correct",
                explanation="Use array destructuring syntax, not tuple syntax",
            )
        ],
    )


def get_missing_vendored_package_guidance(package_name: str | None = None) -> ErrorGuidance:
    """Generate guidance for missing vendored package imports (Python).

    Args:
        package_name: Name of the missing package

    Returns:
        Structured error guidance
    """
    guidance: list[str] = [
        "ModuleNotFoundError for a vendored package indicates sys.path is not configured.",
        "The sandbox includes 30+ pre-installed Python packages in /data/site-packages,",
        "but they must be explicitly added to sys.path before importing.",
    ]

    if package_name:
        guidance.append(f"\nMissing package: {package_name}")

    guidance.extend(
        [
            "\nSolutions:",
            "1. Add sys.path configuration at the start of your code:",
            "   import sys",
            "   sys.path.insert(0, '/data/site-packages')",
            "2. Then import the package normally: import openpyxl",
            "3. List available packages: call list_available_packages MCP tool",
        ]
    )

    # Package-specific fuel requirements
    fuel_notes = ""
    if package_name in ["openpyxl", "PyPDF2", "jinja2"]:
        fuel_notes = f"\nNote: {package_name} requires 5-10B fuel on first import. Increase fuel_budget if needed."

    if fuel_notes:
        guidance.append(fuel_notes)

    example_package = package_name or "openpyxl"
    return ErrorGuidance(
        error_type=ERROR_MISSING_VENDORED_PACKAGE,
        actionable_guidance=guidance,
        related_docs=[
            "docs/PYTHON_CAPABILITIES.md#vendored-packages",
            "docs/MCP_INTEGRATION.md#package-usage",
        ],
        code_examples=[
            CodeExample(
                before=f"import {example_package}  # ❌ ModuleNotFoundError",
                after=f"import sys\nsys.path.insert(0, '/data/site-packages')\nimport {example_package}  # ✅ Works",
                explanation="Add vendored packages to sys.path before importing",
            )
        ],
    )


def get_missing_require_vendor_guidance(package_name: str | None = None) -> ErrorGuidance:
    """Generate guidance for missing requireVendor calls (JavaScript).

    Args:
        package_name: Name of the missing vendored package

    Returns:
        Structured error guidance
    """
    guidance: list[str] = [
        "Vendored JavaScript packages must be loaded via requireVendor(), not standard require().",
        "The sandbox includes vendored packages (csv-simple, string-utils, json-utils),",
        "but they are not in the standard module search path.",
    ]

    if package_name:
        guidance.append(f"\nMissing package: {package_name}")

    guidance.extend(
        [
            "\nSolutions:",
            "1. Use requireVendor() for vendored packages:",
            "   const csv = requireVendor('csv-simple');",
            "2. Available vendored packages: csv-simple, string-utils, json-utils",
            "3. For standard library modules, use regular require(): const fs = require('fs');",
        ]
    )

    example_package = package_name or "csv-simple"
    return ErrorGuidance(
        error_type=ERROR_MISSING_REQUIRE_VENDOR,
        actionable_guidance=guidance,
        related_docs=[
            "docs/JAVASCRIPT_CAPABILITIES.md#vendored-packages",
            "docs/MCP_JAVASCRIPT_USAGE.md#importing-packages",
        ],
        code_examples=[
            CodeExample(
                before=f"const pkg = require('{example_package}');  // ❌ Module not found",
                after=f"const pkg = requireVendor('{example_package}');  // ✅ Works",
                explanation="Use requireVendor() for vendored packages",
            )
        ],
    )


def get_memory_exhausted_guidance(
    memory_used: int | None = None, memory_limit: int | None = None
) -> ErrorGuidance:
    """Generate guidance for memory exhaustion errors.

    Args:
        memory_used: Memory used before trap (if available)
        memory_limit: Configured memory limit (if available)

    Returns:
        Structured error guidance
    """
    guidance: list[str] = [
        "Code execution exceeded the memory limit (linear memory cap).",
        "This typically occurs with:",
        "  - Loading large files entirely into memory (multi-MB datasets)",
        "  - Creating large data structures (big arrays, nested objects)",
        "  - Memory leaks in long-running computations",
    ]

    guidance.extend(
        [
            "\nSolutions:",
            "1. Increase memory_bytes when creating session or calling execute_code:",
            "   - Default: 128 MB (sufficient for most tasks)",
            "   - Large files: 256-512 MB",
            "   - Very large datasets: 1 GB+",
            "2. Process data in chunks instead of loading entire files",
            "3. Use generators/iterators to avoid materializing full datasets",
            "4. Clear large objects after use: del large_array",
        ]
    )

    if memory_limit and memory_used:
        suggestion = int(memory_limit * 2)  # 100% safety margin
        guidance.append(
            f"\nConcrete recommendation: Increase memory_bytes from {memory_limit:,} to {suggestion:,} bytes"
        )
    elif memory_limit:
        suggestion = int(memory_limit * 2)
        guidance.append(f"\nConcrete recommendation: Increase memory_bytes to {suggestion:,} bytes")

    return ErrorGuidance(
        error_type=ERROR_MEMORY_EXHAUSTED,
        actionable_guidance=guidance,
        related_docs=[
            "docs/MCP_INTEGRATION.md#memory-limits",
            "HARDENING.md#resource-limits",
        ],
        code_examples=[
            CodeExample(
                before="sandbox.execute(code)  # Uses default 128 MB",
                after="sandbox.execute(code, memory_bytes=256_000_000)  # 256 MB for larger datasets",
                explanation="Increase memory limit for large file processing",
            )
        ],
    )


def classify_error_from_trap(
    trap_message: str, fuel_consumed: int | None = None, fuel_budget: int | None = None
) -> ErrorGuidance | None:
    """Classify error from Wasmtime trap message.

    Args:
        trap_message: Trap message from Wasmtime
        fuel_consumed: Fuel consumed before trap
        fuel_budget: Original fuel budget

    Returns:
        Error guidance if classified, None otherwise
    """
    trap_lower = trap_message.lower()

    if (
        "out of fuel" in trap_lower
        or "fuel exhausted" in trap_lower
        or "all fuel consumed" in trap_lower
        or "fuel consumed by webassembly" in trap_lower
    ):
        return get_outoffuel_guidance(fuel_consumed, fuel_budget)

    if "out of bounds memory" in trap_lower or "memory fault" in trap_lower:
        return get_memory_exhausted_guidance()

    return None


def classify_error_from_stderr(stderr: str, language: str = "python") -> ErrorGuidance | None:
    """Classify error from stderr output.

    Args:
        stderr: Captured stderr output
        language: Runtime language (python or javascript)

    Returns:
        Error guidance if classified, None otherwise
    """
    # Limit stderr scanning to first 10KB to avoid performance issues
    stderr_sample = stderr[:10000]

    if language == "python":
        # Detect ModuleNotFoundError for vendored packages
        if "ModuleNotFoundError" in stderr_sample:
            # Extract package name if possible
            import re

            match = re.search(r"No module named '([^']+)'", stderr_sample)
            package_name = match.group(1) if match else None

            # Check if it's a known vendored package
            vendored_packages = {
                "openpyxl",
                "xlsxwriter",
                "PyPDF2",
                "odfpy",
                "mammoth",
                "tabulate",
                "jinja2",
                "markdown",
                "dateutil",
                "attrs",
            }
            if package_name and any(pkg in package_name.lower() for pkg in vendored_packages):
                return get_missing_vendored_package_guidance(package_name)

        # Detect FileNotFoundError with paths outside /app
        if "FileNotFoundError" in stderr_sample or "PermissionError" in stderr_sample:
            import re

            # Look for ALL file paths in error messages (findall instead of search)
            path_matches = re.findall(r"['\"]([/\\][^'\"]+)['\"]", stderr_sample)
            for path in path_matches:
                # Check if path is outside /app and /data
                if not path.startswith("/app") and not path.startswith("/data"):
                    return get_path_restriction_guidance(path)

    elif language == "javascript":
        # Detect QuickJS tuple destructuring errors
        if "TypeError" in stderr_sample and "not iterable" in stderr_sample:
            # Extract problematic line if possible
            import re

            line_match = re.search(r"at <eval>:(\d+)", stderr_sample)
            detected_line = f"line {line_match.group(1)}" if line_match else None
            return get_quickjs_tuple_guidance(detected_line)

        # Detect missing requireVendor calls
        if "ReferenceError" in stderr_sample or "Cannot find module" in stderr_sample:
            import re

            pkg_match = re.search(r"'([^']+)'", stderr_sample)
            package_name = pkg_match.group(1) if pkg_match else None
            vendored_packages = {"csv-simple", "string-utils", "json-utils"}
            if package_name in vendored_packages:
                return get_missing_require_vendor_guidance(package_name)

    return None


def get_error_guidance(
    trap_message: str | None = None,
    stderr: str = "",
    language: str = "python",
    fuel_consumed: int | None = None,
    fuel_budget: int | None = None,
    memory_used: int | None = None,
    memory_limit: int | None = None,
) -> ErrorGuidance | None:
    """Get error guidance from execution context.

    Attempts to classify error from multiple signals in priority order:
    1. Wasmtime trap messages (most reliable)
    2. Stderr pattern matching (less reliable but covers more cases)

    Args:
        trap_message: Wasmtime trap message (if execution trapped)
        stderr: Captured stderr output
        language: Runtime language (python or javascript)
        fuel_consumed: Fuel consumed before trap
        fuel_budget: Original fuel budget
        memory_used: Memory used before trap
        memory_limit: Configured memory limit

    Returns:
        Error guidance if error classified, None otherwise
    """
    # Priority 1: Trap-based classification (most reliable)
    if trap_message:
        guidance = classify_error_from_trap(trap_message, fuel_consumed, fuel_budget)
        if guidance:
            return guidance

    # Priority 2: Stderr pattern matching
    if stderr:
        guidance = classify_error_from_stderr(stderr, language)
        if guidance:
            return guidance

    return None
