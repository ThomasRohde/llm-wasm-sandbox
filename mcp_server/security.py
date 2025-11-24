"""
Security utilities for MCP Server.

Provides input validation, sanitization, and security checks
to prevent injection attacks and ensure safe code execution.
"""

from __future__ import annotations

import re
from typing import ClassVar


class SecurityValidator:
    """
    Security validator for MCP tool inputs.

    Validates and sanitizes inputs to prevent:
    - Code injection attacks
    - Path traversal attacks
    - Resource exhaustion attacks
    - Malicious package installations
    """

    # Dangerous patterns in code
    DANGEROUS_CODE_PATTERNS: ClassVar[list[str]] = [
        # File system access - COMMENTED OUT to allow file operations
        # r'\b(open|file|os\.|pathlib|shutil)\b',
        # Network access
        r"\b(socket|urllib|requests|http|ftp)\b",
        # System commands
        r"\b(subprocess|os\.system|os\.popen|commands)\b",
        # Dynamic code execution
        r"\b(eval|exec|compile|__import__|importlib)\b",
        # Process manipulation
        r"\b(psutil|signal|kill|terminate)\b",
    ]

    # Dangerous package names
    DANGEROUS_PACKAGES: ClassVar[set[str]] = {
        # 'os', 'sys', 'pathlib' - REMOVED to allow basic file operations
        "subprocess",
        "shutil",
        "socket",
        "urllib",
        "eval",
        "exec",
        "compile",
        "importlib",
        "psutil",
        "signal",
        "multiprocessing",
        "threading",
        "asyncio",
        "ctypes",
        "mmap",
        "resource",
        "gc",
        "inspect",
        "pickle",
        "shelve",
    }

    MAX_CODE_LENGTH = 10000  # characters
    MAX_PACKAGE_NAME_LENGTH = 100
    MAX_SESSION_ID_LENGTH = 100

    @classmethod
    def validate_code_input(cls, code: str, language: str) -> tuple[bool, str]:
        """
        Validate code input for security.

        Returns (is_valid, error_message)
        """
        if not code or not isinstance(code, str):
            return False, "Code must be a non-empty string"

        if len(code) > cls.MAX_CODE_LENGTH:
            return False, f"Code too long: {len(code)} > {cls.MAX_CODE_LENGTH} characters"

        # Language-specific validation
        if language == "python":
            return cls._validate_python_code(code)
        elif language == "javascript":
            return cls._validate_javascript_code(code)
        else:
            return False, f"Unsupported language: {language}"

    @classmethod
    def _validate_python_code(cls, code: str) -> tuple[bool, str]:
        """Validate Python code for security issues."""
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_CODE_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Potentially dangerous code pattern detected: {pattern}"

        # Check for suspicious imports
        import_matches = re.findall(r"^\s*(?:import|from)\s+(\w+)", code, re.MULTILINE)
        for module in import_matches:
            if module.lower() in cls.DANGEROUS_PACKAGES:
                return False, f"Import of potentially dangerous module: {module}"

        return True, ""

    @classmethod
    def _validate_javascript_code(cls, code: str) -> tuple[bool, str]:
        """Validate JavaScript code for security issues."""
        # Basic checks for Node.js APIs
        dangerous_js_patterns = [
            r"\b(require|process|fs|path|child_process|http|https|net)\b",
            r"\b(eval|Function|setTimeout|setInterval)\b",
            r"\b(window|document|XMLHttpRequest)\b",  # Browser APIs
        ]

        for pattern in dangerous_js_patterns:
            if re.search(pattern, code):
                return False, f"Potentially dangerous JavaScript pattern detected: {pattern}"

        return True, ""

    @classmethod
    def validate_package_name(cls, package_name: str) -> tuple[bool, str]:
        """Validate package name for security."""
        if not package_name or not isinstance(package_name, str):
            return False, "Package name must be a non-empty string"

        if len(package_name) > cls.MAX_PACKAGE_NAME_LENGTH:
            return (
                False,
                f"Package name too long: {len(package_name)} > {cls.MAX_PACKAGE_NAME_LENGTH}",
            )

        # Check for dangerous package names
        if package_name.lower() in cls.DANGEROUS_PACKAGES:
            return False, f"Installation of dangerous package not allowed: {package_name}"

        # Basic package name validation (PEP 508 compliant-ish)
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", package_name):
            return False, "Invalid package name format"

        # Check for path traversal attempts
        if ".." in package_name or "/" in package_name or "\\" in package_name:
            return False, "Package name contains invalid characters"

        return True, ""

    @classmethod
    def validate_session_id(cls, session_id: str) -> tuple[bool, str]:
        """Validate session ID."""
        if not session_id or not isinstance(session_id, str):
            return False, "Session ID must be a non-empty string"

        if len(session_id) > cls.MAX_SESSION_ID_LENGTH:
            return False, f"Session ID too long: {len(session_id)} > {cls.MAX_SESSION_ID_LENGTH}"

        # Allow alphanumeric, hyphens, underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
            return False, "Session ID contains invalid characters"

        return True, ""

    @classmethod
    def sanitize_string(cls, input_str: str, max_length: int = 1000) -> str:
        """Sanitize string input by removing potentially dangerous characters."""
        if not isinstance(input_str, str):
            return ""

        # Remove null bytes and other control characters
        sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", input_str)

        # Truncate if too long
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized.strip()

    @classmethod
    def validate_timeout(cls, timeout: int | float | None) -> tuple[bool, int]:
        """Validate and normalize timeout value."""
        if timeout is None:
            return True, 30  # Default timeout

        if not isinstance(timeout, (int, float)) or timeout < 1 or timeout > 300:
            return False, 30

        return True, int(timeout)
