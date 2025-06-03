#!/usr/bin/env python3
"""
setup_permissions.py - Ensure all tooling scripts have executable permissions

This script sets executable permissions for all tooling scripts in the project.
It handles both .sh and .py versions during the transition period.

Requires: Python 3.6+

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import stat
from pathlib import Path
from typing import List, Tuple

# ============================================================================
# CONSTANTS
# ============================================================================

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_color(color: str, message: str):
    """Print colored message"""
    print(f"{color}{message}{Colors.NC}")

# List of all scripts that should be executable (without extension)
SCRIPT_NAMES = [
    # Core configuration
    "common_config",
    # Commit tools
    "smart_commit",
    "smart_commit_fast",
    # Changelog tools
    "sync_changelogs",
    "sync_changelog_ultra",
    "analyze_changelog_history",
    # Release workflow
    "release",
    "prepare_new_patch",
    "push_new_patch",
    "retag_release",
    "get_new_patch_tag",
    "update_version",
    # Validation tools
    "validate_changelogs",
    "pre_release_check",
    # Release note generation
    "generate_release_notes",
    # Setup tools
    "setup_permissions",
    "setup_ai_tools",
    "install_gemini_cli",
    # Test scripts (optional)
    "test_hang",
    "test_git_commands",
    "simple_changelog_test"
]

# ============================================================================
# MAIN FUNCTIONS
# ============================================================================

def make_executable(file_path: Path) -> bool:
    """Make a file executable
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current permissions
        current_permissions = file_path.stat().st_mode
        
        # Add executable permissions for user, group, and others
        new_permissions = current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        
        # Apply new permissions
        file_path.chmod(new_permissions)
        return True
    except Exception as e:
        return False

def get_script_dir() -> Path:
    """Get the tooling directory path"""
    # This script should be in the tooling directory
    return Path(__file__).parent.absolute()

def process_scripts() -> Tuple[List[str], List[str], List[str]]:
    """Process all scripts and set permissions
    
    Returns:
        Tuple of (successful_scripts, not_found_scripts, failed_scripts)
    """
    script_dir = get_script_dir()
    
    successful = []
    not_found = []
    failed = []
    
    for script_name in SCRIPT_NAMES:
        # Check for both .py and .sh versions
        processed = False
        
        for extension in ['.py', '.sh']:
            script_path = script_dir / f"{script_name}{extension}"
            
            if script_path.exists():
                if make_executable(script_path):
                    successful.append(f"{script_name}{extension}")
                else:
                    failed.append(f"{script_name}{extension}")
                processed = True
        
        if not processed:
            # Neither .py nor .sh version found
            not_found.append(script_name)
    
    return successful, not_found, failed

def main():
    """Main execution function"""
    print_color(Colors.BLUE, "Setting executable permissions for all tooling scripts...")
    print()
    
    # First, ensure this script itself is executable
    script_dir = get_script_dir()
    this_script = script_dir / "setup_permissions.py"
    if this_script.exists():
        make_executable(this_script)
    
    # Process all scripts
    successful, not_found, failed = process_scripts()
    
    # Display results
    for script in successful:
        print_color(Colors.GREEN, f"✓ Made executable: tooling/{script}")
    
    for script in not_found:
        print_color(Colors.YELLOW, f"⚠ Not found: tooling/{script}.py or .sh")
    
    for script in failed:
        print_color(Colors.RED, f"✗ Failed to set permissions: tooling/{script}")
    
    print()
    
    if failed:
        print_color(Colors.YELLOW, "Some scripts failed to update. You may need to run with sudo.")
        print()
    
    if successful:
        print_color(Colors.GREEN, "All found scripts have been made executable!")
    else:
        print_color(Colors.RED, "No scripts were found to make executable!")
        print_color(Colors.YELLOW, "Make sure you're running this from the project root.")
    
    print()
    print_color(Colors.BLUE, "You can now use:")
    print()
    print_color(Colors.GREEN, "🚀 AI-Powered Commit Tools:")
    print("  • ./tooling/smart_commit_fast.py - Ultra-fast AI commits (2-3s)")
    print("  • ./tooling/smart_commit.py - Detailed AI commit analysis")
    print()
    print_color(Colors.GREEN, "📋 Changelog & Release Tools:")
    print("  • ./tooling/sync_changelogs.py - AI changelog generation")
    print("  • ./tooling/sync_changelog_ultra.py - Ultra-fast changelog sync")
    print("  • ./tooling/analyze_changelog_history.py - Analyze changelog patterns")
    print("  • ./tooling/release.py - Complete release workflow")
    print("  • ./tooling/prepare_new_patch.py - Prepare new patch version")
    print("  • ./tooling/push_new_patch.py - Push and create GitHub release")
    print("  • ./tooling/retag_release.py - Re-tag existing releases")
    print("  • ./tooling/update_version.py - Manual version updates")
    print()
    print_color(Colors.GREEN, "✅ Validation Tools:")
    print("  • ./tooling/validate_changelogs.py - Check changelog entries")
    print("  • ./tooling/pre_release_check.py - Pre-release validation")
    print()
    print_color(Colors.YELLOW, "💡 Tip: Run ./tooling/setup_ai_tools.py for full AI setup!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error: {e}")
        sys.exit(1)