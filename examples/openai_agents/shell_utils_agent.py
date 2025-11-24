"""
OpenAI Agents SDK + llm-wasm-sandbox: Shell-Like Utilities Demo

This example demonstrates the new sandbox_utils library features:
- File operations (find, tree, grep, etc.)
- Data manipulation (group_by, filter_by, etc.)
- Format conversions (csv_to_json, xml_to_dict)
- Text processing (sed, head, tail, wc)
- Vendored packages (tabulate, python-dateutil, markdown)

The agent can perform complex file and data operations using shell-like
Python APIs while maintaining strict WASM security boundaries.

Requirements:
    pip install -e ".[openai-example]"  # From repo root
    # OR: pip install llm-wasm-sandbox agents-sdk python-dotenv rich

Setup:
    1. Copy .env.example to .env
    2. Add your OpenAI API key to .env
    3. Download WASM binaries: .\\scripts\\fetch_wlr_python.ps1

Run:
    python shell_utils_agent.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated, Any

from agents import Agent, ModelSettings, RunContextWrapper, Runner, function_tool
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox

# Load environment variables
load_dotenv()

console = Console()


# ---------- Enhanced Sandbox Function Tool ----------


@function_tool
async def run_python_with_utils(
    ctx: RunContextWrapper,
    code: Annotated[str, "Python source code to execute with sandbox_utils available"],
    description: Annotated[str, "Brief description of what this code does"] = "",
) -> dict[str, Any]:
    """
    Execute Python code in WASM sandbox with sandbox_utils and vendored packages.

    Available utilities (auto-imported):
    - File ops: find(), tree(), walk(), grep(), ls(), cat(), mkdir(), rm(), cp(), mv()
    - Text: sed(), head(), tail(), wc(), diff()
    - Data: group_by(), filter_by(), map_items(), sort_by(), unique(), chunk()
    - Formats: csv_to_json(), json_to_csv(), xml_to_dict()

    Available vendored packages (need sys.path setup):
    - tabulate: Pretty-print tables
    - python-dateutil: Advanced date/time parsing
    - markdown: Markdown to HTML conversion
    - attrs: Data modeling

    IMPORTANT for vendored packages:
    - First line must be: import sys; sys.path.insert(0, '/app/site-packages')
    - jinja2 requires fuel_budget >= 5_000_000_000 for first import

    All operations are restricted to /app directory for security.

    Args:
        code: Python source code to execute
        description: What the code does (for logging/debugging)

    Returns:
        Dict with execution results including success, stdout, stderr, and metrics
    """
    # Higher fuel budget to accommodate vendored packages like jinja2
    policy = ExecutionPolicy(
        fuel_budget=5_000_000_000,  # 5B for jinja2, markdown, etc.
        memory_bytes=128 * 1024 * 1024,  # 128 MB for data processing
        stdout_max_bytes=500_000,  # Allow larger output for reports
    )

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
    result = sandbox.execute(code)

    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "fuel_consumed": result.fuel_consumed,
        "fuel_percentage": round(result.fuel_consumed / policy.fuel_budget * 100, 1),
        "duration_ms": result.duration_ms,
        "memory_used_bytes": result.memory_used_bytes,
        "description": description,
    }


# ---------- Agent Definition ----------

shell_utils_agent = Agent(
    name="WASM Shell Utilities Agent",
    instructions=(
        "You are a data processing and file manipulation assistant with shell-like "
        "utilities running in a secure WASM sandbox.\n\n"
        "CAPABILITIES:\n"
        "1. File Operations:\n"
        "   - find('*.txt') - Search for files by pattern\n"
        "   - tree('/app') - Show directory structure\n"
        "   - grep(r'ERROR', files) - Search text across files\n"
        "   - ls('/app', long=True) - List directory contents\n"
        "   - cat(), mkdir(), rm(), cp(), mv(), touch() - Standard file ops\n\n"
        "2. Text Processing:\n"
        "   - sed(pattern, replacement, text) - Regex find/replace\n"
        "   - head(file, lines=10) - First N lines\n"
        "   - tail(file, lines=10) - Last N lines\n"
        "   - wc(file) - Count lines/words/chars\n"
        "   - diff(file1, file2) - Compare files\n\n"
        "3. Data Manipulation:\n"
        "   - group_by(items, key_func) - Group by key\n"
        "   - filter_by(items, predicate) - Filter items\n"
        "   - map_items(items, transform) - Transform items\n"
        "   - sort_by(items, key_func) - Sort by key\n"
        "   - unique(items) - Remove duplicates\n"
        "   - chunk(items, size) - Split into chunks\n\n"
        "4. Format Conversions:\n"
        "   - csv_to_json(file) - CSV to JSON\n"
        "   - json_to_csv(file) - JSON to CSV\n"
        "   - xml_to_dict(xml_str) - XML to dict\n\n"
        "5. Vendored Packages (need sys.path setup):\n"
        "   - tabulate: Pretty tables\n"
        "   - python-dateutil: Date parsing\n"
        "   - markdown: Markdown rendering\n"
        "   - attrs: Data modeling\n\n"
        "USAGE PATTERNS:\n"
        "- All utilities are in sandbox_utils module\n"
        "- Example: from sandbox_utils import find, grep, csv_to_json\n"
        "- For vendored packages: import sys; sys.path.insert(0, '/app/site-packages')\n"
        "- All paths must be within /app (enforced by security)\n"
        "- Use run_python_with_utils tool for execution\n\n"
        "BEHAVIOR:\n"
        "1. Write complete, runnable code with imports\n"
        "2. Use shell-like utils instead of verbose stdlib code\n"
        "3. Handle errors gracefully (try/except)\n"
        "4. Print clear output showing results\n"
        "5. Explain what the code does before running it\n"
        "6. If execution fails, analyze stderr and fix issues\n"
    ),
    model="gpt-4.1",
    model_settings=ModelSettings(
        temperature=0.1,  # Slightly creative for code patterns
        tool_choice="auto",
    ),
    tools=[
        run_python_with_utils,
    ],
)


# ---------- Demo Scenarios ----------


async def demo_file_exploration():
    """Demo: File system exploration with find, tree, grep."""
    console.print(
        Panel(
            "Demo 1: File System Exploration",
            subtitle="Using find(), tree(), grep()",
            style="bold blue",
            expand=False,
        )
    )

    prompt = (
        "Create a sample project structure with:\n"
        "- /app/src/main.py (contains 'def main(): print(\"Hello World\")')\n"
        "- /app/src/utils.py (contains 'def helper(): pass')\n"
        "- /app/tests/test_main.py (contains 'import unittest')\n"
        "- /app/README.md (contains '# My Project')\n\n"
        "Then:\n"
        "1. Show the directory tree\n"
        "2. Find all Python files\n"
        "3. Search for the word 'def' in all Python files using grep\n"
        "4. Show file details with ls(long=True)"
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {prompt}\n")

    result = await Runner.run(shell_utils_agent, input=prompt)

    console.print("[bold green]Agent:[/bold green]")
    console.print(result.final_output)
    console.print()


async def demo_data_transformation():
    """Demo: CSV data processing with grouping and tabulate."""
    console.print(
        Panel(
            "Demo 2: Data Transformation & Analysis",
            subtitle="Using group_by(), filter_by(), tabulate",
            style="bold blue",
            expand=False,
        )
    )

    prompt = (
        "Create a CSV file at /app/sales.csv with this data:\n"
        "```\n"
        "date,product,quantity,price\n"
        "2024-01-15,Widget,10,25.50\n"
        "2024-01-16,Gadget,5,45.00\n"
        "2024-01-16,Widget,8,25.50\n"
        "2024-01-17,Widget,12,25.50\n"
        "2024-01-17,Gadget,3,45.00\n"
        "```\n\n"
        "Then:\n"
        "1. Read the CSV and convert to list of dicts\n"
        "2. Group sales by product using group_by()\n"
        "3. Calculate total quantity and revenue per product\n"
        "4. Display results in a nice table using tabulate package\n"
        "5. Show which product generated more revenue"
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {prompt}\n")

    result = await Runner.run(shell_utils_agent, input=prompt)

    console.print("[bold green]Agent:[/bold green]")
    console.print(result.final_output)
    console.print()


async def demo_log_analysis():
    """Demo: Log file analysis with grep, wc, dateutil."""
    console.print(
        Panel(
            "Demo 3: Log File Analysis",
            subtitle="Using grep(), wc(), python-dateutil",
            style="bold blue",
            expand=False,
        )
    )

    prompt = (
        "Create a log file at /app/app.log with these entries:\n"
        "```\n"
        "2024-01-15 10:23:45 [INFO] Application started\n"
        "2024-01-15 10:24:12 [ERROR] Database connection failed\n"
        "2024-01-15 10:24:15 [WARN] Retrying connection\n"
        "2024-01-15 10:24:20 [INFO] Database connected\n"
        "2024-01-15 10:30:45 [ERROR] Invalid user input\n"
        "2024-01-15 10:35:12 [ERROR] File not found: /data/config.json\n"
        "2024-01-15 11:00:00 [INFO] Processing complete\n"
        "```\n\n"
        "Then:\n"
        "1. Count total lines using wc()\n"
        "2. Find all ERROR lines using grep()\n"
        "3. Extract and parse timestamps using python-dateutil\n"
        "4. Calculate time between first and last error\n"
        "5. Show summary statistics"
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {prompt}\n")

    result = await Runner.run(shell_utils_agent, input=prompt)

    console.print("[bold green]Agent:[/bold green]")
    console.print(result.final_output)
    console.print()


async def demo_report_generation():
    """Demo: Generate markdown report from data."""
    console.print(
        Panel(
            "Demo 4: Report Generation",
            subtitle="Using markdown, sed(), format conversions",
            style="bold blue",
            expand=False,
        )
    )

    prompt = (
        "Create a JSON file at /app/metrics.json with:\n"
        "```json\n"
        "{\n"
        '  "system": "Production API",\n'
        '  "date": "2024-01-15",\n'
        '  "metrics": [\n'
        '    {"name": "Requests/sec", "value": 1250},\n'
        '    {"name": "Avg Response Time", "value": 45},\n'
        '    {"name": "Error Rate", "value": 0.2}\n'
        "  ]\n"
        "}\n"
        "```\n\n"
        "Then:\n"
        "1. Read the JSON and extract data\n"
        "2. Generate a Markdown report with:\n"
        "   - Title with system name and date\n"
        "   - Table of metrics\n"
        "   - Status summary (GOOD if error rate < 1%, WARNING otherwise)\n"
        "3. Convert the Markdown to HTML using markdown package\n"
        "4. Save both report.md and report.html to /app\n"
        "5. Show the final markdown content"
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {prompt}\n")

    result = await Runner.run(shell_utils_agent, input=prompt)

    console.print("[bold green]Agent:[/bold green]")
    console.print(result.final_output)
    console.print()


async def demo_text_processing():
    """Demo: Advanced text processing with sed, diff."""
    console.print(
        Panel(
            "Demo 5: Text Processing & Diff",
            subtitle="Using sed(), diff(), head(), tail()",
            style="bold blue",
            expand=False,
        )
    )

    prompt = (
        "Create two Python files:\n"
        "/app/old_version.py:\n"
        "```python\n"
        "def calculate(x, y):\n"
        "    result = x + y\n"
        "    return result\n"
        "\n"
        "def main():\n"
        "    print(calculate(5, 3))\n"
        "```\n\n"
        "/app/new_version.py:\n"
        "```python\n"
        "def calculate(x: int, y: int) -> int:\n"
        '    """Add two numbers."""\n'
        "    return x + y\n"
        "\n"
        "def main() -> None:\n"
        "    result = calculate(5, 3)\n"
        '    print(f"Result: {result}")\n'
        "```\n\n"
        "Then:\n"
        "1. Show diff between the two files\n"
        "2. Use sed() to transform old_version to match new_version style\n"
        "3. Count lines in each file using wc()\n"
        "4. Show first 3 lines of new_version using head()"
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {prompt}\n")

    result = await Runner.run(shell_utils_agent, input=prompt, max_turns=15)

    console.print("[bold green]Agent:[/bold green]")
    console.print(result.final_output)
    console.print()


async def main():
    """Run all demos."""
    console.print(
        Panel.fit(
            "[bold]OpenAI Agents SDK + LLM WASM Sandbox[/bold]\n"
            "Shell-Like Utilities & Vendored Packages Demo",
            style="bold white on blue",
        )
    )
    console.print()

    # Verify API key
    if not os.getenv("OPENAI_API_KEY"):
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY not found in environment.\n"
            "Please copy .env.example to .env and add your API key.",
            style="red",
        )
        return

    # Verify WASM binary
    python_wasm = Path("bin/python.wasm")
    if not python_wasm.exists():
        console.print(
            "[bold yellow]Warning:[/bold yellow] bin/python.wasm not found.\n"
            "Run: .\\scripts\\fetch_wlr_python.ps1",
            style="yellow",
        )
        return

    # Show available utilities
    console.print("[bold]Available sandbox_utils functions:[/bold]")
    utils_code = """from sandbox_utils import (
    # File operations
    find, tree, walk, copy_tree, remove_tree,
    # Text processing
    grep, sed, head, tail, wc, diff,
    # Data manipulation
    group_by, filter_by, map_items, sort_by, unique, chunk,
    # Format conversions
    csv_to_json, json_to_csv, xml_to_dict,
    # Shell commands
    ls, cat, touch, mkdir, rm, cp, mv, echo
)"""
    syntax = Syntax(utils_code, "python", theme="monokai", line_numbers=False)
    console.print(syntax)
    console.print()

    try:
        await demo_file_exploration()
        await demo_data_transformation()
        await demo_log_analysis()
        await demo_report_generation()
        await demo_text_processing()

        console.print(
            Panel(
                "[bold green]✓[/bold green] All demos completed successfully!\n\n"
                "Features demonstrated:\n"
                "  • Shell-like file operations (find, tree, grep, ls)\n"
                "  • Data manipulation (group_by, filter_by, sort_by)\n"
                "  • Format conversions (CSV, JSON, XML)\n"
                "  • Text processing (sed, diff, head, tail, wc)\n"
                "  • Vendored packages (tabulate, python-dateutil, markdown)\n"
                "  • Strict /app sandbox security\n"
                "  • Fuel budgets up to 5B for heavy packages",
                title="Demo Complete",
                style="green",
                expand=False,
            )
        )

        console.print("\n[bold]Key Insights:[/bold]")
        console.print("• sandbox_utils makes LLM code generation much simpler")
        console.print("• Vendored packages enable rich data processing")
        console.print("• All operations maintain WASM security boundaries")
        console.print("• Fuel monitoring prevents runaway computation")

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}", style="red")
        import traceback

        console.print(traceback.format_exc(), style="dim")
        console.print("\n[dim]Check that:")
        console.print("  • OPENAI_API_KEY is valid")
        console.print("  • WASM binaries are downloaded")
        console.print("  • openai-agents is installed")
        console.print("  • sandbox_utils is in vendor/site-packages/")
        console.print("[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
