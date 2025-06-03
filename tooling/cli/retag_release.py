#!/usr/bin/env python3
"""
retag_release.py - Delete current tag, update changelogs, and re-release
Useful when you need to fix a release after it's been tagged

This script handles:
- Version validation and mismatch detection
- Safe tag deletion (local and remote)
- Changelog updates with AI assistance
- Commit and tag recreation

Requires: Python 3.6+, git

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import re

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
# GITHUB LINK UTILITIES
# ============================================================================

def get_github_repo_url() -> Optional[str]:
    """Get the GitHub repository URL from git remote"""
    code, stdout, _ = run_command(['git', 'remote', 'get-url', 'origin'])
    if code == 0 and stdout:
        url = stdout.strip()
        # Convert SSH to HTTPS format
        if url.startswith('git@github.com:'):
            url = url.replace('git@github.com:', 'https://github.com/')
        if url.endswith('.git'):
            url = url[:-4]
        return url
    return None

def make_github_tag_link(tag: str) -> str:
    """Create a clickable GitHub tag link"""
    repo_url = get_github_repo_url()
    if repo_url:
        return f"{repo_url}/releases/tag/{tag}"
    return tag

def make_github_commit_link(commit_hash: str) -> str:
    """Create a clickable GitHub commit link"""
    repo_url = get_github_repo_url()
    if repo_url:
        return f"{repo_url}/commit/{commit_hash}"
    return commit_hash

def make_github_branch_link(branch: str) -> str:
    """Create a clickable GitHub branch link"""
    repo_url = get_github_repo_url()
    if repo_url:
        return f"{repo_url}/tree/{branch}"
    return branch

def make_clickable_link(url: str, text: str = None) -> str:
    """Create a clickable terminal link using ANSI escape sequences"""
    if not text:
        text = url
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"

# ============================================================================
# TAG OPERATIONS
# ============================================================================

class TagManager:
    """Handle git tag operations"""
    
    @staticmethod
    def get_latest_tag() -> Optional[str]:
        """Get the latest tag in the repository"""
        code, stdout, _ = run_command(['git', 'describe', '--tags', '--abbrev=0'])
        return stdout.strip() if code == 0 and stdout else None
    
    @staticmethod
    def tag_exists_local(tag: str) -> bool:
        """Check if tag exists locally"""
        code, stdout, _ = run_command(['git', 'tag', '-l'])
        if code == 0 and stdout:
            return tag in stdout.strip().split('\n')
        return False
    
    @staticmethod
    def tag_exists_remote(tag: str) -> bool:
        """Check if tag exists on remote"""
        code, stdout, _ = run_command(['git', 'ls-remote', '--tags', 'origin'])
        if code == 0 and stdout:
            return f"refs/tags/{tag}" in stdout
        return False
    
    @staticmethod
    def delete_tag(tag: str, delete_remote: bool = False) -> bool:
        """Delete tag locally and optionally remotely"""
        tag_version = tag.lstrip('v')
        code_version = get_current_version()
        
        # Safety check - warn if deleting a tag that matches current code version
        if tag_version == code_version:
            tag_link = make_clickable_link(make_github_tag_link(tag), tag)
            print_color(Colors.YELLOW, f"⚠️  WARNING: This tag ({tag_link}) matches your current code version!")
            print_color(Colors.YELLOW, "   Deleting it will create a version mismatch.")
            confirm = input("Are you sure you want to delete it? (y/N): ")
            if not confirm.lower().startswith('y'):
                print_color(Colors.YELLOW, "Tag deletion cancelled")
                return False
        
        tag_link = make_clickable_link(make_github_tag_link(tag), tag)
        print_color(Colors.YELLOW, f"Deleting tag {tag_link}...")
        
        # Delete local tag
        if TagManager.tag_exists_local(tag):
            code, _, stderr = run_command(['git', 'tag', '-d', tag])
            if code == 0:
                print_color(Colors.GREEN, "  ✓ Deleted local tag")
            else:
                print_color(Colors.RED, f"  ✗ Failed to delete local tag: {stderr}")
                return False
        else:
            print_color(Colors.YELLOW, "  ⚠ Local tag not found")
        
        # Delete remote tag if requested
        if delete_remote:
            if TagManager.tag_exists_remote(tag):
                print_color(Colors.YELLOW, "  Deleting remote tag...")
                code, _, stderr = run_command(['git', 'push', 'origin', '--delete', tag])
                if code == 0:
                    print_color(Colors.GREEN, "  ✓ Deleted remote tag")
                else:
                    print_color(Colors.RED, f"  ✗ Failed to delete remote tag: {stderr}")
                    return False
            else:
                print_color(Colors.YELLOW, "  ⚠ Remote tag not found")
        
        return True
    
    @staticmethod
    def create_tag(tag: str) -> bool:
        """Create a new tag"""
        tag_link = make_clickable_link(make_github_tag_link(tag), tag)
        print_color(Colors.BLUE, f"Creating tag {tag_link}...")
        code, _, stderr = run_command(['git', 'tag', tag])
        if code == 0:
            print_color(Colors.GREEN, "✓ Tag created locally")
            return True
        else:
            print_color(Colors.RED, f"Failed to create tag: {stderr}")
            return False
    
    @staticmethod
    def push_tag(tag: str, force: bool = False) -> bool:
        """Push tag to remote"""
        print_color(Colors.BLUE, "Pushing tag to remote...")
        cmd = ['git', 'push', 'origin', tag]
        if force:
            cmd.append('--force')
        
        code, _, stderr = run_command(cmd)
        if code == 0:
            print_color(Colors.GREEN, "✓ Tag pushed to remote")
            return True
        else:
            print_color(Colors.RED, f"Failed to push tag: {stderr}")
            return False

# ============================================================================
# VERSION COMPARISON
# ============================================================================

class VersionComparer:
    """Handle version comparisons and validation"""
    
    @staticmethod
    def parse_version(version: str) -> Tuple[int, int, int]:
        """Parse version string into major, minor, patch"""
        parts = version.lstrip('v').split('.')
        return (
            int(parts[0]) if len(parts) > 0 else 0,
            int(parts[1]) if len(parts) > 1 else 0,
            int(parts[2]) if len(parts) > 2 else 0
        )
    
    @staticmethod
    def compare_versions(v1: str, v2: str) -> int:
        """Compare versions: -1 if v1 < v2, 0 if equal, 1 if v1 > v2"""
        v1_parts = VersionComparer.parse_version(v1)
        v2_parts = VersionComparer.parse_version(v2)
        
        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        else:
            return 0
    
    @staticmethod
    def version_is_ahead(code_version: str, tag_version: str) -> bool:
        """Check if code version is ahead of tag version"""
        return VersionComparer.compare_versions(code_version, tag_version) > 0
    
    @staticmethod
    def version_is_behind(code_version: str, tag_version: str) -> bool:
        """Check if code version is behind tag version"""
        return VersionComparer.compare_versions(code_version, tag_version) < 0

# ============================================================================
# RELEASE INFO DISPLAY
# ============================================================================

class ReleaseInfoDisplay:
    """Display release information"""
    
    @staticmethod
    def show_release_info(tag: str):
        """Show comprehensive release information"""
        version = tag.lstrip('v')
        code_version = get_current_version()
        
        print_header("Current Release Information")
        
        tag_link = make_clickable_link(make_github_tag_link(tag), tag)
        print_color(Colors.BLUE, f"Tag: {tag_link}")
        print_color(Colors.BLUE, f"Tag Version: {version}")
        print_color(Colors.BLUE, f"Code Version: v{code_version}")
        
        # Show version match status
        if version == code_version:
            print_color(Colors.GREEN, "  ✓ Tag and code versions match")
        else:
            print_color(Colors.YELLOW, "  ⚠ Tag and code versions differ")
        
        # Check tag existence
        local_exists = TagManager.tag_exists_local(tag)
        remote_exists = TagManager.tag_exists_remote(tag)
        
        if local_exists:
            print_color(Colors.GREEN, "  ✓ Tag exists locally")
        else:
            print_color(Colors.YELLOW, "  ⚠ Tag not found locally")
        
        if remote_exists:
            print_color(Colors.GREEN, "  ✓ Tag exists on remote")
        else:
            print_color(Colors.YELLOW, "  ⚠ Tag not found on remote")
        
        # Show tag commit info if exists
        if local_exists:
            print()
            print_color(Colors.BLUE, "Tag commit:")
            code, stdout, _ = run_command([
                'git', 'show', '--no-patch', 
                '--format=%h %s%n%an <%ae>%n%ad',
                tag
            ])
            if code == 0 and stdout:
                lines = stdout.strip().split('\n')
                if len(lines) >= 3:
                    commit_hash = lines[0].split()[0]
                    commit_msg = ' '.join(lines[0].split()[1:])
                    author = lines[1]
                    date = lines[2]
                    
                    commit_link = make_clickable_link(make_github_commit_link(commit_hash), commit_hash)
                    print(f"  {commit_link} {commit_msg}")
                    print(f"  Author: {author}")
                    print(f"  Date: {date}")
        
        # Show changelog entries
        print()
        print_color(Colors.BLUE, f"Current changelog entries for v{version}:")
        
        ReleaseInfoDisplay._show_changelog_entries(version)
    
    @staticmethod
    def _show_changelog_entries(version: str):
        """Show changelog entries for a version"""
        changelogs = [
            (DART_CHANGELOG, "Dart"),
            (FLUTTER_CHANGELOG, "Flutter"),
            (RUST_CHANGELOG, "Rust")
        ]
        
        for changelog_path, package_name in changelogs:
            if Path(changelog_path).exists():
                print()
                print_color(Colors.YELLOW, f"  {package_name} package ({changelog_path}):")
                
                # Extract version section
                entry = extract_changelog_section(changelog_path, version)
                
                if entry:
                    lines = entry.strip().split('\n')
                    # Show first 10 lines and make commit links clickable
                    for i, line in enumerate(lines[:10]):
                        # Look for commit hashes and make them clickable
                        commit_pattern = r'\[([a-f0-9]{7,40})\]'
                        def make_commit_clickable(match):
                            commit_hash = match.group(1)
                            commit_link = make_clickable_link(make_github_commit_link(commit_hash), commit_hash)
                            return f"[{commit_link}]"
                        
                        line = re.sub(commit_pattern, make_commit_clickable, line)
                        print(f"    {line}")
                    
                    if len(lines) > 10:
                        print_color(Colors.GRAY, f"    ... and {len(lines) - 10} more lines")
                else:
                    print_color(Colors.GRAY, f"    No entry found for v{version}")

# ============================================================================
# CHANGELOG UPDATER
# ============================================================================

class ChangelogUpdater:
    """Handle changelog updates with AI assistance"""
    
    def __init__(self, tag: str, version: str):
        self.tag = tag
        self.version = version
        self.tag_commit = self._get_tag_commit()
    
    def _get_tag_commit(self) -> Optional[str]:
        """Get the commit SHA that the tag points to"""
        code, stdout, _ = run_command(['git', 'rev-list', '-n', '1', self.tag])
        return stdout.strip() if code == 0 and stdout else None
    
    def analyze_changes(self) -> Dict[str, int]:
        """Analyze what changed since the tag"""
        print_color(Colors.BLUE, f"Analyzing changes since tag {self.tag}...")
        
        changes = {
            'dart': 0,
            'flutter': 0,
            'rust': 0,
            'tooling': 0,
            'other': 0
        }
        
        if not self.tag_commit:
            return changes
        
        # Get files changed since tag
        code, stdout, _ = run_command(['git', 'diff', '--name-only', f'{self.tag_commit}..HEAD'])
        
        if code == 0 and stdout:
            for file in stdout.strip().split('\n'):
                if file.startswith('dart/rust/'):
                    changes['rust'] += 1
                elif file.startswith('flutter/'):
                    changes['flutter'] += 1
                elif file.startswith('dart/'):
                    changes['dart'] += 1
                elif file.startswith('tooling/'):
                    changes['tooling'] += 1
                else:
                    changes['other'] += 1
        
        # Show summary
        print_color(Colors.GREEN, f"Changes detected since {self.tag}:")
        for module, count in changes.items():
            if count > 0:
                print_color(Colors.YELLOW, f"  {module.capitalize()}: {count} files")
        
        return changes
    
    def update_changelogs(self) -> bool:
        """Update changelogs with AI assistance"""
        print_header("Updating Changelogs")
        
        # Check if sync_changelogs.py exists
        sync_script = Path("tooling/sync_changelogs.py")
        if not sync_script.exists():
            # Try bash version as fallback
            sync_script = Path("tooling/sync_changelogs.sh")
            if not sync_script.exists():
                print_color(Colors.RED, "Error: sync_changelogs script not found")
                return False
        
        # Make it executable
        ensure_executable(str(sync_script))
        
        # Analyze changes
        changes = self.analyze_changes()
        
        # Ask for retag reason
        print()
        print_color(Colors.BLUE, "Why are you retagging this release?")
        print_color(Colors.YELLOW, "This helps the AI generate better changelog updates.")
        print("Examples:")
        print("  - Fixed typos in documentation")
        print("  - Added missing changelog entries")
        print("  - Corrected version numbers")
        print("  - Fixed build configuration")
        print()
        retag_reason = input("Reason for retagging (or press Enter to skip): ")
        
        # Create context file
        context_file = self._create_context_file(changes, retag_reason)
        
        try:
            # Set environment variables for sync_changelogs
            env = os.environ.copy()
            env.update({
                'RETAG_MODE': 'true',
                'RETAG_VERSION': self.version,
                'RETAG_TAG': self.tag,
                'RETAG_REASON': retag_reason,
                'RETAG_CONTEXT_FILE': str(context_file)
            })
            
            # Run sync_changelogs
            print_color(Colors.BLUE, "Running changelog sync with retag context...")
            
            result = subprocess.run(
                [sys.executable, str(sync_script), '--smart'] if sync_script.suffix == '.py' else [str(sync_script), '--smart'],
                env=env
            )
            
            if result.returncode != 0:
                print_color(Colors.RED, "Failed to sync changelogs")
                return False
            
            return True
            
        finally:
            # Clean up
            if context_file.exists():
                context_file.unlink()
    
    def _create_context_file(self, changes: Dict[str, int], retag_reason: str) -> Path:
        """Create context file for sync_changelogs"""
        context_file = Path(tempfile.mktemp(suffix='_retag_context.txt'))
        
        # Get files changed
        changed_files = []
        if self.tag_commit:
            code, stdout, _ = run_command(['git', 'diff', '--name-only', f'{self.tag_commit}..HEAD'])
            if code == 0 and stdout:
                changed_files = stdout.strip().split('\n')
        
        with open(context_file, 'w') as f:
            f.write("RETAG CONTEXT INFORMATION\n")
            f.write("========================\n")
            f.write(f"Tag being fixed: {self.tag}\n")
            f.write(f"Version: {self.version}\n")
            if retag_reason:
                f.write(f"Reason: {retag_reason}\n")
            f.write("\n")
            f.write("Files changed since tag:\n")
            
            if changed_files:
                for i, file in enumerate(changed_files[:20]):
                    f.write(f"{file}\n")
                if len(changed_files) > 20:
                    f.write(f"... and {len(changed_files) - 20} more files\n")
            else:
                f.write("No files changed since tag\n")
            
            f.write("\n")
            f.write("Module breakdown:\n")
            for module, count in changes.items():
                f.write(f"  {module.capitalize()}: {count} files\n")
        
        return context_file

# ============================================================================
# MAIN RETAG RELEASE CLASS
# ============================================================================

class RetagRelease:
    """Main class for retagging releases"""
    
    def __init__(self):
        self.tag_manager = TagManager()
        self.version_comparer = VersionComparer()
        
    def run(self):
        """Main execution"""
        print_color(Colors.PURPLE, "╔════════════════════════════════════════╗")
        print_color(Colors.PURPLE, "║      Release Re-tagging Tool v1.0      ║")
        print_color(Colors.PURPLE, "║   Update and Re-release Current Tag    ║")
        print_color(Colors.PURPLE, "╚════════════════════════════════════════╝")
        print()
        
        # Ensure we're in project root
        ensure_project_root()
        
        # Check git state
        if not check_git_state():
            print_color(Colors.RED, "Please resolve git state issues before proceeding")
            sys.exit(1)
        
        # Get latest tag
        latest_tag = self.tag_manager.get_latest_tag()
        
        if not latest_tag:
            print_color(Colors.RED, "Error: No tags found in repository")
            print_color(Colors.YELLOW, "This tool is for updating existing releases.")
            print_color(Colors.YELLOW, "To create a new release, use: ./tooling/release.py")
            sys.exit(1)
        
        # Handle version mismatches and determine tag to use
        tag_to_use = self._handle_version_mismatch(latest_tag)
        
        # Show release info
        ReleaseInfoDisplay.show_release_info(tag_to_use)
        
        # Confirm action - default to yes
        print()
        tag_link = make_clickable_link(make_github_tag_link(tag_to_use), tag_to_use)
        print_color(Colors.YELLOW, f"⚠️  WARNING: This will delete and recreate tag {tag_link}")
        print_color(Colors.YELLOW, "   This should only be done if:")
        print_color(Colors.YELLOW, "   - The release hasn't been widely distributed")
        print_color(Colors.YELLOW, "   - You need to fix critical issues in the release")
        print_color(Colors.YELLOW, "   - No one has pulled/used this tag yet")
        print()
        
        confirm = input("Continue? (Y/n): ") or "Y"
        if confirm.lower().startswith('n'):
            print_color(Colors.YELLOW, "Operation cancelled")
            return
        
        # Delete the tag
        if not self.tag_manager.delete_tag(tag_to_use, delete_remote=True):
            print_color(Colors.RED, "Failed to delete tag")
            sys.exit(1)
        
        # Update changelogs - default to yes
        print()
        self._handle_changelog_updates(tag_to_use)
        
        # Allow manual edits - default to no
        print()
        edit_choice = input("Make manual edits to files? (y/N): ") or "N"
        if edit_choice.lower().startswith('y'):
            print_color(Colors.BLUE, "Opening changelog files for editing...")
            editor = os.environ.get('EDITOR', 'vim')
            subprocess.call([editor, DART_CHANGELOG, FLUTTER_CHANGELOG, RUST_CHANGELOG])
        
        # Commit changes
        self._commit_changes(tag_to_use)
        
        # Recreate and push tag - default to yes
        print()
        print_color(Colors.BLUE, f"Ready to recreate tag {tag_to_use}")
        proceed = input("Proceed? (Y/n): ") or "Y"
        
        if proceed.lower().startswith('n'):
            print_color(Colors.YELLOW, "Tag recreation cancelled")
            print_color(Colors.YELLOW, "Note: The original tag has already been deleted!")
            print_color(Colors.YELLOW, f"You'll need to manually create it with: git tag {tag_to_use} && git push origin {tag_to_use}")
            sys.exit(1)
        
        # Recreate tag
        if not self.tag_manager.create_tag(tag_to_use):
            print_color(Colors.RED, "Failed to recreate tag")
            sys.exit(1)
        
        # Push tag
        if not self.tag_manager.push_tag(tag_to_use, force=True):
            print_color(Colors.RED, "Failed to push tag")
            # Clean up local tag
            self.tag_manager.delete_tag(tag_to_use, delete_remote=False)
            sys.exit(1)
        
        # Success!
        print_header("Success! 🎉")
        
        tag_link = make_clickable_link(make_github_tag_link(tag_to_use), tag_to_use)
        print_color(Colors.GREEN, f"Successfully re-tagged release {tag_link}")
        print()
        print_color(Colors.BLUE, "What happened:")
        print_color(Colors.GREEN, "  ✓ Deleted old tag (local and remote)")
        print_color(Colors.GREEN, "  ✓ Updated changelogs and files")
        print_color(Colors.GREEN, "  ✓ Committed changes")
        print_color(Colors.GREEN, "  ✓ Recreated tag at current commit")
        print_color(Colors.GREEN, "  ✓ Pushed tag to remote")
        print()
        print_color(Colors.YELLOW, "Note: If CI/CD was triggered by the original tag,")
        print_color(Colors.YELLOW, "it may run again for the new tag.")
    
    def _handle_version_mismatch(self, latest_tag: str) -> str:
        """Handle version mismatches and return tag to use"""
        code_version = get_current_version()
        latest_tag_version = latest_tag.lstrip('v')
        
        if code_version == latest_tag_version:
            # Versions match, allow user to choose tag
            tag_link = make_clickable_link(make_github_tag_link(latest_tag), latest_tag)
            print_color(Colors.BLUE, f"Latest tag: {tag_link}")
            chosen_tag = input("Use this tag or specify another? (Enter for latest, or type tag name): ")
            
            if chosen_tag:
                # Validate tag exists
                if not self.tag_manager.tag_exists_local(chosen_tag) and \
                   not self.tag_manager.tag_exists_remote(chosen_tag):
                    print_color(Colors.RED, f"Error: Tag {chosen_tag} not found")
                    sys.exit(1)
                
                # Validate version isn't too low
                chosen_version = chosen_tag.lstrip('v')
                if self.version_comparer.version_is_behind(chosen_version, code_version):
                    print_color(Colors.RED, f"Error: Cannot retag v{chosen_version} when code is at v{code_version}")
                    sys.exit(1)
                
                return chosen_tag
            
            return latest_tag
        
        # Version mismatch
        print_color(Colors.YELLOW, "⚠️  Version mismatch detected!")
        print_color(Colors.YELLOW, f"   Code version: v{code_version}")
        print_color(Colors.YELLOW, f"   Latest tag: v{latest_tag_version}")
        print()
        
        if self.version_comparer.version_is_ahead(code_version, latest_tag_version):
            # Code is ahead
            return self._handle_code_ahead(code_version, latest_tag)
        else:
            # Code is behind
            print_color(Colors.YELLOW, "Your code version is behind the latest tag.")
            print_color(Colors.YELLOW, "This is unusual - you may want to:")
            print_color(Colors.WHITE, "  • Update your code to match the tag version")
            print_color(Colors.WHITE, "  • Or proceed with retagging if intentional")
            print()
            
            continue_choice = input(f"Continue with retagging v{latest_tag}? (y/N): ")
            if not continue_choice.lower().startswith('y'):
                sys.exit(0)
            
            return latest_tag
    
    def _handle_code_ahead(self, code_version: str, latest_tag: str) -> str:
        """Handle case where code is ahead of latest tag"""
        print_color(Colors.BLUE, f"Your code is at v{code_version} but there's no matching tag.")
        
        code_tag = f"v{code_version}"
        code_tag_exists_local = self.tag_manager.tag_exists_local(code_tag)
        code_tag_exists_remote = self.tag_manager.tag_exists_remote(code_tag)
        
        if code_tag_exists_local or code_tag_exists_remote:
            # Tag exists, offer to retag it
            tag_link = make_clickable_link(make_github_tag_link(code_tag), code_tag)
            print_color(Colors.YELLOW, f"⚠️  Tag {tag_link} already exists!")
            if code_tag_exists_local:
                print_color(Colors.GREEN, "  ✓ Found locally")
            if code_tag_exists_remote:
                print_color(Colors.GREEN, "  ✓ Found on remote")
            
            print()
            print_color(Colors.CYAN, "What would you like to do?")
            print_color(Colors.WHITE, f"  1) Retag {code_tag} (delete and recreate) [DEFAULT]")
            print_color(Colors.WHITE, "  2) Retag a different version")
            print_color(Colors.WHITE, "  3) Cancel")
            print()
            
            choice = input("Choose option (1-3) [1]: ") or "1"
            
            if choice == "1":
                return code_tag
            elif choice == "2":
                return self._get_custom_tag(code_version)
            else:
                print_color(Colors.YELLOW, "Operation cancelled")
                sys.exit(0)
        else:
            # Tag doesn't exist, offer to create it
            print_color(Colors.CYAN, "What would you like to do?")
            print_color(Colors.WHITE, f"  1) Create tag {code_tag} (recommended) [DEFAULT]")
            print_color(Colors.WHITE, f"  2) Retag a different version (must be >= v{code_version})")
            print_color(Colors.WHITE, "  3) Cancel")
            print()
            
            choice = input("Choose option (1-3) [1]: ") or "1"
            
            if choice == "1":
                # Create the tag now
                print_color(Colors.BLUE, f"Creating tag {code_tag}...")
                if self.tag_manager.create_tag(code_tag):
                    push_choice = input("Push tag to remote? (Y/n): ") or "Y"
                    if not push_choice.lower().startswith('n'):
                        if self.tag_manager.push_tag(code_tag):
                            tag_link = make_clickable_link(make_github_tag_link(code_tag), code_tag)
                            print_color(Colors.GREEN, f"✓ Tag {tag_link} pushed to remote")
                            print_color(Colors.YELLOW, "Tag created successfully. No retag needed.")
                            sys.exit(0)
                        else:
                            self.tag_manager.delete_tag(code_tag)
                            sys.exit(1)
                else:
                    sys.exit(1)
            elif choice == "2":
                return self._get_custom_tag(code_version)
            else:
                print_color(Colors.YELLOW, "Operation cancelled")
                sys.exit(0)
    
    def _get_custom_tag(self, min_version: str) -> str:
        """Get custom tag from user with validation"""
        chosen_tag = input(f"Enter tag to retag (must be v{min_version} or higher): ")
        
        if not chosen_tag:
            print_color(Colors.RED, "No tag specified")
            sys.exit(1)
        
        # Validate version
        chosen_version = chosen_tag.lstrip('v')
        if self.version_comparer.version_is_behind(chosen_version, min_version):
            print_color(Colors.RED, f"Error: Cannot retag v{chosen_version} when code is at v{min_version}")
            sys.exit(1)
        
        return chosen_tag
    
    def _handle_changelog_updates(self, tag: str):
        """Handle changelog updates"""
        # Check if AI tools are available
        can_sync = check_gemini_cli() and check_api_key()
        
        if not can_sync:
            print_color(Colors.YELLOW, "⚠  AI changelog sync unavailable")
            if not check_gemini_cli():
                print_color(Colors.YELLOW, "   Run ./tooling/setup_ai_tools.py to install gemini-cli")
            else:
                print_color(Colors.YELLOW, "   Set up your API key - see tooling/SETUP.md")
            print_color(Colors.YELLOW, "Skipping AI changelog sync")
            return
        
        sync_choice = input("Run changelog sync to update entries? (Y/n): ") or "Y"
        if not sync_choice.lower().startswith('n'):
            version = tag.lstrip('v')
            updater = ChangelogUpdater(tag, version)
            
            if not updater.update_changelogs():
                continue_choice = input("Continue anyway? (Y/n): ") or "Y"
                if continue_choice.lower().startswith('n'):
                    sys.exit(1)
    
    def _commit_changes(self, tag: str):
        """Commit any changes"""
        # Check for changes
        code, stdout, _ = run_command(['git', 'status', '--porcelain'])
        if code != 0 or not stdout:
            print_color(Colors.YELLOW, "No changes to commit")
            return
        
        print_header("Committing Changes")
        
        # Show changes
        print_color(Colors.BLUE, "Files changed:")
        run_command(['git', 'status', '--short'], capture_output=False)
        print()
        
        commit_choice = input("Commit these changes? (Y/n): ") or "Y"
        if commit_choice.lower().startswith('n'):
            print_color(Colors.YELLOW, "Skipping commit")
            return
        
        # Stage all changes
        run_command(['git', 'add', '.'])
        
        # Generate commit message
        commit_msg = f"""chore: update release {tag}

- Updated changelog entries
- Synchronized package documentation
- Fixed release artifacts"""
        
        # Show commit message
        print_color(Colors.BLUE, "Commit message:")
        print(commit_msg)
        print()
        
        msg_choice = input("Use this message? (Y/n/e to edit): ") or "Y"
        
        if msg_choice.lower() == 'e':
            # Edit message
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(commit_msg)
                temp_file = f.name
            
            editor = os.environ.get('EDITOR', 'vim')
            subprocess.call([editor, temp_file])
            
            with open(temp_file, 'r') as f:
                commit_msg = f.read().strip()
            
            os.unlink(temp_file)
            
        elif msg_choice.lower() == 'n':
            # Get new message
            print_color(Colors.BLUE, "Enter your commit message (press Ctrl+D when done):")
            commit_msg = sys.stdin.read().strip()
        
        # Commit
        code, _, stderr = run_command(['git', 'commit', '-m', commit_msg])
        if code == 0:
            print_color(Colors.GREEN, "✓ Changes committed")
            
            # Push commits - default to yes
            code, branch, _ = run_command(['git', 'branch', '--show-current'])
            if code == 0 and branch:
                branch_link = make_clickable_link(make_github_branch_link(branch), f"origin/{branch}")
                push_choice = input(f"Push commits to {branch_link}? (Y/n): ") or "Y"
                if not push_choice.lower().startswith('n'):
                    code, _, _ = run_command(['git', 'push', 'origin', branch])
                    if code == 0:
                        print_color(Colors.GREEN, "✓ Pushed commits")
        else:
            print_color(Colors.RED, f"Commit failed: {stderr}")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    retagger = RetagRelease()
    
    try:
        retagger.run()
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error: {str(e)}")
        sys.exit(1)
    finally:
        cleanup_temp_files()

if __name__ == "__main__":
    main()