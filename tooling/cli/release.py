#!/usr/bin/env python3
"""
release.py - Unified release management script

Combines changelog generation, version bumping, and release pushing into one workflow.
This is the main entry point for creating releases with full automation support.

Features:
- Interactive release type selection (patch, minor, major, custom)
- AI-powered changelog generation
- Version mismatch detection and resolution
- Comprehensive pre-release checks
- Automated commit and tag creation
- GitHub release integration

Requires: Python 3.6+, git, gemini-cli (optional)

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from enum import Enum
import shutil

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
# RELEASE TYPES
# ============================================================================

class ReleaseType(Enum):
    """Types of releases"""
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"
    CUSTOM = "custom"

@dataclass
class ReleaseInfo:
    """Information about the release to create"""
    type: ReleaseType
    version: str
    
    def __str__(self):
        if self.type == ReleaseType.PATCH:
            return "patch"
        else:
            return f"custom|{self.version}"

# ============================================================================
# PREREQUISITES CHECKER
# ============================================================================

class PrerequisitesChecker:
    """Check all prerequisites for release"""
    
    def __init__(self):
        self.required_tools = ["git", "sed", "grep", "awk"]
        self.required_scripts = [
            "tooling/sync_changelogs.py",
            "tooling/prepare_new_patch.py", 
            "tooling/push_new_patch.py",
            "tooling/update_version.py",
            "tooling/get_new_patch_tag.py",
            "tooling/smart_commit.py",
            "tooling/pre_release_check.py",
            "tooling/validate_changelogs.py"
        ]
        # Also check for .sh versions as fallback
        self.fallback_scripts = {
            script.replace('.py', '.sh'): script 
            for script in self.required_scripts
        }
    
    def check(self) -> bool:
        """Run all prerequisite checks"""
        print_header("Checking Prerequisites")
        
        # Check required tools
        if not self._check_required_tools():
            return False
        
        # Check required scripts
        if not self._check_required_scripts():
            return False
        
        # Check AI tools (optional)
        self._check_ai_tools()
        
        print_color(Colors.GREEN, "\n✓ All prerequisites met")
        return True
    
    def _check_required_tools(self) -> bool:
        """Check if required system tools are available"""
        missing_tools = []
        
        for tool in self.required_tools:
            if not shutil.which(tool):
                missing_tools.append(tool)
        
        if missing_tools:
            print_color(Colors.RED, f"Error: Missing required tools: {', '.join(missing_tools)}")
            return False
        
        return True
    
    def _check_required_scripts(self) -> bool:
        """Check if required scripts exist"""
        all_scripts_ok = True
        
        for script in self.required_scripts:
            script_path = Path(script)
            fallback_path = Path(self.fallback_scripts.get(script.replace('.py', '.sh'), ''))
            
            if script_path.exists():
                ensure_executable(str(script_path))
                print_color(Colors.GREEN, f"  ✓ Ready: {script}")
            elif fallback_path.exists():
                ensure_executable(str(fallback_path))
                print_color(Colors.GREEN, f"  ✓ Ready: {fallback_path} (fallback)")
            else:
                print_color(Colors.RED, f"  ✗ Missing: {script}")
                all_scripts_ok = False
        
        if not all_scripts_ok:
            print_color(Colors.RED, "\nError: Some required scripts are missing")
            return False
        
        return True
    
    def _check_ai_tools(self):
        """Check AI tools setup (optional)"""
        ai_tools_ok = True
        
        # Check gemini-cli
        if not shutil.which('gemini-cli'):
            print_color(Colors.YELLOW, "⚠  Warning: gemini-cli not installed")
            print_color(Colors.YELLOW, "   AI-powered features will be unavailable")
            print_color(Colors.YELLOW, "   Run ./tooling/setup_ai_tools.py to install")
            ai_tools_ok = False
        elif not os.environ.get('GEMINI_API_KEY') and \
             not os.environ.get('GEMINI_API_KEY_GLOBAL_CLOUD_RUNTIME_ACCESS'):
            print_color(Colors.YELLOW, "⚠  Warning: No Gemini API key found")
            print_color(Colors.YELLOW, "   AI-powered features will be unavailable")
            print_color(Colors.YELLOW, "   See tooling/SETUP.md for API key setup")
            ai_tools_ok = False
        else:
            print_color(Colors.GREEN, "✓ Gemini API key available")
            print_color(Colors.GREEN, "✓ AI tools ready (gemini-cli installed)")

# ============================================================================
# WORKING TREE CHECKER
# ============================================================================

class WorkingTreeChecker:
    """Check and handle working tree state"""
    
    def check(self) -> bool:
        """Check working tree state"""
        print_header("Checking Working Tree")
        
        # Check git state
        if not check_git_state():
            print_color(Colors.RED, "Please resolve git state issues before proceeding")
            return False
        
        # Check remote sync (just warn)
        check_remote_sync()
        
        # Check for uncommitted changes
        code, stdout, _ = run_command(['git', 'status', '--porcelain'])
        if code != 0:
            return False
        
        if stdout:
            return self._handle_uncommitted_changes(stdout)
        else:
            print_color(Colors.GREEN, "✓ Working tree is clean")
            return True
    
    def _handle_uncommitted_changes(self, changes: str) -> bool:
        """Handle uncommitted changes interactively"""
        print_color(Colors.YELLOW, "You have uncommitted changes:")
        
        # Show first 10 files
        change_lines = changes.strip().split('\n')
        for i, line in enumerate(change_lines[:10]):
            print(f"  {line}")
        
        if len(change_lines) > 10:
            print_color(Colors.YELLOW, f"... and {len(change_lines) - 10} more files")
        
        print()
        
        # Check if smart commit is available
        can_use_ai = self._check_smart_commit_available()
        
        if can_use_ai:
            choice = input("Use AI to commit these changes? (y/n/skip): ")
        else:
            print_color(Colors.YELLOW, "AI commit tools not available (run ./tooling/setup_ai_tools.py)")
            choice = "n"
        
        if choice.lower() == 'y':
            return self._run_smart_commit()
        elif choice.lower() == 'skip':
            print_color(Colors.YELLOW, "Continuing with uncommitted changes...")
            print_color(Colors.YELLOW, "Note: These changes will NOT be included in the release")
            confirm = input("Are you sure? (Y/n): ")
            return not confirm.lower().startswith('n')
        else:
            print_color(Colors.RED, "Cannot create release with uncommitted changes.")
            print_color(Colors.YELLOW, "Please commit or stash your changes first.")
            return False
    
    def _check_smart_commit_available(self) -> bool:
        """Check if smart commit tools are available"""
        # Check for scripts
        fast_script = Path("tooling/smart_commit_fast.py")
        regular_script = Path("tooling/smart_commit.py")
        fast_script_sh = Path("tooling/smart_commit_fast.sh")
        regular_script_sh = Path("tooling/smart_commit.sh")
        
        has_script = (fast_script.exists() or regular_script.exists() or 
                     fast_script_sh.exists() or regular_script_sh.exists())
        
        if not has_script:
            return False
        
        # Check AI tools
        return check_gemini_cli() and check_api_key()
    
    def _run_smart_commit(self) -> bool:
        """Run smart commit tool"""
        print_color(Colors.BLUE, "Running smart commit tool...")
        
        # Try scripts in order of preference
        scripts_to_try = [
            ("tooling/smart_commit_fast.py", True),
            ("tooling/smart_commit_fast.sh", False),
            ("tooling/smart_commit.py", True),
            ("tooling/smart_commit.sh", False)
        ]
        
        for script_path, is_python in scripts_to_try:
            if Path(script_path).exists():
                ensure_executable(script_path)
                
                if is_python:
                    result = subprocess.run([sys.executable, script_path])
                else:
                    result = subprocess.run([script_path])
                
                if result.returncode == 0:
                    return True
                else:
                    print_color(Colors.RED, "Smart commit failed")
                    return False
        
        print_color(Colors.RED, "No smart commit script found")
        return False

# ============================================================================
# RELEASE TYPE DETERMINER
# ============================================================================

class ReleaseTypeDeterminer:
    """Determine what type of release to create"""
    
    def determine(self) -> Optional[ReleaseInfo]:
        """Determine release type interactively"""
        print_header("Release Type Selection")
        
        # Get current version and check for mismatches
        current_version = get_current_version()
        if not current_version:
            print_color(Colors.RED, "Error: Could not determine current version")
            return None
        
        # Handle version mismatches
        if not self._handle_version_mismatches(current_version):
            return None
        
        # Get next patch version
        next_patch = self._get_next_patch_version()
        if not next_patch:
            return None
        
        # Show release type menu
        return self._show_release_menu(current_version, next_patch)
    
    def _handle_version_mismatches(self, current_version: str) -> bool:
        """Check and handle version mismatches"""
        # Get latest tag
        code, stdout, _ = run_command(['git', 'describe', '--tags', '--abbrev=0'])
        if code != 0 or not stdout:
            return True  # No tags yet, that's OK
        
        latest_tag = stdout.strip()
        latest_tag_version = latest_tag.lstrip('v')
        
        if current_version == latest_tag_version:
            return True  # Versions match, all good
        
        # Version mismatch detected
        print_color(Colors.YELLOW, "⚠️  Version mismatch detected!")
        print_color(Colors.YELLOW, f"   Code version: v{current_version}")
        print_color(Colors.YELLOW, f"   Latest tag: v{latest_tag_version}")
        print()
        
        # Check if code is ahead
        comparison = compare_versions(current_version, latest_tag_version)
        if comparison > 0:
            return self._handle_code_ahead(current_version)
        else:
            # Code is behind tag - unusual
            print_color(Colors.YELLOW, "Your code version is behind the latest tag.")
            print_color(Colors.YELLOW, "This is unusual. Consider updating your code version.")
            return True
    
    def _handle_code_ahead(self, code_version: str) -> bool:
        """Handle case where code version is ahead of latest tag"""
        print_color(Colors.BLUE, f"Your code is at v{code_version} but the tag v{code_version} is missing.")
        
        # Check if tag exists
        tag = f"v{code_version}"
        code_local, _, _ = run_command(['git', 'tag', '-l', tag])
        has_local = code_local == 0
        
        code_remote, stdout, _ = run_command(['git', 'ls-remote', '--tags', 'origin'])
        has_remote = code_remote == 0 and f"refs/tags/{tag}" in stdout
        
        if has_local or has_remote:
            # Tag exists
            print_color(Colors.YELLOW, f"⚠️  Tag {tag} already exists!")
            if has_local:
                print_color(Colors.GREEN, "  ✓ Found locally")
            if has_remote:
                print_color(Colors.GREEN, "  ✓ Found on remote")
            
            print()
            print_color(Colors.YELLOW, "This tag matches your current code version.")
            print_color(Colors.YELLOW, "To retag this version, use: ./tooling/retag_release.py")
            print()
            print_color(Colors.CYAN, "What would you like to do?")
            print_color(Colors.WHITE, "  1) Continue with next version")
            print_color(Colors.WHITE, "  2) Switch to retag tool")
            print_color(Colors.WHITE, "  3) Cancel")
            print()
            
            choice = input("Choose option (1-3): ")
            
            if choice == '1':
                print_color(Colors.YELLOW, "Continuing to create next version...")
                return True
            elif choice == '2':
                print_color(Colors.BLUE, "Switching to retag tool...")
                # Try Python version first
                if Path("tooling/retag_release.py").exists():
                    os.execv(sys.executable, [sys.executable, "tooling/retag_release.py"])
                else:
                    subprocess.run(["./tooling/retag_release.sh"])
                sys.exit(0)
            else:
                print_color(Colors.YELLOW, "Release cancelled.")
                return False
        else:
            # Tag doesn't exist, offer to create it
            print()
            print_color(Colors.CYAN, "What would you like to do?")
            print_color(Colors.WHITE, f"  1) Create missing tag v{code_version}")
            print_color(Colors.WHITE, f"  2) Continue with next version (skip v{code_version})")
            print_color(Colors.WHITE, "  3) Cancel")
            print()
            
            choice = input("Choose option (1-3): ")
            
            if choice == '1':
                if self._create_missing_tag(code_version):
                    print_color(Colors.GREEN, f"✓ Tag v{code_version} created successfully")
                    print_color(Colors.YELLOW, "Run the release script again to create the next release")
                    sys.exit(0)
                else:
                    return False
            elif choice == '2':
                print_color(Colors.YELLOW, f"Continuing without creating v{code_version} tag...")
                return True
            else:
                print_color(Colors.YELLOW, "Release cancelled.")
                return False
    
    def _create_missing_tag(self, version: str) -> bool:
        """Create a missing tag"""
        tag = f"v{version}"
        print_color(Colors.BLUE, f"Creating tag {tag}...")
        
        code, _, stderr = run_command(['git', 'tag', tag])
        if code != 0:
            print_color(Colors.RED, f"Failed to create tag: {stderr}")
            return False
        
        print_color(Colors.GREEN, "✓ Tag created locally")
        
        push_choice = input("Push tag to remote? (Y/n): ")
        if not push_choice.lower().startswith('n'):
            code, _, stderr = run_command(['git', 'push', 'origin', tag])
            if code != 0:
                print_color(Colors.RED, f"Failed to push tag: {stderr}")
                run_command(['git', 'tag', '-d', tag])
                return False
            
            print_color(Colors.GREEN, "✓ Tag pushed to remote")
        
        return True
    
    def _get_next_patch_version(self) -> Optional[str]:
        """Get next patch version using the script"""
        # Try Python version first
        script_path = Path("tooling/get_new_patch_tag.py")
        if not script_path.exists():
            script_path = Path("tooling/get_new_patch_tag.sh")
        
        if not script_path.exists():
            print_color(Colors.RED, "Error: get_new_patch_tag script not found")
            return None
        
        ensure_executable(str(script_path))
        
        if script_path.suffix == '.py':
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                [str(script_path)],
                capture_output=True,
                text=True
            )
        
        if result.returncode != 0:
            print_color(Colors.RED, "Failed to determine next version")
            print(result.stdout)
            print(result.stderr)
            return None
        
        # Extract new tag from output
        for line in result.stdout.split('\n'):
            if line.startswith("New tag:"):
                return line.split(":", 1)[1].strip()
        
        return None
    
    def _show_release_menu(self, current_version: str, next_patch: str) -> Optional[ReleaseInfo]:
        """Show release type selection menu"""
        print_color(Colors.BLUE, f"Current version: v{current_version}")
        print_color(Colors.BLUE, f"Next patch version: {next_patch}")
        print()
        
        print_color(Colors.CYAN, "What type of release is this?")
        print_color(Colors.WHITE, f"  1) Patch release (bug fixes, small improvements) → {next_patch}")
        print_color(Colors.WHITE, "  2) Minor release (new features, backward compatible)")
        print_color(Colors.WHITE, "  3) Major release (breaking changes)")
        print_color(Colors.WHITE, "  4) Custom version")
        print_color(Colors.WHITE, "  5) Cancel")
        print()
        
        choice = input("Choose option (1-5): ")
        
        if choice == '1':
            return ReleaseInfo(ReleaseType.PATCH, next_patch.lstrip('v'))
        elif choice == '2':
            # Calculate minor version
            parts = current_version.split('.')
            new_version = f"{parts[0]}.{int(parts[1]) + 1}.0"
            return ReleaseInfo(ReleaseType.MINOR, new_version)
        elif choice == '3':
            # Calculate major version
            parts = current_version.split('.')
            new_version = f"{int(parts[0]) + 1}.0.0"
            return ReleaseInfo(ReleaseType.MAJOR, new_version)
        elif choice == '4':
            custom_version = input("Enter custom version (without 'v' prefix): ")
            
            # Validate version format
            if not validate_version(custom_version):
                print_color(Colors.RED, "Invalid version format. Must be X.Y.Z")
                return None
            
            # Check if version already exists
            if self._check_tag_exists(f"v{custom_version}"):
                print_color(Colors.RED, f"Error: Version v{custom_version} already exists!")
                return None
            
            return ReleaseInfo(ReleaseType.CUSTOM, custom_version)
        else:
            print_color(Colors.YELLOW, "Release cancelled.")
            return None
    
    def _check_tag_exists(self, tag: str) -> bool:
        """Check if a tag exists locally or remotely"""
        code, _, _ = run_command(['git', 'tag', '-l', tag])
        if code == 0:
            return True
        
        code, stdout, _ = run_command(['git', 'ls-remote', '--tags', 'origin'])
        if code == 0 and f"refs/tags/{tag}" in stdout:
            return True
        
        return False

# ============================================================================
# RELEASE MANAGER
# ============================================================================

class ReleaseManager:
    """Main release management orchestrator"""
    
    def __init__(self):
        self.prerequisites = PrerequisitesChecker()
        self.working_tree = WorkingTreeChecker()
        self.type_determiner = ReleaseTypeDeterminer()
    
    def run(self):
        """Run the complete release workflow"""
        print_color(Colors.PURPLE, "╔══════════════════════════════════════════╗")
        print_color(Colors.PURPLE, "║   Unified Release Management Tool v2.0   ║")
        print_color(Colors.PURPLE, "║     Enhanced with Package Awareness      ║")
        print_color(Colors.PURPLE, "╚══════════════════════════════════════════╝")
        
        # Check prerequisites
        if not self.prerequisites.check():
            sys.exit(1)
        
        # Check working tree
        if not self.working_tree.check():
            sys.exit(1)
        
        # Determine release type
        release_info = self.type_determiner.determine()
        if not release_info:
            sys.exit(1)
        
        # Run pre-release checks
        if not self._run_pre_release_checks():
            sys.exit(1)
        
        # Generate changelogs
        self._generate_changelogs()
        
        # Prepare the release
        if not self._prepare_release(release_info):
            sys.exit(1)
        
        # Review changes
        if not self._review_changes():
            sys.exit(1)
        
        # Push the release
        version = self._push_release(release_info)
        if not version:
            sys.exit(1)
        
        # Show post-release info
        self._show_post_release_info(version)
    
    def _run_pre_release_checks(self) -> bool:
        """Run comprehensive pre-release checks"""
        print_header("Running Pre-Release Checks")
        
        # Try Python version first
        check_script = Path("tooling/pre_release_check.py")
        if not check_script.exists():
            check_script = Path("tooling/pre_release_check.sh")
        
        if check_script.exists():
            ensure_executable(str(check_script))
            print_color(Colors.BLUE, "Running comprehensive pre-release validation...")
            
            if check_script.suffix == '.py':
                result = subprocess.run([sys.executable, str(check_script)])
            else:
                result = subprocess.run([str(check_script)])
            
            if result.returncode == 0:
                print_color(Colors.GREEN, "✓ All pre-release checks passed")
                return True
            else:
                print_color(Colors.RED, "✗ Pre-release checks failed")
                print()
                continue_choice = input("Some checks failed. Continue anyway? (y/N): ")
                return continue_choice.lower().startswith('y')
        else:
            # Fallback: simple version check
            print_color(Colors.YELLOW, "⚠ Pre-release check script not found")
            print_color(Colors.YELLOW, "  Consider running: ./tooling/pre_release_check.py")
            
            current_version = get_current_version()
            tag = f"v{current_version}"
            code, _, _ = run_command(['git', 'tag', '-l', tag])
            if code == 0:
                print_color(Colors.RED, f"✗ Tag {tag} already exists!")
                print_color(Colors.YELLOW, "  You need to bump the version first")
                return False
            
            return True
    
    def _generate_changelogs(self):
        """Generate changelogs with AI assistance"""
        print_header("Generating Changelogs")
        
        # Check if AI tools are available
        if not check_gemini_cli() or not check_api_key():
            print_color(Colors.YELLOW, "AI changelog generation not available.")
            print_color(Colors.YELLOW, "You can manually add changelog entries in the next step.")
            return
        
        print_color(Colors.BLUE, "Running AI-powered changelog generation (v2.0)...")
        print_color(Colors.YELLOW, "This will analyze commits and changes by package...")
        
        # Try Python version first
        sync_script = Path("tooling/sync_changelogs.py")
        if not sync_script.exists():
            sync_script = Path("tooling/sync_changelogs.sh")
        
        if sync_script.exists():
            ensure_executable(str(sync_script))
            
            if sync_script.suffix == '.py':
                result = subprocess.run([sys.executable, str(sync_script)])
            else:
                result = subprocess.run([str(sync_script)])
            
            if result.returncode != 0:
                print_color(Colors.RED, "Changelog generation failed!")
                continue_choice = input("Continue without AI changelogs? (y/N): ")
                if not continue_choice.lower().startswith('y'):
                    sys.exit(1)
        
        # Show changelog diffs if any
        changelog_files = ["dart/CHANGELOG.md", "flutter/CHANGELOG.md", "dart/rust/CHANGELOG.md"]
        code, _, _ = run_command(['git', 'diff', '--quiet'] + changelog_files)
        
        if code != 0:  # Changes exist
            print_color(Colors.BLUE, "\nChangelog updates:")
            run_command(['git', 'diff', '--stat'] + changelog_files, capture_output=False)
            
            edit_choice = input("\nReview and edit changelogs now? (y/N): ")
            if edit_choice.lower().startswith('y'):
                editor = os.environ.get('EDITOR', 'vim')
                for changelog in changelog_files:
                    if Path(changelog).exists():
                        subprocess.call([editor, changelog])
        else:
            print_color(Colors.YELLOW, "No changelog updates generated")
    
    def _prepare_release(self, release_info: ReleaseInfo) -> bool:
        """Prepare the release"""
        print_header("Preparing Release")
        
        if release_info.type == ReleaseType.PATCH:
            print_color(Colors.BLUE, "Preparing patch release...")
            
            # Try Python version first
            prepare_script = Path("tooling/prepare_new_patch.py")
            if not prepare_script.exists():
                prepare_script = Path("tooling/prepare_new_patch.sh")
            
            if prepare_script.exists():
                ensure_executable(str(prepare_script))
                
                if prepare_script.suffix == '.py':
                    result = subprocess.run([sys.executable, str(prepare_script)])
                else:
                    result = subprocess.run([str(prepare_script)])
                
                if result.returncode != 0:
                    print_color(Colors.RED, "Failed to prepare patch release")
                    return False
            else:
                print_color(Colors.RED, "prepare_new_patch script not found")
                return False
        else:
            # Update version files
            print_color(Colors.BLUE, f"Updating to version {release_info.version}...")
            
            # Try Python version first
            update_script = Path("tooling/update_version.py")
            if not update_script.exists():
                update_script = Path("tooling/update_version.sh")
            
            if update_script.exists():
                ensure_executable(str(update_script))
                
                if update_script.suffix == '.py':
                    result = subprocess.run([sys.executable, str(update_script), release_info.version])
                else:
                    result = subprocess.run([str(update_script), release_info.version])
                
                if result.returncode != 0:
                    print_color(Colors.RED, "Failed to update version")
                    return False
            else:
                print_color(Colors.RED, "update_version script not found")
                return False
            
            # Add version headers to changelogs
            self._add_changelog_headers(release_info.version)
        
        return True
    
    def _add_changelog_headers(self, version: str):
        """Add version headers to changelog files if missing"""
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        changelog_files = [
            ("dart/CHANGELOG.md", "Dart"),
            ("flutter/CHANGELOG.md", "Flutter"),
            ("dart/rust/CHANGELOG.md", "Rust")
        ]
        
        for changelog_path, package_name in changelog_files:
            if not Path(changelog_path).exists():
                continue
            
            # Check if version header already exists
            with open(changelog_path, 'r') as f:
                content = f.read()
            
            if f"## [v{version}]" not in content:
                print_color(Colors.YELLOW, f"Adding version header to {changelog_path}")
                
                # Split content to preserve header
                lines = content.split('\n')
                header_lines = lines[:7] if len(lines) >= 7 else lines
                rest_lines = lines[7:] if len(lines) > 7 else []
                
                # Create new content
                new_lines = header_lines + [
                    "",
                    f"## [v{version}] - {current_date}",
                    "",
                    "### Changed",
                    f"- Version bump to v{version}",
                    ""
                ] + rest_lines
                
                # Write back
                with open(changelog_path, 'w') as f:
                    f.write('\n'.join(new_lines))
    
    def _review_changes(self) -> bool:
        """Review all changes before release"""
        print_header("Review Changes")
        
        print_color(Colors.BLUE, "Summary of changes:")
        print()
        
        # Show version changes
        print_color(Colors.YELLOW, "Version updates:")
        for file in ["dart/pubspec.yaml", "flutter/pubspec.yaml"]:
            if Path(file).exists():
                version = extract_yaml_value(file, "version")
                if version:
                    print(f"  {file}: {version}")
        
        if Path("dart/rust/Cargo.toml").exists():
            version = extract_toml_value("dart/rust/Cargo.toml", "version")
            if version:
                print(f"  dart/rust/Cargo.toml: {version}")
        
        print()
        
        # Show recent changelog entries
        print_color(Colors.YELLOW, "Recent changelog entries:")
        self._show_recent_changelog_entries()
        
        # Show git diff summary
        print_color(Colors.YELLOW, "Files changed:")
        run_command(['git', 'diff', '--name-status'], capture_output=False)
        print()
        
        # Count changes
        code, stdout, _ = run_command(['git', 'diff', '--name-only'])
        if code == 0 and stdout:
            changes_count = len(stdout.strip().split('\n'))
            print_color(Colors.BLUE, f"Total files changed: {changes_count}")
            
            view_diff = input("\nView full diff? (y/N): ")
            if view_diff.lower().startswith('y'):
                subprocess.call(['git', 'diff'])
        else:
            print_color(Colors.YELLOW, "No uncommitted changes to review")
        
        print()
        print_color(Colors.GREEN, "Ready to create release!")
        proceed = input("Proceed with release? (y/N): ")
        
        return proceed.lower().startswith('y')
    
    def _show_recent_changelog_entries(self):
        """Show recent changelog entries for review"""
        changelog_files = [
            "dart/CHANGELOG.md",
            "flutter/CHANGELOG.md", 
            "dart/rust/CHANGELOG.md"
        ]
        
        for changelog in changelog_files:
            if not Path(changelog).exists():
                continue
            
            print(f"\n--- {changelog} ---")
            
            try:
                with open(changelog, 'r') as f:
                    lines = f.readlines()
                
                # Find most recent version entry
                in_recent = False
                line_count = 0
                
                for line in lines:
                    if line.startswith('## [v'):
                        if in_recent:
                            break  # Stop at next version
                        else:
                            in_recent = True
                    
                    if in_recent:
                        print(line.rstrip())
                        line_count += 1
                        if line_count > 15:
                            print("...")
                            break
            except Exception as e:
                print(f"Error reading changelog: {e}")
    
    def _push_release(self, release_info: ReleaseInfo) -> Optional[str]:
        """Push the release"""
        print_header("Pushing Release")
        
        if release_info.type == ReleaseType.PATCH:
            # Use push script for patch releases
            print_color(Colors.BLUE, "Using enhanced push script...")
            
            push_script = Path("tooling/push_new_patch.py")
            if not push_script.exists():
                push_script = Path("tooling/push_new_patch.sh")
            
            if push_script.exists():
                ensure_executable(str(push_script))
                
                if push_script.suffix == '.py':
                    result = subprocess.run([sys.executable, str(push_script)])
                else:
                    result = subprocess.run([str(push_script)])
                
                if result.returncode != 0:
                    print_color(Colors.RED, "Failed to push release")
                    return None
            else:
                print_color(Colors.RED, "push_new_patch script not found")
                return None
            
            # Get the version that was released
            code, stdout, _ = run_command(['git', 'describe', '--tags', '--abbrev=0'])
            return stdout.strip() if code == 0 else None
        else:
            # Manual commit and tag for custom versions
            version = release_info.version
            
            # Check for uncommitted changes
            code, stdout, _ = run_command(['git', 'diff', '--quiet'])
            if code != 0:  # Changes exist
                # Commit changes
                run_command(['git', 'add', '.'])
                
                commit_msg = f"""chore: release v{version}

- Updated version to {version} in all packages
- Updated CHANGELOG.md files with release notes
- Synchronized package versions across Dart, Flutter, and Rust

Release type: {release_info.type.value}"""
                
                code, _, stderr = run_command(['git', 'commit', '-m', commit_msg])
                if code != 0:
                    print_color(Colors.RED, f"Failed to commit: {stderr}")
                    return None
                
                print_color(Colors.GREEN, "✓ Changes committed")
            
            # Create tag
            tag = f"v{version}"
            code, _, stderr = run_command(['git', 'tag', tag])
            if code != 0:
                print_color(Colors.RED, f"Failed to create tag: {stderr}")
                return None
            
            print_color(Colors.GREEN, f"✓ Tag {tag} created")
            
            # Push commits
            code, branch, _ = run_command(['git', 'branch', '--show-current'])
            if code == 0 and branch:
                print_color(Colors.BLUE, f"Pushing to origin/{branch}...")
                code, _, stderr = run_command(['git', 'push', 'origin', branch])
                if code != 0:
                    print_color(Colors.RED, f"Failed to push commits: {stderr}")
                    return None
            
            # Push tag
            print_color(Colors.BLUE, f"Pushing tag {tag}...")
            code, _, stderr = run_command(['git', 'push', 'origin', tag])
            if code != 0:
                print_color(Colors.RED, f"Failed to push tag: {stderr}")
                run_command(['git', 'tag', '-d', tag])
                return None
            
            print_color(Colors.GREEN, "✓ Pushed to origin")
            return tag
    
    def _show_post_release_info(self, version: str):
        """Show post-release information"""
        print_header("Release Complete! 🎉")
        
        print_color(Colors.GREEN, f"Successfully released version {version}")
        print()
        
        # Try to get GitHub URL
        github_url = self._get_github_url()
        
        print_color(Colors.BLUE, "What happens next:")
        print_color(Colors.WHITE, "  1. GitHub Actions will build for all platforms")
        print_color(Colors.WHITE, "  2. Release artifacts will be uploaded to Google Cloud Storage")
        print_color(Colors.WHITE, "  3. A GitHub Release will be created with AI-generated notes")
        print_color(Colors.WHITE, "  4. Package registries will be updated (if configured)")
        print()
        
        if github_url:
            print_color(Colors.BLUE, "Monitor the release:")
            print_color(Colors.WHITE, f"  • GitHub Actions: {github_url}/actions")
            print_color(Colors.WHITE, f"  • Releases page: {github_url}/releases")
            print_color(Colors.WHITE, f"  • Tag page: {github_url}/releases/tag/{version}")
        else:
            print_color(Colors.BLUE, "Monitor the release:")
            print_color(Colors.WHITE, "  • Check your CI/CD pipeline")
            print_color(Colors.WHITE, "  • Verify the release artifacts")
        
        print()
        print_color(Colors.YELLOW, "Next steps:")
        print_color(Colors.WHITE, "  • Monitor the CI/CD pipeline for any issues")
        print_color(Colors.WHITE, "  • Verify the GitHub Release was created correctly")
        print_color(Colors.WHITE, "  • Check that artifacts are available")
        print_color(Colors.WHITE, "  • Update any dependent projects")
        print_color(Colors.WHITE, "  • Announce the release if needed")
        print()
        print_color(Colors.GRAY, "If you need to fix this release:")
        print_color(Colors.WHITE, "  • Use ./tooling/retag_release.py to update and re-tag")
    
    def _get_github_url(self) -> Optional[str]:
        """Extract GitHub URL from git remote"""
        code, stdout, _ = run_command(['git', 'config', '--get', 'remote.origin.url'])
        if code != 0 or not stdout:
            return None
        
        repo_url = stdout.strip()
        
        # Handle various URL formats
        patterns = [
            r'^https://github.com/([^/]+)/([^/.]+)',
            r'^git@github.com:([^/]+)/([^/.]+)',
            r'github.com[:/]([^/]+)/([^/.]+)'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, repo_url)
            if match:
                return f"https://github.com/{match.group(1)}/{match.group(2)}"
        
        return None

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    manager = ReleaseManager()
    
    try:
        manager.run()
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Release cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error: {str(e)}")
        sys.exit(1)
    finally:
        cleanup_temp_files()

if __name__ == "__main__":
    main()