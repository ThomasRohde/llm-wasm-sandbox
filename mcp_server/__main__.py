#!/usr/bin/env python3
"""
MCP Server CLI for LLM WASM Sandbox.

Command-line interface to run the MCP server with promiscuous security
(all code allowed - security relies on WASM sandbox boundaries).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
import warnings
from pathlib import Path
from typing import Any, ClassVar

from .config import MCPConfig
from .security import SecurityValidator
from .server import create_mcp_server
from .sessions import stage_external_files

# Suppress python-dotenv warnings when it's installed as a transitive dependency
# (e.g., from openai-example extras) but not actually used by the MCP server
warnings.filterwarnings("ignore", message="Python-dotenv could not parse statement.*")
warnings.filterwarnings("ignore", message="python-dotenv could not parse statement.*")

# Get version from pyproject.toml
try:
    import importlib.metadata

    __version__ = importlib.metadata.version("llm-wasm-sandbox")
except Exception:
    __version__ = "unknown"


class ProtocolFilterIO:
    """
    A smart wrapper for stdout that directs JSON-RPC messages to real stdout
    and everything else (banners, logs) to stderr.

    This prevents FastMCP's ASCII art banner from breaking the MCP protocol.
    """

    def __init__(self, original_stdout: Any, stderr: Any) -> None:
        self.original_stdout = original_stdout
        self.stderr = stderr
        # Expose the underlying buffer for binary I/O operations
        self.buffer = original_stdout.buffer if hasattr(original_stdout, "buffer") else None

    def write(self, message: str) -> int:
        # Heuristic: MCP JSON-RPC messages are JSON objects starting with '{'
        # Redirect banners and logs to stderr, JSON-RPC to stdout
        try:
            if message.strip().startswith("{"):
                self.original_stdout.write(message)
                self.original_stdout.flush()
            else:
                self.stderr.write(message)
                self.stderr.flush()
        except ValueError:
            # Handle closed file during shutdown - silently ignore
            pass
        return len(message)

    def flush(self) -> None:
        with contextlib.suppress(ValueError):
            # Handle closed file during shutdown
            self.original_stdout.flush()
        with contextlib.suppress(ValueError):
            # Handle closed file during shutdown
            self.stderr.flush()

    def isatty(self) -> bool:
        return bool(self.original_stdout.isatty())

    def __getattr__(self, name: str) -> Any:
        # Proxy any other attributes to the original stdout
        return getattr(self.original_stdout, name)


class PromiscuousSecurityValidator(SecurityValidator):
    """
    Promiscuous security validator - ALLOWS EVERYTHING.

    WARNING: This validator disables all security checks.
    Use only in trusted environments where the WASM sandbox
    provides the primary security boundary.
    """

    # No patterns blocked - allow everything
    DANGEROUS_CODE_PATTERNS: ClassVar[list[str]] = []

    # No packages blocked - allow everything
    DANGEROUS_PACKAGES: ClassVar[set[str]] = set()

    @classmethod
    def _validate_javascript_code(cls, code: str) -> tuple[bool, str]:
        """
        Validate JavaScript code - ALLOWS EVERYTHING.

        All JavaScript code is permitted. Security relies entirely
        on the WASM sandbox boundaries.
        """
        return True, ""


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="llm-wasm-mcp",
        description="LLM WASM Sandbox MCP Server - Secure code execution via Model Context Protocol",
    )
    parser.add_argument(
        "--external-files",
        nargs="*",
        default=[],
        metavar="FILE",
        help="External files to copy to ./storage and mount read-only at /external in sessions. "
        "Files are copied flat (no subdirectory structure). All filenames must be unique.",
    )
    parser.add_argument(
        "--max-external-file-size-mb",
        type=int,
        default=50,
        metavar="MB",
        help="Maximum size in MB for each external file (default: 50)",
    )
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=Path("./storage"),
        metavar="DIR",
        help="Directory to copy external files into (default: ./storage)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args()


async def async_main(
    external_files: list[str],
    max_external_file_size_mb: int,
    storage_dir: Path,
) -> None:
    """Async main entry point with proper signal handling."""
    # Monkey-patch the security module to use promiscuous validator
    import mcp_server.security
    import mcp_server.server

    mcp_server.security.SecurityValidator = PromiscuousSecurityValidator  # type: ignore[misc]
    mcp_server.server.SecurityValidator = PromiscuousSecurityValidator  # type: ignore[misc]

    # Stage external files if provided
    external_mount_dir: Path | None = None
    if external_files:
        print(f"Staging {len(external_files)} external files to {storage_dir}...", file=sys.stderr)
        try:
            external_mount_dir = stage_external_files(
                file_paths=external_files,
                storage_dir=storage_dir,
                max_size_mb=max_external_file_size_mb,
            )
            print(f"External files staged at {external_mount_dir}", file=sys.stderr)
            print("Files will be available at /external/ in sessions", file=sys.stderr)
        except (FileNotFoundError, ValueError, IsADirectoryError) as e:
            print(f"ERROR: Failed to stage external files: {e}", file=sys.stderr)
            sys.exit(1)

    config = MCPConfig()
    server = create_mcp_server(config, external_mount_dir=external_mount_dir)

    print("Available tools: execute_code, list_runtimes, create_session, etc.", file=sys.stderr)

    try:
        await server.start_stdio()
    except asyncio.CancelledError:
        print("\nShutting down MCP server...", file=sys.stderr)
    except Exception as e:
        print(f"MCP server error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await server.shutdown()


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()

    print(f"LLM WASM Sandbox MCP Server v{__version__}", file=sys.stderr)
    print("Starting MCP server with PROMISCUOUS security (ALL CODE ALLOWED)...", file=sys.stderr)
    print("WARNING: All security filters disabled!", file=sys.stderr)
    print("Security relies entirely on WASM sandbox boundaries.", file=sys.stderr)

    if args.external_files:
        print(
            f"External files: {len(args.external_files)} file(s) will be mounted at /external/",
            file=sys.stderr,
        )

    print("", file=sys.stderr)

    # Install the smart stdout filter to redirect banners to stderr
    # while preserving JSON-RPC messages on stdout
    original_stdout = sys.stdout
    sys.stdout = ProtocolFilterIO(original_stdout, sys.stderr)

    try:
        asyncio.run(
            async_main(
                external_files=args.external_files,
                max_external_file_size_mb=args.max_external_file_size_mb,
                storage_dir=args.storage_dir,
            )
        )
    except KeyboardInterrupt:
        print("\nGraceful shutdown complete.", file=sys.stderr)


if __name__ == "__main__":
    main()
