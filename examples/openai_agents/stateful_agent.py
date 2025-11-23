"""
OpenAI Agents SDK + llm-wasm-sandbox: Stateful Sessions with Error Recovery

This example demonstrates:
- Session-based stateful code execution
- File persistence across multiple agent turns
- Error recovery patterns (syntax errors, fuel exhaustion)
- Session cleanup and lifecycle management

Requirements:
    pip install -e ".[openai-example]"  # From repo root
    # OR: pip install llm-wasm-sandbox agents-sdk python-dotenv rich

Setup:
    1. Copy .env.example to .env
    2. Add your OpenAI API key to .env
    3. Download WASM binaries: .\\scripts\\fetch_wlr_python.ps1

Run:
    python stateful_agent.py
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from agents import Agent, ModelSettings, Runner, RunContextWrapper, SQLiteSession, function_tool
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from sandbox import (
    ExecutionPolicy,
    RuntimeType,
    create_sandbox,
    delete_session_workspace,
)


# ---------- Sandbox State Management ----------


@dataclass
class SandboxState:
    """
    Local context for managing WASM sandbox session state.
    
    This is NOT sent to the LLM - it's Python-side state that persists
    across tool calls within the same Runner.run() execution and can be
    reused across multiple turns by passing the same instance.
    """

    wasm_session_id: str | None = None

# Load environment variables
load_dotenv()

console = Console()


# ---------- Stateful Sandbox Function Tool ----------


@function_tool
async def run_python_in_wasm(
    ctx: RunContextWrapper[SandboxState],
    code: Annotated[str, "Python source code to execute in the WASM sandbox"],
    persistent: Annotated[
        bool,
        "If True, reuse the same workspace across calls (files persist). "
        "If False, use a fresh workspace each time.",
    ] = True,
) -> dict[str, Any]:
    """
    Execute Python code in the WASM sandbox.
    
    When persistent=True (default), the same workspace is automatically
    reused across all calls in this conversation, allowing files written
    to /app to persist between executions.
    
    When persistent=False, a fresh workspace is created for this execution.
    
    Returns:
        Dict with execution results:
            - success: bool - Whether execution completed without errors
            - stdout: str - Standard output from the code
            - stderr: str - Standard error output
            - fuel_consumed: int - WASM instructions executed
            - duration_ms: float - Wall-clock execution time in milliseconds
            - memory_used_bytes: int - Peak memory usage in bytes
            - session_id: str - Workspace session ID (for logging/debugging)
    """
    # Slightly higher limits for stateful work
    policy = ExecutionPolicy(
        fuel_budget=500_000_000,
        memory_bytes=64 * 1024 * 1024,  # 64 MB for data processing
        stdout_max_bytes=200_000,
    )

    # Decide which session_id to use based on persistence
    if persistent:
        if ctx.context.wasm_session_id is None:
            # First persistent call - create new session and cache it
            sandbox = create_sandbox(
                runtime=RuntimeType.PYTHON,
                session_id=None,
                policy=policy,
            )
            ctx.context.wasm_session_id = sandbox.session_id
        else:
            # Reuse existing session from context
            sandbox = create_sandbox(
                runtime=RuntimeType.PYTHON,
                session_id=ctx.context.wasm_session_id,
                policy=policy,
            )
    else:
        # Explicitly requested fresh workspace - don't cache session_id
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            session_id=None,
            policy=policy,
        )

    result = sandbox.execute(code)

    return {
        "success": result.success,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "fuel_consumed": result.fuel_consumed,
        "duration_ms": result.duration_ms,
        "memory_used_bytes": result.memory_used_bytes,
        "session_id": sandbox.session_id,  # For logging/debugging
    }


# ---------- Agent Definition ----------

stateful_agent = Agent[SandboxState](
    name="Stateful WASM Sandbox Agent",
    instructions=(
        "You are a coding assistant that executes Python code in WASM sandbox sessions.\n\n"
        "Behavior guidelines:\n"
        "1. Use `run_python_in_wasm` for all code execution.\n"
        "2. By default (persistent=True), files you write to /app will persist across "
        "multiple executions in the same conversation. This is automatic - you don't need "
        "to track any session IDs.\n"
        "3. If you want a completely fresh workspace for testing, use persistent=False.\n"
        "4. If execution fails with errors:\n"
        "   - Read stderr carefully\n"
        "   - Explain the error\n"
        "   - Fix the code and retry (files from previous calls will still be there)\n"
        "5. If fuel is exhausted, simplify the algorithm and retry.\n"
        "6. Present results with code blocks and clear explanations."
    ),
    model="gpt-5-nano",  # Newer model with better instruction following
    model_settings=ModelSettings(
        tool_choice="auto",
    ),
    tools=[
        run_python_in_wasm,
    ],
)


# ---------- Demo Scenarios ----------


async def demo_multi_turn_session():
    """Demo: Multi-turn conversation with file persistence."""
    console.print(
        Panel(
            "Demo 1: Multi-Turn Session with File Persistence",
            style="bold blue",
            expand=False,
        )
    )

    # Create OpenAI Agents SDK session to maintain conversation history
    agent_session = SQLiteSession("demo1_conversation")

    # Create sandbox state to track WASM session across turns
    # This is the KEY: same state object passed to all Runner.run() calls
    sandbox_state = SandboxState()

    # Turn 1: Create data file
    console.print("\n[bold cyan]Turn 1: Create Data File[/bold cyan]\n")
    prompt1 = (
        "Create a JSON file at /app/users.json with this data: "
        '{"users": ["Alice", "Bob"], "count": 2}. '
        "Print confirmation that the file was created."
    )
    console.print(f"User: {prompt1}\n")

    result1 = await Runner.run(
        stateful_agent,
        input=prompt1,
        session=agent_session,
        context=sandbox_state,  # State persists across turns
    )
    console.print("[bold green]Agent:[/bold green]")
    console.print(result1.final_output)
    console.print(f"\n[dim]Sandbox session ID: {sandbox_state.wasm_session_id}[/dim]\n")

    # Turn 2: Read and modify the file (same sandbox_state = same workspace!)
    console.print("\n[bold cyan]Turn 2: Read and Modify File[/bold cyan]\n")
    prompt2 = (
        "Read /app/users.json, add 'Charlie' to the users list, "
        "update the count, write it back, and print the updated data."
    )
    console.print(f"User: {prompt2}\n")

    result2 = await Runner.run(
        stateful_agent,
        input=prompt2,
        session=agent_session,
        context=sandbox_state,  # Same state = files persist!
    )
    console.print("[bold green]Agent:[/bold green]")
    console.print(result2.final_output)
    console.print(f"\n[dim]Sandbox session ID: {sandbox_state.wasm_session_id}[/dim]\n")

    # Turn 3: Final verification (still same sandbox_state)
    console.print("\n[bold cyan]Turn 3: Verify Persistence[/bold cyan]\n")
    prompt3 = "Read /app/users.json one more time and show me the final content."
    console.print(f"User: {prompt3}\n")

    result3 = await Runner.run(
        stateful_agent,
        input=prompt3,
        session=agent_session,
        context=sandbox_state,  # Same state = files still there!
    )
    console.print("[bold green]Agent:[/bold green]")
    console.print(result3.final_output)
    console.print(f"\n[dim]Sandbox session ID: {sandbox_state.wasm_session_id}[/dim]\n")

    # Cleanup
    await agent_session.clear_session()
    if sandbox_state.wasm_session_id:
        with contextlib.suppress(Exception):
            delete_session_workspace(sandbox_state.wasm_session_id)


async def demo_error_recovery_syntax():
    """Demo: Agent recovers from syntax error."""
    console.print(
        Panel(
            "Demo 2: Error Recovery - Syntax Error",
            style="bold blue",
            expand=False,
        )
    )

    console.print("\n[bold cyan]Scenario: Agent will initially write buggy code[/bold cyan]\n")

    agent_session = SQLiteSession("demo2_error_recovery")
    sandbox_state = SandboxState()

    prompt = (
        "Write Python code that creates a list of squares [1, 4, 9, 16, 25] "
        "and calculates their sum. Make sure to run it in the sandbox."
    )
    console.print(f"User: {prompt}\n")

    # Inject a deliberate syntax error instruction to demonstrate recovery
    error_prompt = (
        f"{prompt}\n\n"
        "SYSTEM NOTE (for demo): In your first attempt, intentionally make a small "
        "syntax error (like forgetting a colon or parenthesis). Then when you see the "
        "stderr, fix it and retry."
    )

    result = await Runner.run(
        stateful_agent, input=error_prompt, session=agent_session, context=sandbox_state
    )
    console.print("[bold green]Agent (with error recovery):[/bold green]")
    console.print(result.final_output)
    console.print()

    # Cleanup
    await agent_session.clear_session()
    if sandbox_state.wasm_session_id:
        with contextlib.suppress(Exception):
            delete_session_workspace(sandbox_state.wasm_session_id)


async def demo_error_recovery_fuel():
    """Demo: Agent handles fuel exhaustion by simplifying code."""
    console.print(
        Panel(
            "Demo 3: Error Recovery - Fuel Exhaustion",
            style="bold blue",
            expand=False,
        )
    )

    console.print("\n[bold cyan]Scenario: Agent simplifies code when fuel is exhausted[/bold cyan]\n")

    agent_session = SQLiteSession("demo3_fuel_recovery")
    sandbox_state = SandboxState()

    # This prompt encourages creating heavy computation
    prompt = (
        "Calculate the sum of all prime numbers between 1 and 100,000. "
        "If you hit a fuel limit, simplify your algorithm or reduce the range."
    )
    console.print(f"User: {prompt}\n")

    result = await Runner.run(
        stateful_agent, input=prompt, session=agent_session, context=sandbox_state
    )
    console.print("[bold green]Agent:[/bold green]")
    console.print(result.final_output)
    console.print()

    # Cleanup
    await agent_session.clear_session()
    if sandbox_state.wasm_session_id:
        with contextlib.suppress(Exception):
            delete_session_workspace(sandbox_state.wasm_session_id)


async def main():
    """Run all demos with cleanup."""
    console.print(
        Panel.fit(
            "[bold]OpenAI Agents SDK + LLM WASM Sandbox[/bold]\n"
            "Stateful Sessions with Error Recovery",
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
            "Run: .\\\\scripts\\\\fetch_wlr_python.ps1",
            style="yellow",
        )
        return

    try:
        await demo_multi_turn_session()
        await demo_error_recovery_syntax()
        await demo_error_recovery_fuel()

        console.print(
            Panel(
                "[bold green]✓[/bold green] All demos completed successfully!\n\n"
                "Key features demonstrated:\n"
                "  • Session-based file persistence\n"
                "  • Multi-turn stateful execution\n"
                "  • Automatic error recovery\n"
                "  • Fuel limit handling\n"
                "  • Security boundaries maintained",
                title="Demo Complete",
                style="green",
                expand=False,
            )
        )

        # Cleanup sessions
        console.print("\n[dim]Cleaning up demo sessions...[/dim]")
        workspace = Path("workspace")
        if workspace.exists():
            for session_dir in workspace.iterdir():
                if session_dir.is_dir() and session_dir.name not in [
                    ".gitkeep",
                    "site-packages",
                ]:
                    with contextlib.suppress(Exception):
                        delete_session_workspace(session_dir.name)

    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}", style="red")
        console.print("\n[dim]Check that:")
        console.print("  • OPENAI_API_KEY is valid")
        console.print("  • WASM binaries are downloaded")
        console.print("  • openai-agents is installed[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
