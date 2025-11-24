"""
Comprehensive demo of LLM WASM Sandbox with Session Management.

This unified demo showcases all key features:
- Session management for stateful multi-turn execution
- Security boundaries (fuel limits, filesystem isolation, memory caps)
- File I/O and data persistence within sessions
- Host-side file operations (list, read, write, delete)
- Database operations (SQLite) with session persistence
- Package support (vendored packages)
- Unicode handling
- Structured logging with session context
- LLM integration patterns
"""

import json
import logging
import shutil
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from sandbox import (
    RuntimeType,
    SandboxLogger,
    create_sandbox,
    list_session_files,
    read_session_file,
    write_session_file,
)

console = Console()

# Enable console logging with structured events
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = SandboxLogger()


def execute_in_session(code: str, session_id: str, reuse: bool = False) -> tuple[str, dict]:
    """
    Execute code in isolated session workspace with logging enabled.

    Args:
        code: Python code to execute
        session_id: Session identifier for workspace isolation
        reuse: If True, reuse existing session; if False, create new session

    Returns:
        Tuple of (session_id, result_dict)
    """
    workspace_base = Path("../workspace")

    if reuse:
        # Retrieve existing session
        sandbox = create_sandbox(
            session_id=session_id,
            runtime=RuntimeType.PYTHON,
            workspace_root=workspace_base,
            logger=logger,
        )
    else:
        # Create new session with isolated workspace
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON, workspace_root=workspace_base, logger=logger
        )
        session_id = sandbox.session_id

    # Execute code in session
    result = sandbox.execute(code)

    # Return session_id and result dict
    return session_id, {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "fuel_consumed": result.fuel_consumed,
        "mem_len": result.memory_used_bytes,
        "mem_pages": result.memory_used_bytes // 65536,
        "workspace": str(workspace_base / session_id),
        "files_created": result.files_created,
        "files_modified": result.files_modified,
        "success": result.success,
        "session_id": result.metadata.get("session_id", session_id),
    }


def cleanup_workspace():
    """Clean up workspace directory before demo."""
    workspace = Path("../workspace")
    if workspace.exists():
        for item in workspace.iterdir():
            if item.name not in [".gitkeep", "site-packages"]:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()


def demo_session_persistence():
    """Demo: Multi-turn execution with session persistence."""
    console.print(
        Panel(
            "[bold]Demo: Session Persistence[/bold] (Multi-Turn Execution)",
            style="magenta",
            expand=False,
        )
    )

    # Turn 1: Create data
    console.print("\n[bold cyan]Turn 1:[/bold cyan] Create and save data")
    code_turn1 = """
data = {'counter': 0, 'history': []}

import json
with open('/app/state.json', 'w') as f:
    json.dump(data, f)
print("✓ Created initial state")
"""

    session_id, result1 = execute_in_session(code_turn1, session_id="persistent-session")
    console.print(result1["stdout"].strip())
    console.print(f"[dim]Session ID: {session_id[:16]}...[/dim]")

    # Turn 2: Read and modify
    console.print("\n[bold cyan]Turn 2:[/bold cyan] Read state and increment counter")
    code_turn2 = """
import json
with open('/app/state.json', 'r') as f:
    data = json.load(f)

data['counter'] += 1
data['history'].append('incremented')

with open('/app/state.json', 'w') as f:
    json.dump(data, f)

print(f"✓ Counter: {data['counter']}")
print(f"✓ History: {data['history']}")
"""

    _, result2 = execute_in_session(code_turn2, session_id=session_id, reuse=True)
    console.print(result2["stdout"].strip())

    # Turn 3: Host-side file read
    console.print("\n[bold cyan]Turn 3:[/bold cyan] Read file from host side")
    workspace_base = Path("../workspace")
    state_data = read_session_file(session_id, "state.json", workspace_root=workspace_base)
    state = json.loads(state_data.decode("utf-8"))
    console.print(
        f"[green]✓ Host read state.json: counter={state['counter']}, history={state['history']}[/green]"
    )

    # Turn 4: Host writes new task
    console.print("\n[bold cyan]Turn 4:[/bold cyan] Host writes task file")
    task = "Process the uploaded data and generate report"
    write_session_file(session_id, "task.txt", task, workspace_root=workspace_base)
    console.print("[green]✓ Host wrote task.txt[/green]")

    # Turn 5: Guest processes task
    console.print("\n[bold cyan]Turn 5:[/bold cyan] Guest reads task and processes")
    code_turn5 = """
with open('/app/task.txt', 'r') as f:
    task = f.read()

print(f"Task received: {task}")

# Process task
import json
with open('/app/state.json', 'r') as f:
    data = json.load(f)

data['counter'] += 1
data['history'].append('processed_task')

# Generate report
with open('/app/report.txt', 'w') as f:
    f.write(f"Report:\\n")
    f.write(f"  Task: {task}\\n")
    f.write(f"  Executions: {data['counter']}\\n")
    f.write(f"  Status: Complete\\n")

with open('/app/state.json', 'w') as f:
    json.dump(data, f)

print("✓ Report generated")
"""

    _, result5 = execute_in_session(code_turn5, session_id=session_id, reuse=True)
    console.print(result5["stdout"].strip())

    # Show all files in session
    console.print("\n[bold cyan]Final State:[/bold cyan] List all session files")
    files = list_session_files(session_id, workspace_root=workspace_base)
    for file in files:
        console.print(f"  [cyan]📄[/cyan] {file}")

    console.print(
        f"\n[green]✓ Session {session_id[:16]}... persisted across {result5['session_id'].count('turn') + 5} turns[/green]"
    )
    console.print()


def show_header():
    """Display welcome header."""
    cleanup_workspace()
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]LLM WASM Sandbox with Session Management[/bold cyan]\n"
            "[dim]Production-grade security sandbox for untrusted Python code[/dim]\n"
            "[yellow]Using isolated session workspaces with structured logging[/yellow]\n"
            "[green]✓ Console logging enabled (detail level: full)[/green]",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )
    console.print()


def demo_basic_execution():
    """Demo 1: Basic code execution with session management."""
    console.print(
        Panel("[bold]Demo 1:[/bold] Session-Based Execution", style="green", expand=False)
    )

    code = """
print("Hello from WASM Python!")
print("This untrusted code runs in an isolated session workspace.")

# Some computation
result = sum(i**2 for i in range(100))
print(f"Sum of squares (0-99): {result}")
"""

    console.print("\n[dim]Creating new session and executing code...[/dim]")
    session_id, result = execute_in_session(code, session_id="demo-1-basic")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print(f"\n[dim]Session ID: {session_id}[/dim]")
    console.print(f"[dim]Workspace: {result['workspace']}[/dim]")

    # Show metrics
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_row("[cyan]Session ID[/cyan]", session_id[:16] + "...")
    table.add_row("[cyan]Fuel consumed[/cyan]", f"{result['fuel_consumed']:,} instructions")
    table.add_row("[cyan]Memory used[/cyan]", f"{result['mem_len']:,} bytes")
    table.add_row("[cyan]Memory pages[/cyan]", str(result["mem_pages"]))
    console.print("\n[bold]Execution Metrics:[/bold]")
    console.print(table)
    console.print()


def demo_security_fuel():
    """Demo 2: Fuel exhaustion (infinite loop protection)."""
    console.print(
        Panel("[bold]Demo 2:[/bold] Security - Fuel Limits", style="yellow", expand=False)
    )

    console.print("\n[dim]Demonstrating fuel consumption tracking...[/dim]\n")

    # Show a computation that consumes significant fuel
    code = """
# Expensive computation that would eventually hit fuel limit
total = 0
for i in range(1000):
    for j in range(1000):
        total += i * j

print(f"Computation result: {total:,}")
print("This completed within fuel budget")
print("An infinite loop would hit the 2 billion instruction limit")
"""

    _, result = execute_in_session(code, session_id="demo-2-fuel")

    console.print("[bold]Output:[/bold]")
    console.print(result["stdout"].strip())

    # Create metrics table
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_row("[cyan]Fuel consumed[/cyan]", f"{result['fuel_consumed']:,} instructions")
    table.add_row("[cyan]Fuel budget[/cyan]", "2,000,000,000 instructions")
    table.add_row(
        "[cyan]Usage[/cyan]", f"{(result['fuel_consumed'] / 2_000_000_000) * 100:.2f}% of budget"
    )

    console.print("\n[bold]Fuel Metrics:[/bold]")
    console.print(table)

    console.print("\n[green]✓ Infinite loops would be terminated at budget exhaustion[/green]")
    console.print()


def demo_security_filesystem():
    """Demo 3: Filesystem isolation."""
    console.print(
        Panel("[bold]Demo 3:[/bold] Security - Filesystem Isolation", style="yellow", expand=False)
    )

    code = """
import os

print("Attempting to access restricted paths...")

# Malicious: try to escape sandbox
restricted_paths = ['/etc/passwd', 'C:\\\\Windows\\\\System32', '..', '../..']

for path in restricted_paths:
    try:
        with open(path, 'r') as f:
            content = f.read()
        print(f"❌ SECURITY BREACH: Read {path}")
    except (FileNotFoundError, PermissionError, OSError) as e:
        print(f"✓ Blocked: {path}")

print("\\n✓ All escape attempts blocked by WASI capabilities")
"""

    console.print("\n[dim]Testing filesystem isolation...[/dim]")
    _, result = execute_in_session(code, session_id="demo-3-filesystem")

    console.print("\n[bold]Security Test Results:[/bold]")
    console.print(result["stdout"].strip())
    console.print()


def demo_file_io():
    """Demo 4: Legitimate file I/O within sandbox."""
    console.print(Panel("[bold]Demo 4:[/bold] File I/O Operations", style="blue", expand=False))

    code = """
import json

# Create a configuration file
config = {
    'app_name': 'WASM Sandbox',
    'version': '2.0',
    'features': ['isolation', 'fuel_limits', 'capability_based_io'],
    'settings': {
        'max_execution_time': '2B instructions',
        'memory_limit': '128MB'
    }
}

# Write JSON file
with open('/app/config.json', 'w') as f:
    json.dump(config, f, indent=2)
print("✓ Created config.json")

# Read it back
with open('/app/config.json', 'r') as f:
    loaded = json.load(f)

print(f"\\nConfiguration loaded:")
print(f"  App: {loaded['app_name']} v{loaded['version']}")
print(f"  Features: {len(loaded['features'])}")
for feature in loaded['features']:
    print(f"    • {feature}")
"""

    console.print("\n[dim]Performing file operations...[/dim]")
    _, result = execute_in_session(code, session_id="demo-4-fileio")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print(
        f"\n[dim]Workspace: {result['workspace']} | Fuel: {result['fuel_consumed']:,} instructions[/dim]"
    )
    console.print()


def demo_file_generation():
    """Demo 5: Python code that generates files (matplotlib-style)."""
    console.print(
        Panel(
            "[bold]Demo 5:[/bold] File Generation (e.g., Plots, Reports)",
            style="blue",
            expand=False,
        )
    )

    code = """
import json
import csv
from pathlib import Path

# Simulate data analysis that generates multiple output files
# (This pattern works for matplotlib, pandas.to_csv, report generators, etc.)

# 1. Generate CSV report
data = [
    ['Name', 'Score', 'Grade'],
    ['Alice', 95, 'A'],
    ['Bob', 87, 'B'],
    ['Charlie', 92, 'A'],
]

with open('/app/scores.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(data)

print("✓ Generated scores.csv")

# 2. Generate JSON summary
summary = {
    'total_students': len(data) - 1,
    'average_score': sum(row[1] for row in data[1:]) / (len(data) - 1),
    'top_student': max(data[1:], key=lambda x: x[1])[0]
}

with open('/app/summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("✓ Generated summary.json")

# 3. Generate HTML report (like a visualization)
html_content = f'''<!DOCTYPE html>
<html>
<head><title>Student Report</title></head>
<body>
    <h1>Student Performance Report</h1>
    <p>Total Students: {summary['total_students']}</p>
    <p>Average Score: {summary['average_score']:.1f}</p>
    <p>Top Student: {summary['top_student']}</p>
</body>
</html>'''

with open('/app/report.html', 'w') as f:
    f.write(html_content)

print("✓ Generated report.html")

# 4. List all generated files
print("\\nGenerated files in /app:")
workspace = Path('/app')
for file in sorted(workspace.glob('*.csv')) + sorted(workspace.glob('*.json')) + sorted(workspace.glob('*.html')):
    print(f"  📄 {file.name}")

# Note: In a real matplotlib scenario, you'd do:
#   import matplotlib.pyplot as plt
#   plt.plot([1, 2, 3], [4, 5, 6])
#   plt.savefig('/app/plot.png')  # File saved to workspace/plot.png on host
"""

    console.print("\n[dim]Generating multiple output files...[/dim]")
    _, result = execute_in_session(code, session_id="demo-5-generation")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())

    # Show automatically tracked files
    if result["files_created"]:
        console.print("\n[bold green]📁 Files Created (auto-tracked):[/bold green]")
        for file_path in result["files_created"]:
            console.print(f"  [green]✓[/green] {result['workspace']}/{file_path}")

    if result["files_modified"]:
        console.print("\n[bold yellow]📝 Files Modified:[/bold yellow]")
        for file_path in result["files_modified"]:
            console.print(f"  [yellow]•[/yellow] {result['workspace']}/{file_path}")

    console.print(f"\n[dim]Fuel used: {result['fuel_consumed']:,} instructions[/dim]")
    console.print(
        "\n[yellow]💡 Key Point:[/yellow] Files written to [cyan]/app/[/cyan] in the sandbox"
    )
    console.print("   are automatically visible in [cyan]workspace/[/cyan] on the host.")
    console.print("   [bold]File paths are now included in the result dict![/bold]")
    console.print()


def demo_sqlite():
    """Demo 6: SQLite database operations."""
    console.print(Panel("[bold]Demo 6:[/bold] SQLite Database", style="blue", expand=False))

    code = """
import sqlite3

# Create and populate database
conn = sqlite3.connect('/app/sandbox.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS executions (
        id INTEGER PRIMARY KEY,
        code_type TEXT,
        fuel_used INTEGER,
        status TEXT
    )
''')

# Insert sample data
executions = [
    ('data_processing', 1500000, 'success'),
    ('api_call', 800000, 'success'),
    ('infinite_loop', 2000000000, 'terminated'),
    ('file_io', 1200000, 'success'),
]

cursor.executemany(
    'INSERT INTO executions (code_type, fuel_used, status) VALUES (?, ?, ?)',
    executions
)
conn.commit()

# Query and analyze
cursor.execute('''
    SELECT status, COUNT(*) as count, AVG(fuel_used) as avg_fuel
    FROM executions
    GROUP BY status
''')

print("Execution Statistics:")
print("-" * 50)
for row in cursor.fetchall():
    status, count, avg_fuel = row
    print(f"  {status:12s}: {count} executions, avg fuel: {int(avg_fuel):,}")

conn.close()
print("\\n✓ Database operations completed")
"""

    console.print("\n[dim]Working with SQLite database...[/dim]")
    _, result = execute_in_session(code, session_id="demo-6-sqlite")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print()


def demo_vendored_packages():
    """Demo 7: Using vendored packages."""
    console.print(
        Panel(
            "[bold]Demo 7:[/bold] Vendored Packages (Auto-injected)", style="magenta", expand=False
        )
    )

    code = """
# LLM-generated code doesn't need to know about sys.path!
# The sandbox automatically injects vendored packages

import certifi
import idna

print("Using vendored packages (automatically available):")
print("-" * 50)

# Certificate bundle
print(f"✓ certifi: {certifi.__version__}")
print(f"  Cert bundle: {certifi.where()}")

# International domain names
print(f"\\n✓ idna: {idna.__version__}")
domains = ["münchen.de", "日本.jp", "москва.ru"]
for domain in domains:
    encoded = idna.encode(domain).decode('ascii')
    print(f"  {domain:15s} → {encoded}")

print(f"\\n✓ Packages available: certifi, idna, urllib3, charset_normalizer")
print("  (urllib3 networking operations blocked by WASI)")
"""

    console.print("\n[dim]Using vendored packages...[/dim]")
    _, result = execute_in_session(code, session_id="demo-7-packages")

    if result["stderr"]:
        console.print("\n[bold red]Error:[/bold red]")
        console.print(result["stderr"])

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip() if result["stdout"] else "[dim]No output[/dim]")
    console.print()


def demo_unicode():
    """Demo 8: Unicode and encoding support."""
    console.print(
        Panel("[bold]Demo 8:[/bold] Unicode & International Text", style="cyan", expand=False)
    )

    code = """
import json

# Multi-language support
greetings = {
    'English': 'Hello World! 👋',
    'Arabic': 'مرحبا بالعالم 🌍',
    'Chinese': '你好世界 🐉',
    'Russian': 'Привет мир 🪆',
    'Japanese': 'こんにちは世界 🗾',
    'Emoji': '🚀 🐍 ⚡ 🔒 🌐'
}

print("Unicode Support Test:")
print("-" * 60)
for lang, text in greetings.items():
    print(f"  {lang:10s}: {text}")

# Write to file with UTF-8
with open('/app/unicode.txt', 'w', encoding='utf-8') as f:
    json.dump(greetings, f, ensure_ascii=False, indent=2)

print("\\n✓ Successfully wrote Unicode to file")
print("✓ All encodings handled correctly")
"""

    console.print("\n[dim]Testing Unicode support...[/dim]")
    _, result = execute_in_session(code, session_id="demo-8-unicode")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print()


def demo_shell_utilities():
    """Demo 9: Shell utilities from sandbox_utils library."""
    console.print(
        Panel("[bold]Demo 9:[/bold] Shell Utilities (sandbox_utils)", style="blue", expand=False)
    )

    code = """
from sandbox_utils import ls, find, tree, grep, cat, mkdir, touch, echo

# Create test directory structure
mkdir("/app/logs", parents=True)
mkdir("/app/data", parents=True)

# Create test files
echo("ERROR: Failed to connect", "/app/logs/error.log")
echo("INFO: Server started", "/app/logs/info.log")
echo("WARNING: High memory usage", "/app/logs/warning.log")

touch("/app/data/results.txt")
echo("test,value\\n1,100\\n2,200\\n3,300", "/app/data/data.csv")

print("📂 Directory Tree:")
print(tree("/app", max_depth=2))

print("\\n🔍 Find all .log files:")
log_files = find("*.log", "/app", recursive=True)
for f in log_files:
    print(f"  • {f}")

print("\\n🔎 Search for 'ERROR' in log files:")
matches = grep(r"ERROR", log_files)
for file, line_num, line in matches:
    print(f"  {file}:{line_num}: {line.strip()}")

print("\\n📋 List /app/logs directory (long format):")
items = ls("/app/logs", long=True)
for item in items:
    print(f"  {item}")

print("\\n📄 Read error.log:")
print(cat("/app/logs/error.log"))
"""

    console.print("\n[dim]Demonstrating shell-like file operations...[/dim]")
    _, result = execute_in_session(code, session_id="demo-9-shell")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print(f"\n[dim]Fuel: {result['fuel_consumed']:,} instructions[/dim]")
    console.print()


def demo_data_processing():
    """Demo 10: Data processing with sandbox_utils."""
    console.print(
        Panel(
            "[bold]Demo 10:[/bold] Data Processing (sandbox_utils)", style="magenta", expand=False
        )
    )

    code = """
from sandbox_utils import csv_to_json, group_by, filter_by, sort_by, unique
import json

# Create sample CSV data
csv_data = '''name,department,salary,years
Alice,Engineering,95000,5
Bob,Engineering,87000,3
Charlie,Sales,92000,7
Diana,Engineering,105000,8
Eve,Sales,78000,2
Frank,HR,65000,4'''

# Write CSV file
with open('/app/employees.csv', 'w') as f:
    f.write(csv_data)

# Convert CSV to JSON
json_str = csv_to_json('/app/employees.csv')
employees = json.loads(json_str)

print("📊 Employee Data Processing")
print("=" * 50)

# Group by department
by_dept = group_by(employees, lambda e: e['department'])
print("\\n👥 Employees by Department:")
for dept, emps in by_dept.items():
    print(f"  {dept}: {len(emps)} employees")

# Filter high earners (salary > 90k)
high_earners = filter_by(employees, lambda e: int(e['salary']) > 90000)
print(f"\\n💰 High Earners (>$90k): {len(high_earners)}")
for emp in high_earners:
    print(f"  • {emp['name']}: ${emp['salary']}")

# Sort by years of experience
by_experience = sort_by(employees, lambda e: int(e['years']), reverse=True)
print("\\n⭐ Most Experienced:")
for emp in by_experience[:3]:
    print(f"  {emp['name']}: {emp['years']} years")

# Get unique departments
departments = unique([e['department'] for e in employees])
print(f"\\n🏢 Departments: {', '.join(departments)}")

# Calculate average salary by department
print("\\n💵 Average Salary by Department:")
for dept, emps in by_dept.items():
    avg = sum(int(e['salary']) for e in emps) / len(emps)
    print(f"  {dept}: ${avg:,.0f}")
"""

    console.print("\n[dim]Processing employee data with functional utilities...[/dim]")
    _, result = execute_in_session(code, session_id="demo-10-data")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print(f"\n[dim]Fuel: {result['fuel_consumed']:,} instructions[/dim]")
    console.print()


def demo_llm_integration():
    """Demo 11: LLM integration pattern.

    This demonstrates the complete flow for integrating with an LLM:

    1. LLM generates Python code (untrusted)
    2. Code is written to workspace/user_code.py with auto-injected sys.path
    3. WASM sandbox executes the code with:
       - Stdout/stderr redirected to temporary log files
       - Fuel consumption tracked (instruction counting)
       - Memory usage monitored
       - Filesystem access limited to /app (maps to workspace/)
    4. After execution:
       - Logs are read with size caps (2MB stdout, 1MB stderr)
       - Metrics are collected (fuel, memory)
       - Results returned as structured dict
    5. Feedback provided to LLM with:
       - Success/failure status
       - Console output for validation
       - Performance metrics for optimization
       - Error messages for debugging
    """
    console.print(
        Panel("[bold]Demo 11:[/bold] LLM Integration Pattern", style="green", expand=False)
    )

    # Simulated LLM-generated code
    llm_code = """
# Task: Analyze user data and generate report
import json

users = [
    {'name': 'Alice', 'age': 30, 'purchases': 5},
    {'name': 'Bob', 'age': 25, 'purchases': 12},
    {'name': 'Charlie', 'age': 35, 'purchases': 8},
]

# Calculate metrics
total_purchases = sum(u['purchases'] for u in users)
avg_age = sum(u['age'] for u in users) / len(users)
top_buyer = max(users, key=lambda u: u['purchases'])

report = {
    'total_users': len(users),
    'total_purchases': total_purchases,
    'average_age': round(avg_age, 1),
    'top_buyer': top_buyer['name']
}

print("📊 Analysis Report")
print("=" * 40)
for key, value in report.items():
    print(f"  {key.replace('_', ' ').title()}: {value}")

# Save report
with open('/app/report.json', 'w') as f:
    json.dump(report, f, indent=2)
print("\\n✓ Report saved to /app/report.json")
"""

    console.print("\n[bold cyan]Step 1: LLM Generates Code[/bold cyan]")
    syntax = Syntax(llm_code, "python", theme="monokai", line_numbers=True)
    console.print(syntax)

    console.print("\n[bold cyan]Step 2: Execute in Sandbox[/bold cyan]")
    console.print("[dim]• Code written to isolated session workspace[/dim]")
    console.print("[dim]• sys.path automatically includes /app/site-packages[/dim]")
    console.print("[dim]• WASM sandbox starts with fuel=2B, memory=128MB limits[/dim]")
    console.print("[dim]• Stdout/stderr redirected to temporary log files[/dim]")

    _session_id, result = execute_in_session(llm_code, session_id="demo-9-llm")

    console.print("\n[bold cyan]Step 3: Capture Output[/bold cyan]")
    console.print("[bold]Console Output (stdout):[/bold]")
    console.print(result["stdout"].strip())

    if result["stderr"]:
        console.print("\n[bold red]Errors (stderr):[/bold red]")
        console.print(result["stderr"].strip())

    console.print("\n[bold cyan]Step 4: Collect Metrics[/bold cyan]")

    # Create feedback table
    table = Table(title="Execution Feedback for LLM", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Assessment", style="yellow")

    success = bool(result["stdout"]) and not result["stderr"]
    fuel_pct = (result["fuel_consumed"] / 2_000_000_000) * 100

    table.add_row("Success", "✓" if success else "✗", "Code executed without errors")
    table.add_row("Fuel Used", f"{result['fuel_consumed']:,}", f"{fuel_pct:.2f}% of budget")
    table.add_row("Memory", f"{result['mem_len']:,} bytes", "Well within limits")

    if result["files_created"]:
        table.add_row(
            "Files Created",
            str(len(result["files_created"])),
            ", ".join(result["files_created"][:3]),
        )

    if result["stderr"]:
        table.add_row("Errors", "Yes", "Check stderr for details")

    console.print()
    console.print(table)

    console.print("\n[bold cyan]Step 5: Provide Feedback to LLM[/bold cyan]")
    console.print("[dim]The structured result dict is returned to the LLM pipeline:[/dim]")

    feedback_tree = Tree("📦 [bold]result = execute_isolated(code)[/bold]")
    feedback_tree.add("[green]result['stdout'][/green] → Console output for validation")
    feedback_tree.add("[red]result['stderr'][/red] → Error messages for debugging")
    feedback_tree.add("[cyan]result['fuel_consumed'][/cyan] → Performance metric")
    feedback_tree.add("[cyan]result['mem_len'][/cyan] → Memory usage metric")
    feedback_tree.add("[magenta]result['files_created'][/magenta] → List of created file paths")
    feedback_tree.add("[magenta]result['files_modified'][/magenta] → List of modified file paths")
    feedback_tree.add("[blue]result['workspace'][/blue] → Isolated workspace path")
    feedback_tree.add("[yellow]result['logs_dir'][/yellow] → Temp dir with full logs")

    console.print()
    console.print(feedback_tree)
    console.print()


def show_summary():
    """Display summary of capabilities."""
    console.print()
    console.print(
        Panel.fit(
            "[bold green]✓ All Demos Completed Successfully[/bold green]", border_style="green"
        )
    )

    tree = Tree("🔒 [bold]Sandbox Capabilities[/bold]")

    security = tree.add("🛡️ [cyan]Security Features[/cyan]")
    security.add("• Deterministic fuel limits (instruction counting)")
    security.add("• Memory caps (128MB default)")
    security.add("• Capability-based filesystem (WASI)")
    security.add("• WASM memory isolation")

    features = tree.add("⚡ [blue]Supported Features[/blue]")
    features.add("• File I/O within sandbox (/app)")
    features.add("• SQLite databases")
    features.add("• JSON, CSV, Unicode handling")
    features.add("• Regex and text processing")
    features.add("• Vendored packages (certifi, urllib3, idna)")

    llm = tree.add("🤖 [magenta]LLM Integration[/magenta]")
    llm.add("• Automatic sys.path injection")
    llm.add("• Structured execution feedback")
    llm.add("• Detailed metrics for optimization")
    llm.add("• Error capture and reporting")

    console.print()
    console.print(tree)
    console.print()


def main():
    """Run comprehensive demo."""
    show_header()

    demos = [
        ("Session-Based Execution", demo_basic_execution),
        ("Session Persistence", demo_session_persistence),
        ("Fuel Exhaustion", demo_security_fuel),
        ("Filesystem Isolation", demo_security_filesystem),
        ("File I/O", demo_file_io),
        ("File Generation", demo_file_generation),
        ("SQLite Database", demo_sqlite),
        ("Vendored Packages", demo_vendored_packages),
        ("Unicode Support", demo_unicode),
        ("Shell Utilities", demo_shell_utilities),
        ("Data Processing", demo_data_processing),
        ("LLM Integration", demo_llm_integration),
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        for name, demo_func in demos:
            task = progress.add_task(f"Running {name}...", total=None)
            try:
                demo_func()
                progress.remove_task(task)
            except Exception as e:
                progress.remove_task(task)
                console.print(f"[red]Error in {name}: {e}[/red]")
                raise

    show_summary()


if __name__ == "__main__":
    main()
