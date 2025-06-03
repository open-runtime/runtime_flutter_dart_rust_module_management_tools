#!/usr/bin/env python3
"""
install_gemini_cli.py - Wrapper script for AI tools setup
This script is kept for backward compatibility

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved

Requires: Python 3.6+
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Run the main setup script"""
    print("Note: This script now calls setup_ai_tools.py for complete AI tools setup")
    print()
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    
    # Path to the main setup script
    setup_script = script_dir / "setup_ai_tools.py"
    
    # Make sure setup_ai_tools.py is executable
    if setup_script.exists():
        try:
            setup_script.chmod(setup_script.stat().st_mode | 0o111)
        except:
            pass
    
    # Run the main setup script with all arguments passed through
    try:
        result = subprocess.run([sys.executable, str(setup_script)] + sys.argv[1:])
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error running setup_ai_tools.py: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()