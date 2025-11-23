"""
Vendor Package Management Script

This script helps manage pure-Python packages for the WASM sandbox.
It installs packages to a vendor directory that can be copied into
the sandbox workspace.

Usage:
    python scripts/manage_vendor.py install <package>
    python scripts/manage_vendor.py bootstrap
    python scripts/manage_vendor.py list
    python scripts/manage_vendor.py clean
    python scripts/manage_vendor.py copy
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sandbox.vendor import (
    bootstrap_common_packages,
    clean_vendor_dir,
    copy_vendor_to_workspace,
    install_pure_python_package,
    list_vendored_packages,
    setup_vendor_dir,
)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "install":
        if len(sys.argv) < 3:
            print("Error: Package name required")
            print("Usage: python scripts/manage_vendor.py install <package>")
            sys.exit(1)

        package = sys.argv[2]
        setup_vendor_dir()
        success = install_pure_python_package(package)
        sys.exit(0 if success else 1)

    elif command == "bootstrap":
        bootstrap_common_packages()

    elif command == "list":
        packages = list_vendored_packages()
        if packages:
            print("Vendored packages:")
            for pkg in packages:
                print(f"  - {pkg}")
        else:
            print("No vendored packages found.")

    elif command == "clean":
        clean_vendor_dir()

    elif command == "copy":
        copy_vendor_to_workspace()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
