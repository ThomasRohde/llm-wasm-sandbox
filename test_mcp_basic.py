"""
Basic test for MCP server functionality.
"""

import asyncio
import pytest
from mcp_server.server import create_mcp_server


@pytest.mark.asyncio
async def test_server_creation():
    """Test that MCP server can be created."""
    server = create_mcp_server()
    assert server is not None
    assert server.config is not None
    assert server.app is not None


@pytest.mark.asyncio
async def test_stdio_transport():
    """Test stdio transport startup (will be interrupted)."""
    server = create_mcp_server()

    # Start server in background and cancel immediately
    task = asyncio.create_task(server.start_stdio())

    # Let it start
    await asyncio.sleep(0.1)

    # Cancel the task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass  # Expected


if __name__ == "__main__":
    asyncio.run(test_server_creation())
    print("Basic server test passed!")