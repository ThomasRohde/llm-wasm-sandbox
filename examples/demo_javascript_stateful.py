"""
Comprehensive demo of JavaScript state persistence and vendored packages.

This demo showcases:
- Auto-persisted state across multiple executions
- Using vendored JavaScript packages (CSV, JSON utils, string utils)
- Helper utilities (readJson, writeJson, etc.)
- Stateful workflow patterns for LLM agents
- Session isolation and cleanup
"""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from sandbox import RuntimeType, create_sandbox, delete_session_workspace

console = Console()


def demo_state_persistence():
    """Demo 1: Basic state persistence across executions."""
    console.print(Panel("[bold]Demo 1:[/bold] State Persistence", style="cyan", expand=False))

    # Create session with state persistence enabled
    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)
    session_id = sandbox.session_id

    console.print(f"\n[dim]Session ID: {session_id[:16]}...[/dim]\n")

    # First execution: Initialize counter
    code1 = """
_state.counter = (_state.counter || 0) + 1;
_state.user = 'Alice';
_state.logs = _state.logs || [];
_state.logs.push(`Execution ${_state.counter} at ${Date.now()}`);

console.log(`Counter: ${_state.counter}`);
console.log(`User: ${_state.user}`);
console.log(`Total logs: ${_state.logs.length}`);
"""

    console.print("[yellow]Execution 1:[/yellow]")
    result1 = sandbox.execute(code1)
    console.print(result1.stdout.strip())

    # Second execution: Increment counter
    code2 = """
_state.counter = (_state.counter || 0) + 1;
_state.logs.push(`Execution ${_state.counter} at ${Date.now()}`);

console.log(`\\nCounter: ${_state.counter}`);
console.log(`User: ${_state.user}`);
console.log(`Logs: ${_state.logs.join(', ')}`);
"""

    console.print("\n[yellow]Execution 2 (state persisted):[/yellow]")
    result2 = sandbox.execute(code2)
    console.print(result2.stdout.strip())

    # Show state file
    state_file = sandbox.workspace / ".session_state.json"
    if state_file.exists():
        console.print("\n[bold]Persisted state file:[/bold]")
        syntax = Syntax(state_file.read_text(), "json", theme="monokai", line_numbers=False)
        console.print(syntax)

    # Cleanup
    delete_session_workspace(session_id)
    console.print("\n[green]✓ Demo 1 complete[/green]\n")


def demo_vendored_packages():
    """Demo 2: Using vendored JavaScript packages."""
    console.print(Panel("[bold]Demo 2:[/bold] Vendored Packages", style="cyan", expand=False))

    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
    session_id = sandbox.session_id

    code = """
// CSV Processing
const csv = requireVendor('csv-simple');
const salesData = `product,units,revenue
Widget A,150,4500
Widget B,230,6900
Widget C,95,3800`;

const sales = csv.parse(salesData);
console.log('📊 CSV Parsing:');
console.log(`  Parsed ${sales.length} products`);
console.log(`  First product: ${sales[0].product} - ${sales[0].units} units`);

// String Utilities
const str = requireVendor('string-utils');
console.log('\\n📝 String Utilities:');
console.log(`  Slug: ${str.slugify('Hello World!')}`);
console.log(`  CamelCase: ${str.camelCase('user-first-name')}`);
console.log(`  Truncate: ${str.truncate('This is a very long sentence', 20)}`);

// JSON Utilities
const jsonUtils = requireVendor('json-utils');
const data = {
    user: {
        profile: {
            name: 'Alice',
            age: 30
        }
    }
};
console.log('\\n🔍 JSON Path Access:');
console.log(`  Deep get: ${jsonUtils.get(data, 'user.profile.name')}`);
console.log(`  Has path: ${jsonUtils.has(data, 'user.profile.age')}`);

// Set nested value
jsonUtils.set(data, 'user.profile.city', 'NYC');
console.log(`  After set: ${jsonUtils.get(data, 'user.profile.city')}`);
"""

    console.print("\n[dim]Executing code with vendored packages...[/dim]\n")
    result = sandbox.execute(code)
    console.print(result.stdout.strip())

    # Show metrics
    console.print("\n[bold]Execution Metrics:[/bold]")
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_row("[cyan]Fuel consumed[/cyan]", f"{result.fuel_consumed:,} instructions")
    table.add_row("[cyan]Memory used[/cyan]", f"{result.memory_used_bytes:,} bytes")
    console.print(table)

    delete_session_workspace(session_id)
    console.print("\n[green]✓ Demo 2 complete[/green]\n")


def demo_helper_utilities():
    """Demo 3: Using auto-injected helper utilities."""
    console.print(Panel("[bold]Demo 3:[/bold] Helper Utilities", style="cyan", expand=False))

    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT)
    session_id = sandbox.session_id

    code = """
// File I/O helpers (automatically available)
console.log('📁 File I/O Helpers:');

// Write JSON
writeJson('/app/config.json', {
    mode: 'production',
    debug: false,
    apiEndpoint: 'https://api.example.com'
});
console.log('  ✓ Wrote config.json');

// Read JSON
const config = readJson('/app/config.json');
console.log(`  ✓ Read config: mode=${config.mode}, debug=${config.debug}`);

// Write text
writeText('/app/notes.txt', 'First note\\n');
appendText('/app/notes.txt', 'Second note\\n');
appendText('/app/notes.txt', 'Third note\\n');
console.log('  ✓ Wrote notes.txt');

// Read lines
const lines = readLines('/app/notes.txt');
console.log(`  ✓ Read ${lines.length} lines`);

// File operations
console.log(`\\n📋 File Operations:`);
console.log(`  File exists: ${fileExists('/app/config.json')}`);
console.log(`  File size: ${fileSize('/app/config.json')} bytes`);

// List files
const files = listFiles('/app');
console.log(`  Files in /app: ${files.join(', ')}`);

// Copy file
copyFile('/app/config.json', '/app/config-backup.json');
console.log('  ✓ Copied config.json → config-backup.json');

console.log('\\n✓ All helper utilities working!');
"""

    console.print("\n[dim]Using auto-injected helpers...[/dim]\n")
    result = sandbox.execute(code)
    console.print(result.stdout.strip())

    delete_session_workspace(session_id)
    console.print("\n[green]✓ Demo 3 complete[/green]\n")


def demo_stateful_workflow():
    """Demo 4: Complex stateful workflow with vendored packages."""
    console.print(
        Panel("[bold]Demo 4:[/bold] Stateful Data Processing Workflow", style="cyan", expand=False)
    )

    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)
    session_id = sandbox.session_id

    console.print("\n[yellow]Step 1: Initialize state and write sample data[/yellow]")
    code1 = """
// Initialize persistent state
_state.processed = _state.processed || [];
_state.errors = _state.errors || [];
_state.totalRevenue = _state.totalRevenue || 0;

// Create sample CSV data
const csv = requireVendor('csv-simple');
const sampleData = [
    { product: 'Widget A', units: 150, price: 30 },
    { product: 'Widget B', units: 230, price: 30 },
    { product: 'Widget C', units: 95, price: 40 }
];

const csvString = csv.stringify(sampleData);
writeText('/app/sales.csv', csvString);

console.log('✓ Created sales.csv with 3 products');
console.log(`✓ State initialized (processed: ${_state.processed.length})`);
"""

    result1 = sandbox.execute(code1)
    console.print(result1.stdout.strip())

    console.print("\n[yellow]Step 2: Process data and update state[/yellow]")
    code2 = """
const csv = requireVendor('csv-simple');
const str = requireVendor('string-utils');

// Read and parse CSV
const csvText = readText('/app/sales.csv');
const sales = csv.parse(csvText);

console.log(`\\nProcessing ${sales.length} sales records...`);

// Process each record
sales.forEach(record => {
    try {
        const units = parseInt(record.units);
        const price = parseFloat(record.price);
        const revenue = units * price;

        // Update state
        _state.processed.push(record.product);
        _state.totalRevenue += revenue;

        // Create summary
        const slug = str.slugify(record.product);
        writeJson(`/app/${slug}.json`, {
            product: record.product,
            units: units,
            price: price,
            revenue: revenue
        });

        console.log(`  ✓ ${record.product}: ${units} units x $${price} = $${revenue}`);
    } catch (e) {
        _state.errors.push({ product: record.product, error: e.message });
        console.log(`  ✗ Error processing ${record.product}`);
    }
});

console.log(`\\nState updated:`);
console.log(`  Processed: ${_state.processed.length} products`);
console.log(`  Total revenue: $${_state.totalRevenue}`);
console.log(`  Errors: ${_state.errors.length}`);
"""

    result2 = sandbox.execute(code2)
    console.print(result2.stdout.strip())

    console.print("\n[yellow]Step 3: Generate final report[/yellow]")
    code3 = """
// Generate summary report
const report = {
    summary: {
        productsProcessed: _state.processed.length,
        totalRevenue: _state.totalRevenue,
        errors: _state.errors.length
    },
    products: _state.processed,
    timestamp: new Date().toISOString()
};

writeJson('/app/report.json', report, 4);

console.log('\\n📊 Final Report:');
console.log(JSON.stringify(report, null, 2));
"""

    result3 = sandbox.execute(code3)
    console.print(result3.stdout.strip())

    # Show files created
    console.print("\n[bold]Files created in session:[/bold]")
    files = list(sandbox.workspace.glob("*.json")) + list(sandbox.workspace.glob("*.csv"))
    for f in sorted(files):
        size = f.stat().st_size
        console.print(f"  [dim]{f.name}[/dim] ({size} bytes)")

    delete_session_workspace(session_id)
    console.print("\n[green]✓ Demo 4 complete[/green]\n")


def demo_session_isolation():
    """Demo 5: Demonstrate session isolation."""
    console.print(Panel("[bold]Demo 5:[/bold] Session Isolation", style="cyan", expand=False))

    # Create two sessions
    sandbox_a = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)
    sandbox_b = create_sandbox(runtime=RuntimeType.JAVASCRIPT, auto_persist_globals=True)

    console.print(f"\n[dim]Session A: {sandbox_a.session_id[:16]}...[/dim]")
    console.print(f"[dim]Session B: {sandbox_b.session_id[:16]}...[/dim]\n")

    # Execute in session A
    code_a = """
_state.name = 'Alice';
_state.counter = 100;
writeText('/app/data.txt', 'Session A data');
console.log(`Session A: name=${_state.name}, counter=${_state.counter}`);
"""

    console.print("[yellow]Session A execution:[/yellow]")
    result_a = sandbox_a.execute(code_a)
    console.print(result_a.stdout.strip())

    # Execute in session B
    code_b = """
_state.name = 'Bob';
_state.counter = 200;
writeText('/app/data.txt', 'Session B data');
console.log(`Session B: name=${_state.name}, counter=${_state.counter}`);
"""

    console.print("\n[yellow]Session B execution:[/yellow]")
    result_b = sandbox_b.execute(code_b)
    console.print(result_b.stdout.strip())

    # Verify isolation
    code_verify_a = """
const data = readText('/app/data.txt');
console.log(`Verify A: name=${_state.name}, counter=${_state.counter}, file="${data}"`);
"""

    code_verify_b = """
const data = readText('/app/data.txt');
console.log(`Verify B: name=${_state.name}, counter=${_state.counter}, file="${data}"`);
"""

    console.print("\n[yellow]Verify session isolation:[/yellow]")
    result_verify_a = sandbox_a.execute(code_verify_a)
    result_verify_b = sandbox_b.execute(code_verify_b)

    console.print(result_verify_a.stdout.strip())
    console.print(result_verify_b.stdout.strip())

    console.print("\n[green]✓ Sessions are completely isolated![/green]")

    # Cleanup
    delete_session_workspace(sandbox_a.session_id)
    delete_session_workspace(sandbox_b.session_id)
    console.print("\n[green]✓ Demo 5 complete[/green]\n")


def main():
    """Run all demos."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]JavaScript Stateful Execution & Vendored Packages Demo[/bold cyan]\n"
            "[dim]Demonstrating state persistence and LLM-friendly utilities[/dim]",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )
    console.print()

    demos = [
        ("State Persistence", demo_state_persistence),
        ("Vendored Packages", demo_vendored_packages),
        ("Helper Utilities", demo_helper_utilities),
        ("Stateful Workflow", demo_stateful_workflow),
        ("Session Isolation", demo_session_isolation),
    ]

    for name, demo_func in demos:
        try:
            demo_func()
        except Exception as e:
            console.print(f"[red]Error in {name}: {e}[/red]")
            raise

    # Summary
    console.print(
        Panel.fit(
            "[bold green]✓ All Demos Completed Successfully[/bold green]\n\n"
            "[bold]Key Takeaways:[/bold]\n"
            "• State persists across executions via `auto_persist_globals`\n"
            "• Vendored packages provide CSV, JSON, and string utilities\n"
            "• Helper functions are automatically injected (no require needed)\n"
            "• Sessions are completely isolated from each other\n"
            "• Perfect for stateful LLM agent workflows",
            border_style="green",
        )
    )
    console.print()


if __name__ == "__main__":
    main()
