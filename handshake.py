#!/usr/bin/env python3
"""
Convenience launcher for handshake clicker.
Just run: python handshake.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run
from scripts.run_handshake_clicker import main

if __name__ == "__main__":
    main()
