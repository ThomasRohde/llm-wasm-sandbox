"""
OpenAI Agents SDK + llm-wasm-sandbox: Basic Integration

This example demonstrates:
- Function calling tools for secure code execution
- Python and JavaScript runtime support
- Structured result handling with metrics
- Security boundaries via ExecutionPolicy

Requirements:
    pip install -e ".[openai-example]"  # From repo root
    # OR: pip install llm-wasm-sandbox agents-sdk python-dotenv rich

Setup:
    1. Copy .env.example to .env
    2. Add your OpenAI API key to .env
    3. Download WASM binaries: .\\scripts\\fetch_wlr_python.ps1
                                .\\scripts\\fetch_quickjs.ps1

Run:
    python basic_agent.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from agents import Agent, ModelSettings, Runner, function_tool
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox

# Load environment variables
load_dotenv()

console = Console()


# ---------- Sandbox Function Tools ----------


@function_tool
def run_python_in_wasm(code: str) -> dict[str, Any]:
    """
    Execute untrusted Python code inside the llm-wasm-sandbox.

    Use this when you have Python code that should be run in a secure,
    fuel-limited WASM sandbox instead of the host interpreter.

    Args:
        code: Full Python source code to execute. It should be self-contained.

    Returns:
        Dict with:
            - success: bool
            - stdout: str
            - stderr: str
            - fuel_consumed: int
            - duration_seconds: float
            - mem_pages: int
    """
    # Conservative defaults for untrusted LLM-generated code
    policy = ExecutionPolicy(
        fuel_budget=500_000_000,  # Prevent runaway / super-heavy code
        memory_bytes=32 * 1024 * 1024,  # 32 MB
        stdout_max_bytes=100_000,  # Truncate noisy output
    )

    sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
    result = sandbox.execute(code)

    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "fuel_consumed": result.fuel_consumed,
        "duration_seconds": result.duration_seconds,
        "mem_pages": result.mem_pages,
    }


@function_tool
def run_javascript_in_wasm(code: str) -> dict[str, Any]:
    """
    Execute untrusted JavaScript code inside the llm-wasm-sandbox (QuickJS-NG).

    Use this when you have JS code that should be run in a secure,
    fuel-limited WASM sandbox instead of the host runtime.

    Args:
        code: Full JavaScript source code to execute. It should be self-contained.

    Returns:
        Dict with:
            - success: bool
            - stdout: str
            - stderr: str
            - fuel_consumed: int
            - duration_seconds: float
            - mem_pages: int
    """
    policy = ExecutionPolicy(
        fuel_budget=500_000_000,
        memory_bytes=32 * 1024 * 1024,
        stdout_max_bytes=100_000,
    )

    sandbox = create_sandbox(runtime=RuntimeType.JAVASCRIPT, policy=policy)
    result = sandbox.execute(code)

    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "fuel_consumed": result.fuel_consumed,
        "duration_seconds": result.duration_seconds,
        "mem_pages": result.mem_pages,
    }


# ---------- Agent Definition ----------

code_agent = Agent(
    name="WASM Sandbox Code Agent",
    instructions=(
        "You are a coding assistant that MUST execute any code you write "
        "inside the llm-wasm-sandbox tools, never directly on the host.\n\n"
        "Behavior guidelines:\n"
        "1. When the user asks you to run Python code, you should:\n"
        "   - Draft the Python code as a complete, runnable script.\n"
        "   - Call the `run_python_in_wasm` tool with that code.\n"
        "   - Inspect stdout/stderr and explain the result back to the user.\n"
        "2. For JavaScript snippets, use `run_javascript_in_wasm` similarly.\n"
        "3. Never pretend you ran code. Always call a sandbox tool when "
        "   execution results are needed.\n"
        "4. If sandbox execution fails, read stderr, explain the error to the user, "
        "   and suggest fixes if appropriate.\n"
        "5. Present results clearly with code blocks and explanations."
    ),
    model="gpt-4.1",  # Use gpt-5 or gpt-5-mini for better performance/cost
    model_settings=ModelSettings(
        temperature=0.0,  # Deterministic code generation
        tool_choice="auto",  # Let model decide when to call tools
    ),
    tools=[
        run_python_in_wasm,
        run_javascript_in_wasm,
    ],
)


# ---------- Demo Harness ----------


async def demo_fibonacci():
    """Demo: Calculate Fibonacci numbers with Python."""
    console.print(
        Panel(
            "Demo 1: Fibonacci Calculation (Python)",
            style="bold blue",
            expand=False,
        )
    )

    user_prompt = (
        "Write a Python function fibonacci(n) that returns the nth Fibonacci number. "
        "Then run fibonacci(10) inside the WASM sandbox and show me the result."
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {user_prompt}\n")

    result = await Runner.run(code_agent, input=user_prompt)

    console.print("[bold green]Agent Response:[/bold green]")
    console.print(result.final_output)
    console.print()


async def demo_javascript_array():
    """Demo: JavaScript array operations."""
    console.print(
        Panel(
            "Demo 2: Array Operations (JavaScript)",
            style="bold blue",
            expand=False,
        )
    )

    user_prompt = (
        "Write JavaScript code that creates an array [1, 2, 3, 4, 5], "
        "filters even numbers, maps them to their squares, and prints the result. "
        "Run this in the WASM sandbox."
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {user_prompt}\n")

    result = await Runner.run(code_agent, input=user_prompt)

    console.print("[bold green]Agent Response:[/bold green]")
    console.print(result.final_output)
    console.print()


async def demo_data_processing():
    """Demo: Data processing with error handling."""
    console.print(
        Panel(
            "Demo 3: Data Processing with Statistics (Python)",
            style="bold blue",
            expand=False,
        )
    )

    user_prompt = (
        "Create a Python script that defines a list of numbers [12, 45, 23, 78, 34, 56, 89, 12], "
        "calculates the mean, median, min, max, and standard deviation, "
        "then prints a formatted summary. Run this in the sandbox."
    )

    console.print(f"\n[bold cyan]User:[/bold cyan] {user_prompt}\n")

    result = await Runner.run(code_agent, input=user_prompt)

    console.print("[bold green]Agent Response:[/bold green]")
    console.print(result.final_output)
    console.print()


async def main():
    """Run all demos."""
    console.print(
        Panel.fit(
            "[bold]OpenAI Agents SDK + LLM WASM Sandbox[/bold]\n"
            "Basic Function Calling Integration",
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

    # Verify WASM binaries
    python_wasm = Path("bin/python.wasm")
    if not python_wasm.exists():
        console.print(
            "[bold yellow]Warning:[/bold yellow] bin/python.wasm not found.\n"
            "Run: .\\scripts\\fetch_wlr_python.ps1",
            style="yellow",
        )
        return

    try:
        await demo_fibonacci()
        await demo_javascript_array()
        await demo_data_processing()

        console.print(
            Panel(
                "[bold green]✓[/bold green] All demos completed successfully!\n\n"
                "The agent executed code securely in WASM sandboxes with:\n"
                "  • Fuel-based instruction limits\n"
                "  • Memory caps (32 MB)\n"
                "  • Filesystem isolation\n"
                "  • No host access",
                title="Demo Complete",
                style="green",
                expand=False,
            )
        )

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}", style="red")
        console.print("\n[dim]Check that:")
        console.print("  • OPENAI_API_KEY is valid")
        console.print("  • WASM binaries are downloaded")
        console.print("  • agents-sdk is installed[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
