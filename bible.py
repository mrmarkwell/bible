#!/usr/bin/env python3
"""Executable entry point for Bible Engine CLI."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli.main import main

if __name__ == "__main__":
    sys.exit(main())
