"""
Workspace Session Management for MCP Server.

Manages workspace sessions that bind MCP client connections to sandbox sessions
for automatic state persistence across tool calls.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from sandbox import RuntimeType, create_sandbox
from sandbox.core.logging import SandboxLogger
from sandbox.core.models import SandboxResult


@dataclass
class WorkspaceSession:
    """A workspace session bound to an MCP client."""

    workspace_id: str
    language: str
    sandbox_session_id: str
    auto_persist_globals: bool = False
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    execution_count: int = 0
    variables: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return time.time() - self.last_used_at > 600  # Default 10 minutes

    def get_sandbox(self) -> Any:
        """Get the sandbox instance for this session."""
        runtime = RuntimeType.PYTHON if self.language == "python" else RuntimeType.JAVASCRIPT
        return create_sandbox(
            runtime=runtime,
            session_id=self.sandbox_session_id,
            auto_persist_globals=self.auto_persist_globals,
        )

    async def execute_code(self, code: str, timeout: int | None = None) -> SandboxResult:
        """Execute code in this workspace session."""
        sandbox = self.get_sandbox()
        # Note: sandbox.execute is synchronous, not async
        result: SandboxResult = sandbox.execute(code, timeout=timeout)

        self.last_used_at = time.time()
        self.execution_count += 1

        return result


class WorkspaceSessionManager:
    """
    Manages workspace sessions for MCP clients.

    Each MCP client gets one workspace session per language that persists
    across tool calls.
    """

    def __init__(self) -> None:
        self.logger = SandboxLogger("mcp-sessions")
        self._sessions: dict[str, WorkspaceSession] = {}
        self._cleanup_task: asyncio.Task | None = None

    async def get_or_create_session(
        self, language: str, session_id: str | None = None, auto_persist_globals: bool = False
    ) -> WorkspaceSession:
        """
        Get or create a workspace session.

        Creates a persistent sandbox session for state management.
        """
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
            if not session.is_expired:
                return session

        # Create new sandbox session
        runtime = RuntimeType.PYTHON if language == "python" else RuntimeType.JAVASCRIPT
        sandbox = create_sandbox(runtime=runtime, auto_persist_globals=auto_persist_globals)
        sandbox_session_id = sandbox.session_id

        # Create workspace session
        workspace_id = session_id or f"workspace_{secrets.token_urlsafe(8)}"
        session = WorkspaceSession(
            workspace_id=workspace_id,
            language=language,
            sandbox_session_id=sandbox_session_id,
            auto_persist_globals=auto_persist_globals,
        )

        self._sessions[workspace_id] = session
        self.logger._emit(
            logging.INFO,
            "Created workspace session",
            workspace_id=workspace_id,
            language=language,
            sandbox_session_id=sandbox_session_id,
        )

        return session

    async def create_session(
        self, language: str, session_id: str | None = None, auto_persist_globals: bool = False
    ) -> WorkspaceSession:
        """Create a new workspace session explicitly."""
        # Create new sandbox session
        runtime = RuntimeType.PYTHON if language == "python" else RuntimeType.JAVASCRIPT
        sandbox = create_sandbox(runtime=runtime, auto_persist_globals=auto_persist_globals)
        sandbox_session_id = sandbox.session_id

        # Create workspace session
        workspace_id = session_id or f"workspace_{secrets.token_urlsafe(8)}"
        session = WorkspaceSession(
            workspace_id=workspace_id,
            language=language,
            sandbox_session_id=sandbox_session_id,
            auto_persist_globals=auto_persist_globals,
        )

        self._sessions[workspace_id] = session
        self.logger._emit(
            logging.INFO,
            "Created workspace session",
            workspace_id=workspace_id,
            language=language,
            sandbox_session_id=sandbox_session_id,
        )

        return session

    async def destroy_session(self, session_id: str) -> bool:
        """Destroy a workspace session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            # Clean up sandbox session
            try:
                from sandbox import delete_session_workspace

                delete_session_workspace(session.sandbox_session_id)
            except Exception as e:
                self.logger._emit(
                    logging.WARNING,
                    "Failed to cleanup sandbox session",
                    session_id=session.sandbox_session_id,
                    error=str(e),
                )

            del self._sessions[session_id]
            self.logger._emit(logging.INFO, "Destroyed workspace session", workspace_id=session_id)
            return True
        return False

    async def reset_session(self, session_id: str) -> bool:
        """Reset a workspace session (clear workspace but keep session)."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            try:
                # Clear all files in the session workspace using sandbox's storage adapter
                from pathlib import Path

                # Get the sandbox instance to access its storage adapter
                sandbox = session.get_sandbox()
                
                # Use the storage adapter's workspace_root
                workspace_path = sandbox.storage_adapter.workspace_root / session.sandbox_session_id
                if workspace_path.exists():
                    for item in workspace_path.iterdir():
                        # Skip metadata file and vendored packages
                        if item.name in (".metadata.json", "site-packages"):
                            continue
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            import shutil

                            shutil.rmtree(item)
                session.execution_count = 0
                session.variables.clear()
                session.imports.clear()
                self.logger._emit(logging.INFO, "Reset workspace session", workspace_id=session_id)
                return True
            except Exception as e:
                self.logger._emit(
                    logging.WARNING, "Failed to reset session", session_id=session_id, error=str(e)
                )
                return False
        return False

    async def get_session_info(self, session_id: str) -> dict | None:
        """Get information about a workspace session."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            try:
                from sandbox import list_session_files

                files = list_session_files(session.sandbox_session_id)
            except Exception:
                files = []

            return {
                "workspace_id": session.workspace_id,
                "language": session.language,
                "sandbox_session_id": session.sandbox_session_id,
                "created_at": session.created_at,
                "last_used_at": session.last_used_at,
                "execution_count": session.execution_count,
                "variables": session.variables,
                "imports": session.imports,
                "files": files,
                "is_expired": session.is_expired,
            }
        return None

    async def cleanup(self) -> None:
        """Clean up expired sessions."""
        expired = [wid for wid, session in self._sessions.items() if session.is_expired]

        for wid in expired:
            del self._sessions[wid]
            self.logger._emit(logging.INFO, "Cleaned up expired session", workspace_id=wid)

        if expired:
            self.logger._emit(logging.INFO, "Session cleanup completed", cleaned_count=len(expired))

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

    async def _periodic_cleanup(self) -> None:
        """Periodic cleanup of expired sessions."""
        while True:
            await asyncio.sleep(300)  # Clean up every 5 minutes
            await self.cleanup()
