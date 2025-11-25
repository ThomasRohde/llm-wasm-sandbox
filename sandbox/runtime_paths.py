"""Runtime binary path resolution for bundled WASM runtimes.

Provides utilities to locate WASM binaries that are bundled with the package,
falling back to project-relative paths for development workflows.
"""

from __future__ import annotations

from pathlib import Path


def get_bundled_binary_path(binary_name: str) -> Path:
    """Get path to bundled WASM binary, with fallback for development.

    Searches for WASM binaries in the following order:
    1. In package installation directory (PyPI installation)
    2. In project bin/ directory (development/source installation)
    3. In current working directory's bin/ (backward compatibility)

    Args:
        binary_name: Name of WASM binary file (e.g., "python.wasm", "quickjs.wasm")

    Returns:
        Path to WASM binary file

    Raises:
        FileNotFoundError: If binary cannot be found in any search location

    Examples:
        >>> path = get_bundled_binary_path("python.wasm")
        >>> print(path)
        PosixPath('/usr/local/lib/python3.11/site-packages/bin/python.wasm')

        >>> # In development
        >>> path = get_bundled_binary_path("quickjs.wasm")
        >>> print(path)
        PosixPath('/path/to/project/bin/quickjs.wasm')
    """
    # Strategy 1: Look in package installation directory (PyPI install)
    # This is where the binary will be after `pip install llm-wasm-sandbox`
    package_dir = Path(__file__).parent.parent  # sandbox/ -> project root
    bundled_path = package_dir / "bin" / binary_name

    if bundled_path.is_file():
        return bundled_path

    # Strategy 2: Look in project bin/ relative to package (development)
    # Handles source installations and development environments
    project_bin = Path("bin") / binary_name
    if project_bin.is_file():
        return project_bin.resolve()

    # Strategy 3: Look relative to current working directory (backward compat)
    cwd_bin = Path.cwd() / "bin" / binary_name
    if cwd_bin.is_file():
        return cwd_bin

    # Strategy 4: Check if running from site-packages (installed package)
    # Navigate up from sandbox module to find bin directory
    if "site-packages" in str(Path(__file__)):
        # /path/to/site-packages/sandbox/runtime_paths.py
        # -> /path/to/site-packages/bin/python.wasm
        site_packages = Path(__file__).parent.parent.parent
        site_bin = site_packages / "bin" / binary_name
        if site_bin.is_file():
            return site_bin

    # All strategies failed - raise with helpful message
    search_locations = [
        str(bundled_path),
        str(project_bin),
        str(cwd_bin),
    ]
    raise FileNotFoundError(
        f"WASM binary '{binary_name}' not found. Searched locations:\n"
        + "\n".join(f"  - {loc}" for loc in search_locations)
        + "\n\nFor development, run: ./scripts/fetch_wlr_python.ps1 and ./scripts/fetch_quickjs.ps1"
        + "\nFor PyPI install, binaries should be included automatically."
    )


def get_python_wasm_path() -> Path:
    """Get path to bundled CPython WASM binary.

    Returns:
        Path to python.wasm binary

    Raises:
        FileNotFoundError: If python.wasm cannot be found
    """
    return get_bundled_binary_path("python.wasm")


def get_quickjs_wasm_path() -> Path:
    """Get path to bundled QuickJS WASM binary.

    Returns:
        Path to quickjs.wasm binary

    Raises:
        FileNotFoundError: If quickjs.wasm cannot be found
    """
    return get_bundled_binary_path("quickjs.wasm")


def get_vendor_js_path() -> Path | None:
    """Get path to bundled JavaScript vendor packages directory.

    Returns the path to the vendor_js directory containing JavaScript packages
    like sandbox-utils.js, csv-simple.js, etc.

    Returns:
        Path to vendor_js directory, or None if not found

    Examples:
        >>> path = get_vendor_js_path()
        >>> print(path)
        PosixPath('/usr/local/lib/python3.11/site-packages/vendor_js')
    """
    # Strategy 1: Look in package installation directory (PyPI install)
    package_dir = Path(__file__).parent.parent  # sandbox/ -> project root
    bundled_path = package_dir / "vendor_js"

    if bundled_path.is_dir():
        return bundled_path

    # Strategy 2: Look in project vendor_js/ relative to package (development)
    project_vendor = Path("vendor_js")
    if project_vendor.is_dir():
        return project_vendor.resolve()

    # Strategy 3: Look relative to current working directory (backward compat)
    cwd_vendor = Path.cwd() / "vendor_js"
    if cwd_vendor.is_dir():
        return cwd_vendor

    # Strategy 4: Check if running from site-packages (installed package)
    if "site-packages" in str(Path(__file__)):
        site_packages = Path(__file__).parent.parent.parent
        site_vendor = site_packages / "vendor_js"
        if site_vendor.is_dir():
            return site_vendor

    # Return None if not found (JavaScript runtime will work without vendor packages)
    return None
