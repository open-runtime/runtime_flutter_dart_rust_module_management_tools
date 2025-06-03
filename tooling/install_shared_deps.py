#!/usr/bin/env python3
"""
Install shared dependencies for the tooling upgrade.

This script helps install the new dependencies needed for the enhanced tooling.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Install shared dependencies"""
    print("🔧 Installing shared dependencies for tooling upgrade...")
    
    # Check if requirements-shared.txt exists
    req_file = Path("requirements-shared.txt")
    if not req_file.exists():
        print("❌ requirements-shared.txt not found!")
        return 1
    
    # Install dependencies
    print(f"\n📦 Installing from {req_file}...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(req_file)
        ])
        print("\n✅ Dependencies installed successfully!")
        
        # Show what was installed
        print("\n📋 Key dependencies installed:")
        print("  - pydantic & pydantic-settings: Configuration management")
        print("  - structlog: Structured logging") 
        print("  - rich: Beautiful terminal output")
        print("  - click: CLI framework")
        print("  - pytest & plugins: Testing framework")
        print("  - black & ruff: Code formatting and linting")
        print("  - mypy: Type checking")
        
        print("\n🎉 You can now use the new configuration and logging systems!")
        print("\n📚 See documentation/LOGGING_MIGRATION.md for migration guide")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to install dependencies: {e}")
        print("\n💡 Try running: pip install -r requirements-shared.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())