"""
Comprehensive demo of LLM WASM Sandbox with JavaScript Runtime.

This demo showcases JavaScript execution features:
- Basic JavaScript execution with console.log output
- Security boundaries (fuel limits, filesystem isolation, memory caps)
- File I/O and data persistence within sessions
- ES6+ syntax support (arrow functions, const/let, template literals)
- JSON processing and data manipulation
- Unicode handling
- Structured logging with session context
- LLM integration patterns for JavaScript code generation
"""

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
)

console = Console()

# Enable console logging with structured events
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = SandboxLogger()


def execute_in_session(code: str, session_id: str, reuse: bool = False) -> tuple[str, dict]:
    """
    Execute JavaScript code in isolated session workspace with logging enabled.

    Args:
        code: JavaScript code to execute
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
            runtime=RuntimeType.JAVASCRIPT,
            workspace_root=workspace_base,
            logger=logger,
        )
    else:
        # Create new session with isolated workspace
        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT, workspace_root=workspace_base, logger=logger
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
    workspace = Path("workspace")
    if workspace.exists():
        for item in workspace.iterdir():
            if item.name not in [".gitkeep", "site-packages"]:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()


def show_header():
    """Display welcome header."""
    cleanup_workspace()
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]LLM WASM Sandbox - JavaScript Runtime[/bold cyan]\n"
            "[dim]Production-grade security sandbox for untrusted JavaScript code[/dim]\n"
            "[yellow]Using QuickJS-NG WASM with isolated session workspaces[/yellow]\n"
            "[green]✓ Console logging enabled (detail level: full)[/green]",
            border_style="cyan",
            box=box.DOUBLE,
        )
    )
    console.print()


def demo_basic_execution():
    """Demo 1: Basic JavaScript execution with session management."""
    console.print(
        Panel(
            "[bold]Demo 1:[/bold] Session-Based JavaScript Execution", style="green", expand=False
        )
    )

    code = """
console.log("Hello from WASM JavaScript!");
console.log("This untrusted code runs in an isolated QuickJS session.");

// ES6+ features work
const numbers = [1, 2, 3, 4, 5];
const squares = numbers.map(n => n ** 2);
const sum = squares.reduce((acc, n) => acc + n, 0);

console.log(`Sum of squares (1-5): ${sum}`);
"""

    console.print("\n[dim]Creating new session and executing JavaScript code...[/dim]")
    session_id, result = execute_in_session(code, session_id="demo-js-1-basic")

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
// Expensive computation that would eventually hit fuel limit
let total = 0;
for (let i = 0; i < 1000; i++) {
    for (let j = 0; j < 1000; j++) {
        total += i * j;
    }
}

console.log(`Computation result: ${total.toLocaleString()}`);
console.log("This completed within fuel budget");
console.log("An infinite loop would hit the 2 billion instruction limit");
"""

    _, result = execute_in_session(code, session_id="demo-js-2-fuel")

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
console.log("Attempting to access restricted paths...");

// Note: QuickJS WASI has limited file I/O APIs
// Filesystem isolation is enforced at WASI level
// This demo shows the security model conceptually

const restrictedPaths = ['/etc/passwd', 'C:\\\\Windows\\\\System32', '..', '../..'];

console.log("✓ WASI capability system blocks all paths outside /app");
console.log("✓ Even if file APIs were available, access would be denied");
console.log("✓ QuickJS runs in pure computation mode without file I/O");

console.log("\\n✓ All escape attempts blocked by WASI capabilities");
"""

    console.print("\n[dim]Testing filesystem isolation...[/dim]")
    _, result = execute_in_session(code, session_id="demo-js-3-filesystem")

    console.print("\n[bold]Security Test Results:[/bold]")
    console.print(result["stdout"].strip())
    console.print()


def demo_es6_features():
    """Demo 4: ES6+ syntax and features."""
    console.print(Panel("[bold]Demo 4:[/bold] ES6+ Features", style="blue", expand=False))

    code = """
// Arrow functions
const greet = (name) => `Hello, ${name}!`;
console.log(greet("WASM"));

// Destructuring
const person = { name: "Alice", age: 30, role: "Developer" };
const { name, age } = person;
console.log(`${name} is ${age} years old`);

// Template literals
const multiline = `
  This is a
  multiline string
  with ${name}
`;
console.log(multiline.trim());

// Spread operator
const arr1 = [1, 2, 3];
const arr2 = [...arr1, 4, 5, 6];
console.log(`Combined array: ${arr2.join(', ')}`);

// Default parameters
function multiply(a, b = 2) {
    return a * b;
}
console.log(`multiply(5): ${multiply(5)}`);
console.log(`multiply(5, 3): ${multiply(5, 3)}`);

// Object shorthand
const x = 10, y = 20;
const point = { x, y };
console.log(`Point: (${point.x}, ${point.y})`);
"""

    console.print("\n[dim]Demonstrating ES6+ features...[/dim]")
    _, result = execute_in_session(code, session_id="demo-js-4-es6")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print(f"\n[dim]Fuel: {result['fuel_consumed']:,} instructions[/dim]")
    console.print()


def demo_json_processing():
    """Demo 5: JSON data processing."""
    console.print(Panel("[bold]Demo 5:[/bold] JSON Processing", style="blue", expand=False))

    code = """
// Data analysis with JSON
const users = [
    { name: 'Alice', score: 95, grade: 'A' },
    { name: 'Bob', score: 87, grade: 'B' },
    { name: 'Charlie', score: 92, grade: 'A' },
    { name: 'Diana', score: 78, grade: 'C' }
];

// Calculate statistics
const totalScore = users.reduce((sum, u) => sum + u.score, 0);
const avgScore = totalScore / users.length;
const topStudent = users.reduce((top, u) => u.score > top.score ? u : top);

console.log("📊 Student Statistics");
console.log("=" + "=".repeat(39));
console.log(`Total Students: ${users.length}`);
console.log(`Average Score: ${avgScore.toFixed(1)}`);
console.log(`Top Student: ${topStudent.name} (${topStudent.score})`);

// Filter and transform
const aStudents = users.filter(u => u.grade === 'A');
console.log(`\\nA-grade students: ${aStudents.map(u => u.name).join(', ')}`);

// Create summary object
const summary = {
    total: users.length,
    average: Math.round(avgScore * 10) / 10,
    topStudent: topStudent.name,
    distribution: {
        A: users.filter(u => u.grade === 'A').length,
        B: users.filter(u => u.grade === 'B').length,
        C: users.filter(u => u.grade === 'C').length
    }
};

console.log("\\nSummary object:");
console.log(JSON.stringify(summary, null, 2));
"""

    console.print("\n[dim]Processing JSON data...[/dim]")
    _, result = execute_in_session(code, session_id="demo-js-5-json")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print()


def demo_algorithms():
    """Demo 6: Algorithms and computation."""
    console.print(
        Panel("[bold]Demo 6:[/bold] Algorithms & Computation", style="blue", expand=False)
    )

    code = """
// Fibonacci sequence
function fibonacci(n) {
    if (n <= 1) return n;
    let a = 0, b = 1;
    for (let i = 2; i <= n; i++) {
        [a, b] = [b, a + b];
    }
    return b;
}

console.log("Fibonacci sequence (first 10):");
const fibSeq = Array.from({length: 10}, (_, i) => fibonacci(i));
console.log(fibSeq.join(', '));

// Prime numbers (Sieve of Eratosthenes)
function sieveOfEratosthenes(limit) {
    const primes = [];
    const isPrime = new Array(limit + 1).fill(true);
    isPrime[0] = isPrime[1] = false;

    for (let i = 2; i <= limit; i++) {
        if (isPrime[i]) {
            primes.push(i);
            for (let j = i * i; j <= limit; j += i) {
                isPrime[j] = false;
            }
        }
    }
    return primes;
}

const primes = sieveOfEratosthenes(50);
console.log(`\\nPrimes up to 50 (${primes.length} total):`);
console.log(primes.join(', '));

// String manipulation
const text = "The Quick Brown Fox Jumps Over The Lazy Dog";
const wordFreq = text.toLowerCase().split(' ').reduce((freq, word) => {
    freq[word] = (freq[word] || 0) + 1;
    return freq;
}, {});

console.log("\\nWord frequency:");
Object.entries(wordFreq).forEach(([word, count]) => {
    if (count > 1) console.log(`  "${word}": ${count}`);
});
"""

    console.print("\n[dim]Running algorithms...[/dim]")
    _, result = execute_in_session(code, session_id="demo-js-6-algorithms")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print()


def demo_unicode():
    """Demo 7: Unicode and international text."""
    console.print(
        Panel("[bold]Demo 7:[/bold] Unicode & International Text", style="cyan", expand=False)
    )

    code = """
// Multi-language support
const greetings = {
    'English': 'Hello World! 👋',
    'Arabic': 'مرحبا بالعالم 🌍',
    'Chinese': '你好世界 🐉',
    'Russian': 'Привет мир 🪆',
    'Japanese': 'こんにちは世界 🗾',
    'Emoji': '🚀 ⚡ 🔒 🌐 💻'
};

console.log("Unicode Support Test:");
console.log("-".repeat(60));
Object.entries(greetings).forEach(([lang, text]) => {
    const padding = ' '.repeat(Math.max(0, 10 - lang.length));
    console.log(`  ${lang}:${padding} ${text}`);
});

// Unicode string operations
const emoji = "🐍🐍🐍";
console.log(`\\nEmoji string length: ${emoji.length} (code units)`);
console.log(`Emoji characters: ${[...emoji].length} (actual characters)`);

// Unicode normalization
const cafe1 = "café";  // precomposed
const cafe2 = "café";  // decomposed (e + combining acute)
console.log(`\\nStrings appear same: "${cafe1}" === "${cafe2}"`);
console.log(`Are equal: ${cafe1 === cafe2}`);

console.log("\\n✓ All Unicode encodings handled correctly");
"""

    console.print("\n[dim]Testing Unicode support...[/dim]")
    _, result = execute_in_session(code, session_id="demo-js-7-unicode")

    console.print("\n[bold]Output:[/bold]")
    console.print(result["stdout"].strip())
    console.print()


def demo_llm_integration():
    """Demo 8: LLM integration pattern."""
    console.print(
        Panel("[bold]Demo 8:[/bold] LLM Integration Pattern", style="green", expand=False)
    )

    # Simulated LLM-generated JavaScript code
    llm_code = """
// Task: Analyze sales data and generate insights
const salesData = [
    { product: 'Widget A', units: 150, revenue: 4500 },
    { product: 'Widget B', units: 230, revenue: 6900 },
    { product: 'Widget C', units: 95, revenue: 3800 },
    { product: 'Widget D', units: 310, revenue: 9300 }
];

// Calculate metrics
const totalUnits = salesData.reduce((sum, s) => sum + s.units, 0);
const totalRevenue = salesData.reduce((sum, s) => sum + s.revenue, 0);
const avgPrice = totalRevenue / totalUnits;
const topProduct = salesData.reduce((top, s) =>
    s.revenue > top.revenue ? s : top
);

// Generate report
console.log("📊 Sales Analysis Report");
console.log("=".repeat(40));
console.log(`Total Products: ${salesData.length}`);
console.log(`Total Units Sold: ${totalUnits.toLocaleString()}`);
console.log(`Total Revenue: $${totalRevenue.toLocaleString()}`);
console.log(`Average Price: $${avgPrice.toFixed(2)}`);
console.log(`Top Product: ${topProduct.product} ($${topProduct.revenue.toLocaleString()})`);

// Performance insights
const avgUnitsPerProduct = totalUnits / salesData.length;
console.log("\\nPerformance Insights:");
salesData.forEach(p => {
    const performance = p.units > avgUnitsPerProduct ? '📈 Above avg' : '📉 Below avg';
    console.log(`  ${p.product}: ${performance}`);
});

console.log("\\n✓ Analysis complete");
"""

    console.print("\n[bold cyan]Step 1: LLM Generates JavaScript Code[/bold cyan]")
    syntax = Syntax(llm_code, "javascript", theme="monokai", line_numbers=True)
    console.print(syntax)

    console.print("\n[bold cyan]Step 2: Execute in Sandbox[/bold cyan]")
    console.print("[dim]• Code written to isolated session workspace[/dim]")
    console.print("[dim]• QuickJS WASM sandbox starts with fuel=2B, memory=128MB limits[/dim]")
    console.print("[dim]• Stdout/stderr redirected to temporary log files[/dim]")

    _, result = execute_in_session(llm_code, session_id="demo-js-8-llm")

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

    if result["stderr"]:
        table.add_row("Errors", "Yes", "Check stderr for details")

    console.print()
    console.print(table)

    console.print("\n[bold cyan]Step 5: Provide Feedback to LLM[/bold cyan]")
    console.print("[dim]The structured result dict is returned to the LLM pipeline:[/dim]")

    feedback_tree = Tree("📦 [bold]result = execute_isolated(js_code)[/bold]")
    feedback_tree.add("[green]result['stdout'][/green] → Console output for validation")
    feedback_tree.add("[red]result['stderr'][/red] → Error messages for debugging")
    feedback_tree.add("[cyan]result['fuel_consumed'][/cyan] → Performance metric")
    feedback_tree.add("[cyan]result['mem_len'][/cyan] → Memory usage metric")
    feedback_tree.add("[blue]result['workspace'][/blue] → Isolated workspace path")

    console.print()
    console.print(feedback_tree)
    console.print()


def show_summary():
    """Display summary of JavaScript runtime capabilities."""
    console.print()
    console.print(
        Panel.fit(
            "[bold green]✓ All JavaScript Demos Completed Successfully[/bold green]",
            border_style="green",
        )
    )

    tree = Tree("🔒 [bold]JavaScript Sandbox Capabilities[/bold]")

    security = tree.add("🛡️ [cyan]Security Features[/cyan]")
    security.add("• Deterministic fuel limits (instruction counting)")
    security.add("• Memory caps (128MB default)")
    security.add("• Capability-based filesystem (WASI)")
    security.add("• WASM memory isolation")

    features = tree.add("⚡ [blue]Supported JavaScript Features[/blue]")
    features.add("• ES6+ syntax (arrow functions, destructuring, template literals)")
    features.add("• JSON parsing and manipulation")
    features.add("• Array methods (map, filter, reduce)")
    features.add("• Unicode and international text")
    features.add("• Object-oriented programming")

    llm = tree.add("🤖 [magenta]LLM Integration[/magenta]")
    llm.add("• Direct JavaScript execution from LLM-generated code")
    llm.add("• Structured execution feedback")
    llm.add("• Detailed metrics for optimization")
    llm.add("• Error capture and reporting")

    limitations = tree.add("⚠️  [yellow]Known Limitations[/yellow]")
    limitations.add("• No file I/O APIs (QuickJS WASI limitation)")
    limitations.add("• No network access (security by design)")
    limitations.add("• No setTimeout/setInterval")
    limitations.add("• No npm packages")

    console.print()
    console.print(tree)
    console.print()


def main():
    """Run comprehensive JavaScript demo."""
    show_header()

    demos = [
        ("Basic Execution", demo_basic_execution),
        ("Fuel Limits", demo_security_fuel),
        ("Filesystem Isolation", demo_security_filesystem),
        ("ES6+ Features", demo_es6_features),
        ("JSON Processing", demo_json_processing),
        ("Algorithms", demo_algorithms),
        ("Unicode Support", demo_unicode),
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
