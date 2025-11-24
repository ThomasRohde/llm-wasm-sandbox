"""Test that MCP list_available_packages tool uses correct path.

Verifies the fix for the bug report where the tool was instructing users
to use /app/site-packages instead of the correct /data/site-packages path.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path to import local mcp_server
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.server import create_mcp_server  # noqa: E402


async def test():
    """Test MCP tool returns correct path."""
    server = create_mcp_server()
    result = await server.app._tool_manager.call_tool("list_available_packages", {})
    content = result.content[0].text

    # Verify CORRECT path is documented
    assert (
        "/data/site-packages" in content
    ), "Missing correct path /data/site-packages in MCP tool response"

    # Verify WRONG path is NOT in response
    assert (
        "/app/site-packages" not in content
    ), "Found incorrect path /app/site-packages in MCP tool response"

    print("✅ MCP list_available_packages tool uses correct path")


if __name__ == "__main__":
    asyncio.run(test())
