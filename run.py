#!/usr/bin/env python3
"""
Econome - Real-Time Conversation Intelligence System
Entry point for the application

This is the main entry point that imports and runs the core application
from the src package.
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import and run the main application
if __name__ == "__main__":
    from main import main
    main()
