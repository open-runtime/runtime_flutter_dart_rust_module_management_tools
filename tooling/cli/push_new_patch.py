#!/usr/bin/env python3
"""
push_new_patch.py - Commit and push the new patch release
Creates git commit, tag, and optionally creates GitHub release

This script:
1. Validates that changes are ready to be committed
2. Creates a git commit with the version changes
3. Creates a git tag for the new version
4. Pushes changes and tag to remote
5. Optionally creates a GitHub release

Requires: Python 3.6+, git, optionally gh CLI for GitHub releases

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple

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

class PatchPusher:
    """Handles pushing new patch releases"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent.absolute()
        self.current_version = None
        self.dart_package_name = None
        self.flutter_package_name = None
        self.rust_package_name = None
        self.has_gh_cli = False
        
    def run(self):
        """Main execution flow"""
        try:
            # Ensure we're in the project root
            self.ensure_project_root()
            
            # Validate git repository state
            self.validate_git_state()
            
            # Get current version and package information
            self.get_current_info()
            
            # Check for GitHub CLI
            self.check_github_cli()
            
            # Validate that we have changes to commit
            self.validate_changes()
            
            # Show what we're about to do
            self.show_plan()
            
            # Confirm with user
            if not self.confirm_action():
                print_color(Colors.YELLOW, "Operation cancelled by user")
                sys.exit(0)
            
            # Create commit
            self.create_commit()
            
            # Create tag
            self.create_tag()
            
            # Push to remote
            self.push_to_remote()
            
            # Create GitHub release if possible
            self.create_github_release()
            
            # Show completion summary
            self.show_completion()
            
        except KeyboardInterrupt:
            print_color(Colors.YELLOW, "\nOperation cancelled by user")
            sys.exit(1)
        except Exception as e:
            print_color(Colors.RED, f"Error: {e}")
            sys.exit(1)
    
    def ensure_project_root(self):
        """Ensure we're in the project root"""
        dart_pubspec = Path(DART_PUBSPEC)
        flutter_pubspec = Path(FLUTTER_PUBSPEC)
        
        if not dart_pubspec.exists() or not flutter_pubspec.exists():
            print_color(Colors.RED, "Error: This script must be run from the project root directory")
            print_color(Colors.YELLOW, f"Current directory: {os.getcwd()}")
            print_color(Colors.YELLOW, "Please cd to the project root and try again")
            sys.exit(1)
    
    def validate_git_state(self):
        """Validate git repository state"""
        print_header("Validating Git State")
        
        # Check if we're in a git repository
        if not check_git_repo():
            print_color(Colors.RED, "Error: Not in a git repository")
            sys.exit(1)
        
        # Check git state (no rebase, merge, etc. in progress)
        if not check_git_state():
            sys.exit(1)
        
        # Check remote sync (optional warning)
        check_remote_sync()
        
        print_color(Colors.GREEN, "✓ Git repository state is valid")
    
    def get_current_info(self):
        """Get current version and package information"""
        print_header("Reading Current Information")
        
        # Get current version
        self.current_version = get_current_version()
        if not self.current_version:
            sys.exit(1)
        
        print_color(Colors.GREEN, f"✓ Current version: {self.current_version}")
        
        # Extract package names
        self.dart_package_name = extract_yaml_value(DART_PUBSPEC, "name")
        self.flutter_package_name = extract_yaml_value(FLUTTER_PUBSPEC, "name")
        
        if Path(RUST_CARGO).exists():
            self.rust_package_name = extract_toml_value(RUST_CARGO, "name")
        elif Path(CARGO_DART_CONFIG).exists():
            # Extract from cargo.dart config
            try:
                with open(CARGO_DART_CONFIG, 'r') as f:
                    content = f.read()
                    import re
                    match = re.search(r'name = "([^"]*)"', content)
                    if match:
                        self.rust_package_name = match.group(1)
            except:
                pass
        
        print_color(Colors.GREEN, f"✓ Dart package: {self.dart_package_name}")
        print_color(Colors.GREEN, f"✓ Flutter package: {self.flutter_package_name}")
        if self.rust_package_name:
            print_color(Colors.GREEN, f"✓ Rust package: {self.rust_package_name}")
    
    def check_github_cli(self):
        """Check if GitHub CLI is available"""
        import shutil
        self.has_gh_cli = shutil.which('gh') is not None
        
        if self.has_gh_cli:
            # Check if authenticated
            code, stdout, stderr = run_command(['gh', 'auth', 'status'])
            if code == 0:
                print_color(Colors.GREEN, "✓ GitHub CLI available and authenticated")
            else:
                print_color(Colors.YELLOW, "⚠ GitHub CLI available but not authenticated")
                self.has_gh_cli = False
        else:
            print_color(Colors.YELLOW, "⚠ GitHub CLI not available - won't create GitHub release")
    
    def validate_changes(self):
        """Validate that we have changes to commit"""
        print_header("Validating Changes")
        
        # Check if there are any changes staged or unstaged
        code, stdout, stderr = run_command(['git', 'status', '--porcelain'])
        if code != 0:
            print_color(Colors.RED, "Error: Failed to check git status")
            sys.exit(1)
        
        if not stdout.strip():
            print_color(Colors.RED, "Error: No changes detected to commit")
            print_color(Colors.YELLOW, "Make sure you've run './tooling/prepare_new_patch.py' first")
            sys.exit(1)
        
        # Show what files will be committed
        print_color(Colors.BLUE, "Files with changes:")
        for line in stdout.strip().split('\n'):
            status = line[:2]
            filename = line[3:]
            if status.strip():
                print_color(Colors.YELLOW, f"  {status} {filename}")
        
        print_color(Colors.GREEN, "✓ Changes detected and ready to commit")
    
    def show_plan(self):
        """Show what we're about to do"""
        print_header("Release Plan")
        
        print_color(Colors.BLUE, "This script will:")
        print_color(Colors.YELLOW, f"  1. Create a commit with message: 'Release v{self.current_version}'")
        print_color(Colors.YELLOW, f"  2. Create a git tag: 'v{self.current_version}'")
        print_color(Colors.YELLOW, f"  3. Push commits and tags to remote")
        
        if self.has_gh_cli:
            print_color(Colors.YELLOW, f"  4. Create a GitHub release for v{self.current_version}")
        else:
            print_color(Colors.GRAY, f"  4. (Skip GitHub release - CLI not available)")
        
        print()
    
    def confirm_action(self) -> bool:
        """Confirm action with user"""
        try:
            response = input(f"{Colors.YELLOW}Continue with release? (Y/n): {Colors.NC}")
            return not response.lower().startswith('n')
        except (EOFError, KeyboardInterrupt):
            return False
    
    def create_commit(self):
        """Create git commit"""
        print_header("Creating Commit")
        
        # Add all changes
        code, stdout, stderr = run_command(['git', 'add', '.'])
        if code != 0:
            print_color(Colors.RED, f"Error: Failed to stage changes: {stderr}")
            sys.exit(1)
        
        # Create commit
        commit_message = f"Release v{self.current_version}"
        code, stdout, stderr = run_command(['git', 'commit', '-m', commit_message])
        if code != 0:
            print_color(Colors.RED, f"Error: Failed to create commit: {stderr}")
            sys.exit(1)
        
        print_color(Colors.GREEN, f"✓ Created commit: {commit_message}")
    
    def create_tag(self):
        """Create git tag"""
        print_header("Creating Tag")
        
        tag_name = f"v{self.current_version}"
        tag_message = f"Release {tag_name}"
        
        # Check if tag already exists
        code, stdout, stderr = run_command(['git', 'tag', '-l', tag_name])
        if stdout.strip():
            print_color(Colors.RED, f"Error: Tag {tag_name} already exists")
            sys.exit(1)
        
        # Create annotated tag
        code, stdout, stderr = run_command(['git', 'tag', '-a', tag_name, '-m', tag_message])
        if code != 0:
            print_color(Colors.RED, f"Error: Failed to create tag: {stderr}")
            sys.exit(1)
        
        print_color(Colors.GREEN, f"✓ Created tag: {tag_name}")
    
    def push_to_remote(self):
        """Push commits and tags to remote"""
        print_header("Pushing to Remote")
        
        # Get current branch
        code, branch, stderr = run_command(['git', 'branch', '--show-current'])
        if code != 0:
            print_color(Colors.RED, f"Error: Failed to get current branch: {stderr}")
            sys.exit(1)
        
        # Push commits
        print_color(Colors.YELLOW, f"Pushing commits to origin/{branch}...")
        code, stdout, stderr = run_command(['git', 'push', 'origin', branch])
        if code != 0:
            print_color(Colors.RED, f"Error: Failed to push commits: {stderr}")
            sys.exit(1)
        
        print_color(Colors.GREEN, "✓ Pushed commits")
        
        # Push tags
        print_color(Colors.YELLOW, "Pushing tags...")
        code, stdout, stderr = run_command(['git', 'push', 'origin', '--tags'])
        if code != 0:
            print_color(Colors.RED, f"Error: Failed to push tags: {stderr}")
            sys.exit(1)
        
        print_color(Colors.GREEN, "✓ Pushed tags")
    
    def generate_release_notes(self) -> str:
        """Generate release notes from changelogs"""
        release_notes = []
        tag_name = f"v{self.current_version}"
        
        # Extract changelog sections for each package
        packages = [
            (DART_CHANGELOG, self.dart_package_name, "Dart"),
            (FLUTTER_CHANGELOG, self.flutter_package_name, "Flutter"),
            (RUST_CHANGELOG, self.rust_package_name, "Rust")
        ]
        
        for changelog_path, package_name, package_type in packages:
            if not package_name:
                continue
                
            changelog_section = extract_changelog_section(changelog_path, self.current_version)
            if changelog_section.strip():
                release_notes.append(f"## {package_type} Package ({package_name})")
                release_notes.append("")
                release_notes.append(changelog_section.strip())
                release_notes.append("")
        
        if not release_notes:
            release_notes = [
                f"Release {tag_name}",
                "",
                "See individual package changelogs for details:",
                f"- [Dart]({DART_CHANGELOG})",
                f"- [Flutter]({FLUTTER_CHANGELOG})",
                f"- [Rust]({RUST_CHANGELOG})"
            ]
        
        return "\n".join(release_notes)
    
    def create_github_release(self):
        """Create GitHub release using gh CLI"""
        if not self.has_gh_cli:
            return
        
        print_header("Creating GitHub Release")
        
        tag_name = f"v{self.current_version}"
        release_notes = self.generate_release_notes()
        
        # Create release
        cmd = [
            'gh', 'release', 'create', tag_name,
            '--title', f"Release {tag_name}",
            '--notes', release_notes
        ]
        
        print_color(Colors.YELLOW, f"Creating GitHub release for {tag_name}...")
        code, stdout, stderr = run_command(cmd)
        
        if code != 0:
            print_color(Colors.YELLOW, f"⚠ Failed to create GitHub release: {stderr}")
            print_color(Colors.YELLOW, "You can create it manually at: https://github.com/your-repo/releases/new")
        else:
            print_color(Colors.GREEN, f"✓ Created GitHub release: {tag_name}")
            if stdout.strip():
                print_color(Colors.BLUE, f"  Release URL: {stdout.strip()}")
    
    def show_completion(self):
        """Show completion summary"""
        print_header("Release Complete!")
        
        tag_name = f"v{self.current_version}"
        
        print_color(Colors.GREEN, f"✓ Successfully released {tag_name}")
        print()
        print_color(Colors.BLUE, "What happened:")
        print_color(Colors.GREEN, f"  • Created commit with version changes")
        print_color(Colors.GREEN, f"  • Created git tag: {tag_name}")
        print_color(Colors.GREEN, f"  • Pushed to remote repository")
        
        if self.has_gh_cli:
            print_color(Colors.GREEN, f"  • Created GitHub release")
        
        print()
        print_color(Colors.BLUE, "Next steps:")
        print_color(Colors.YELLOW, "  • Verify the release at your repository's releases page")
        print_color(Colors.YELLOW, "  • Update any dependent projects")
        print_color(Colors.YELLOW, "  • Announce the release if needed")
        
        print()
        print_color(Colors.PURPLE, f"🎉 Version {tag_name} is now live!")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    pusher = PatchPusher()
    pusher.run()

if __name__ == "__main__":
    main()