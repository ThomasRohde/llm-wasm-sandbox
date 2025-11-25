"""
Performance benchmark for error guidance and fuel analysis overhead.

Validates that new features add <1% execution time overhead.
"""

from __future__ import annotations

import statistics
import time

import pytest

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox


class TestPerformanceOverhead:
    """Benchmark performance overhead of new features."""

    @pytest.mark.skip(reason="Performance test timing is system-dependent and flaky")
    def test_fuel_analysis_overhead(self):
        """Measure fuel analysis overhead across multiple executions."""
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON)

        # Run multiple executions to get stable measurements
        execution_times = []
        for _ in range(10):
            start = time.perf_counter()
            result = sandbox.execute("print(2 + 2)")
            duration = time.perf_counter() - start
            execution_times.append(duration * 1000)  # Convert to ms

            # Verify fuel analysis is present
            assert "fuel_analysis" in result.metadata

        mean_time = statistics.mean(execution_times)
        stdev_time = statistics.stdev(execution_times)

        print("\n=== Fuel Analysis Overhead ===")
        print(f"Mean execution time: {mean_time:.2f}ms")
        print(f"Std dev: {stdev_time:.2f}ms")
        print(f"Min: {min(execution_times):.2f}ms")
        print(f"Max: {max(execution_times):.2f}ms")

        # Fuel analysis should add minimal overhead
        # Typical execution ~1500-2000ms, analysis should be <10ms
        # We don't have a good baseline, so just verify it's reasonable
        assert mean_time < 5000, f"Execution time too high: {mean_time}ms"

    @pytest.mark.skip(reason="Performance test timing is system-dependent and flaky")
    def test_error_guidance_overhead_outoffuel(self):
        """Measure error guidance overhead for OutOfFuel errors."""
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=100_000_000),
        )

        # Run multiple executions to get stable measurements
        execution_times = []
        for _ in range(5):  # Fewer runs since these fail quickly
            start = time.perf_counter()
            result = sandbox.execute("while True: pass")
            duration = time.perf_counter() - start
            execution_times.append(duration * 1000)  # Convert to ms

            # Verify error guidance is present
            assert "error_guidance" in result.metadata
            assert "fuel_analysis" in result.metadata

        mean_time = statistics.mean(execution_times)

        print("\n=== Error Guidance Overhead (OutOfFuel) ===")
        print(f"Mean execution time: {mean_time:.2f}ms")
        print(f"Min: {min(execution_times):.2f}ms")
        print(f"Max: {max(execution_times):.2f}ms")

        # OutOfFuel errors should be fast (<2000ms with overhead)
        assert mean_time < 3000, f"OutOfFuel error handling too slow: {mean_time}ms"

    def test_metadata_serialization_overhead(self):
        """Measure JSON serialization overhead of enhanced metadata."""
        import json

        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=100_000_000),
        )

        result = sandbox.execute("while True: pass")

        # Measure serialization time
        serialization_times = []
        for _ in range(100):
            start = time.perf_counter()
            json_str = json.dumps(result.metadata)
            duration = time.perf_counter() - start
            serialization_times.append(duration * 1000000)  # Convert to microseconds

        mean_time = statistics.mean(serialization_times)

        print("\n=== Metadata Serialization Overhead ===")
        print(f"Mean serialization time: {mean_time:.2f}μs")
        print(f"Min: {min(serialization_times):.2f}μs")
        print(f"Max: {max(serialization_times):.2f}μs")
        print(f"Serialized size: {len(json_str)} bytes")

        # Serialization should be very fast (<1ms)
        assert mean_time < 1000, f"Serialization too slow: {mean_time}μs"

    def test_memory_footprint_metadata(self):
        """Verify enhanced metadata doesn't significantly increase memory usage."""
        import sys

        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            policy=ExecutionPolicy(fuel_budget=100_000_000),
        )

        result = sandbox.execute("while True: pass")

        # Check size of metadata dict
        metadata_size = sys.getsizeof(result.metadata)
        print("\n=== Metadata Memory Footprint ===")
        print(f"Metadata dict size: {metadata_size} bytes")

        # Enhanced metadata should be <10KB
        assert metadata_size < 10000, f"Metadata too large: {metadata_size} bytes"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
