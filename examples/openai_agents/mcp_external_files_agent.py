"""
OpenAI Agents SDK + llm-wasm-mcp: External Files Demo

This example demonstrates using the OpenAI Agents SDK with the llm-wasm-mcp
MCP server, showcasing the external files feature that mounts external files
read-only at /external/ in the sandbox.

The agent connects to the MCP server via stdio transport and can:
- Read external files mounted at /external/
- Process data from external sources
- Execute Python or JavaScript code securely
- Save processed results to /app/ for retrieval

Key Use Case - File Processing Pipeline:
    1. Read external input file from /external/
    2. Process/transform data in the WASM sandbox
    3. Save results to /app/output.json
    4. After agent run, harness retrieves and displays the file

Requirements:
    pip install -e ".[openai-example]"  # From repo root
    pip install openai-agents  # For MCP support (agents-sdk)

Setup:
    1. Copy .env.example to .env
    2. Add your OpenAI API key to .env
    3. Download WASM binaries: .\\scripts\\fetch_wlr_python.ps1

Run:
    python mcp_external_files_agent.py

This will:
    1. Create a sample external data file
    2. Start the MCP server with that file mounted at /external/
    3. Create an OpenAI agent that can read and process the file
    4. Run demo conversations including file processing pipeline
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Load environment variables
load_dotenv()

console = Console()


def check_dependencies() -> bool:
    """Check if required dependencies are available."""
    missing = []

    try:
        from agents import Agent, Runner  # noqa: F401
    except ImportError:
        missing.append("openai-agents (pip install openai-agents)")

    try:
        from agents.mcp import MCPServerStdio  # noqa: F401
    except ImportError:
        missing.append("agents with MCP support (pip install openai-agents)")

    if not os.getenv("OPENAI_API_KEY"):
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY not found in environment.\n"
            "Please copy .env.example to .env and add your API key.",
            style="red",
        )
        return False

    if missing:
        console.print("[bold red]Error:[/bold red] Missing dependencies:", style="red")
        for dep in missing:
            console.print(f"  - {dep}", style="red")
        console.print("\nInstall with: pip install openai-agents")
        return False

    # Check WASM binary
    python_wasm = Path(__file__).parent.parent.parent / "bin" / "python.wasm"
    if not python_wasm.exists():
        console.print(
            "[bold yellow]Warning:[/bold yellow] bin/python.wasm not found.\n"
            "Run from repo root: .\\scripts\\fetch_wlr_python.ps1",
            style="yellow",
        )
        return False

    return True


def create_sample_data_file(temp_dir: Path) -> Path:
    """Create a sample data file to be mounted as external file."""
    data_file = temp_dir / "sales_report.json"

    sample_data = {
        "report_date": "2025-01-15",
        "company": "ACME Corp",
        "quarterly_sales": [
            {"quarter": "Q1", "revenue": 125000, "units_sold": 542, "region": "North"},
            {"quarter": "Q1", "revenue": 98000, "units_sold": 421, "region": "South"},
            {"quarter": "Q2", "revenue": 147000, "units_sold": 612, "region": "North"},
            {"quarter": "Q2", "revenue": 112000, "units_sold": 489, "region": "South"},
            {"quarter": "Q3", "revenue": 163000, "units_sold": 701, "region": "North"},
            {"quarter": "Q3", "revenue": 128000, "units_sold": 556, "region": "South"},
            {"quarter": "Q4", "revenue": 189000, "units_sold": 823, "region": "North"},
            {"quarter": "Q4", "revenue": 145000, "units_sold": 634, "region": "South"},
        ],
        "products": ["Widget Pro", "Gadget Plus", "Super Tool"],
    }

    with data_file.open("w", encoding="utf-8") as f:
        json.dump(sample_data, f, indent=2)

    console.print(f"[green]Created sample data file:[/green] {data_file}")
    return data_file


async def run_mcp_agent_demo(external_file: Path) -> None:
    """Run the MCP agent demo with external file access."""
    # Import here after dependency check
    from agents import Agent, ModelSettings, Runner
    from agents.mcp import MCPServerStdio

    # Path to the llm-wasm-mcp command
    # When installed as a package, use the entry point directly
    # For development, we can also use: python -m mcp_server
    repo_root = Path(__file__).parent.parent.parent

    console.print(
        Panel(
            "[bold]OpenAI Agents SDK + llm-wasm-mcp Demo[/bold]\n\n"
            "This demo shows how to:\n"
            "  1. Start llm-wasm-mcp with external files mounted at /external/\n"
            "  2. Create an OpenAI agent with MCP server access\n"
            "  3. Have the agent read and process external data",
            style="bold blue",
        )
    )

    # MCP server command with external file
    # Use uv run to ensure correct environment when running from dev
    mcp_command = "llm-wasm-mcp"
    mcp_args = [
        "--external-files",
        str(external_file),
        "--max-external-file-size-mb",
        "10",
    ]

    # Check if we're in development mode (not installed as package)
    try:
        import importlib.util

        if importlib.util.find_spec("mcp_server") is not None:
            # We can use the module directly
            mcp_command = sys.executable
            mcp_args = ["-m", "mcp_server", *mcp_args]
    except Exception:
        pass

    console.print("\n[bold cyan]MCP Server Configuration:[/bold cyan]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Command:", f"[green]{mcp_command}[/green]")
    table.add_row("Arguments:", f"[green]{' '.join(mcp_args)}[/green]")
    table.add_row("External File:", f"[green]{external_file.name}[/green]")
    table.add_row("Mount Point:", "[green]/external/[/green]")
    console.print(table)
    console.print()

    # Start MCP server with external file mounted
    console.print("[bold]Starting MCP server...[/bold]")

    async with MCPServerStdio(
        name="llm-wasm-sandbox",
        params={
            "command": mcp_command,
            "args": mcp_args,
            "cwd": str(repo_root),  # Run from repo root so it finds bin/python.wasm
        },
        client_session_timeout_seconds=60.0,  # WASM execution can take time
    ) as mcp_server:
        console.print("[green]✓ MCP server started successfully[/green]\n")

        # List available tools from the MCP server
        tools = await mcp_server.list_tools()
        console.print("[bold cyan]Available MCP Tools:[/bold cyan]")
        for tool in tools:
            console.print(f"  • [yellow]{tool.name}[/yellow]: {tool.description[:60]}...")
        console.print()

        # Create agent with MCP server
        agent = Agent(
            name="Data Analysis Agent",
            instructions=(
                "You are a data analysis assistant with access to a secure WASM sandbox.\n\n"
                "IMPORTANT - EXTERNAL FILES:\n"
                "External files are mounted READ-ONLY at /external/ in the sandbox.\n"
                "- To list external files: import os; print(os.listdir('/external/'))\n"
                "- To read a file: open('/external/filename.json', 'r').read()\n"
                "- These files are READ-ONLY - you cannot modify them\n\n"
                "You can also write files to /app/ for processing.\n\n"
                "WORKFLOW:\n"
                "1. First, explore what external files are available\n"
                "2. Read and analyze the data as requested\n"
                "3. Present results clearly with summaries\n\n"
                "Use the execute_code tool with language='python' to run code."
            ),
            model="gpt-4.1",
            model_settings=ModelSettings(
                temperature=0.1,
            ),
            mcp_servers=[mcp_server],
        )

        # Demo prompt
        prompt = (
            "Please analyze the external sales report file:\n"
            "1. First, list what files are available in /external/\n"
            "2. Read the sales_report.json file from /external/\n"
            "3. Calculate total revenue by region\n"
            "4. Find the best performing quarter\n"
            "5. Summarize the key findings"
        )

        console.print("[bold cyan]User Prompt:[/bold cyan]")
        console.print(Panel(prompt, style="cyan"))
        console.print()

        console.print("[bold]Agent Processing...[/bold]")
        console.print("(The agent will call MCP tools to execute code in the WASM sandbox)\n")

        # Run the agent
        result = await Runner.run(
            agent,
            input=prompt,
            max_turns=10,
        )

        console.print("\n[bold green]Agent Response:[/bold green]")
        console.print(Panel(result.final_output, style="green"))


async def demo_file_processing_pipeline(external_file: Path) -> None:
    """
    Demo: Read external file → Process in sandbox → Save result → Retrieve file.

    This demonstrates the complete workflow:
    1. Agent reads external data from /external/
    2. Agent processes/transforms the data in the WASM sandbox
    3. Agent saves the processed result to /app/
    4. After the agent run, harness retrieves the file and prints it
    """
    from agents import Agent, ModelSettings, Runner
    from agents.mcp import MCPServerStdio

    console.print(
        Panel(
            "[bold]File Processing Pipeline Demo[/bold]\n\n"
            "This demo shows the complete workflow:\n"
            "  1. Agent reads external data from /external/\n"
            "  2. Agent processes the data in the WASM sandbox\n"
            "  3. Agent saves transformed result to /app/\n"
            "  4. Harness retrieves and displays the processed file",
            style="bold magenta",
        )
    )

    repo_root = Path(__file__).parent.parent.parent
    mcp_command = sys.executable
    mcp_args = ["-m", "mcp_server", "--external-files", str(external_file)]

    async with MCPServerStdio(
        name="llm-wasm-sandbox",
        params={"command": mcp_command, "args": mcp_args, "cwd": str(repo_root)},
        client_session_timeout_seconds=60.0,  # WASM execution can take time
    ) as mcp_server:
        # First, create a session so we can retrieve files later
        console.print("\n[bold]Step 1: Creating sandbox session...[/bold]")

        # Call create_session tool to get a session_id
        create_session_result = await mcp_server.call_tool("create_session", {"language": "python"})

        # Parse session_id from structured content or text content
        # The MCP result has a nested structure: structuredContent["structured_content"]["session_id"]
        if create_session_result.structuredContent:
            inner_content = create_session_result.structuredContent.get("structured_content", {})
            session_id = inner_content.get("session_id")
            if not session_id:
                # Try top-level (in case structure changes)
                session_id = create_session_result.structuredContent.get("session_id")
        else:
            # Fallback: parse from text content (which is JSON)
            text_content = create_session_result.content[0].text
            parsed = json.loads(text_content)
            session_id = parsed.get("structured_content", {}).get("session_id")

        if not session_id:
            raise ValueError("Could not parse session_id from result")
        console.print(f"[green]✓ Session created: {session_id}[/green]\n")

        # Create agent with specific instructions for file processing
        agent = Agent(
            name="Data Processing Agent",
            instructions=(
                "You are a data processing assistant with access to a secure WASM sandbox.\n\n"
                "IMPORTANT INSTRUCTIONS:\n"
                "1. External files are at /external/ (READ-ONLY)\n"
                "2. You can write output files to /app/\n"
                "3. You MUST use the provided session_id for all execute_code calls\n\n"
                "YOUR TASK:\n"
                "- Read the input data from /external/\n"
                "- Transform it into an analysis report\n"
                "- Save the report as JSON to /app/analysis_report.json\n"
                "- The report should include calculated metrics and summaries\n\n"
                f"CRITICAL: Use session_id='{session_id}' in all execute_code calls!"
            ),
            model="gpt-4.1",
            model_settings=ModelSettings(temperature=0.0),
            mcp_servers=[mcp_server],
        )

        # Prompt for file processing
        prompt = (
            f"Process the sales data with session_id='{session_id}':\n\n"
            "1. Read /external/sales_report.json\n"
            "2. Calculate these metrics:\n"
            "   - Total revenue (all regions, all quarters)\n"
            "   - Revenue by region (North vs South)\n"
            "   - Revenue by quarter (Q1-Q4)\n"
            "   - Best and worst performing quarter\n"
            "   - Average revenue per quarter\n"
            "3. Create a structured analysis report as JSON\n"
            "4. Save it to /app/analysis_report.json\n"
            "5. Print confirmation that the file was saved\n\n"
            f"Remember: Use session_id='{session_id}' in execute_code!"
        )

        console.print("[bold]Step 2: Agent processing data...[/bold]")
        console.print("[bold cyan]User Prompt:[/bold cyan]")
        console.print(Panel(prompt, style="cyan"))
        console.print()

        # Run the agent
        result = await Runner.run(agent, input=prompt, max_turns=10)

        console.print("\n[bold green]Agent Response:[/bold green]")
        console.print(Panel(result.final_output, style="green"))

        # Step 3: Retrieve the processed file from the sandbox
        console.print("\n[bold]Step 3: Retrieving processed file from sandbox...[/bold]")

        # Use execute_code to read the file content
        read_result = await mcp_server.call_tool(
            "execute_code",
            {
                "code": "print(open('/app/analysis_report.json').read())",
                "language": "python",
                "session_id": session_id,
            },
        )

        # Parse the result - the MCP result has nested structure
        # structuredContent["structured_content"]["stdout"] contains the actual output
        if read_result.structuredContent:
            inner = read_result.structuredContent.get("structured_content", {})
            execution_result = {
                "success": inner.get("success", read_result.structuredContent.get("success")),
                "stdout": inner.get("stdout", ""),
                "stderr": inner.get("stderr", ""),
            }
        else:
            parsed = json.loads(read_result.content[0].text)
            inner = parsed.get("structured_content", parsed)
            execution_result = {
                "success": inner.get("success", parsed.get("success")),
                "stdout": inner.get("stdout", parsed.get("content", "")),
                "stderr": inner.get("stderr", ""),
            }

        if execution_result.get("success"):
            file_content = execution_result.get("stdout", "").strip()

            console.print("\n[bold magenta]═══ PROCESSED FILE OUTPUT ═══[/bold magenta]")
            console.print("[dim]File: /app/analysis_report.json[/dim]\n")

            # Pretty-print the JSON
            try:
                parsed_json = json.loads(file_content)
                console.print_json(data=parsed_json)
            except json.JSONDecodeError:
                console.print(file_content)

            console.print("\n[bold magenta]═══════════════════════════════[/bold magenta]")

            # Show summary
            console.print("\n[bold green]✓ File processing pipeline complete![/bold green]")
            console.print("[dim]The harness successfully retrieved the agent's output file.[/dim]")
        else:
            console.print(f"[red]Failed to read file: {execution_result.get('stderr')}[/red]")

        # Clean up session
        await mcp_server.call_tool("destroy_session", {"session_id": session_id})
        console.print(f"\n[dim]Session {session_id} destroyed.[/dim]")


async def demo_read_only_protection(external_file: Path) -> None:
    """Demo that shows external files are read-only."""
    from agents import Agent, ModelSettings, Runner
    from agents.mcp import MCPServerStdio

    console.print(
        Panel(
            "[bold]Read-Only Protection Demo[/bold]\n\n"
            "This demo verifies that external files cannot be modified.\n"
            "The agent will attempt to write to /external/ and should fail.",
            style="bold yellow",
        )
    )

    # MCP server command
    repo_root = Path(__file__).parent.parent.parent
    mcp_command = sys.executable
    mcp_args = ["-m", "mcp_server", "--external-files", str(external_file)]

    async with MCPServerStdio(
        name="llm-wasm-sandbox",
        params={"command": mcp_command, "args": mcp_args, "cwd": str(repo_root)},
        client_session_timeout_seconds=60.0,  # WASM execution can take time
    ) as mcp_server:
        agent = Agent(
            name="Security Test Agent",
            instructions=(
                "You are a security testing assistant.\n"
                "Your job is to verify that /external/ files are read-only.\n"
                "Try to write to /external/ and report what happens."
            ),
            model="gpt-4.1",
            model_settings=ModelSettings(temperature=0.0),
            mcp_servers=[mcp_server],
        )

        prompt = (
            "Please verify read-only protection:\n"
            "1. Try to create a new file at /external/test.txt\n"
            "2. Try to modify /external/sales_report.json\n"
            "3. Report the error messages you encounter\n"
            "This should fail - we're testing security!"
        )

        console.print("[bold cyan]Test Prompt:[/bold cyan]")
        console.print(Panel(prompt, style="cyan"))

        result = await Runner.run(agent, input=prompt, max_turns=5)

        console.print("\n[bold yellow]Security Test Result:[/bold yellow]")
        console.print(Panel(result.final_output, style="yellow"))


async def main() -> None:
    """Main entry point."""
    console.print(
        Panel.fit(
            "[bold]OpenAI Agents + llm-wasm-mcp External Files Demo[/bold]",
            style="bold white on blue",
        )
    )
    console.print()

    # Check dependencies
    if not check_dependencies():
        return

    # Create temporary directory with sample data
    with tempfile.TemporaryDirectory(prefix="mcp_demo_") as temp_dir:
        temp_path = Path(temp_dir)

        # Create sample data file
        external_file = create_sample_data_file(temp_path)
        console.print()

        try:
            # Run main demo
            await run_mcp_agent_demo(external_file)

            console.print("\n" + "=" * 60 + "\n")

            # File processing pipeline demo (the important use case!)
            console.print("[bold]Run file processing pipeline demo? (y/n):[/bold] ", end="")
            response = input().strip().lower()
            if response == "y":
                await demo_file_processing_pipeline(external_file)
                console.print("\n" + "=" * 60 + "\n")

            # Optional: Run read-only protection demo
            console.print("[bold]Run read-only protection demo? (y/n):[/bold] ", end="")
            response = input().strip().lower()
            if response == "y":
                await demo_read_only_protection(external_file)

        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}", style="red")
            import traceback

            console.print(traceback.format_exc(), style="dim")

            console.print("\n[dim]Troubleshooting:[/dim]")
            console.print("[dim]  • Ensure OPENAI_API_KEY is valid[/dim]")
            console.print("[dim]  • Ensure WASM binaries are downloaded[/dim]")
            console.print("[dim]  • Ensure openai-agents is installed[/dim]")
            console.print("[dim]  • Check that llm-wasm-mcp can start[/dim]")
            return

    console.print(
        Panel(
            "[bold green]✓ Demo completed successfully![/bold green]\n\n"
            "This demonstrated:\n"
            "  • MCPServerStdio connecting to llm-wasm-mcp\n"
            "  • External files mounted at /external/ (read-only)\n"
            "  • Agent reading and analyzing external data\n"
            "  • Secure WASM sandbox execution via MCP\n\n"
            "For production use, consider:\n"
            "  • Using --storage-dir for persistent file storage\n"
            "  • Setting appropriate --max-external-file-size-mb limits\n"
            "  • Configuring Claude Desktop with external files",
            title="Demo Complete",
            style="green",
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
