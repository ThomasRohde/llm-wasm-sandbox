"""Dependency vendoring for WASM sandbox environment.

This module manages pure-Python package installation into a vendor directory,
enabling LLM-generated code to import common libraries within the WASM sandbox.

Key constraints:
- Only pure-Python packages (no native extensions - WASM doesn't support them)
- Packages installed as wheels to avoid compilation
- Dependencies must be explicitly managed (--no-deps flag prevents transitive bloat)

Typical workflow:
1. install_pure_python_package() → downloads wheels to vendor/site-packages
2. copy_vendor_to_workspace() → makes packages available at /app/site-packages in WASM guest
3. Guest code uses sys.path.insert(0, '/app/site-packages') to import vendored modules
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def setup_vendor_dir(vendor_dir: str | Path = "vendor") -> Path:
    """Initialize vendor directory with site-packages subdirectory.

    Creates a pip-compatible directory structure matching Python's site-packages
    layout, enabling standard import mechanisms in the WASM guest.

    Args:
        vendor_dir: Path to vendor root directory (default: "vendor")

    Returns:
        Path object for the vendor directory (not site-packages subdirectory)
    """
    vendor_path = Path(vendor_dir)
    vendor_path.mkdir(parents=True, exist_ok=True)
    (vendor_path / "site-packages").mkdir(exist_ok=True)
    return vendor_path


def install_pure_python_package(
    package: str, vendor_dir: str | Path = "vendor", python_version: str = "3.12"
) -> bool:
    """Install a pure-Python package to vendor directory using wheels only.

    Enforces --only-binary to prevent compilation (WASM guest cannot load native
    extensions). Uses --no-deps to require explicit dependency management, avoiding
    accidental inclusion of incompatible transitive dependencies.

    Prefers uv (faster, better resolver) over pip when available.

    Args:
        package: Package specifier (e.g., 'certifi' or 'certifi==2023.7.22')
        vendor_dir: Path to vendor root directory (default: "vendor")
        python_version: Target Python version for wheel compatibility (default: "3.12")

    Returns:
        True if installation succeeded, False otherwise (prints diagnostics to stdout)
    """
    vendor_path = Path(vendor_dir)
    site_packages = vendor_path / "site-packages"

    try:
        import shutil

        uv_path = shutil.which("uv")

        if uv_path:
            result = subprocess.run(
                [
                    uv_path,
                    "pip",
                    "install",
                    "--target",
                    str(site_packages),
                    "--only-binary=:all:",
                    "--python-version",
                    python_version,
                    "--no-deps",
                    package,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    str(site_packages),
                    "--only-binary=:all:",
                    "--python-version",
                    python_version,
                    "--platform",
                    "any",
                    "--no-deps",
                    package,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        if result.returncode == 0:
            print(f"✓ Installed {package} to {site_packages}")
            return True
        else:
            print(f"✗ Failed to install {package}: {result.stderr}")
            return False

    except Exception as e:
        print(f"✗ Error installing {package}: {e}")
        return False


def copy_vendor_to_workspace(
    vendor_dir: str | Path = "vendor", workspace_dir: str | Path = "workspace"
) -> None:
    """Copy vendored packages into workspace for WASM guest access.

    The workspace directory is preopened in WASI as /app (capability-based mount),
    so packages copied to workspace/site-packages become importable via
    sys.path.insert(0, '/app/site-packages') in guest code.

    Replaces existing workspace/site-packages to ensure clean state.

    Args:
        vendor_dir: Source vendor root directory (default: "vendor")
        workspace_dir: Target workspace directory (default: "workspace")
    """
    vendor_path = Path(vendor_dir)
    workspace_path = Path(workspace_dir)

    src = vendor_path / "site-packages"
    dst = workspace_path / "site-packages"

    if not src.exists():
        print(f"⚠ Vendor directory {src} does not exist")
        return

    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst)
    print(f"✓ Copied vendored packages from {src} to {dst}")


def clean_vendor_dir(vendor_dir: str | Path = "vendor") -> None:
    """Remove vendor directory and all contents.

    Use to reset vendored packages before reinstalling with different versions
    or to reclaim disk space.

    Args:
        vendor_dir: Path to vendor root directory to delete (default: "vendor")
    """
    vendor_path = Path(vendor_dir)
    if vendor_path.exists():
        shutil.rmtree(vendor_path)
        print(f"✓ Cleaned vendor directory: {vendor_path}")


def list_vendored_packages(vendor_dir: str | Path = "vendor") -> list[str]:
    """List installed packages in vendor directory.

    Scans vendor/site-packages for package directories, normalizing names by
    stripping version suffixes and converting underscores to hyphens (PyPI convention).

    Args:
        vendor_dir: Path to vendor root directory (default: "vendor")

    Returns:
        Sorted list of package names (empty list if vendor/site-packages doesn't exist)
    """
    vendor_path = Path(vendor_dir) / "site-packages"

    if not vendor_path.exists():
        return []

    packages = set()
    for item in vendor_path.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            name = item.name.split("-")[0].replace("_", "-")
            packages.add(name)

    return sorted(packages)


RECOMMENDED_PACKAGES = [
    # HTTP/Network utilities (note: actual networking requires WASI-sockets support)
    "certifi",
    "charset-normalizer",
    "idna",
    "urllib3",
    # Document processing - Excel
    "openpyxl",  # Read/write Excel .xlsx files
    "XlsxWriter",  # Write Excel .xlsx files (write-only, lighter than openpyxl)
    # Document processing - PDF
    "PyPDF2",  # Read/write/merge PDF files
    # Document processing - Other formats
    "odfpy",  # Read/write OpenDocument Format (.odf, .ods, .odp)
    "mammoth",  # Convert Word .docx to HTML/markdown (read-only)
    # Python 2/3 compatibility utilities
    "six",  # Required by python-dateutil and other packages
    # Date/Time utilities
    "python-dateutil",  # Advanced date/time parsing and manipulation
    # Text and data presentation
    "tabulate",  # Pretty-print tabular data (ASCII, Markdown, HTML tables)
    # Template rendering
    "jinja2",  # Template engine for generating text/HTML/code
    "MarkupSafe",  # HTML/XML escaping (required by jinja2)
    # Markdown processing
    "markdown",  # Convert Markdown to HTML
    # Structured data with validation
    "attrs",  # Classes without boilerplate (useful for data modeling)
    # XML processing
    "defusedxml",  # Secure XML processing wrapper around stdlib
    # TOML parsing (Python <3.11 compatibility)
    "tomli ; python_version < '3.11'",  # TOML parser for older Python versions
]
"""Curated list of pure-Python packages compatible with WASM sandbox.

These packages have been verified to work without native extensions and are
commonly useful for LLM-generated code.

**Network utilities** (certifi, charset-normalizer, idna, urllib3):
- urllib3 networking functions will fail in baseline WASI (no socket API)
- Included for potential future WASI-sockets support and for encoding utilities

**Document processing packages** (openpyxl, XlsxWriter, PyPDF2, odfpy, mammoth):
- Successfully tested in WASM with fuel budgets of 3-7B instructions
- Enable reading/writing Excel, PDF, and OpenDocument formats
- mammoth provides Word .docx to HTML/markdown conversion

**Python 2/3 compatibility** (six):
- Required dependency for python-dateutil and other legacy packages
- Pure-Python utilities for writing code compatible with both Python 2 and 3

**Date/Time utilities** (python-dateutil):
- Advanced date parsing, timezone support, and date arithmetic
- Commonly used in data analysis and processing workflows
- Requires `six` package

**Text and data presentation** (tabulate):
- Pretty-print tables in multiple formats (ASCII, Markdown, HTML, LaTeX)
- Lightweight and pure-Python (no dependencies)

**Template rendering** (jinja2, MarkupSafe):
- Industry-standard template engine for generating text, HTML, or code
- MarkupSafe is a required dependency providing HTML/XML escaping
- Useful for report generation and code generation workflows
- **Important**: jinja2 requires ~4-5B fuel budget for initial import (first execution)

**Markdown processing** (markdown):
- Convert Markdown to HTML with extension support
- Pure-Python implementation (no C extensions)

**Structured data** (attrs):
- Create classes without boilerplate using decorators
- Useful for data modeling and configuration objects
- Pure-Python package with no dependencies

**TOML parsing** (tomli):
- Backport of Python 3.11+ tomllib for older Python versions
- Conditionally installed only for Python <3.11
- stdlib tomllib preferred when available

**Known incompatible packages** (have C/Rust extension dependencies):
- **python-pptx**: Requires lxml.etree (C ext) + Pillow (C ext) - PowerPoint not supported
- **python-docx**: Requires lxml.etree (C ext) - use mammoth for .docx reading instead
- **lxml**: Base package imports but lxml.etree (C ext) doesn't work - use stdlib xml.etree
- **Pillow/PIL**: Image processing C extension - not available in WASM
- **pdfminer.six**: Requires cryptography (C ext) - use PyPDF2 instead
- **cryptography**: Pure C extension package - not available
- **cffi**: C FFI not functional in WASM
- **rpds-py**: Rust extension (jsonschema dependency) - jsonschema may have limited functionality
- Any package requiring native (C/Rust/C++) extensions

**Installation notes**:
- Packages may include optional native extensions (.pyd, .so) that are safely ignored
- charset-normalizer has mypyc-compiled optimizations that gracefully fall back to pure Python
- Always test new packages in WASM before adding to this list
"""


def bootstrap_common_packages(vendor_dir: str | Path = "vendor") -> None:
    """Install all packages from RECOMMENDED_PACKAGES list with dependencies.

    Convenience function for setting up a standard vendored library environment.
    Automatically creates vendor directory structure if it doesn't exist.

    Note: This installs dependencies for document processing packages, which may
    include packages with optional native extensions (e.g., et_xmlfile for openpyxl).
    These are safe as long as pure Python fallbacks exist.

    Args:
        vendor_dir: Path to vendor root directory (default: "vendor")
    """
    import subprocess

    print("Bootstrapping common pure-Python packages...")
    vendor_path = setup_vendor_dir(vendor_dir)
    site_packages = vendor_path / "site-packages"

    # Install all packages with dependencies using uv or pip
    try:
        uv_path = shutil.which("uv")

        if uv_path:
            # Use uv - faster and better dependency resolution
            result = subprocess.run(
                [
                    uv_path,
                    "pip",
                    "install",
                    "--target",
                    str(site_packages),
                    "--python-version",
                    "3.12",
                    *RECOMMENDED_PACKAGES,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            # Fallback to pip
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--target",
                    str(site_packages),
                    "--python-version",
                    "3.12",
                    *RECOMMENDED_PACKAGES,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        if result.returncode == 0:
            print(f"✓ Installed {len(RECOMMENDED_PACKAGES)} packages with dependencies")
        else:
            print(f"✗ Installation failed: {result.stderr}")
            return

    except Exception as e:
        print(f"✗ Error during bootstrap: {e}")
        return

    print("\nVendored packages:")
    for pkg in list_vendored_packages(vendor_dir):
        print(f"  - {pkg}")
