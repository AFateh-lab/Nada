"""PyInstaller entry point (see .github/workflows/build-exe.yml)."""
import sys

from ram_mesh_import.cli import main

if __name__ == "__main__":
    sys.exit(main())
