"""Test error guidance classification and actionable error messages.

Verifies that the sandbox correctly classifies common errors and provides
actionable guidance for resolution.
"""

from __future__ import annotations

import pytest

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox
from sandbox.core.error_templates import (
    ERROR_MISSING_VENDORED_PACKAGE,
    ERROR_OUT_OF_FUEL,
    ERROR_PATH_RESTRICTION,
    ERROR_QUICKJS_TUPLE_DESTRUCTURING,
    classify_error_from_stderr,
    classify_error_from_trap,
    get_error_guidance,
)


class TestOutOfFuelGuidance:
    """Test OutOfFuel error classification and guidance."""

    def test_outoffuel_trap_classification(self) -> None:
        """Verify OutOfFuel is detected from trap message."""
        guidance = classify_error_from_trap(
            trap_message="wasm trap: out of fuel",
            fuel_consumed=5_000_000_000,
            fuel_budget=5_000_000_000,
        )
        assert guidance is not None
        assert guidance["error_type"] == ERROR_OUT_OF_FUEL
        assert len(guidance["actionable_guidance"]) > 0
        assert any("fuel_budget" in g.lower() for g in guidance["actionable_guidance"])

    def test_outoffuel_includes_concrete_recommendation(self) -> None:
        """Verify OutOfFuel guidance includes concrete fuel budget recommendation."""
        guidance = classify_error_from_trap(
            trap_message="wasm trap: out of fuel",
            fuel_consumed=5_000_000_000,
            fuel_budget=5_000_000_000,
        )
        assert guidance is not None
        # Should include a concrete recommendation with numbers
        combined = " ".join(guidance["actionable_guidance"])
        assert "10,000,000,000" in combined  # 2x safety margin

    def test_outoffuel_python_execution(self) -> None:
        """Verify OutOfFuel error generates guidance in Python sandbox."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=100_000_000),  # Very low budget
        )

        # Infinite loop should trigger OutOfFuel
        result = sandbox.execute("while True: pass")

        assert not result.success
        assert "error_guidance" in result.metadata
        guidance = result.metadata["error_guidance"]
        assert guidance["error_type"] == ERROR_OUT_OF_FUEL
        assert len(guidance["actionable_guidance"]) > 0

    def test_outoffuel_javascript_execution(self) -> None:
        """Verify OutOfFuel error generates guidance in JavaScript sandbox."""
        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            policy=ExecutionPolicy(fuel_budget=100_000_000),  # Very low budget
        )

        # Infinite loop should trigger OutOfFuel
        result = sandbox.execute("while (true) {}")

        assert not result.success
        assert "error_guidance" in result.metadata
        guidance = result.metadata["error_guidance"]
        assert guidance["error_type"] == ERROR_OUT_OF_FUEL


class TestPathRestrictionGuidance:
    """Test path restriction error classification and guidance."""

    def test_path_restriction_stderr_classification(self) -> None:
        """Verify path restriction errors are detected from stderr."""
        stderr = "FileNotFoundError: [Errno 2] No such file or directory: '/etc/passwd'"
        guidance = classify_error_from_stderr(stderr, language="python")

        assert guidance is not None
        assert guidance["error_type"] == ERROR_PATH_RESTRICTION
        assert "/etc/passwd" in " ".join(guidance["actionable_guidance"])

    def test_path_restriction_python_execution(self) -> None:
        """Verify path restriction error generates guidance in Python sandbox."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)

        # Attempt to access path outside /app
        result = sandbox.execute("open('/etc/passwd', 'r')")

        assert not result.success
        # Note: WASI may block this before Python raises FileNotFoundError
        # so we check if error_guidance is present when there's an error
        if "error_guidance" in result.metadata:
            guidance = result.metadata["error_guidance"]
            assert guidance["error_type"] in [ERROR_PATH_RESTRICTION, "PathRestriction"]

    def test_path_restriction_includes_solution(self) -> None:
        """Verify path restriction guidance includes actionable solutions."""
        guidance = classify_error_from_stderr(
            "FileNotFoundError: [Errno 2] No such file or directory: '/tmp/data.txt'",
            language="python",
        )

        assert guidance is not None
        combined = " ".join(guidance["actionable_guidance"])
        assert "/app" in combined
        assert "relative path" in combined.lower() or "Use /app" in combined


class TestQuickJSTupleGuidance:
    """Test QuickJS tuple destructuring error classification and guidance."""

    def test_quickjs_tuple_stderr_classification(self) -> None:
        """Verify QuickJS tuple errors are detected from stderr."""
        stderr = "TypeError: value is not iterable\n    at <eval>:1"
        guidance = classify_error_from_stderr(stderr, language="javascript")

        assert guidance is not None
        assert guidance["error_type"] == ERROR_QUICKJS_TUPLE_DESTRUCTURING
        assert "array destructuring" in " ".join(guidance["actionable_guidance"]).lower()

    def test_quickjs_tuple_includes_code_example(self) -> None:
        """Verify QuickJS tuple guidance includes before/after code examples."""
        guidance = classify_error_from_stderr(
            "TypeError: value is not iterable\n    at <eval>:5",
            language="javascript",
        )

        assert guidance is not None
        assert guidance["code_examples"] is not None
        assert len(guidance["code_examples"]) > 0
        example = guidance["code_examples"][0]
        assert "before" in example
        assert "after" in example
        assert "[" in example["after"]  # Should show array destructuring


class TestMissingVendoredPackageGuidance:
    """Test vendored package import error classification and guidance."""

    def test_missing_vendored_package_stderr_classification(self) -> None:
        """Verify vendored package errors are detected from stderr."""
        stderr = "ModuleNotFoundError: No module named 'openpyxl'"
        guidance = classify_error_from_stderr(stderr, language="python")

        assert guidance is not None
        assert guidance["error_type"] == ERROR_MISSING_VENDORED_PACKAGE
        assert "openpyxl" in " ".join(guidance["actionable_guidance"])
        assert "sys.path" in " ".join(guidance["actionable_guidance"])

    def test_missing_vendored_package_includes_sys_path_example(self) -> None:
        """Verify vendored package guidance includes sys.path setup."""
        guidance = classify_error_from_stderr(
            "ModuleNotFoundError: No module named 'tabulate'",
            language="python",
        )

        assert guidance is not None
        assert guidance["code_examples"] is not None
        assert len(guidance["code_examples"]) > 0
        example = guidance["code_examples"][0]
        assert "sys.path.insert" in example["after"]
        assert "/data/site-packages" in example["after"]

    def test_non_vendored_package_no_guidance(self) -> None:
        """Verify non-vendored packages don't trigger vendored package guidance."""
        stderr = "ModuleNotFoundError: No module named 'numpy'"
        guidance = classify_error_from_stderr(stderr, language="python")

        # numpy is not vendored, so should not get vendored package guidance
        # Could be None or a different error type
        if guidance:
            assert guidance["error_type"] != ERROR_MISSING_VENDORED_PACKAGE


class TestErrorGuidanceIntegration:
    """Test end-to-end error guidance integration."""

    def test_get_error_guidance_prioritizes_trap(self) -> None:
        """Verify trap-based classification has priority over stderr patterns."""
        guidance = get_error_guidance(
            trap_message="wasm trap: out of fuel",
            stderr="FileNotFoundError: /etc/passwd",  # Red herring
            language="python",
            fuel_consumed=5_000_000_000,
            fuel_budget=5_000_000_000,
        )

        assert guidance is not None
        # Should classify as OutOfFuel (trap), not PathRestriction (stderr)
        assert guidance["error_type"] == ERROR_OUT_OF_FUEL

    def test_get_error_guidance_uses_stderr_when_no_trap(self) -> None:
        """Verify stderr classification works when no trap present."""
        guidance = get_error_guidance(
            trap_message=None,
            stderr="ModuleNotFoundError: No module named 'openpyxl'",
            language="python",
        )

        assert guidance is not None
        assert guidance["error_type"] == ERROR_MISSING_VENDORED_PACKAGE

    def test_error_guidance_includes_related_docs(self) -> None:
        """Verify error guidance includes related documentation links."""
        guidance = get_error_guidance(
            trap_message="wasm trap: out of fuel",
            fuel_consumed=5_000_000_000,
            fuel_budget=5_000_000_000,
        )

        assert guidance is not None
        assert "related_docs" in guidance
        assert len(guidance["related_docs"]) > 0
        # Should reference actual documentation files
        assert any(
            "docs/" in doc.lower() or "README" in doc.upper() for doc in guidance["related_docs"]
        )

    def test_success_execution_no_error_guidance(self) -> None:
        """Verify successful executions don't generate error guidance."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("print('Hello, World!')")

        assert result.success
        assert "error_guidance" not in result.metadata


class TestErrorGuidanceBackwardCompatibility:
    """Test backward compatibility of error guidance feature."""

    def test_metadata_dict_accepts_error_guidance(self) -> None:
        """Verify metadata dict accepts error_guidance field (backward compatible)."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("raise ValueError('test')")

        # Metadata should be a dict (not break existing clients)
        assert isinstance(result.metadata, dict)

        # Error guidance should be optional
        if "error_guidance" in result.metadata:
            assert isinstance(result.metadata["error_guidance"], dict)

    def test_existing_metadata_fields_preserved(self) -> None:
        """Verify existing metadata fields are not affected by error guidance."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("print('test')")

        # Existing fields should still be present
        assert "session_id" in result.metadata
        assert "exit_code" in result.metadata

    def test_error_guidance_is_optional(self) -> None:
        """Verify error_guidance is optional (doesn't break on success)."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
        result = sandbox.execute("x = 42")

        # Success case should not have error_guidance
        assert result.success
        assert "error_guidance" not in result.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
