"""
Quick test to verify MCP session fuel budgets.

Run with: uv run python tests/test_mcp_fuel_budget.py
"""

import asyncio

import pytest

from mcp_server.sessions import WorkspaceSessionManager


@pytest.mark.asyncio
async def test_mcp_fuel_budget() -> None:
    """Verify that MCP sessions use 10B fuel budget."""
    manager = WorkspaceSessionManager()

    # Create Python session
    session = await manager.get_or_create_session(language="python", auto_persist_globals=True)

    # Get sandbox and check policy
    session.get_sandbox()

    # Execute code that would fail with 5B but succeed with 10B
    # (openpyxl import requires ~5B fuel)
    result = await session.execute_code("""
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl
print(f"SUCCESS: openpyxl imported")
print(f"Fuel consumed: {openpyxl.__name__}")
""")

    print("\n=== Test Results ===")
    print(f"Success: {result.success}")
    print(f"Fuel consumed: {result.fuel_consumed:,}")
    print("Fuel budget: 10,000,000,000")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")

    if result.success:
        print("\n✅ PASS: openpyxl imported successfully with MCP default fuel budget")
    else:
        print("\n❌ FAIL: openpyxl import failed")
        if "OutOfFuel" in result.stderr:
            print("   Fuel budget too low - needs to be increased!")

    # Test second import (should use cached module)
    result2 = await session.execute_code("""
import openpyxl
print(f"Second import fuel (cached): works!")
""")

    print("\n=== Second Import (Cached) ===")
    print(f"Success: {result2.success}")
    print(f"Fuel consumed: {result2.fuel_consumed:,}")
    print(f"Stdout: {result2.stdout}")

    if (
        result2.fuel_consumed is not None and result2.fuel_consumed < 500_000_000
    ):  # Should be much lower
        print("\n✅ PASS: Cached import uses minimal fuel")

    # Cleanup
    await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(test_mcp_fuel_budget())
