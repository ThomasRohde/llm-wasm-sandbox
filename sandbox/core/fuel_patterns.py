"""Fuel consumption pattern detection and budget recommendation logic.

Provides utilities for analyzing fuel usage patterns, detecting heavy package
imports, and generating actionable recommendations for fuel budget adjustments.
"""

from __future__ import annotations

import re
from typing import Any

# Package fuel requirements (first import, in billions of instructions)
PACKAGE_FUEL_REQUIREMENTS = {
    # Document processing (heavy)
    "openpyxl": (5, 7),  # 5-7B
    "PyPDF2": (5, 6),  # 5-6B
    "jinja2": (5, 10),  # 5-10B (varies by template complexity)
    # Text/data (moderate)
    "tabulate": (2, 2),  # ~2B
    "markdown": (2, 2),  # ~2B
    "python-dateutil": (2, 2),  # ~2B
    # Standard library (light)
    "json": (0.1, 0.2),
    "csv": (0.1, 0.2),
    "pathlib": (0.1, 0.2),
}


def detect_heavy_packages(stderr: str) -> list[str]:
    """Detect heavy package imports from stderr output.

    Scans stderr for import statements or package mentions that indicate
    heavy package usage requiring significant fuel budgets.

    Args:
        stderr: Captured stderr output from execution

    Returns:
        List of detected heavy package names
    """
    detected = []

    for package, (_min_fuel, max_fuel) in PACKAGE_FUEL_REQUIREMENTS.items():
        # Skip light packages (< 1B fuel)
        if max_fuel < 1:
            continue

        # Check for various import patterns
        patterns = [
            rf"\bimport\s+{re.escape(package)}\b",
            rf"\bfrom\s+{re.escape(package)}\b",
            rf"\b{re.escape(package)}\b.*imported",
        ]

        for pattern in patterns:
            if re.search(pattern, stderr, re.IGNORECASE):
                detected.append(package)
                break

    return detected


def detect_large_dataset_processing(fuel_consumed: int, detected_packages: list[str]) -> bool:
    """Heuristic to detect large dataset processing based on high fuel usage.

    Args:
        fuel_consumed: Number of instructions executed
        detected_packages: List of detected heavy packages

    Returns:
        True if likely processing large datasets (high fuel, no heavy packages)
    """
    # High fuel consumption (> 3B) without heavy packages suggests
    # large dataset processing or complex computation
    high_fuel_threshold = 3_000_000_000
    return fuel_consumed > high_fuel_threshold and not detected_packages


def analyze_fuel_usage(
    consumed: int | None,
    budget: int,
    stderr: str = "",
    is_cached_import: bool = False,
) -> dict[str, Any]:
    """Analyze fuel consumption and generate status and recommendations.

    Args:
        consumed: Instructions executed (None if not tracked)
        budget: Total fuel budget allocated
        stderr: Stderr output for pattern detection
        is_cached_import: Whether imports are cached in session

    Returns:
        Fuel analysis dict with consumed, budget, utilization_percent,
        status, recommendation, and likely_causes fields
    """
    # Handle cases where fuel wasn't tracked
    if consumed is None:
        return {
            "consumed": 0,
            "budget": budget,
            "utilization_percent": 0.0,
            "status": "unknown",
            "recommendation": "Fuel tracking not enabled",
            "likely_causes": [],
        }

    # Calculate utilization
    utilization_percent = (consumed / budget * 100) if budget > 0 else 0.0

    # Classify status based on thresholds
    if utilization_percent >= 100:
        status = "exhausted"
    elif utilization_percent >= 90:
        status = "critical"
    elif utilization_percent >= 75:
        status = "warning"
    elif utilization_percent >= 50:
        status = "moderate"
    else:
        status = "efficient"

    # Detect patterns
    detected_packages = detect_heavy_packages(stderr)
    is_large_dataset = detect_large_dataset_processing(consumed, detected_packages)

    # Build likely causes
    likely_causes = []
    if detected_packages:
        packages_str = ", ".join(detected_packages)
        likely_causes.append(f"Heavy package imports detected: {packages_str}")
        if is_cached_import:
            likely_causes.append("Note: Subsequent imports in this session will be faster (cached)")
    if is_large_dataset:
        likely_causes.append(
            "High fuel usage suggests large dataset processing or complex computation"
        )

    # Generate recommendation
    recommendation = _generate_recommendation(
        status=status,
        consumed=consumed,
        budget=budget,
        utilization_percent=utilization_percent,
        detected_packages=detected_packages,
        is_cached_import=is_cached_import,
    )

    return {
        "consumed": consumed,
        "budget": budget,
        "utilization_percent": round(utilization_percent, 2),
        "status": status,
        "recommendation": recommendation,
        "likely_causes": likely_causes,
    }


def _generate_recommendation(
    status: str,
    consumed: int,
    budget: int,
    utilization_percent: float,
    detected_packages: list[str],
    is_cached_import: bool,
) -> str:
    """Generate concrete fuel budget recommendation based on usage patterns.

    Args:
        status: Fuel status classification
        consumed: Instructions executed
        budget: Current fuel budget
        utilization_percent: Usage percentage
        detected_packages: Detected heavy packages
        is_cached_import: Whether imports are cached

    Returns:
        Actionable recommendation text
    """
    if status == "efficient":
        return "Fuel budget is appropriate for this workload"

    if status == "moderate":
        return (
            f"Fuel usage is moderate ({utilization_percent:.1f}%). "
            "Current budget is adequate, but consider increasing if similar tasks are planned"
        )

    # For warning, critical, and exhausted statuses, provide concrete numbers
    # Use 50-100% safety margin
    safety_margin = 1.5 if status == "warning" else 2.0
    suggested_budget = int(consumed * safety_margin)

    # Round to nearest billion for readability (minimum 1B)
    suggested_budget_b = max(1, round(suggested_budget / 1_000_000_000))

    recommendation_parts = []

    if status == "exhausted":
        recommendation_parts.append(
            f"⚠️ Fuel budget exhausted! Increase to at least {suggested_budget_b}B instructions "
            f"(current: {budget / 1_000_000_000:.0f}B, consumed: {consumed / 1_000_000_000:.1f}B)"
        )
    elif status == "critical":
        recommendation_parts.append(
            f"🚨 Fuel usage is critical ({utilization_percent:.1f}%). "
            f"Increase budget to {suggested_budget_b}B instructions to avoid exhaustion "
            f"(current: {budget / 1_000_000_000:.0f}B)"
        )
    else:  # warning
        recommendation_parts.append(
            f"⚠️ Fuel usage is high ({utilization_percent:.1f}%). "
            f"Consider increasing budget to {suggested_budget_b}B instructions for similar tasks "
            f"(current: {budget / 1_000_000_000:.0f}B)"
        )

    # Add package-specific guidance
    if detected_packages:
        package_guidance = []
        for package in detected_packages:
            if package in PACKAGE_FUEL_REQUIREMENTS:
                min_fuel, max_fuel = PACKAGE_FUEL_REQUIREMENTS[package]
                package_guidance.append(
                    f"{package} requires {min_fuel}-{max_fuel}B for first import"
                )

        if package_guidance:
            recommendation_parts.append("Package fuel requirements: " + "; ".join(package_guidance))

        # Always suggest persistent sessions for heavy packages
        if not is_cached_import:
            recommendation_parts.append(
                "Note: Using a persistent session will cache imports, "
                "reducing fuel needs for subsequent executions"
            )

    return ". ".join(recommendation_parts)
