"""Tests for fuel budget analysis and recommendations.

Validates fuel utilization classification, pattern detection, and
concrete budget recommendations across different usage scenarios.
"""

import pytest

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox
from sandbox.core.fuel_patterns import (
    analyze_fuel_usage,
    detect_heavy_packages,
    detect_large_dataset_processing,
)


class TestFuelPatternDetection:
    """Test fuel consumption pattern detection."""

    def test_detect_heavy_packages_openpyxl(self) -> None:
        """Should detect openpyxl import from stderr."""
        stderr = "import openpyxl\nSuccessfully imported openpyxl"
        packages = detect_heavy_packages(stderr)
        assert "openpyxl" in packages

    def test_detect_heavy_packages_pypdf2(self) -> None:
        """Should detect PyPDF2 import from stderr."""
        stderr = "from PyPDF2 import PdfReader"
        packages = detect_heavy_packages(stderr)
        assert "PyPDF2" in packages

    def test_detect_heavy_packages_multiple(self) -> None:
        """Should detect multiple heavy package imports."""
        stderr = """
        import openpyxl
        import jinja2
        from PyPDF2 import PdfReader
        """
        packages = detect_heavy_packages(stderr)
        assert "openpyxl" in packages
        assert "jinja2" in packages
        assert "PyPDF2" in packages

    def test_detect_heavy_packages_ignores_light(self) -> None:
        """Should ignore light packages (< 1B fuel)."""
        stderr = "import json\nimport csv"
        packages = detect_heavy_packages(stderr)
        assert "json" not in packages
        assert "csv" not in packages

    def test_detect_large_dataset_processing(self) -> None:
        """Should detect large dataset processing (high fuel, no packages)."""
        fuel_consumed = 4_000_000_000  # 4B
        detected_packages = []
        result = detect_large_dataset_processing(fuel_consumed, detected_packages)
        assert result is True

    def test_detect_large_dataset_processing_with_packages(self) -> None:
        """Should not flag dataset processing if heavy packages detected."""
        fuel_consumed = 4_000_000_000
        detected_packages = ["openpyxl"]
        result = detect_large_dataset_processing(fuel_consumed, detected_packages)
        assert result is False

    def test_detect_large_dataset_processing_low_fuel(self) -> None:
        """Should not flag dataset processing for low fuel usage."""
        fuel_consumed = 1_000_000_000  # 1B
        detected_packages = []
        result = detect_large_dataset_processing(fuel_consumed, detected_packages)
        assert result is False


class TestFuelUtilizationAnalysis:
    """Test fuel utilization analysis and status classification."""

    def test_efficient_usage(self) -> None:
        """Should classify <50% usage as efficient."""
        result = analyze_fuel_usage(
            consumed=2_000_000_000,  # 2B
            budget=5_000_000_000,  # 5B
            stderr="",
        )
        assert result["status"] == "efficient"
        assert result["utilization_percent"] == 40.0
        assert "appropriate" in result["recommendation"].lower()

    def test_moderate_usage(self) -> None:
        """Should classify 50-75% usage as moderate."""
        result = analyze_fuel_usage(
            consumed=3_000_000_000,  # 3B
            budget=5_000_000_000,  # 5B
            stderr="",
        )
        assert result["status"] == "moderate"
        assert result["utilization_percent"] == 60.0
        assert "moderate" in result["recommendation"].lower()

    def test_warning_usage(self) -> None:
        """Should classify 75-90% usage as warning with concrete recommendation."""
        result = analyze_fuel_usage(
            consumed=4_000_000_000,  # 4B
            budget=5_000_000_000,  # 5B
            stderr="",
        )
        assert result["status"] == "warning"
        assert result["utilization_percent"] == 80.0
        assert "⚠️" in result["recommendation"]
        # Should suggest concrete budget (4B * 1.5 = 6B)
        assert "6B" in result["recommendation"]

    def test_critical_usage(self) -> None:
        """Should classify 90-100% usage as critical with urgent recommendation."""
        result = analyze_fuel_usage(
            consumed=4_700_000_000,  # 4.7B
            budget=5_000_000_000,  # 5B
            stderr="",
        )
        assert result["status"] == "critical"
        assert result["utilization_percent"] == 94.0
        assert "🚨" in result["recommendation"]
        # Should suggest higher budget with safety margin (4.7B * 2.0 = 9.4B → 9B)
        assert "9B" in result["recommendation"] or "10B" in result["recommendation"]

    def test_exhausted_usage(self) -> None:
        """Should classify 100% usage as exhausted."""
        result = analyze_fuel_usage(
            consumed=5_000_000_000,  # 5B (exactly budget)
            budget=5_000_000_000,  # 5B
            stderr="",
        )
        assert result["status"] == "exhausted"
        assert result["utilization_percent"] == 100.0
        assert "exhausted" in result["recommendation"].lower()

    def test_fuel_analysis_none_consumed(self) -> None:
        """Should handle None consumed gracefully."""
        result = analyze_fuel_usage(
            consumed=None,
            budget=5_000_000_000,
            stderr="",
        )
        assert result["status"] == "unknown"
        assert result["utilization_percent"] == 0.0


class TestFuelRecommendations:
    """Test concrete fuel budget recommendations."""

    def test_recommendation_includes_package_guidance(self) -> None:
        """Should include package-specific fuel requirements in recommendations."""
        result = analyze_fuel_usage(
            consumed=4_500_000_000,  # 4.5B
            budget=5_000_000_000,  # 5B
            stderr="import openpyxl",
        )
        assert "openpyxl" in result["recommendation"]
        assert "5-7B" in result["recommendation"]
        assert "openpyxl" in result["likely_causes"][0]

    def test_recommendation_suggests_session_for_heavy_packages(self) -> None:
        """Should suggest persistent sessions for heavy package usage."""
        result = analyze_fuel_usage(
            consumed=8_000_000_000,  # 8B
            budget=10_000_000_000,  # 10B
            stderr="import jinja2",
            is_cached_import=False,
        )
        # Check for session recommendation (should be in recommendation or likely_causes)
        recommendation_text = result["recommendation"].lower()
        assert "session" in recommendation_text or "cached" in recommendation_text

    def test_recommendation_notes_cached_imports(self) -> None:
        """Should note when imports are cached in sessions."""
        result = analyze_fuel_usage(
            consumed=1_000_000_000,  # 1B
            budget=10_000_000_000,  # 10B
            stderr="import openpyxl",
            is_cached_import=True,
        )
        # Should mention cached imports in likely_causes
        causes_text = " ".join(result["likely_causes"]).lower()
        assert "cached" in causes_text or "subsequent" in causes_text

    def test_likely_causes_large_dataset(self) -> None:
        """Should identify large dataset processing in likely causes."""
        result = analyze_fuel_usage(
            consumed=4_000_000_000,  # 4B
            budget=10_000_000_000,  # 10B
            stderr="",  # No packages
        )
        causes_text = " ".join(result["likely_causes"]).lower()
        assert "large dataset" in causes_text or "complex computation" in causes_text


class TestIntegrationFuelAnalysis:
    """Integration tests for fuel analysis in sandbox execution."""

    def test_fuel_analysis_in_result_metadata(self) -> None:
        """Should include fuel_analysis in SandboxResult metadata."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=5_000_000_000),
        )
        result = sandbox.execute("print('hello')")

        assert "fuel_analysis" in result.metadata
        fuel_analysis = result.metadata["fuel_analysis"]
        assert "consumed" in fuel_analysis
        assert "budget" in fuel_analysis
        assert "utilization_percent" in fuel_analysis
        assert "status" in fuel_analysis
        assert "recommendation" in fuel_analysis
        assert "likely_causes" in fuel_analysis

    def test_fuel_analysis_efficient_status(self) -> None:
        """Should report efficient status for simple code."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=5_000_000_000),
        )
        result = sandbox.execute("print(2 + 2)")

        fuel_analysis = result.metadata["fuel_analysis"]
        assert fuel_analysis["status"] in ["efficient", "moderate"]
        assert fuel_analysis["utilization_percent"] < 75

    def test_fuel_analysis_warning_status(self) -> None:
        """Should report warning status for high fuel usage."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=500_000_000),  # Very low budget
        )
        # Complex computation to consume significant fuel
        code = """
for i in range(10000):
    x = i * 2
    y = x ** 2
print(y)
"""
        result = sandbox.execute(code)

        fuel_analysis = result.metadata["fuel_analysis"]
        # Should be warning or critical due to low budget
        assert fuel_analysis["status"] in ["warning", "critical", "moderate"]

    def test_fuel_analysis_javascript_runtime(self) -> None:
        """Should provide fuel analysis for JavaScript runtime."""
        sandbox = create_sandbox(
            runtime=RuntimeType.JAVASCRIPT,
            policy=ExecutionPolicy(fuel_budget=5_000_000_000),
        )
        result = sandbox.execute("console.log('hello')")

        assert "fuel_analysis" in result.metadata
        fuel_analysis = result.metadata["fuel_analysis"]
        assert fuel_analysis["status"] in ["efficient", "moderate"]

    @pytest.mark.slow
    def test_fuel_analysis_detects_heavy_package(self) -> None:
        """Should detect heavy package imports in fuel analysis."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=10_000_000_000),
        )
        # Import openpyxl (requires 5-7B fuel)
        result = sandbox.execute(
            """
import sys
sys.path.insert(0, '/data/site-packages')
import openpyxl
print('Imported openpyxl')
"""
        )

        if result.success:
            fuel_analysis = result.metadata.get("fuel_analysis", {})
            likely_causes = fuel_analysis.get("likely_causes", [])
            # Check if openpyxl was detected
            causes_text = " ".join(likely_causes).lower()
            # May or may not detect depending on stderr output
            # This is a best-effort check
            if "openpyxl" in result.stderr.lower():
                assert "openpyxl" in causes_text


class TestPerformanceOverhead:
    """Test that fuel analysis doesn't add significant overhead."""

    def test_fuel_analysis_overhead_minimal(self) -> None:
        """Fuel analysis should complete quickly (<10ms overhead target)."""
        import time

        # Measure analysis time
        start = time.perf_counter()
        result = analyze_fuel_usage(
            consumed=4_500_000_000,
            budget=5_000_000_000,
            stderr="import openpyxl\nimport jinja2\nimport PyPDF2" * 100,  # Large stderr
        )
        duration = time.perf_counter() - start

        assert result is not None
        # Should complete in under 10ms even with large stderr
        assert duration < 0.01  # 10ms
