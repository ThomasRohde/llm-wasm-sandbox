"""
MCP Server for LLM WASM Sandbox.

This module implements a Model Context Protocol (MCP) server that exposes
the sandbox's secure code execution capabilities to MCP clients.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel

from sandbox.core.logging import SandboxLogger

from .audit import AuditLogger
from .config import MCPConfig
from .metrics import MCPMetricsCollector
from .rate_limiter import RateLimitConfig, RateLimiter
from .security import SecurityValidator
from .sessions import WorkspaceSessionManager
from .transports import HTTPTransportConfig


class MCPToolResult(BaseModel):
    """Result from an MCP tool execution."""

    content: str
    structured_content: dict[str, Any] | None = None
    execution_time_ms: float | None = None
    success: bool = True


class MCPServer:
    """
    MCP Server for secure code execution.

    Provides MCP tools for executing Python and JavaScript code in a
    WebAssembly sandbox with automatic session management.
    """

    def __init__(
        self,
        config: MCPConfig | None = None,
        external_mount_dir: Path | None = None,
    ):
        self.config = config or MCPConfig()
        self.logger = SandboxLogger()
        self.audit_logger = AuditLogger()
        self.session_manager = WorkspaceSessionManager(
            external_mount_dir=external_mount_dir,
            timeout_seconds=self.config.sessions.default_timeout_seconds,
            max_total_sessions=self.config.sessions.max_total_sessions,
            memory_limit_mb=self.config.sessions.max_memory_mb,
        )
        self.metrics = MCPMetricsCollector()
        self._external_mount_dir = external_mount_dir

        # Initialize rate limiter
        rate_limit_config = RateLimitConfig(
            requests_per_window=self.config.transport_http.rate_limit_requests,
            window_seconds=self.config.transport_http.rate_limit_window_seconds,
        )
        self.rate_limiter = RateLimiter(rate_limit_config)

        # Initialize FastMCP app with lifespan for background task management
        # FastMCP expects Callable[[FastMCP], AsyncContextManager], so we wrap _lifespan
        self.app = FastMCP(
            name=self.config.server.name,
            version=self.config.server.version,
            instructions=self.config.server.instructions,
            lifespan=lambda _mcp: self._lifespan(),
        )

        # Register tools
        self._register_tools()

        log_extra: dict[str, Any] = {"config": self.config.model_dump()}
        if external_mount_dir:
            log_extra["external_mount_dir"] = str(external_mount_dir)
        self.logger._emit(logging.INFO, "MCP server initialized", **log_extra)

    async def _check_rate_limit(self, client_key: str = "default") -> bool:
        """Check rate limit for a client."""
        allowed, retry_after = await self.rate_limiter.check_rate_limit(client_key)
        if not allowed:
            client_stats = self.rate_limiter.get_client_stats(client_key) or {}
            self.audit_logger.log_rate_limit_violation(
                client_id=client_key,
                request_count=client_stats.get("requests_in_window", 0),
                limit=self.rate_limiter.config.requests_per_window,
                window_seconds=self.rate_limiter.config.window_seconds,
                blocked_duration=retry_after,
            )
            self.logger._emit(
                logging.WARNING,
                "mcp.rate_limit.blocked",
                client_key=client_key,
                retry_after=retry_after,
            )
        return allowed

    # System file names that should be filtered from workspace listings
    _SYSTEM_FILES = frozenset(
        {
            ".metadata.json",  # Session metadata
            "user_code.py",  # Temporary Python execution file
            "user_code.js",  # Temporary JavaScript execution file
            "__state__.json",  # Auto-persist state file
        }
    )
    # System directory prefixes that should be filtered
    _SYSTEM_DIR_PREFIXES = ("site-packages/", "__pycache__/")

    @staticmethod
    def _filter_system_files(files: list[str]) -> tuple[list[str], list[str]]:
        """Filter files into client files and system files.

        System files are internal sandbox artifacts that should normally be hidden
        from MCP clients. Client files are user-created data files.

        Args:
            files: List of file paths (relative to workspace root)

        Returns:
            Tuple of (client_files, system_files)
        """
        client_files: list[str] = []
        system_files: list[str] = []

        for f in files:
            # Normalize path to POSIX format for consistent filtering across platforms
            normalized = f.replace("\\", "/")
            # Check if it's a system file by name or in a system directory
            filename = normalized.split("/")[-1] if "/" in normalized else normalized
            is_system = filename in MCPServer._SYSTEM_FILES or any(
                normalized.startswith(prefix) for prefix in MCPServer._SYSTEM_DIR_PREFIXES
            )
            if is_system:
                system_files.append(f)
            else:
                client_files.append(f)

        return client_files, system_files

    def _register_tools(self) -> None:
        """Register all MCP tools."""

        @self.app.tool(
            name="execute_code",
            description="""Execute code in a secure WebAssembly sandbox. Supports Python and JavaScript.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ⚙️ WHEN TO USE THIS TOOL:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ✅ Data processing and analysis (CSV, JSON, Excel, PDF parsing)
            ✅ File manipulation (read, write, transform files in /app directory)
            ✅ Mathematical computations and algorithms
            ✅ Text processing (parsing, formatting, templates)
            ✅ One-off calculations or code snippets
            ✅ Stateful workflows (counter, accumulator patterns with sessions)

            ❌ DO NOT USE FOR:
            - Network operations (HTTP requests, API calls) - not supported in WASI
            - Long-running servers/daemons - execution times out
            - Operations requiring system resources outside /app directory
            - Package installation (pip/npm) - use pre-installed packages only

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            🐍 PYTHON RUNTIME (CPython 3.12 in WASM):
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            📦 Pre-installed Packages (30+, no pip install needed):
               • Document processing: openpyxl, XlsxWriter, PyPDF2, mammoth, odfpy
               • Text/data: tabulate, jinja2, markdown, python-dateutil
               • Full standard library: json, csv, pathlib, re, math, statistics, etc.

            💡 Usage Pattern:
               import openpyxl  # Works automatically, no sys.path needed
               from tabulate import tabulate
               # Process data, read/write files in /app directory

            ⚠️ Common Pitfalls:
               • Fuel limits: Heavy packages (openpyxl, PyPDF2, jinja2) require 10B fuel
                 for FIRST import. Use create_session with custom policy or increase budget.
               • Path restrictions: All file operations MUST use /app/ prefix
                 Example: open('/app/data.csv') ✅  |  open('data.csv') ❌
               • C extensions: python-pptx, Pillow, lxml.etree NOT supported (use alternatives)
               • Import caching: First import expensive, subsequent imports fast (use sessions!)

            🔄 State Persistence (when auto_persist_globals=True in session):
               • All global variables automatically saved between executions
               • Example: counter = globals().get('counter', 0) + 1  # Persists across runs

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            🟨 JAVASCRIPT RUNTIME (QuickJS ES2023 in WASM):
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            📦 Built-in Capabilities:
               • QuickJS std module: File I/O (std.open, std.loadFile, std.writeFile)
               • QuickJS os module: Filesystem ops (os.readdir, os.stat, os.now, os.remove)
               • Global helpers (auto-injected): readJson(), writeJson(), readText(),
                 writeText(), listFiles(), fileExists(), copyFile(), etc.
               • Vendored packages: csv-simple, json-utils, string-utils
                 Usage: const csv = requireVendor('csv-simple'); csv.parse(data);

            💡 Usage Pattern:
               // Option 1: Use global helpers (recommended for simple cases)
               const data = readJson('/app/config.json');
               writeText('/app/output.txt', 'result');

               // Option 2: Use QuickJS std/os globals for advanced I/O
               // Note: std and os are global objects (via --std flag), NOT ES6 modules
               const file = std.open('/app/data.csv', 'r');
               const content = file.readAsString();
               file.close();

            ⚠️ Common Pitfalls:
               • Tuple returns: QuickJS functions return tuples as [value, error]
                 WRONG: const data = readJson('/app/file.json');  // TypeError if destructured
                 RIGHT: const data = readJson('/app/file.json'); if (data) { use(data); }

               • Path restrictions: All file operations MUST use /app/ prefix
                 Example: readText('/app/data.txt') ✅  |  readText('data.txt') ❌

               • No Node.js APIs: fs, http, child_process, etc. NOT available
                 Use QuickJS std/os globals or auto-injected helpers instead

               • std/os are globals: Access via std.open(), os.readdir() directly
                 (NOT import * as std from 'std' - ES6 module imports don't work)

            🔄 State Persistence (when auto_persist_globals=True in session):
               • Use _state object to persist data between executions
               • Example: _state.counter = (_state.counter || 0) + 1;  // Persists across runs
               • _state is automatically saved/restored per session

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            📋 USAGE PATTERNS:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            1️⃣ One-off Calculation (no session needed):
               execute_code(code="print(2 + 2)", language="python")

            2️⃣ File Processing (single execution):
               execute_code(code="data = readJson('/app/input.json'); ...", language="javascript")

            3️⃣ Stateful Workflow (requires session with auto_persist_globals=True):
               # First, create session:
               create_session(language="python", auto_persist_globals=True)
               # Then execute with state:
               execute_code(code="counter = globals().get('counter', 0) + 1; print(counter)",
                          session_id=<session_id>)

            4️⃣ Heavy Package Usage (requires custom fuel budget):
               # Create session with high fuel budget for openpyxl/PyPDF2:
               create_session(language="python", session_id="excel-processor")
               # Note: Use ExecutionPolicy(fuel_budget=10_000_000_000) at library level
               execute_code(code="import openpyxl; ...", session_id="excel-processor")

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ⚙️ PARAMETERS:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            • code (str): Code to execute. Remember to use /app/ prefix for all file paths!
            • language (str): "python" or "javascript"
            • timeout (int|None): Execution timeout in seconds (optional, defaults from policy)
            • session_id (str|None): Session ID for persistent state/imports (optional)
              - Omit for one-off executions (new temporary session created)
              - Provide to reuse existing session (preserves imports, state, files)
              - Use create_session first for custom configuration (fuel, auto_persist)

            Returns: {stdout, stderr, exit_code, execution_time_ms, fuel_consumed, success}
            """,
        )
        async def execute_code(
            code: str,
            language: str,
            timeout: int | None = None,
            session_id: str | None = None,
        ) -> MCPToolResult:
            """Execute code with automatic session management."""
            # Check rate limit
            if not await self._check_rate_limit(session_id or "anonymous"):
                return MCPToolResult(
                    content="Rate limit exceeded. Please try again later.",
                    success=False,
                )

            with self.metrics.time_tool_execution("execute_code"):
                try:
                    # Validate inputs
                    is_valid, error_msg = SecurityValidator.validate_code_input(code, language)
                    if not is_valid:
                        self.audit_logger.log_security_violation(
                            violation_type="invalid_code_input",
                            client_id=session_id or "anonymous",
                            details={"language": language, "error": error_msg},
                            severity="high",
                        )
                        return MCPToolResult(
                            content=f"Input validation failed: {error_msg}",
                            success=False,
                        )

                    # Validate timeout
                    timeout_valid, timeout_value = SecurityValidator.validate_timeout(timeout)
                    if not timeout_valid:
                        return MCPToolResult(
                            content="Invalid timeout value",
                            success=False,
                        )

                    # Validate language
                    if language not in ["python", "javascript"]:
                        return MCPToolResult(
                            content=f"Unsupported language: {language}. Supported: python, javascript",
                            success=False,
                        )

                    # Get or create session
                    session_result = await self.session_manager.get_or_create_session(
                        language=language, session_id=session_id
                    )

                    # Check if session limit was exceeded (returns dict with error)
                    if isinstance(session_result, dict) and "error" in session_result:
                        return MCPToolResult(
                            content=str(session_result.get("message", "Session limit exceeded")),
                            structured_content=session_result,
                            success=False,
                        )

                    session = session_result
                    # Type narrowing: session is WorkspaceSession here
                    assert not isinstance(session, dict)

                    # Execute code
                    result = await session.execute_code(code, timeout=timeout_value)

                    # Record resource usage
                    self.metrics.record_resource_usage(
                        result.fuel_consumed or 0,
                        result.duration_ms / 1000,
                        result.memory_used_bytes,
                    )

                    # Audit log successful execution
                    self.audit_logger.log_tool_execution(
                        tool_name="execute_code",
                        client_id=session_id or "anonymous",
                        session_id=session_id,
                        success=result.success,
                        execution_time_ms=result.duration_ms,
                        fuel_consumed=result.fuel_consumed or 0,
                        language=language,
                    )

                    # Build structured content with error guidance if available
                    structured_content = {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_code,
                        "execution_time_ms": result.duration_ms,
                        "fuel_consumed": result.fuel_consumed,
                        "success": result.success,
                    }

                    # Add files_changed to structured content
                    # Combine files_created and files_modified, deduplicate, and filter system files
                    all_changed_files = list(
                        dict.fromkeys(result.files_created + result.files_modified)
                    )
                    client_files, _ = self._filter_system_files(all_changed_files)

                    # Build structured file objects with absolute/relative/filename
                    # TODO: Consider moving workspace root resolution to MCPConfig
                    workspace_root = Path(result.workspace_path)
                    cwd = Path.cwd()
                    files_changed: list[dict[str, str]] = []
                    for rel_path in client_files:
                        # rel_path is like "data.csv" or "subdir/file.txt"
                        filename = rel_path.split("/")[-1] if "/" in rel_path else rel_path
                        abs_path = workspace_root / rel_path
                        # Compute path relative to current working directory
                        try:
                            relative_to_cwd = abs_path.relative_to(cwd)
                        except ValueError:
                            # If not relative to cwd, use absolute path
                            relative_to_cwd = abs_path
                        files_changed.append(
                            {
                                "absolute": str(abs_path),
                                "relative": str(relative_to_cwd),
                                "filename": filename,
                            }
                        )
                    structured_content["files_changed"] = files_changed

                    # Add error guidance to structured content if available
                    if "error_guidance" in result.metadata:
                        structured_content["error_guidance"] = result.metadata["error_guidance"]

                    # Add fuel analysis to structured content if available
                    if "fuel_analysis" in result.metadata:
                        structured_content["fuel_analysis"] = result.metadata["fuel_analysis"]

                    # Build content string with fuel guidance when relevant
                    content = result.stdout or result.stderr
                    fuel_analysis = result.metadata.get("fuel_analysis", {})
                    fuel_status = fuel_analysis.get("status", "")

                    # Add fuel guidance to content for warning/critical/exhausted statuses
                    if fuel_status in ("warning", "critical", "exhausted"):
                        fuel_note = fuel_analysis.get("recommendation", "")
                        if fuel_note and content:
                            content = f"{content}\n\n📊 Fuel Analysis: {fuel_note}"
                        elif fuel_note:
                            content = f"📊 Fuel Analysis: {fuel_note}"

                    return MCPToolResult(
                        content=content,
                        structured_content=structured_content,
                        execution_time_ms=result.duration_ms,
                        success=result.success,
                    )

                except Exception as e:
                    error_msg = str(e)
                    self.audit_logger.log_tool_execution(
                        tool_name="execute_code",
                        client_id=session_id or "anonymous",
                        session_id=session_id,
                        success=False,
                        execution_time_ms=0.0,
                        fuel_consumed=0,
                        error_message=error_msg,
                        language=language,
                    )
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="execute_code", error=str(e)
                    )
                    return MCPToolResult(content=f"Execution failed: {e!s}", success=False)

        @self.app.tool(
            name="list_runtimes",
            description="List all available programming language runtimes in the sandbox with version details, feature support, and API patterns",
        )
        async def list_runtimes() -> MCPToolResult:
            """List available runtimes."""
            with self.metrics.time_tool_execution("list_runtimes"):
                try:
                    runtimes = [
                        {
                            "name": "python",
                            "version": "3.12",
                            "description": "CPython compiled to WebAssembly",
                            "features": {
                                "es_version": "N/A (Python, not JavaScript)",
                                "standard_library": "Full Python 3.12 stdlib",
                                "pre_installed_packages": 30,
                                "notable_packages": [
                                    "openpyxl (Excel .xlsx)",
                                    "PyPDF2 (PDF processing)",
                                    "tabulate (table formatting)",
                                    "jinja2 (templating)",
                                    "markdown, python-dateutil, attrs",
                                ],
                                "state_persistence": "All global variables (when auto_persist_globals=True)",
                                "import_caching": "Automatic in sessions (100x faster subsequent imports)",
                            },
                            "api_patterns": {
                                "file_io": "Standard Python: open('/app/file.txt', 'r')",
                                "import_syntax": "import openpyxl  # No sys.path needed, automatic",
                                "state_access": "globals().get('var_name', default)  # Recommended pattern",
                                "path_requirement": "All paths must start with /app/ (WASI restriction)",
                            },
                            "helper_functions": [
                                "N/A - Use standard Python built-ins and stdlib",
                                "pathlib.Path for path operations",
                                "json.load/dump, csv.reader/writer for data",
                            ],
                            "fuel_requirements": {
                                "stdlib_modules": "<500M fuel per import",
                                "light_packages": "1-3B fuel (tabulate, markdown, dateutil)",
                                "heavy_packages": "5-10B fuel (openpyxl, PyPDF2, jinja2) - FIRST import only",
                                "cached_imports": "<100M fuel (subsequent imports in same session)",
                            },
                        },
                        {
                            "name": "javascript",
                            "version": "ES2023",
                            "description": "QuickJS JavaScript engine in WebAssembly",
                            "features": {
                                "es_version": "ES2020+ (async/await, optional chaining, nullish coalescing, etc.)",
                                "standard_library": "Full ES2023 built-ins (Array, Object, Map, Set, Promise, etc.)",
                                "quickjs_modules": ["std (file I/O)", "os (filesystem operations)"],
                                "vendored_packages": 5,
                                "notable_packages": [
                                    "csv-simple (CSV parsing/generation)",
                                    "json-utils (JSON path access/schema validation)",
                                    "string-utils (string manipulation)",
                                    "sandbox-utils (file I/O helpers - auto-injected)",
                                ],
                                "state_persistence": "_state object (when auto_persist_globals=True)",
                                "global_helpers": "Auto-injected: readJson, writeJson, readText, writeText, listFiles, etc.",
                            },
                            "api_patterns": {
                                "file_io_simple": "readJson('/app/data.json')  # Global helper, returns data or null",
                                "file_io_advanced": "const f = std.open('/app/file.txt', 'r');  # std is a global, not ES6 module",
                                "vendored_packages": "const csv = requireVendor('csv-simple');  # Function auto-injected",
                                "state_access": "_state.counter = (_state.counter || 0) + 1;  # Always initialize",
                                "path_requirement": "All paths must start with /app/ (WASI restriction)",
                                "tuple_returns": "⚠️ QuickJS functions return [value, error] tuples - check truthiness before use",
                            },
                            "helper_functions": [
                                "readJson(path), writeJson(path, data) - JSON I/O",
                                "readText(path), writeText(path, text) - Text I/O",
                                "readLines(path), writeLines(path, lines) - Line-based I/O",
                                "appendText(path, text) - Append to file",
                                "listFiles(dirPath) - List directory contents",
                                "fileExists(path), fileSize(path) - File info",
                                "copyFile(src, dest), removeFile(path) - File ops",
                            ],
                            "fuel_requirements": {
                                "vendored_packages": "<100M fuel per requireVendor() call",
                                "std_os_modules": "<50M fuel per import",
                                "helper_functions": "<10M fuel per call (negligible overhead)",
                            },
                        },
                    ]

                    # Format runtimes for display
                    content_lines = ["Available runtimes:\n"]
                    for runtime in runtimes:
                        content_lines.append(f"🔹 {runtime['name']} ({runtime['version']})")
                        content_lines.append(f"   {runtime['description']}")
                        features = runtime.get("features", {})
                        if isinstance(features, dict):
                            pkg_count = features.get("pre_installed_packages", 0)
                            content_lines.append(f"   📦 Packages: {pkg_count}")
                            notable = features.get("notable_packages", [])
                            if isinstance(notable, list) and notable:
                                content_lines.append(f"   💡 Notable: {', '.join(notable[:3])}")
                        content_lines.append("")

                    content_lines.append(
                        "\n💡 Tip: Use list_available_packages for complete package list with fuel requirements"
                    )

                    return MCPToolResult(
                        content="\n".join(content_lines),
                        structured_content={"runtimes": runtimes},
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="list_runtimes", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to list runtimes: {e!s}", success=False)

        @self.app.tool(
            name="create_session",
            description="""Create a new workspace session for code execution with optional automatic global variable persistence.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            🤔 WHEN TO CREATE A SESSION vs. USE DEFAULT:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ✅ CREATE SESSION when you need:
               1. Stateful execution (counter, accumulator, multi-step workflows)
               2. Heavy package imports (openpyxl, PyPDF2, jinja2) - reuse cached imports
               3. Persistent files across multiple executions
               4. Custom execution policy (higher fuel budget, memory limits)
               5. Multiple related operations on same dataset

            ❌ USE DEFAULT (omit session_id in execute_code) when:
               • One-off calculations or simple scripts
               • No state needed between executions
               • No heavy package imports
               • Default resource limits sufficient (5B fuel, 128MB memory)

            💡 Decision Tree:
               Will you run multiple related executions? → YES → Create session
               Do you need to preserve state/variables? → YES → Create session + auto_persist_globals
               Will you import openpyxl/PyPDF2/jinja2? → YES → Create session (import caching!)
               Simple one-time calculation? → NO session needed

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            🔄 AUTO-PERSIST GUIDELINES:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            🐍 Python (auto_persist_globals=True):
               • ALL global variables automatically saved between executions
               • Includes imported modules (cached for 100x faster subsequent imports!)
               • Example workflow:
                 1st execution: counter = 1; data = [1, 2, 3]
                 2nd execution: print(counter)  # Output: 1 (persisted!)
                                counter += 1
                 3rd execution: print(counter)  # Output: 2

               • Best practices:
                 - Use globals().get('var_name', default) for safety
                 - Imports are cached: import openpyxl once, reuse forever in session
                 - Module-level variables persist automatically

            🟨 JavaScript (auto_persist_globals=True):
               • Use _state object for persistence (automatically injected)
               • Example workflow:
                 1st execution: _state.counter = (_state.counter || 0) + 1;
                               console.log(_state.counter);  // Output: 1
                 2nd execution: _state.counter = (_state.counter || 0) + 1;
                               console.log(_state.counter);  // Output: 2

               • What gets persisted:
                 ✅ _state object properties (any JSON-serializable data)
                 ❌ Regular variables (let/const/var) - NOT persisted without _state
                 ❌ Functions, closures - NOT persisted

               • Best practices:
                 - Always initialize: _state.var = _state.var || defaultValue
                 - Store data structures: _state.results = _state.results || []
                 - Check existence: if (_state.config) { ... }

            ⚠️ Limitations:
               • Python: Functions/classes defined in global scope persist (be careful!)
               • JavaScript: Only _state object persists, not regular variables
               • Both: File system changes persist (files in /app directory)
               • Performance: auto_persist adds ~5-10ms per execution (negligible)

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            🔧 SESSION LIFECYCLE:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            1. Create session:
               create_session(language="python", session_id="my-workflow",
                            auto_persist_globals=True)

            2. Execute code (repeat as needed):
               execute_code(code="...", language="python", session_id="my-workflow")
               # State, imports, and files persist between calls

            3. Check session status (optional):
               get_workspace_info(session_id="my-workflow")
               # Returns: execution_count, files, language, created_at

            4. Clean up (optional):
               destroy_session(session_id="my-workflow")
               # Or let it auto-cleanup after inactivity timeout

            💡 Session Management Tips:
               • Sessions auto-cleanup after inactivity (default: 1 hour)
               • Use meaningful session_id names ("excel-processor", "data-pipeline")
               • Call destroy_session when done to free resources immediately
               • reset_workspace to clear files but keep session (useful for testing)

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ⚡ CUSTOM CONFIGURATION (Advanced):
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            For custom fuel budgets or memory limits, use the Python library directly:

            from sandbox import create_sandbox, ExecutionPolicy, RuntimeType

            policy = ExecutionPolicy(
                fuel_budget=10_000_000_000,      # 10B for heavy packages
                memory_bytes=256 * 1024 * 1024,  # 256MB for large datasets
            )
            sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
            result = sandbox.execute(code)

            ⚠️ Note: MCP tool API does not expose custom policies yet. Use default session
            for most cases. Heavy package imports (openpyxl, PyPDF2, jinja2) require
            10B fuel - increase via library if hitting OutOfFuel errors.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            📋 USAGE EXAMPLES:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            Example 1 - Counter Pattern (Python):
              create_session(language="python", session_id="counter", auto_persist_globals=True)
              execute_code("counter = globals().get('counter', 0) + 1; print(counter)",
                          session_id="counter")  # Output: 1
              execute_code("counter = globals().get('counter', 0) + 1; print(counter)",
                          session_id="counter")  # Output: 2

            Example 2 - Counter Pattern (JavaScript):
              create_session(language="javascript", session_id="counter", auto_persist_globals=True)
              execute_code("_state.counter = (_state.counter || 0) + 1; console.log(_state.counter)",
                          session_id="counter")  # Output: 1
              execute_code("_state.counter = (_state.counter || 0) + 1; console.log(_state.counter)",
                          session_id="counter")  # Output: 2

            Example 3 - Heavy Package Caching (Python):
              create_session(language="python", session_id="excel-proc")
              execute_code("import openpyxl; print('Imported!')", session_id="excel-proc")
              # First import: ~5-7B fuel, slow
              execute_code("import openpyxl; print('Cached!')", session_id="excel-proc")
              # Subsequent: <100M fuel, 100x faster!

            Example 4 - Multi-Step Data Pipeline (JavaScript):
              create_session(language="javascript", session_id="pipeline", auto_persist_globals=True)
              execute_code("_state.data = readJson('/app/input.json'); _state.step = 1;",
                          session_id="pipeline")
              execute_code("_state.processed = _state.data.map(x => x * 2); _state.step = 2;",
                          session_id="pipeline")
              execute_code("writeJson('/app/output.json', _state.processed);",
                          session_id="pipeline")

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            ⚙️ PARAMETERS:
            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            • language (str): "python" or "javascript"
            • session_id (str|None): Custom session identifier (auto-generated if omitted)
              - Use descriptive names: "excel-processor", "data-pipeline", "counter"
              - Reuse same ID to continue existing session
            • auto_persist_globals (bool): Enable automatic state persistence (default: False)
              - Python: All global variables persist
              - JavaScript: _state object persists
              - Recommended: True for stateful workflows, False for one-off tasks

            Returns: {session_id, language, sandbox_session_id, created_at, auto_persist_globals}
            """,
        )
        async def create_session(
            language: str,
            session_id: str | None = None,
            auto_persist_globals: bool = False,
        ) -> MCPToolResult:
            """Create a new workspace session."""
            # Check rate limit
            if not await self._check_rate_limit(session_id or "anonymous"):
                return MCPToolResult(
                    content="Rate limit exceeded. Please try again later.",
                    success=False,
                )

            with self.metrics.time_tool_execution("create_session"):
                try:
                    # Validate language
                    if language not in ["python", "javascript"]:
                        return MCPToolResult(
                            content=f"Unsupported language: {language}. Supported: python, javascript",
                            success=False,
                        )

                    session_result = await self.session_manager.create_session(
                        language=language,
                        session_id=session_id,
                        auto_persist_globals=auto_persist_globals,
                    )

                    # Check if session limit was exceeded (returns dict with error)
                    if isinstance(session_result, dict) and "error" in session_result:
                        return MCPToolResult(
                            content=str(session_result.get("message", "Session limit exceeded")),
                            structured_content=session_result,
                            success=False,
                        )

                    session = session_result
                    # Type narrowing: session is WorkspaceSession here
                    assert not isinstance(session, dict)

                    # Record session creation
                    self.metrics.record_session_created()

                    return MCPToolResult(
                        content=f"Created session {session.workspace_id} for {language}"
                        + (
                            " with automatic global variable persistence"
                            if auto_persist_globals
                            else ""
                        ),
                        structured_content={
                            "session_id": session.workspace_id,
                            "language": session.language,
                            "sandbox_session_id": session.sandbox_session_id,
                            "created_at": session.created_at,
                            "auto_persist_globals": session.auto_persist_globals,
                        },
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="create_session", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to create session: {e!s}", success=False)

        @self.app.tool(
            name="destroy_session",
            description="Destroy an existing workspace session",
        )
        async def destroy_session(session_id: str) -> MCPToolResult:
            """Destroy a workspace session."""
            with self.metrics.time_tool_execution("destroy_session"):
                try:
                    # Calculate lifetime before destroying
                    if session_id in self.session_manager._sessions:
                        session = self.session_manager._sessions[session_id]
                        lifetime = time.time() - session.created_at
                    else:
                        lifetime = 0.0

                    success = await self.session_manager.destroy_session(session_id)

                    if success:
                        # Record session destruction
                        self.metrics.record_session_destroyed(lifetime)

                        return MCPToolResult(
                            content=f"Destroyed session {session_id}",
                            structured_content={"session_id": session_id},
                        )
                    else:
                        return MCPToolResult(
                            content=f"Session {session_id} not found", success=False
                        )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="destroy_session", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to destroy session: {e!s}", success=False)

        @self.app.tool(
            name="list_available_packages",
            description="List pre-installed packages available in Python and JavaScript sessions (no installation required). Includes fuel budget requirements and runtime-specific capabilities.",
        )
        async def list_available_packages() -> MCPToolResult:
            """List pre-installed packages with fuel requirements."""
            with self.metrics.time_tool_execution("list_available_packages"):
                try:
                    packages = {
                        "python_document_processing": [
                            "openpyxl - Read/write Excel .xlsx files (⚠️ REQUIRES 10B fuel budget for first import)",
                            "XlsxWriter - Write Excel .xlsx files, write-only, lighter alternative",
                            "PyPDF2 - Read/write/merge PDF files (⚠️ REQUIRES 10B fuel budget for first import)",
                            "pdfminer.six - PDF text extraction (pure-Python mode)",
                            "odfpy - Read/write OpenDocument Format (.odf, .ods, .odp)",
                            "mammoth - Convert Word .docx to HTML/Markdown",
                        ],
                        "python_text_data": [
                            "tabulate - Pretty-print tables (ASCII, Markdown, HTML) [~1.4B fuel for first import]",
                            "jinja2 - Template rendering (⚠️ REQUIRES 5-10B fuel budget for first import)",
                            "MarkupSafe - HTML/XML escaping (required by jinja2)",
                            "markdown - Convert Markdown to HTML [~1.8B fuel for first import]",
                            "python-dateutil - Advanced date/time parsing [~1.6B fuel for first import]",
                            "attrs - Classes without boilerplate",
                        ],
                        "python_utilities": [
                            "certifi - Mozilla's CA bundle",
                            "charset-normalizer - Character encoding detection",
                            "idna - Internationalized domain names",
                            "urllib3 - HTTP client (encoding utilities only, no networking)",
                            "six - Python 2/3 compatibility",
                            "tomli - TOML parser (Python <3.11)",
                            "cffi - Foreign function interface (limited WASM support)",
                        ],
                        "python_stdlib_highlights": [
                            "json, csv, xml - Data formats [lightweight, <500M fuel]",
                            "re - Regular expressions",
                            "pathlib, os, shutil - File operations",
                            "math, statistics, decimal - Mathematics",
                            "datetime, time, calendar - Date/time",
                            "collections, itertools, functools - Data structures",
                            "base64, hashlib, hmac - Encoding/hashing",
                            "zipfile, tarfile, gzip - Compression",
                            "sqlite3 - In-memory SQL database",
                        ],
                        "javascript_vendored_packages": [
                            "csv-simple - CSV parsing and generation (pure JS)",
                            "json-utils - JSON path access and schema validation",
                            "string-utils - String manipulation (slugify, truncate, case conversion, etc.)",
                            "sandbox-utils - File I/O helpers (readJson, writeJson, readText, listFiles, etc.)",
                        ],
                        "javascript_stdlib": [
                            "std global - File I/O (std.open, FILE operations) - access directly, not via import",
                            "os global - Environment variables, file stats, directory operations",
                            "JSON, Math, Date - Built-in JavaScript objects",
                            "String, Array, Object - Native data structures",
                            "RegExp - Regular expressions",
                        ],
                        "fuel_requirements": [
                            "📊 FUEL BUDGET REQUIREMENTS (Python - first import only):",
                            "  • Standard packages (tabulate, markdown, dateutil): 2-5B fuel (default budget OK)",
                            "  • Heavy packages (openpyxl, PyPDF2, jinja2): 5-10B fuel (increase budget!)",
                            "  • Stdlib modules: <500M fuel each",
                            "",
                            "⚡ PERFORMANCE TIPS:",
                            "  • First import is expensive, subsequent imports use cached modules",
                            "  • Sessions persist imports across executions",
                            "  • Set ExecutionPolicy(fuel_budget=10_000_000_000) for document processing",
                            "  • Use auto_persist_globals=True to cache imports/state automatically",
                        ],
                        "incompatible_c_extensions": [
                            "❌ python-pptx - Requires lxml.etree (C extension not available in WASM)",
                            "❌ python-docx - Requires lxml.etree (C extension not available in WASM)",
                            "❌ Pillow/PIL - Image processing (C extension not available in WASM)",
                            "❌ lxml.etree - XML processing C extension (base lxml imports but etree doesn't work)",
                            "Note: Use mammoth for Word .docx reading, PyPDF2 for PDFs, openpyxl for Excel",
                        ],
                    }

                    usage_note = (
                        "\n✅ PYTHON USAGE:\n"
                        "1. Packages are automatically available via /data/site-packages\n"
                        "2. No need to add sys.path.insert() - it's done automatically!\n"
                        "3. Just import directly: import openpyxl, from tabulate import tabulate\n\n"
                        "✅ JAVASCRIPT USAGE:\n"
                        "1. Vendored packages available via requireVendor() function (auto-injected)\n"
                        "2. Example: const csv = requireVendor('csv-simple'); csv.parse(data)\n"
                        "3. sandbox-utils auto-injected: readJson(), writeJson(), listFiles(), etc.\n"
                        "4. QuickJS std/os are globals: std.open(), os.readdir() (NOT ES6 modules!)\n\n"
                        "⚠️ FUEL BUDGET REQUIREMENTS (Python):\n"
                        "- DEFAULT budget (5B): Works for tabulate, markdown, dateutil, stdlib\n"
                        "- INCREASE to 10B for: openpyxl, PyPDF2, jinja2 (first import only)\n"
                        "- Subsequent imports in same session use cached modules (<100M fuel)\n\n"
                        "💡 BEST PRACTICES (Both Runtimes):\n"
                        "- Use auto_persist_globals=True when creating sessions\n"
                        "  * Python: All global variables auto-saved between executions\n"
                        "  * JavaScript: Use _state object (_state.counter = 1) for persistence\n"
                        "- Import/load heavy packages once at session start\n"
                        "- Reuse sessions to benefit from cached imports/state\n\n"
                        "🚫 NOT SUPPORTED:\n"
                        "- pip install / npm install (WASI limitation - use pre-installed packages only)\n"
                        "- Python: PowerPoint .pptx editing (requires C extensions: python-pptx, Pillow)\n"
                        "- Python: Image processing (Pillow/PIL requires C extensions)\n"
                        "- Python: Full lxml.etree (C extension not available, use xml.etree.ElementTree instead)\n"
                        "- JavaScript: Node.js-specific APIs (fs, http, child_process, etc.)\n\n"
                        "📦 DOCUMENT PROCESSING:\n"
                        "  Python Excel: openpyxl (read/write), XlsxWriter (write-only)\n"
                        "  Python PDF: PyPDF2 (read/write/merge), pdfminer.six (text extraction)\n"
                        "  Python Word: mammoth (read-only, converts to HTML/Markdown)\n"
                        "  Python OpenDocument: odfpy (.odt, .ods, .odp)\n"
                        "  JavaScript CSV: csv-simple (parse/stringify CSV data)\n"
                        "  JavaScript JSON: json-utils (path access with dot notation, schema validation)"
                    )

                    content_lines = []
                    for category, pkgs in packages.items():
                        content_lines.append(f"\n{category.replace('_', ' ').title()}:")
                        for pkg in pkgs:
                            content_lines.append(f"  - {pkg}")

                    content = "\n".join(content_lines) + usage_note

                    return MCPToolResult(
                        content=content,
                        structured_content={"packages": packages, "usage_note": usage_note},
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR,
                        "Tool execution failed",
                        tool="list_available_packages",
                        error=str(e),
                    )
                    return MCPToolResult(content=f"Failed to list packages: {e!s}", success=False)

        @self.app.tool(
            name="cancel_execution",
            description="Cancel a running execution (not yet implemented - executions are synchronous)",
        )
        async def cancel_execution(session_id: str) -> MCPToolResult:
            """Cancel a running execution."""
            with self.metrics.time_tool_execution("cancel_execution"):
                # Note: Current implementation is synchronous, so cancellation is not possible
                # This would require async execution support
                return MCPToolResult(
                    content="Execution cancellation is not yet supported (synchronous execution only)",
                    structured_content={"supported": False},
                    success=False,
                )

        @self.app.tool(
            name="get_workspace_info",
            description="""Get information about a workspace session.

            By default, returns only client files (user-created data files) to keep
            the response clean. System files (internal sandbox artifacts like
            user_code.py, .metadata.json, __state__.json, site-packages/) are
            filtered out unless explicitly requested.

            Parameters:
            • session_id (str): The session ID to query
            • include_system_files (bool): If True, also returns system_files list
              (default: False)

            Returns:
            • files: List of client files (user-created)
            • system_files: List of system files (only when include_system_files=True)
            • execution_count, language, created_at, etc.
            """,
        )
        async def get_workspace_info(
            session_id: str,
            include_system_files: bool = False,
        ) -> MCPToolResult:
            """Get workspace session information."""
            with self.metrics.time_tool_execution("get_workspace_info"):
                try:
                    info = await self.session_manager.get_session_info(session_id)

                    if info:
                        all_files = info.get("files", [])
                        if not isinstance(all_files, (list, tuple)):
                            all_files = []

                        # Filter files into client and system categories
                        client_files, system_files = self._filter_system_files(list(all_files))

                        # Update info with filtered files
                        info["files"] = client_files

                        # Build content string showing both counts
                        client_count = len(client_files)
                        system_count = len(system_files)
                        if include_system_files:
                            info["system_files"] = system_files
                            content = (
                                f"Session {session_id}: {info['language']}, "
                                f"{info['execution_count']} executions, "
                                f"{client_count} files ({system_count} system)"
                            )
                        else:
                            content = (
                                f"Session {session_id}: {info['language']}, "
                                f"{info['execution_count']} executions, "
                                f"{client_count} files"
                            )

                        return MCPToolResult(
                            content=content,
                            structured_content=info,
                        )
                    else:
                        return MCPToolResult(
                            content=f"Session {session_id} not found", success=False
                        )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR,
                        "Tool execution failed",
                        tool="get_workspace_info",
                        error=str(e),
                    )
                    return MCPToolResult(
                        content=f"Failed to get workspace info: {e!s}", success=False
                    )

        @self.app.tool(
            name="reset_workspace",
            description="Reset a workspace session (clear all files but keep session)",
        )
        async def reset_workspace(session_id: str) -> MCPToolResult:
            """Reset a workspace session."""
            with self.metrics.time_tool_execution("reset_workspace"):
                try:
                    success = await self.session_manager.reset_session(session_id)

                    if success:
                        return MCPToolResult(
                            content=f"Reset workspace session {session_id}",
                            structured_content={"session_id": session_id},
                        )
                    else:
                        return MCPToolResult(
                            content=f"Failed to reset session {session_id}", success=False
                        )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="reset_workspace", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to reset workspace: {e!s}", success=False)

        @self.app.tool(
            name="get_metrics",
            description="Get performance metrics and monitoring data for the MCP server",
        )
        async def get_metrics() -> MCPToolResult:
            """Get MCP server metrics."""
            with self.metrics.time_tool_execution("get_metrics"):
                try:
                    metrics_summary = self.metrics.get_summary()

                    # Add version information
                    server_version = self.config.server.version
                    metrics_summary["server"] = {
                        "version": server_version,
                        "name": self.config.server.name,
                    }

                    return MCPToolResult(
                        content=f"MCP Server v{server_version}: {metrics_summary['tool_executions']['total_count']} tool executions, {metrics_summary['sessions']['active_count']} active sessions",
                        structured_content=metrics_summary,
                    )

                except Exception as e:
                    self.logger._emit(
                        logging.ERROR, "Tool execution failed", tool="get_metrics", error=str(e)
                    )
                    return MCPToolResult(content=f"Failed to get metrics: {e!s}", success=False)

    async def start_stdio(self) -> None:
        """Start the MCP server with stdio transport."""
        self.logger._emit(logging.INFO, "Starting MCP server with stdio transport")
        await self.app.run_stdio_async()

    async def start_http(self, config: HTTPTransportConfig | None = None) -> None:
        """Start the MCP server with HTTP transport."""
        if config is None:
            # Convert MCPConfig to HTTPTransportConfig
            http_config = HTTPTransportConfig(
                host=self.config.transport_http.host,
                port=self.config.transport_http.port,
                path=self.config.transport_http.path,
                cors_origins=self.config.transport_http.cors_origins,
                auth_token=self.config.transport_http.auth_token,
                rate_limit_requests=self.config.transport_http.rate_limit_requests,
                rate_limit_window_seconds=self.config.transport_http.rate_limit_window_seconds,
                max_concurrent_requests=self.config.transport_http.max_concurrent_requests,
                request_timeout_seconds=self.config.transport_http.request_timeout_seconds,
                max_request_size_mb=self.config.transport_http.max_request_size_mb,
            )
        else:
            http_config = config

        self.logger._emit(
            logging.INFO,
            "Starting MCP server with HTTP transport",
            host=http_config.host,
            port=http_config.port,
        )

        # Add CORS middleware for web clients
        http_app = self.app.http_app()
        http_app.add_middleware(
            http_config.get_cors_middleware_class(),  # type: ignore[arg-type]
            allow_origins=http_config.cors_origins,
            allow_credentials=True,
            allow_methods=["POST", "GET", "OPTIONS"],
            allow_headers=["*"],
        )

        # Note: HTTP timing would need to be integrated at the FastMCP level
        # For now, we rely on the tool-level timing

        # Get uvicorn config but extract host/port separately
        # to avoid duplicate parameter error in FastMCP
        uvicorn_config = http_config.get_uvicorn_config()
        host = uvicorn_config.pop("host")
        port = uvicorn_config.pop("port")

        await self.app.run_http_async(
            host=host,
            port=port,
            uvicorn_config=uvicorn_config,
        )

    @asynccontextmanager
    async def _lifespan(self) -> AsyncGenerator[None, None]:
        """FastMCP lifespan context manager for background task management.

        This is wired up via FastMCP's lifespan parameter to ensure cleanup tasks
        run during the server's lifetime and are properly stopped on shutdown.
        """
        self.logger._emit(logging.DEBUG, "Starting MCP server lifespan")

        # Start background cleanup tasks
        await self.rate_limiter.start_cleanup_task()
        await self.session_manager.start_cleanup_task()

        try:
            yield
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Shutdown the MCP server and cleanup resources."""
        self.logger._emit(logging.INFO, "Shutting down MCP server")

        # Log final metrics
        metrics_summary = self.metrics.get_summary()
        self.logger._emit(logging.INFO, "Final MCP metrics", metrics=metrics_summary)

        # Stop background cleanup tasks
        await self.rate_limiter.stop_cleanup_task()
        await self.session_manager.stop_cleanup_task()

        # Clean up expired sessions
        await self.session_manager.cleanup()


# Legacy standalone lifespan function - kept for backwards compatibility
# New code should use MCPServer._lifespan which is automatically wired to FastMCP
@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncGenerator[None, None]:
    """FastMCP lifespan context manager (legacy - use server._lifespan instead)."""
    async with server._lifespan():
        yield


def create_mcp_server(
    config: MCPConfig | None = None,
    external_mount_dir: Path | None = None,
) -> MCPServer:
    """Create and configure an MCP server instance.

    Args:
        config: MCP server configuration. If None, uses defaults.
        external_mount_dir: Path to directory containing external files to mount
            read-only at /external in all sessions. Use stage_external_files() to
            prepare this directory from a list of file paths.

    Returns:
        Configured MCPServer instance.
    """
    return MCPServer(config, external_mount_dir=external_mount_dir)
