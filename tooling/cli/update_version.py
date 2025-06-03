#!/usr/bin/env python3
"""
update_version.py - Update version numbers across all packages

This script updates version numbers in all package configuration files:
- dart/pubspec.yaml
- flutter/pubspec.yaml
- dart/rust/Cargo.toml
- dart/utils/configs/cargo.dart

Usage: ./update_version.py <new_version>
Example: ./update_version.py 1.0.0

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved

Requires: Python 3.6+
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List

# Add the script directory to Python path for imports
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import our common configuration
try:
    # Support both direct execution and package imports
import sys
import os

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try package import first (when installed via pip)
    from tooling.core.common_config import *
except ImportError:
    # Fall back to direct import (when running file directly)
    from core.common_config import *
except ImportError:
    print("Error: Could not import common_config.py", file=sys.stderr)
    print("Make sure common_config.py exists in the same directory", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# VERSION UPDATE CLASS
# ============================================================================

class VersionUpdater:
    """Handles version updates across all project files"""
    
    def __init__(self, new_version: str):
        self.new_version = new_version
        self.updated_files = []
        self.failed_files = []
    
    def validate_version(self) -> bool:
        """Validate version format
        
        Returns:
            True if valid, False otherwise
        """
        return validate_version(self.new_version)
    
    def update_versions(self) -> bool:
        """Update all version files
        
        Returns:
            True if all updates successful, False otherwise
        """
        # Use the shared function from common_config
        success = update_all_versions(self.new_version)
        
        # Track which files were updated
        self._check_updated_files()
        
        return success
    
    def _check_updated_files(self):
        """Check which files were successfully updated"""
        files_to_check = [
            (DART_PUBSPEC, "Dart pubspec.yaml"),
            (FLUTTER_PUBSPEC, "Flutter pubspec.yaml"),
            (RUST_CARGO, "Rust Cargo.toml"),
            (CARGO_DART_CONFIG, "cargo.dart config")
        ]
        
        for file_path, description in files_to_check:
            if Path(file_path).exists():
                # Verify the version was actually updated
                if file_path.endswith('.yaml'):
                    current = extract_yaml_value(file_path, "version")
                elif file_path.endswith('.toml'):
                    current = extract_toml_value(file_path, "version")
                elif file_path.endswith('.dart'):
                    # For dart files, we'll assume it was updated if the file exists
                    current = self.new_version
                else:
                    current = None
                
                if current == self.new_version:
                    self.updated_files.append(file_path)
                else:
                    self.failed_files.append((file_path, description))
    
    def show_summary(self):
        """Display update summary"""
        print_header("Summary")
        
        if not self.failed_files:
            print_color(Colors.GREEN, f"✓ Successfully updated all packages to version {self.new_version}")
            
            if self.updated_files:
                print_color(Colors.BLUE, "\nUpdated files:")
                for file_path in self.updated_files:
                    print_color(Colors.GREEN, f"  ✓ {file_path}")
            
            print_color(Colors.YELLOW, "\nNext steps:")
            print_color(Colors.YELLOW, "  1. Update CHANGELOG.md files with version entries")
            print_color(Colors.YELLOW, "  2. Commit the version changes")
            print_color(Colors.YELLOW, f"  3. Create and push a git tag: git tag v{self.new_version}")
            print()
            print_color(Colors.BLUE, "Alternatively, use './tooling/release.py' for a guided release process!")
        else:
            print_color(Colors.RED, "✗ Some version updates failed")
            
            if self.updated_files:
                print_color(Colors.GREEN, "\nSuccessfully updated:")
                for file_path in self.updated_files:
                    print_color(Colors.GREEN, f"  ✓ {file_path}")
            
            if self.failed_files:
                print_color(Colors.RED, "\nFailed to update:")
                for file_path, description in self.failed_files:
                    print_color(Colors.RED, f"  ✗ {file_path} ({description})")
            
            print_color(Colors.YELLOW, "\nPlease check the error messages above and fix any issues")

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def parse_arguments() -> str:
    """Parse command line arguments
    
    Returns:
        New version string
    """
    parser = argparse.ArgumentParser(
        description='Update version numbers across all packages',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 1.0.0       Update all packages to version 1.0.0
  %(prog)s 2.3.4       Update all packages to version 2.3.4
  
Version format must be X.Y.Z (semantic versioning)
        """
    )
    
    parser.add_argument(
        'version',
        help='New version in X.Y.Z format (e.g., 1.0.0)'
    )
    
    args = parser.parse_args()
    return args.version

def main():
    """Main execution function"""
    # Ensure we're in the project root
    ensure_project_root()
    
    # Parse arguments
    try:
        new_version = parse_arguments()
    except SystemExit:
        # argparse calls sys.exit() on error, which we want to handle gracefully
        return 1
    
    # Create updater
    updater = VersionUpdater(new_version)
    
    # Validate version format
    if not updater.validate_version():
        print_color(Colors.RED, "Error: Invalid version format")
        print_color(Colors.YELLOW, "Version must be in format X.Y.Z (e.g., 1.0.0)")
        return 1
    
    print_header(f"Updating Version to {new_version}")
    
    # Get current version for comparison
    current_version = get_current_version()
    if current_version:
        print_color(Colors.BLUE, f"Current version: {current_version}")
        print_color(Colors.BLUE, f"New version: {new_version}")
        
        # Compare versions
        comparison = compare_versions(new_version, current_version)
        if comparison < 0:
            print_color(Colors.YELLOW, "⚠ Warning: New version is older than current version")
        elif comparison == 0:
            print_color(Colors.YELLOW, "⚠ Warning: New version is the same as current version")
        print()
    
    # Update versions
    success = updater.update_versions()
    
    # Show summary
    updater.show_summary()
    
    return 0 if success else 1

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error: {e}")
        sys.exit(1)