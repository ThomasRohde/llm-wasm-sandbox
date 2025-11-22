"""
Performance testing script for session management features.

Benchmarks:
- Session creation time
- File operation performance
- Concurrent session handling
- Large file operations
"""

import time

from sandbox import (
    RuntimeType,
    create_session_sandbox,
    delete_session_workspace,
    list_session_files,
    read_session_file,
    write_session_file,
)


def benchmark(name: str, iterations: int = 1):
    """Simple benchmark decorator."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n{'=' * 70}")
            print(f"Benchmark: {name}")
            print(f"Iterations: {iterations}")
            print("=" * 70)

            start = time.perf_counter()
            for _ in range(iterations):
                result = func(*args, **kwargs)
            end = time.perf_counter()

            total_time = end - start
            avg_time = total_time / iterations

            print(f"Total time: {total_time:.4f}s")
            print(f"Average time: {avg_time:.6f}s ({avg_time * 1000:.2f}ms)")
            if iterations > 1:
                print(f"Throughput: {iterations / total_time:.2f} ops/sec")

            return result

        return wrapper

    return decorator


def test_session_creation_performance():
    """Benchmark session creation time."""

    @benchmark("Session Creation", iterations=10)
    def create_sessions():
        sessions = []
        for _ in range(10):
            session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON)
            sessions.append(session_id)
        return sessions

    sessions = create_sessions()
    print(f"✓ Created {len(sessions)} sessions")

    # Cleanup
    for session_id in sessions:
        delete_session_workspace(session_id)


def test_file_operation_performance():
    """Benchmark file write/read/list operations."""
    session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON)

    try:
        # Write performance
        @benchmark("Write 100 Small Files (1KB each)", iterations=1)
        def write_files():
            for i in range(100):
                write_session_file(
                    session_id, f"file_{i:03d}.txt", b"x" * 1024, overwrite=True
                )

        write_files()
        print("✓ Wrote 100 files")

        # List performance
        @benchmark("List Files (100 files)", iterations=10)
        def list_files():
            return list_session_files(session_id)

        files = list_files()
        print(f"✓ Listed {len(files)} files")

        # Read performance
        @benchmark("Read 100 Files", iterations=1)
        def read_files():
            for i in range(100):
                read_session_file(session_id, f"file_{i:03d}.txt")

        read_files()
        print("✓ Read 100 files")

    finally:
        delete_session_workspace(session_id)


def test_large_file_performance():
    """Benchmark large file operations."""
    session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON)

    try:
        # 10MB file
        large_data = b"x" * (10 * 1024 * 1024)

        @benchmark("Write 10MB File", iterations=3)
        def write_large():
            write_session_file(session_id, "large.bin", large_data, overwrite=True)

        write_large()
        print(f"✓ Wrote {len(large_data) / (1024 * 1024):.1f}MB file")

        @benchmark("Read 10MB File", iterations=3)
        def read_large():
            return read_session_file(session_id, "large.bin")

        data = read_large()
        print(f"✓ Read {len(data) / (1024 * 1024):.1f}MB file")

    finally:
        delete_session_workspace(session_id)


def test_concurrent_session_performance():
    """Test handling multiple concurrent sessions."""

    @benchmark("Create 100 Concurrent Sessions", iterations=1)
    def create_many_sessions():
        sessions = []
        for _ in range(100):
            session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON)
            sessions.append(session_id)
        return sessions

    sessions = create_many_sessions()
    print(f"✓ Created {len(sessions)} sessions")

    # Test writing to all sessions
    @benchmark("Write File to Each of 100 Sessions", iterations=1)
    def write_to_all():
        for i, session_id in enumerate(sessions):
            write_session_file(session_id, "data.txt", f"Session {i}".encode())

    write_to_all()
    print("✓ Wrote to all sessions")

    # Cleanup
    @benchmark("Delete 100 Sessions", iterations=1)
    def cleanup_all():
        for session_id in sessions:
            delete_session_workspace(session_id)

    cleanup_all()
    print("✓ Cleaned up all sessions")


def test_nested_directory_performance():
    """Test performance with nested directory structures."""
    session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON)

    try:

        @benchmark("Create Nested Directory Structure (5 levels, 20 files)", iterations=1)
        def create_nested():
            for level1 in range(2):
                for level2 in range(2):
                    for level3 in range(5):
                        path = f"dir{level1}/sub{level2}/deep{level3}/file.txt"
                        write_session_file(session_id, path, b"nested data")

        create_nested()

        files = list_session_files(session_id)
        print(f"✓ Created {len(files)} files in nested structure")

        @benchmark("List Nested Files", iterations=10)
        def list_nested():
            return list_session_files(session_id)

        list_nested()

    finally:
        delete_session_workspace(session_id)


def test_execution_with_session_performance():
    """Benchmark execution performance in session context."""
    session_id, sandbox = create_session_sandbox(runtime=RuntimeType.PYTHON)

    try:
        code = """
import json
data = {'x': 42, 'y': [1, 2, 3]}
with open('/app/result.json', 'w') as f:
    json.dump(data, f)
print('Done')
"""

        @benchmark("Execute Code in Session", iterations=10)
        def execute_code():
            return sandbox.execute(code)

        result = execute_code()
        print(f"✓ Executed code successfully (fuel: {result.fuel_consumed:,})")

    finally:
        delete_session_workspace(session_id)


def main():
    print("=" * 70)
    print("Session Management Performance Benchmarks")
    print("=" * 70)

    tests = [
        ("Session Creation", test_session_creation_performance),
        ("File Operations", test_file_operation_performance),
        ("Large Files", test_large_file_performance),
        ("Concurrent Sessions", test_concurrent_session_performance),
        ("Nested Directories", test_nested_directory_performance),
        ("Execution in Session", test_execution_with_session_performance),
    ]

    for name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print(f"\n❌ Test '{name}' failed: {e}")

    print("\n" + "=" * 70)
    print("Performance testing completed!")
    print("=" * 70)

    # Print summary
    print("\nPerformance Summary:")
    print("- Session creation should be < 1ms per session")
    print("- File operations should be < 10ms for small files")
    print("- 100 concurrent sessions should complete in < 1s")
    print("- List operations should scale linearly with file count")


if __name__ == "__main__":
    main()
