"""Integration test for session file operations round-trip workflow.

This test demonstrates the complete workflow of:
1. Creating input files from the host side
2. Executing sandbox code that reads those files
3. Sandbox code writing output files
4. Reading the output files from the host side
5. Listing all files in the session
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from sandbox import (
    RuntimeType,
    create_sandbox,
    list_session_files,
    read_session_file,
    write_session_file,
)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create temporary workspace root for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for each test."""
    return str(uuid.uuid4())


class TestSessionFileRoundtrip:
    """Integration tests for complete host-guest file workflows."""

    def test_host_to_guest_to_host_text_file(
        self, temp_workspace: Path
    ) -> None:
        """Complete workflow: write from host, process in guest, read from host."""
        # Create session
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
        )
        session_id = sandbox.session_id

        # Write input file from host
        input_data = "Hello from host side"
        write_session_file(
            session_id, "input.txt", input_data, workspace_root=temp_workspace
        )

        # Execute code that reads input and writes output
        code = """
with open('/app/input.txt', 'r') as f:
    data = f.read()
    
# Process: uppercase and reverse
processed = data.upper()[::-1]

with open('/app/output.txt', 'w') as f:
    f.write(processed)
    
print(f"Processed {len(data)} characters")
"""
        result = sandbox.execute(code)

        # Verify execution succeeded
        assert result.success
        assert "Processed 20 characters" in result.stdout

        # Read output file from host
        output_data = read_session_file(
            session_id, "output.txt", workspace_root=temp_workspace
        )
        assert output_data.decode("utf-8") == "EDIS TSOH MORF OLLEH"

        # List all files
        files = list_session_files(session_id, workspace_root=temp_workspace)
        assert "input.txt" in files
        assert "output.txt" in files
        assert "user_code.py" in files  # Created by sandbox

    def test_host_writes_config_guest_reads_and_generates_output(
        self, temp_workspace: Path
    ) -> None:
        """Host provides JSON config, guest processes and creates multiple outputs."""
        # Create session
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
        )
        session_id = sandbox.session_id

        # Write configuration from host
        config_json = '{"name": "test", "count": 3, "prefix": "item"}'
        write_session_file(
            session_id, "config.json", config_json, workspace_root=temp_workspace
        )

        # Execute code that reads config and generates multiple files
        code = """
import json

with open('/app/config.json', 'r') as f:
    config = json.load(f)
    
# Generate files based on config
for i in range(config['count']):
    filename = f"/app/{config['prefix']}_{i}.txt"
    with open(filename, 'w') as f:
        f.write(f"{config['name']} - {config['prefix']} {i}\\n")
        
print(f"Generated {config['count']} files")
"""
        result = sandbox.execute(code)

        # Verify execution
        assert result.success
        assert "Generated 3 files" in result.stdout

        # List and verify all generated files
        files = list_session_files(
            session_id, workspace_root=temp_workspace, pattern="item_*.txt"
        )
        assert len(files) == 3
        assert "item_0.txt" in files
        assert "item_1.txt" in files
        assert "item_2.txt" in files

        # Read one of the generated files
        item_0_data = read_session_file(
            session_id, "item_0.txt", workspace_root=temp_workspace
        )
        assert item_0_data.decode("utf-8") == "test - item 0\n"

    def test_binary_file_roundtrip(self, temp_workspace: Path) -> None:
        """Binary data can be written by host, processed by guest, read by host."""
        # Create session
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
        )
        session_id = sandbox.session_id

        # Write binary data from host
        binary_input = bytes(range(256))  # All byte values 0-255
        write_session_file(
            session_id, "data.bin", binary_input, workspace_root=temp_workspace
        )

        # Execute code that reads binary, transforms it, writes output
        code = """
with open('/app/data.bin', 'rb') as f:
    data = f.read()
    
# Transform: XOR with 0xFF (bitwise NOT)
transformed = bytes(b ^ 0xFF for b in data)

with open('/app/transformed.bin', 'wb') as f:
    f.write(transformed)
    
print(f"Transformed {len(data)} bytes")
"""
        result = sandbox.execute(code)

        # Verify execution
        assert result.success
        assert "Transformed 256 bytes" in result.stdout

        # Read and verify transformed output
        output_binary = read_session_file(
            session_id, "transformed.bin", workspace_root=temp_workspace
        )
        expected = bytes(b ^ 0xFF for b in range(256))
        assert output_binary == expected

    def test_nested_directory_structure(self, temp_workspace: Path) -> None:
        """Files can be organized in nested directories."""
        # Create session
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
        )
        session_id = sandbox.session_id

        # Write input in nested directory from host
        write_session_file(
            session_id,
            "inputs/data/config.txt",
            "nested input",
            workspace_root=temp_workspace,
        )

        # Execute code that reads nested input and writes nested output
        code = """
with open('/app/inputs/data/config.txt', 'r') as f:
    data = f.read()
    
# Create nested output structure
import os
os.makedirs('/app/outputs/results', exist_ok=True)

with open('/app/outputs/results/summary.txt', 'w') as f:
    f.write(f"Processed: {data.upper()}")
    
print("Created nested output")
"""
        result = sandbox.execute(code)

        # Verify execution
        assert result.success
        assert "Created nested output" in result.stdout

        # List all files with nested paths
        files = list_session_files(session_id, workspace_root=temp_workspace)
        assert "inputs/data/config.txt" in files
        assert "outputs/results/summary.txt" in files

        # Read nested output
        output = read_session_file(
            session_id, "outputs/results/summary.txt", workspace_root=temp_workspace
        )
        assert output.decode("utf-8") == "Processed: NESTED INPUT"

    def test_multi_turn_with_file_persistence(self, temp_workspace: Path) -> None:
        """Files persist across multiple executions in same session."""
        # Create session
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
        )
        session_id = sandbox.session_id

        # Turn 1: Write initial state file from host
        write_session_file(
            session_id, "state.txt", "0", workspace_root=temp_workspace
        )

        # Turn 2: Guest reads, increments, writes
        code_turn_1 = """
with open('/app/state.txt', 'r') as f:
    count = int(f.read())
    
count += 1

with open('/app/state.txt', 'w') as f:
    f.write(str(count))
    
print(f"Count: {count}")
"""
        result1 = sandbox.execute(code_turn_1)
        assert result1.success
        assert "Count: 1" in result1.stdout

        # Turn 3: Guest reads again, increments again
        result2 = sandbox.execute(code_turn_1)
        assert result2.success
        assert "Count: 2" in result2.stdout

        # Turn 4: Host reads final state
        final_state = read_session_file(
            session_id, "state.txt", workspace_root=temp_workspace
        )
        assert final_state.decode("utf-8") == "2"

    def test_list_files_discovers_guest_created_files(
        self, temp_workspace: Path
    ) -> None:
        """Host can discover files created by guest without prior knowledge."""
        # Create session
        sandbox = create_sandbox(
            runtime=RuntimeType.PYTHON,
            workspace_root=temp_workspace,
        )
        session_id = sandbox.session_id

        # Execute code that creates unknown files
        code = """
import random

# Create random number of files with random names
count = random.randint(3, 7)
for i in range(count):
    filename = f"/app/random_{i}_{random.randint(1000,9999)}.txt"
    with open(filename, 'w') as f:
        f.write(f"Random file {i}")
        
print(f"Created {count} files")
"""
        result = sandbox.execute(code)
        assert result.success

        # Host discovers all files using list
        all_files = list_session_files(session_id, workspace_root=temp_workspace)

        # Filter to random files only
        random_files = [f for f in all_files if f.startswith("random_")]
        assert len(random_files) >= 3
        assert len(random_files) <= 7

        # Host can read each discovered file
        for filename in random_files:
            data = read_session_file(
                session_id, filename, workspace_root=temp_workspace
            )
            assert b"Random file" in data
