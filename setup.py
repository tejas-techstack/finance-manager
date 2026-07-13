#!/usr/bin/env python3
"""One-time ONLINE setup. Run this once, while connected to the internet.

It installs the frontend dependencies. There is no ML model to download — the
merchant name is read straight out of the transaction description, so once the
Python + npm packages are installed you never need internet again.

    python setup.py
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")


def main() -> None:
    print("== Installing frontend dependencies (npm install) ==")
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
    print("   frontend deps installed ✓")

    print("\nSetup complete. You can disconnect from the internet now.")
    print("Run everything with:  python run.py")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nsetup failed: {e}", file=sys.stderr)
        sys.exit(1)
