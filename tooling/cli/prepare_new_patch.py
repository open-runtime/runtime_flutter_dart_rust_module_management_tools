#!/usr/bin/env python3
"""
prepare_new_patch.py - Prepare the codebase for a new patch release
Updates versions and creates changelog entries with robust error handling

This script:
1. Determines the next patch version
2. Extracts package information from configuration files
3. Prompts for changelog entries for each package
4. Updates or creates changelog files
5. Updates version numbers across all project files

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved

Requires: Python 3.6+, git
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

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
    # Fallback if common_config is not available
    print("Warning: Could not import common_config, using fallback implementations", file=sys.stderr)
    
    class Colors:
        RED = '\033[0;31m'
        GREEN = '\033[0;32m'
        YELLOW = '\033[1;33m'
        BLUE = '\033[0;34m'
        PURPLE = '\033[0;35m'
        NC = '\033[0m'
    
    def print_color(color, message, file=None):
        print(f"{color}{message}{Colors.NC}", file=file or sys.stdout)
    
    def print_header(message):
        print()
        print_color(Colors.PURPLE, "━" * 40)
        print_color(Colors.PURPLE, f"  {message}")
        print_color(Colors.PURPLE, "━" * 40)
        print()

# ============================================================================
# MAIN SCRIPT CLASS
# ============================================================================

class PatchPreparer:
    """Handles preparation of new patch releases"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.new_tag = None
        self.version_number = None
        self.dart_package_name = None
        self.flutter_package_name = None
        self.rust_package_name = None
        
    def run(self):
        """Main execution flow"""
        try:
            # Setup cleanup
            import atexit
            atexit.register(self.cleanup)
            
            # Ensure we're in the project root
            self.ensure_project_root()
            
            # Get the new version
            self.determine_new_version()
            
            # Read package information
            self.read_package_information()
            
            # Collect changelog entries
            self.collect_changelog_entries()
            
            # Update version files
            self.update_version_files()
            
            # Show summary
            self.show_summary()
            
        except KeyboardInterrupt:
            print_color(Colors.YELLOW, "\nOperation cancelled by user")
            sys.exit(1)
        except Exception as e:
            print_color(Colors.RED, f"Error: {e}")
            sys.exit(1)
    
    def cleanup(self):
        """Cleanup function"""
        # Remove any temporary files we might have created
        temp_dir = Path(tempfile.gettempdir())
        for temp_file in temp_dir.glob("prepare_patch_*"):
            try:
                temp_file.unlink()
            except:
                pass
    
    def ensure_project_root(self):
        """Ensure we're in the project root"""
        dart_pubspec = Path(DART_PUBSPEC)
        flutter_pubspec = Path(FLUTTER_PUBSPEC)
        
        if not dart_pubspec.exists() or not flutter_pubspec.exists():
            print_color(Colors.RED, "Error: This script must be run from the project root directory")
            print_color(Colors.YELLOW, f"Current directory: {os.getcwd()}")
            print_color(Colors.YELLOW, "Please cd to the project root and try again")
            sys.exit(1)
    
    def determine_new_version(self):
        """Get the new tag using get_new_patch_tag.py"""
        print_header("Determining New Version")
        
        # Make sure get_new_patch_tag.py is executable
        get_tag_script = self.script_dir / "get_new_patch_tag.py"
        if get_tag_script.exists():
            get_tag_script.chmod(get_tag_script.stat().st_mode | 0o755)
        else:
            print_color(Colors.RED, f"Error: {get_tag_script} not found")
            sys.exit(1)
        
        # Run the script to get new version
        try:
            result = subprocess.run(
                [sys.executable, str(get_tag_script)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print_color(Colors.RED, "Error: Failed to determine new version")
                print(result.stdout)
                print(result.stderr)
                sys.exit(1)
            
            # Parse the output
            output_lines = result.stdout.strip().split('\n')
            new_tag_line = None
            
            for line in output_lines:
                if line.startswith("New tag:"):
                    new_tag_line = line
                    break
            
            if not new_tag_line:
                print_color(Colors.RED, "Error: Failed to get valid tag from output")
                print("Output was:")
                print(result.stdout)
                sys.exit(1)
            
            self.new_tag = new_tag_line.split(":", 1)[1].strip()
            self.version_number = self.new_tag.lstrip('v')
            
            # Verify we got valid values
            if not self.new_tag or not self.version_number:
                print_color(Colors.RED, "Error: Failed to get valid tag or version number")
                print("Output was:")
                print(result.stdout)
                sys.exit(1)
            
            print_color(Colors.GREEN, f"✓ New version will be: {self.new_tag} ({self.version_number})")
            
        except subprocess.TimeoutExpired:
            print_color(Colors.RED, "Error: Timeout while determining new version")
            sys.exit(1)
        except Exception as e:
            print_color(Colors.RED, f"Error: Failed to run get_new_patch_tag.py: {e}")
            sys.exit(1)
    
    def read_package_information(self):
        """Extract package names from configuration files"""
        print_header("Reading Package Information")
        
        # Extract Dart package name
        if Path(DART_PUBSPEC).exists():
            self.dart_package_name = extract_yaml_value(DART_PUBSPEC, "name")
            if not self.dart_package_name:
                print_color(Colors.RED, f"Error: Could not extract Dart package name from {DART_PUBSPEC}")
                sys.exit(1)
            print_color(Colors.GREEN, f"✓ Dart package: {self.dart_package_name}")
        else:
            print_color(Colors.RED, f"Error: {DART_PUBSPEC} not found")
            sys.exit(1)
        
        # Extract Flutter package name
        if Path(FLUTTER_PUBSPEC).exists():
            self.flutter_package_name = extract_yaml_value(FLUTTER_PUBSPEC, "name")
            if not self.flutter_package_name:
                print_color(Colors.RED, f"Error: Could not extract Flutter package name from {FLUTTER_PUBSPEC}")
                sys.exit(1)
            print_color(Colors.GREEN, f"✓ Flutter package: {self.flutter_package_name}")
        else:
            print_color(Colors.RED, f"Error: {FLUTTER_PUBSPEC} not found")
            sys.exit(1)
        
        # Extract Rust package name
        if Path(RUST_CARGO).exists():
            self.rust_package_name = extract_toml_value(RUST_CARGO, "name")
            if not self.rust_package_name:
                print_color(Colors.RED, f"Error: Could not extract Rust package name from {RUST_CARGO}")
                sys.exit(1)
            print_color(Colors.GREEN, f"✓ Rust package: {self.rust_package_name}")
        else:
            # Check if we can find it in the cargo.dart config file
            if Path(CARGO_DART_CONFIG).exists():
                try:
                    with open(CARGO_DART_CONFIG, 'r') as f:
                        content = f.read()
                        # Extract the package name from the cargo.dart file
                        import re
                        match = re.search(r'name = "([^"]*)"', content)
                        if match and "crate-type" not in content[match.start():match.end()+50]:
                            self.rust_package_name = match.group(1)
                            print_color(Colors.YELLOW, f"⚠  Rust Cargo.toml not found, using package name from cargo.dart config: {self.rust_package_name}")
                        else:
                            print_color(Colors.RED, f"Error: Could not extract Rust package name from {CARGO_DART_CONFIG}")
                            sys.exit(1)
                except Exception as e:
                    print_color(Colors.RED, f"Error reading {CARGO_DART_CONFIG}: {e}")
                    sys.exit(1)
            else:
                print_color(Colors.RED, f"Error: Neither {RUST_CARGO} nor {CARGO_DART_CONFIG} found")
                sys.exit(1)
    
    def prompt_for_changes(self, package_name: str, package_type: str) -> str:
        """Prompt for changelog entries with better UX"""
        changes = []
        
        print_color(Colors.BLUE, f"Enter changes for {package_name} ({package_type} package):")
        print_color(Colors.YELLOW, "Press Enter on empty line when done, or type 'skip' to skip this package")
        
        while True:
            try:
                entry = input("> ").strip()
                if not entry:
                    break
                elif entry.lower() == 'skip':
                    return ""
                else:
                    changes.append(entry)
            except (EOFError, KeyboardInterrupt):
                print()  # New line for clean output
                raise KeyboardInterrupt()
        
        return ",".join(changes)
    
    def collect_changelog_entries(self):
        """Prompt for changelog entries for each package"""
        print_header("Changelog Entry Collection")
        
        self.root_changes = self.prompt_for_changes("vector_search", "Root/Project")
        self.dart_changes = self.prompt_for_changes(self.dart_package_name, "Dart")
        self.flutter_changes = self.prompt_for_changes(self.flutter_package_name, "Flutter")
        self.rust_changes = self.prompt_for_changes(self.rust_package_name, "Rust")
    
    def update_or_create_changelog(self, changelog_file: str, package_name: str, 
                                   package_changes: str, package_type: str):
        """Update or create changelog file"""
        print_color(Colors.BLUE, f"Processing {package_type} changelog...")
        
        changelog_path = Path(changelog_file)
        
        # Create directory if it doesn't exist
        changelog_path.parent.mkdir(parents=True, exist_ok=True)
        if not changelog_path.parent.exists():
            print_color(Colors.YELLOW, f"  Created directory: {changelog_path.parent}")
        
        # Current date for changelog entry
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Create new changelog content
        new_content = []
        
        # Header
        if package_type == "Root/Project":
            new_content.extend([
                f"# Changelog",
                "",
                f"All notable changes to this project will be documented in this file.",
                "",
                "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
                "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
                "",
                f"## [{self.new_tag}] - {current_date}",
                ""
            ])
        else:
            new_content.extend([
                f"# Changelog - {package_name}",
                "",
                f"All notable changes to the {package_type} package will be documented in this file.",
                "",
                "The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),",
                "and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).",
                "",
                f"## [{self.new_tag}] - {current_date}",
                ""
            ])
        
        # Add changes or template
        if not package_changes:
            new_content.extend([
                "### Added",
                "- ",
                "",
                "### Changed", 
                "- ",
                "",
                "### Fixed",
                "- ",
                ""
            ])
        else:
            new_content.append("### Changes")
            for change in package_changes.split(','):
                change = change.strip()
                if change:
                    new_content.append(f"- {change}")
            new_content.append("")
        
        # If changelog exists, append existing content (skipping header)
        if changelog_path.exists():
            try:
                with open(changelog_path, 'r') as f:
                    existing_lines = f.readlines()
                
                # Skip the header (first 7 lines) and append the rest
                if len(existing_lines) > 7:
                    new_content.extend(line.rstrip() for line in existing_lines[7:])
                
                print_color(Colors.GREEN, "  ✓ Updated existing changelog")
            except Exception as e:
                print_color(Colors.RED, f"  ✗ Error reading existing changelog: {e}")
                return False
        else:
            print_color(Colors.GREEN, "  ✓ Created new changelog")
        
        # Write the new content
        try:
            with open(changelog_path, 'w') as f:
                for line in new_content:
                    f.write(line + '\n')
            return True
        except Exception as e:
            print_color(Colors.RED, f"  ✗ Error writing changelog: {e}")
            return False
    
    def update_changelog_files(self):
        """Update all changelog files"""
        print_header("Updating Changelogs")
        
        success = True
        
        # Update all four changelogs
        if not self.update_or_create_changelog(ROOT_CHANGELOG, "vector_search", 
                                               self.root_changes, "Root/Project"):
            success = False
        
        if not self.update_or_create_changelog(DART_CHANGELOG, self.dart_package_name, 
                                               self.dart_changes, "Dart"):
            success = False
        
        if not self.update_or_create_changelog(FLUTTER_CHANGELOG, self.flutter_package_name, 
                                               self.flutter_changes, "Flutter"):
            success = False
        
        if not self.update_or_create_changelog(RUST_CHANGELOG, self.rust_package_name, 
                                               self.rust_changes, "Rust"):
            success = False
        
        return success
    
    def update_version_files(self):
        """Update all version files"""
        # Update changelogs first
        if not self.update_changelog_files():
            print_color(Colors.RED, "Error: Some changelog updates failed")
            sys.exit(1)
        
        # Update all version files using shared function
        if not update_all_versions(self.version_number):
            print_color(Colors.RED, "Error: Some version updates failed")
            sys.exit(1)
    
    def show_summary(self):
        """Show completion summary"""
        print_header("Summary")
        
        print_color(Colors.GREEN, f"✓ Successfully prepared for new version {self.new_tag}")
        print()
        print_color(Colors.BLUE, "Next steps:")
        print_color(Colors.YELLOW, "  1. Review and edit the changelog files if needed:")
        print_color(Colors.YELLOW, f"     - {ROOT_CHANGELOG}")
        print_color(Colors.YELLOW, f"     - {DART_CHANGELOG}")
        print_color(Colors.YELLOW, f"     - {FLUTTER_CHANGELOG}")
        print_color(Colors.YELLOW, f"     - {RUST_CHANGELOG}")
        print_color(Colors.YELLOW, "  2. Run './tooling/push_new_patch.py' to commit and push the changes")
        print()
        print_color(Colors.GREEN, "Alternatively, use './tooling/sync_changelogs.py' to generate AI-powered changelog entries!")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    preparer = PatchPreparer()
    preparer.run()

if __name__ == "__main__":
    main()