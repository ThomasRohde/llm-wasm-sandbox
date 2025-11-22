#!/usr/bin/env python
"""Performance benchmark for sandbox API."""

from __future__ import annotations

import time
from pathlib import Path

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox

# Simple test code that exercises common operations
TEST_CODE = """
import json
import math

# Perform some computations
result = sum(x**2 for x in range(1000))
data = {'result': result, 'sqrt': math.sqrt(result)}

# Write output
with open('/app/test_output.json', 'w') as f:
    json.dump(data, f)

print(f"Computed: {result}")
"""

def benchmark_api(iterations: int = 10) -> tuple[float, list[float]]:
    """Benchmark the create_sandbox() API."""
    import time as time_module
    times = []
    policy = ExecutionPolicy()

    for _ in range(iterations):
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)

        start = time.perf_counter()
        _ = sandbox.execute(TEST_CODE)
        duration = time.perf_counter() - start
        times.append(duration)

        # Clean up - add delay for Windows file locking
        output_file = Path("workspace/test_output.json")
        if output_file.exists():
            time_module.sleep(0.1)  # Brief delay for file handles to release
            try:
                output_file.unlink()
            except PermissionError:
                pass  # File still locked, skip cleanup

    return sum(times) / len(times), times

def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║ Performance Benchmark: Sandbox API              ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    iterations = 10
    print(f"Running {iterations} iterations...\n")

    # Warmup
    print("Warming up...")
    sandbox = create_sandbox(runtime=RuntimeType.PYTHON)
    sandbox.execute("print('warmup')")

    print("\n" + "─" * 52)
    print("Sandbox API (create_sandbox)")
    print("─" * 52)
    avg_time, times = benchmark_api(iterations)
    min_time = min(times)
    max_time = max(times)
    std_dev = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5

    print(f"  Average:  {avg_time:.4f}s")
    print(f"  Min:      {min_time:.4f}s")
    print(f"  Max:      {max_time:.4f}s")
    print(f"  Std Dev:  {std_dev:.4f}s")

    print("\n" + "═" * 52)
    print("Performance Summary")
    print("═" * 52)

    # Calculate throughput
    throughput = 1.0 / avg_time
    print(f"  Throughput:     {throughput:.2f} executions/second")
    print(f"  Consistency:    {(std_dev / avg_time) * 100:.1f}% variance")
    print()

    print("✓ Benchmark completed successfully")
    return 0

if __name__ == "__main__":
    exit(main())
