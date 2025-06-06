#!/usr/bin/env python3
"""
Import helper to standardize imports across all CLI tools.
This eliminates the need for try/except import blocks in every file.
"""

import sys
import os
from pathlib import Path


def setup_imports():
    """Setup import paths for CLI tools"""
    # Get the tooling directory (parent of core)
    tooling_dir = Path(__file__).parent.parent
    
    # Add to path if not already there
    if str(tooling_dir) not in sys.path:
        sys.path.insert(0, str(tooling_dir))
    
    # Also add the parent directory (project root) for backward compatibility
    project_root = tooling_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


# Auto-setup when imported
setup_imports() 