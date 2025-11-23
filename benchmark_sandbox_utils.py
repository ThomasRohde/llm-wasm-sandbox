"""
Performance benchmarks for sandbox_utils operations.

Measures fuel consumption for common operations with varying data sizes.
"""

import json

from sandbox import ExecutionPolicy, RuntimeType, create_sandbox


def benchmark_find():
    """Benchmark find() with different file counts."""
    print("=" * 80)
    print("Benchmarking find() operation")
    print("=" * 80)

    scenarios = [
        ("10 files", 10),
        ("100 files", 100),
        ("1000 files", 1000),
    ]

    results = []

    for scenario_name, file_count in scenarios:
        code = f"""
from sandbox_utils import mkdir, touch, find

# Create test structure with {file_count} files
for i in range({file_count}):
    dir_path = f"/app/test/dir{{i // 10}}"
    mkdir(dir_path, parents=True)
    touch(f"{{dir_path}}/file{{i}}.py")

# Benchmark find operation
found = find("*.py", "/app/test", recursive=True)
print(f"Found {{len(found)}} files")
"""

        # Use higher fuel budget for larger file counts
        fuel_budget = 5_000_000_000 if file_count >= 1000 else 2_000_000_000
        policy = ExecutionPolicy(fuel_budget=fuel_budget, memory_bytes=128 * 1024 * 1024)
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
        result = sandbox.execute(code)

        if result.success:
            fuel_millions = result.fuel_consumed / 1_000_000
            print(f"[OK] {scenario_name}: {fuel_millions:.1f}M instructions")
            results.append(
                {
                    "scenario": scenario_name,
                    "fuel_consumed": result.fuel_consumed,
                    "fuel_millions": f"{fuel_millions:.1f}M",
                    "success": True,
                }
            )
        else:
            print(f"[FAIL] {scenario_name}: FAILED")
            print(f"  Error: {result.stderr[:200]}")
            results.append(
                {"scenario": scenario_name, "success": False, "error": result.stderr[:200]}
            )

    print()
    return results


def benchmark_grep():
    """Benchmark grep() with different text sizes."""
    print("=" * 80)
    print("Benchmarking grep() operation")
    print("=" * 80)

    scenarios = [
        ("1KB text", 1024),
        ("1MB text", 1024 * 1024),
        ("10MB text", 10 * 1024 * 1024),
    ]

    results = []

    for scenario_name, text_size in scenarios:
        code = f"""
from sandbox_utils import grep, mkdir, echo

# Create test file with ~{text_size} bytes
mkdir("/app/test", parents=True)
lines = []
line_template = "This is line {{}} with some searchable text and pattern matches"
target_size = {text_size}
line_size = len(line_template.format(0)) + 1  # +1 for newline

num_lines = target_size // line_size
for i in range(num_lines):
    lines.append(line_template.format(i))

echo("\\n".join(lines), file="/app/test/large.txt")

# Benchmark grep operation
matches = grep(r"pattern", ["/app/test/large.txt"], regex=True)
print(f"Found {{len(matches)}} matches in {{num_lines}} lines")
"""

        # Use higher fuel budget for larger text sizes
        if text_size >= 10 * 1024 * 1024:
            fuel_budget = 20_000_000_000
        elif text_size >= 1024 * 1024:
            fuel_budget = 10_000_000_000
        else:
            fuel_budget = 2_000_000_000

        policy = ExecutionPolicy(fuel_budget=fuel_budget, memory_bytes=256 * 1024 * 1024)
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
        result = sandbox.execute(code)

        if result.success:
            fuel_millions = result.fuel_consumed / 1_000_000
            print(f"[OK] {scenario_name}: {fuel_millions:.1f}M instructions")
            results.append(
                {
                    "scenario": scenario_name,
                    "fuel_consumed": result.fuel_consumed,
                    "fuel_millions": f"{fuel_millions:.1f}M",
                    "success": True,
                }
            )
        else:
            print(f"[FAIL] {scenario_name}: FAILED")
            print(f"  Error: {result.stderr[:200]}")
            results.append(
                {"scenario": scenario_name, "success": False, "error": result.stderr[:200]}
            )

    print()
    return results


def benchmark_csv_to_json():
    """Benchmark csv_to_json() with different row counts."""
    print("=" * 80)
    print("Benchmarking csv_to_json() operation")
    print("=" * 80)

    scenarios = [
        ("100 rows", 100),
        ("1K rows", 1000),
        ("10K rows", 10000),
    ]

    results = []

    for scenario_name, row_count in scenarios:
        code = f"""
from sandbox_utils import csv_to_json, mkdir, echo
import json

# Create CSV file with {row_count} rows
mkdir("/app/test", parents=True)
lines = ["id,name,value,status,category"]
for i in range({row_count}):
    lines.append(f"{{i}},Item{{i}},{{i*10}},active,cat{{i%5}}")

echo("\\n".join(lines), file="/app/test/data.csv")

# Benchmark conversion (returns None when output is provided)
csv_to_json("/app/test/data.csv", output="/app/test/data.json")

# Verify by reading the output
with open("/app/test/data.json", "r") as f:
    result = json.load(f)
    
print(f"Converted {{len(result)}} rows")
"""

        # Use higher fuel budget for larger datasets
        fuel_budget = 5_000_000_000 if row_count >= 10000 else 2_000_000_000
        policy = ExecutionPolicy(fuel_budget=fuel_budget, memory_bytes=256 * 1024 * 1024)
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
        result = sandbox.execute(code)

        if result.success:
            fuel_millions = result.fuel_consumed / 1_000_000
            print(f"[OK] {scenario_name}: {fuel_millions:.1f}M instructions")
            results.append(
                {
                    "scenario": scenario_name,
                    "fuel_consumed": result.fuel_consumed,
                    "fuel_millions": f"{fuel_millions:.1f}M",
                    "success": True,
                }
            )
        else:
            print(f"[FAIL] {scenario_name}: FAILED")
            print(f"  Error: {result.stderr[:200]}")
            results.append(
                {"scenario": scenario_name, "success": False, "error": result.stderr[:200]}
            )

    print()
    return results


def benchmark_tree():
    """Benchmark tree() with different directory counts."""
    print("=" * 80)
    print("Benchmarking tree() operation")
    print("=" * 80)

    scenarios = [
        ("10 directories", 10),
        ("100 directories", 100),
        ("500 directories", 500),
    ]

    results = []

    for scenario_name, dir_count in scenarios:
        code = f"""
from sandbox_utils import mkdir, touch, tree

# Create nested directory structure with {dir_count} directories
for i in range({dir_count}):
    # Create nested paths like /app/test/d0/d1/d2/...
    depth = i % 5
    path_parts = [f"d{{j}}" for j in range(depth + 1)]
    dir_path = "/app/test/" + "/".join(path_parts) + f"/dir{{i}}"
    mkdir(dir_path, parents=True)
    
    # Add some files
    touch(f"{{dir_path}}/file1.txt")
    touch(f"{{dir_path}}/file2.py")

# Benchmark tree operation
tree_output = tree("/app/test", max_depth=None)
lines = len(tree_output.split("\\n"))
print(f"Generated tree with {{lines}} lines for {dir_count} directories")
"""

        # Use higher fuel budget for larger directory counts
        fuel_budget = 10_000_000_000 if dir_count >= 500 else 5_000_000_000
        policy = ExecutionPolicy(fuel_budget=fuel_budget, memory_bytes=256 * 1024 * 1024)
        sandbox = create_sandbox(runtime=RuntimeType.PYTHON, policy=policy)
        result = sandbox.execute(code)

        if result.success:
            fuel_millions = result.fuel_consumed / 1_000_000
            print(f"[OK] {scenario_name}: {fuel_millions:.1f}M instructions")
            results.append(
                {
                    "scenario": scenario_name,
                    "fuel_consumed": result.fuel_consumed,
                    "fuel_millions": f"{fuel_millions:.1f}M",
                    "success": True,
                }
            )
        else:
            print(f"[FAIL] {scenario_name}: FAILED")
            print(f"  Error: {result.stderr[:200]}")
            results.append(
                {"scenario": scenario_name, "success": False, "error": result.stderr[:200]}
            )

    print()
    return results


def main():
    """Run all benchmarks and generate report."""
    print("\n" + "=" * 80)
    print("SANDBOX_UTILS PERFORMANCE BENCHMARKS")
    print("=" * 80)
    print()

    all_results = {}

    # Run benchmarks
    all_results["find"] = benchmark_find()
    all_results["grep"] = benchmark_grep()
    all_results["csv_to_json"] = benchmark_csv_to_json()
    all_results["tree"] = benchmark_tree()

    # Generate summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    for operation, results in all_results.items():
        print(f"\n{operation}():")
        for result in results:
            if result["success"]:
                print(f"  {result['scenario']:20s} → {result['fuel_millions']:>10s} instructions")
            else:
                print(f"  {result['scenario']:20s} → FAILED")

    # Save results to JSON
    with open("benchmark_results_sandbox_utils.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print("\n[OK] Benchmark results saved to benchmark_results_sandbox_utils.json")
    print()


if __name__ == "__main__":
    main()
