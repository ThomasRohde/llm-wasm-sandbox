"""Shared pytest fixtures for all tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from sandbox.core.models import ExecutionPolicy


@pytest.fixture
def policy_with_vendor_js():
    """Create ExecutionPolicy with vendor_js mount configured for JavaScript tests.

    This ensures vendored packages (sandbox-utils, csv-simple, etc.) are available
    when creating JavaScriptSandbox instances directly (not via factory).
    """
    policy = ExecutionPolicy()
    vendor_js_path = Path("vendor_js")
    if vendor_js_path.exists():
        policy.mount_data_dir = str(vendor_js_path.resolve())
        policy.guest_data_path = "/data_js"
    return policy


@pytest.fixture
def policy_with_vendor_python():
    """Create ExecutionPolicy with vendor mount configured for Python tests.

    This ensures vendored packages (sandbox_utils module) are available
    when creating PythonSandbox instances directly (not via factory).
    """
    policy = ExecutionPolicy()
    vendor_path = Path("vendor")
    if vendor_path.exists():
        policy.mount_data_dir = str(vendor_path.resolve())
        policy.guest_data_path = "/data"
    return policy
