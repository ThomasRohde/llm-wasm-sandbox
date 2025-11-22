"""Tests for core Pydantic models and policy loading.

Tests ExecutionPolicy validation, SandboxResult creation, RuntimeType enum,
and load_policy() integration with TOML configuration.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from sandbox.core import (
    ExecutionPolicy,
    PolicyValidationError,
    RuntimeType,
    SandboxResult,
)
from sandbox.policies import DEFAULT_POLICY, load_policy


class TestRuntimeType:
    """Test RuntimeType enum values and behavior."""
    
    def test_python_runtime_type(self):
        """Test RuntimeType.PYTHON value."""
        assert RuntimeType.PYTHON == "python"
        assert RuntimeType.PYTHON.value == "python"
    
    def test_javascript_runtime_type(self):
        """Test RuntimeType.JAVASCRIPT value."""
        assert RuntimeType.JAVASCRIPT == "javascript"
        assert RuntimeType.JAVASCRIPT.value == "javascript"
    
    def test_enum_members(self):
        """Test all RuntimeType enum members."""
        members = list(RuntimeType)
        assert len(members) == 2
        assert RuntimeType.PYTHON in members
        assert RuntimeType.JAVASCRIPT in members


class TestExecutionPolicy:
    """Test ExecutionPolicy model validation and defaults."""
    
    def test_default_values(self):
        """Test ExecutionPolicy has correct default values."""
        policy = ExecutionPolicy()
        
        assert policy.fuel_budget == 2_000_000_000
        assert policy.memory_bytes == 128_000_000
        assert policy.stdout_max_bytes == 2_000_000
        assert policy.stderr_max_bytes == 1_000_000
        assert policy.mount_host_dir == "workspace"
        assert policy.guest_mount_path == "/app"
        assert policy.mount_data_dir is None
        assert policy.guest_data_path is None
        assert policy.argv == ["python", "-I", "/app/user_code.py", "-X", "utf8"]
        assert policy.timeout_seconds is None
        
        # Check default env vars
        assert "PYTHONUTF8" in policy.env
        assert policy.env["PYTHONUTF8"] == "1"
        assert "LC_ALL" in policy.env
        assert policy.env["PYTHONHASHSEED"] == "0"
    
    def test_custom_values(self):
        """Test ExecutionPolicy accepts custom values."""
        policy = ExecutionPolicy(
            fuel_budget=1_000_000,
            memory_bytes=64_000_000,
            stdout_max_bytes=500_000,
            stderr_max_bytes=250_000,
            mount_host_dir="custom_workspace",
            guest_mount_path="/custom",
            timeout_seconds=30.0,
        )
        
        assert policy.fuel_budget == 1_000_000
        assert policy.memory_bytes == 64_000_000
        assert policy.stdout_max_bytes == 500_000
        assert policy.stderr_max_bytes == 250_000
        assert policy.mount_host_dir == "custom_workspace"
        assert policy.guest_mount_path == "/custom"
        assert policy.timeout_seconds == 30.0
    
    def test_negative_fuel_budget_fails(self):
        """Test ExecutionPolicy rejects negative fuel_budget."""
        with pytest.raises(PolicyValidationError) as excinfo:
            ExecutionPolicy(fuel_budget=-100)
        
        assert "fuel_budget" in str(excinfo.value)
    
    def test_zero_fuel_budget_fails(self):
        """Test ExecutionPolicy rejects zero fuel_budget."""
        with pytest.raises(PolicyValidationError) as excinfo:
            ExecutionPolicy(fuel_budget=0)
        
        assert "fuel_budget" in str(excinfo.value)
    
    def test_negative_memory_bytes_fails(self):
        """Test ExecutionPolicy rejects negative memory_bytes."""
        with pytest.raises(PolicyValidationError) as excinfo:
            ExecutionPolicy(memory_bytes=-1000)
        
        assert "memory_bytes" in str(excinfo.value)
    
    def test_zero_memory_bytes_fails(self):
        """Test ExecutionPolicy rejects zero memory_bytes."""
        with pytest.raises(PolicyValidationError) as excinfo:
            ExecutionPolicy(memory_bytes=0)
        
        assert "memory_bytes" in str(excinfo.value)
    
    def test_negative_stdout_max_bytes_fails(self):
        """Test ExecutionPolicy rejects negative stdout_max_bytes."""
        with pytest.raises(PolicyValidationError) as excinfo:
            ExecutionPolicy(stdout_max_bytes=-500)
        
        assert "stdout_max_bytes" in str(excinfo.value)
    
    def test_negative_stderr_max_bytes_fails(self):
        """Test ExecutionPolicy rejects negative stderr_max_bytes."""
        with pytest.raises(PolicyValidationError) as excinfo:
            ExecutionPolicy(stderr_max_bytes=-500)
        
        assert "stderr_max_bytes" in str(excinfo.value)
    
    def test_negative_timeout_fails(self):
        """Test ExecutionPolicy rejects negative timeout_seconds."""
        with pytest.raises(PolicyValidationError) as excinfo:
            ExecutionPolicy(timeout_seconds=-10.0)
        
        assert "timeout_seconds" in str(excinfo.value)
    
    def test_zero_timeout_allowed(self):
        """Test ExecutionPolicy allows zero timeout_seconds."""
        policy = ExecutionPolicy(timeout_seconds=0.0)
        assert policy.timeout_seconds == 0.0
    
    def test_json_serialization(self):
        """Test ExecutionPolicy can be serialized to JSON."""
        policy = ExecutionPolicy(
            fuel_budget=1_000_000,
            memory_bytes=50_000_000,
        )
        
        json_str = policy.model_dump_json()
        data = json.loads(json_str)
        
        assert data["fuel_budget"] == 1_000_000
        assert data["memory_bytes"] == 50_000_000
        assert "env" in data
        assert isinstance(data["env"], dict)
    
    def test_json_deserialization(self):
        """Test ExecutionPolicy can be deserialized from JSON."""
        json_data = {
            "fuel_budget": 1_000_000,
            "memory_bytes": 50_000_000,
            "stdout_max_bytes": 1_000_000,
            "stderr_max_bytes": 500_000,
            "mount_host_dir": "workspace",
            "guest_mount_path": "/app",
            "argv": ["python", "-I", "/app/user_code.py"],
            "env": {"TEST": "value"},
        }
        
        policy = ExecutionPolicy(**json_data)
        
        assert policy.fuel_budget == 1_000_000
        assert policy.memory_bytes == 50_000_000
        assert policy.env["TEST"] == "value"
    
    def test_optional_data_mount(self):
        """Test ExecutionPolicy with optional secondary mount."""
        policy = ExecutionPolicy(
            mount_data_dir="/host/data",
            guest_data_path="/data",
        )
        
        assert policy.mount_data_dir == "/host/data"
        assert policy.guest_data_path == "/data"

    def test_optional_data_mount_defaults_guest_path(self):
        """Test guest_data_path defaults to /data when mount_data_dir is provided programmatically."""
        policy = ExecutionPolicy(mount_data_dir="datasets")

        assert policy.mount_data_dir == "datasets"
        assert policy.guest_data_path == "/data"


class TestSandboxResult:
    """Test SandboxResult model creation and serialization."""
    
    def test_minimal_result(self):
        """Test SandboxResult with minimal required fields."""
        result = SandboxResult(
            success=True,
            workspace_path="/workspace",
        )
        
        assert result.success is True
        assert result.workspace_path == "/workspace"
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.fuel_consumed is None
        assert result.memory_used_bytes == 0
        assert result.duration_ms == 0.0
        assert result.files_created == []
        assert result.files_modified == []
        assert result.metadata == {}
    
    def test_complete_result(self):
        """Test SandboxResult with all fields populated."""
        result = SandboxResult(
            success=True,
            stdout="Hello, world!\n",
            stderr="",
            exit_code=0,
            fuel_consumed=1_234_567,
            memory_used_bytes=8_388_608,
            duration_ms=125.5,
            files_created=["output.txt", "report.json"],
            files_modified=["config.json"],
            workspace_path="/workspace",
            metadata={"runtime": "python", "version": "3.11"},
        )
        
        assert result.success is True
        assert result.stdout == "Hello, world!\n"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.fuel_consumed == 1_234_567
        assert result.memory_used_bytes == 8_388_608
        assert result.duration_ms == 125.5
        assert result.files_created == ["output.txt", "report.json"]
        assert result.files_modified == ["config.json"]
        assert result.workspace_path == "/workspace"
        assert result.metadata["runtime"] == "python"
        assert result.metadata["version"] == "3.11"
    
    def test_failed_result(self):
        """Test SandboxResult for failed execution."""
        result = SandboxResult(
            success=False,
            stdout="",
            stderr="SyntaxError: invalid syntax\n",
            exit_code=1,
            workspace_path="/workspace",
        )
        
        assert result.success is False
        assert result.exit_code == 1
        assert "SyntaxError" in result.stderr
    
    def test_json_serialization(self):
        """Test SandboxResult can be serialized to JSON."""
        result = SandboxResult(
            success=True,
            stdout="Test output\n",
            fuel_consumed=500_000,
            memory_used_bytes=1_000_000,
            duration_ms=50.0,
            files_created=["test.txt"],
            workspace_path="/workspace",
        )
        
        json_str = result.model_dump_json()
        data = json.loads(json_str)
        
        assert data["success"] is True
        assert data["stdout"] == "Test output\n"
        assert data["fuel_consumed"] == 500_000
        assert data["memory_used_bytes"] == 1_000_000
        assert data["duration_ms"] == 50.0
        assert data["files_created"] == ["test.txt"]
        assert data["workspace_path"] == "/workspace"
    
    def test_json_deserialization(self):
        """Test SandboxResult can be deserialized from JSON."""
        json_data = {
            "success": True,
            "stdout": "Test output\n",
            "stderr": "",
            "exit_code": 0,
            "fuel_consumed": 500_000,
            "memory_used_bytes": 1_000_000,
            "duration_ms": 50.0,
            "files_created": ["test.txt"],
            "files_modified": [],
            "workspace_path": "/workspace",
            "metadata": {},
        }
        
        result = SandboxResult(**json_data)
        
        assert result.success is True
        assert result.stdout == "Test output\n"
        assert result.fuel_consumed == 500_000
        assert result.duration_ms == 50.0


class TestLoadPolicy:
    """Test load_policy() function with TOML configuration."""
    
    def test_load_default_policy_no_file(self):
        """Test load_policy returns defaults when file doesn't exist."""
        policy = load_policy("nonexistent_policy.toml")
        
        assert isinstance(policy, ExecutionPolicy)
        assert policy.fuel_budget == DEFAULT_POLICY["fuel_budget"]
        assert policy.memory_bytes == DEFAULT_POLICY["memory_bytes"]
        assert policy.stdout_max_bytes == DEFAULT_POLICY["stdout_max_bytes"]
        assert policy.mount_host_dir == DEFAULT_POLICY["mount_host_dir"]
    
    def test_load_policy_with_custom_toml(self):
        """Test load_policy merges custom TOML with defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
fuel_budget = 1_000_000
memory_bytes = 64_000_000
stdout_max_bytes = 500_000

[env]
CUSTOM_VAR = "custom_value"
""")
            toml_path = f.name
        
        try:
            policy = load_policy(toml_path)
            
            assert isinstance(policy, ExecutionPolicy)
            assert policy.fuel_budget == 1_000_000
            assert policy.memory_bytes == 64_000_000
            assert policy.stdout_max_bytes == 500_000
            
            # Check env deep merge (defaults + custom)
            assert "PYTHONUTF8" in policy.env  # Default preserved
            assert policy.env["PYTHONUTF8"] == "1"
            assert "CUSTOM_VAR" in policy.env  # Custom added
            assert policy.env["CUSTOM_VAR"] == "custom_value"
        finally:
            Path(toml_path).unlink()
    
    def test_load_policy_env_deep_merge(self):
        """Test load_policy deep merges env dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[env]
NEW_VAR = "new"
ANOTHER_VAR = "another"
""")
            toml_path = f.name
        
        try:
            policy = load_policy(toml_path)
            
            # All default env vars should be preserved
            assert policy.env["PYTHONUTF8"] == "1"
            assert policy.env["LC_ALL"] == "C.UTF-8"
            assert policy.env["PYTHONHASHSEED"] == "0"
            
            # Custom vars should be added
            assert policy.env["NEW_VAR"] == "new"
            assert policy.env["ANOTHER_VAR"] == "another"
        finally:
            Path(toml_path).unlink()
    
    def test_load_policy_with_optional_data_mount(self):
        """Test load_policy with optional secondary mount."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
mount_data_dir = "/host/data"
guest_data_path = "/readonly_data"
""")
            toml_path = f.name
        
        try:
            policy = load_policy(toml_path)
            
            assert policy.mount_data_dir == "/host/data"
            assert policy.guest_data_path == "/readonly_data"
        finally:
            Path(toml_path).unlink()
    
    def test_load_policy_invalid_fuel_raises_error(self):
        """Test load_policy raises PolicyValidationError for negative fuel."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("fuel_budget = -1000\n")
            toml_path = f.name
        
        try:
            with pytest.raises(PolicyValidationError) as excinfo:
                load_policy(toml_path)
            
            assert "invalid execution policy" in str(excinfo.value).lower()
            assert "fuel_budget" in str(excinfo.value).lower()
        finally:
            Path(toml_path).unlink()
    
    def test_load_policy_invalid_memory_raises_error(self):
        """Test load_policy raises PolicyValidationError for zero memory."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("memory_bytes = 0\n")
            toml_path = f.name
        
        try:
            with pytest.raises(PolicyValidationError) as excinfo:
                load_policy(toml_path)
            
            assert "invalid execution policy" in str(excinfo.value).lower()
            assert "memory_bytes" in str(excinfo.value).lower()
        finally:
            Path(toml_path).unlink()
    
    def test_load_policy_malformed_toml_raises_error(self):
        """Test load_policy raises error for malformed TOML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("fuel_budget = [invalid syntax\n")
            toml_path = f.name
        
        try:
            with pytest.raises(Exception):  # tomllib.TOMLDecodeError
                load_policy(toml_path)
        finally:
            Path(toml_path).unlink()
    
    def test_load_policy_returns_execution_policy(self):
        """Test load_policy returns ExecutionPolicy instance, not dict."""
        policy = load_policy("nonexistent_policy.toml")
        
        assert isinstance(policy, ExecutionPolicy)
        assert not isinstance(policy, dict)
        
        # Should have Pydantic methods
        assert hasattr(policy, "model_dump")
        assert hasattr(policy, "model_dump_json")
