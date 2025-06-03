#!/usr/bin/env python3
"""
get_new_patch_tag.py - Determine the next patch version tag
Handles edge cases and provides clear error messages

This script works in any git repository and determines the next patch version
by finding the latest semantic version tag and incrementing the patch number.

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved

Requires: Python 3.6+, git
"""

import subprocess
import sys
import re
import os
from typing import Optional, Tuple, List
from dataclasses import dataclass
from functools import total_ordering

# ============================================================================
# CONSTANTS
# ============================================================================

# ANSI color codes
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    
    @classmethod
    def print_color(cls, color: str, message: str, file=None):
        """Print colored message to stderr by default"""
        print(f"{color}{message}{cls.RESET}", file=file or sys.stderr)

# ============================================================================
# VERSION HANDLING
# ============================================================================

@dataclass
@total_ordering
class SemanticVersion:
    """Represents a semantic version with comparison support"""
    major: int
    minor: int
    patch: int
    prefix: str = "v"
    
    @classmethod
    def parse(cls, version_str: str) -> Optional['SemanticVersion']:
        """Parse a version string into SemanticVersion object
        
        Accepts formats: v1.2.3 or 1.2.3
        """
        # Match semantic version pattern with optional 'v' prefix
        match = re.match(r'^(v)?(\d+)\.(\d+)\.(\d+)$', version_str.strip())
        if not match:
            return None
            
        prefix = match.group(1) or ""
        major = int(match.group(2))
        minor = int(match.group(3))
        patch = int(match.group(4))
        
        return cls(major=major, minor=minor, patch=patch, prefix=prefix)
    
    def increment_patch(self) -> 'SemanticVersion':
        """Return a new version with incremented patch number"""
        return SemanticVersion(
            major=self.major,
            minor=self.minor,
            patch=self.patch + 1,
            prefix="v"  # Always use 'v' prefix for new tags
        )
    
    def __str__(self) -> str:
        """String representation of the version"""
        return f"{self.prefix}{self.major}.{self.minor}.{self.patch}"
    
    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    def __lt__(self, other) -> bool:
        """Less than comparison for sorting"""
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

# ============================================================================
# GIT OPERATIONS
# ============================================================================

class GitOperations:
    """Handle git command execution"""
    
    @staticmethod
    def run_command(cmd: List[str]) -> Tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    @classmethod
    def is_git_repository(cls) -> bool:
        """Check if current directory is in a git repository"""
        code, _, _ = cls.run_command(["git", "rev-parse", "--git-dir"])
        return code == 0
    
    @classmethod
    def get_all_tags(cls) -> List[str]:
        """Get all git tags"""
        code, stdout, _ = cls.run_command(["git", "tag", "-l"])
        if code != 0 or not stdout:
            return []
        return stdout.splitlines()
    
    @classmethod
    def tag_exists(cls, tag: str) -> bool:
        """Check if a specific tag exists"""
        tags = cls.get_all_tags()
        return tag in tags
    
    @classmethod
    def get_github_url(cls) -> Optional[str]:
        """Get the GitHub repository URL from git remote
        
        Returns:
            GitHub repository URL (e.g., https://github.com/owner/repo) or None
        """
        # Try to get the remote URL
        code, stdout, _ = cls.run_command(["git", "config", "--get", "remote.origin.url"])
        if code != 0 or not stdout:
            return None
            
        url = stdout.strip()
        
        # Convert SSH URL to HTTPS
        ssh_match = re.match(r'git@github\.com:(.+)/(.+?)(?:\.git)?$', url)
        if ssh_match:
            owner = ssh_match.group(1)
            repo = ssh_match.group(2)
            return f"https://github.com/{owner}/{repo}"
        
        # Handle HTTPS URLs
        https_match = re.match(r'https://github\.com/(.+)/(.+?)(?:\.git)?$', url)
        if https_match:
            owner = https_match.group(1)
            repo = https_match.group(2)
            return f"https://github.com/{owner}/{repo}"
        
        return None

# ============================================================================
# MAIN LOGIC
# ============================================================================

class TagGenerator:
    """Generate next patch version tag"""
    
    def __init__(self):
        self.git = GitOperations()
        self.github_url = self.git.get_github_url()
        
    def get_semantic_version_tags(self) -> List[SemanticVersion]:
        """Get all semantic version tags from the repository
        
        Filters tags to only include those matching semantic version pattern.
        """
        all_tags = self.git.get_all_tags()
        
        semantic_versions = []
        for tag in all_tags:
            version = SemanticVersion.parse(tag)
            if version:
                semantic_versions.append(version)
                
        # Sort versions using natural version ordering
        return sorted(semantic_versions)
    
    def get_latest_version(self) -> Optional[SemanticVersion]:
        """Get the latest semantic version tag"""
        versions = self.get_semantic_version_tags()
        return versions[-1] if versions else None
    
    def generate_new_tag(self) -> Tuple[Optional[str], str]:
        """Generate the next patch version tag
        
        Returns:
            Tuple of (latest_tag, new_tag)
        """
        latest_version = self.get_latest_version()
        
        if latest_version is None:
            # No semantic version tags found, start with v0.0.1
            Colors.print_color(Colors.YELLOW, "⚠️  No semantic version tags found. Starting with v0.0.1")
            return None, "v0.0.1"
        
        # Validate version parts (redundant with parse, but matches bash script behavior)
        if (latest_version.major < 0 or latest_version.minor < 0 or latest_version.patch < 0):
            Colors.print_color(Colors.RED, f"❌ Error: Invalid version format in tag {latest_version}")
            sys.exit(1)
        
        # Increment patch version
        new_version = latest_version.increment_patch()
        
        # Check if new tag already exists (shouldn't happen, but be safe)
        new_tag = str(new_version)
        if self.git.tag_exists(new_tag):
            Colors.print_color(Colors.RED, f"❌ Error: Tag {new_tag} already exists!")
            Colors.print_color(Colors.YELLOW, "⚠️  This might indicate a sync issue. Please check your tags.")
            sys.exit(1)
            
        return str(latest_version), new_tag
    
    def format_tag_url(self, tag: str) -> Optional[str]:
        """Format a GitHub URL for a tag
        
        Args:
            tag: The tag name
            
        Returns:
            GitHub URL for the tag or None if no GitHub URL available
        """
        if not self.github_url:
            return None
        return f"{self.github_url}/releases/tag/{tag}"
    
    def run(self):
        """Main execution logic"""
        # Check if we're in a git repository
        if not self.git.is_git_repository():
            Colors.print_color(Colors.RED, "❌ Error: Not in a git repository")
            sys.exit(1)
            
        # Generate new tag
        latest_tag, new_tag = self.generate_new_tag()
        
        # Print a header
        print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
        print(f"{Colors.BLUE}🏷️  Git Tag Information{Colors.RESET}")
        print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")
        
        # Output results with colors (to stdout, matching bash script behavior)
        if latest_tag:
            print(f"{Colors.YELLOW}📌 Latest tag:{Colors.RESET} {Colors.GREEN}{latest_tag}{Colors.RESET}")
        else:
            print(f"{Colors.YELLOW}📌 Latest tag:{Colors.RESET} none")
        
        # Output clickable link for latest tag if available
        if latest_tag and self.github_url:
            latest_url = self.format_tag_url(latest_tag)
            if latest_url:
                print(f"{Colors.YELLOW}🔗 Latest tag URL:{Colors.RESET} {Colors.BLUE}{latest_url}{Colors.RESET}")
        
        print()  # Empty line for spacing
        print(f"{Colors.YELLOW}✨ New tag:{Colors.RESET} {Colors.GREEN}{new_tag}{Colors.RESET}")
        
        # Output clickable link for new tag if GitHub URL available
        if self.github_url:
            new_url = self.format_tag_url(new_tag)
            if new_url:
                print(f"{Colors.YELLOW}🔗 New tag URL:{Colors.RESET} {Colors.BLUE}{new_url}{Colors.RESET}")
        else:
            print(f"\n{Colors.YELLOW}ℹ️  Note:{Colors.RESET} GitHub remote not detected - no release URLs available")
        
        print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}\n")

# ============================================================================
# COMMON CONFIG COMPATIBILITY
# ============================================================================

def load_common_config():
    """Load configuration from common_config.sh if available
    
    This maintains compatibility with the bash script's sourcing of common_config.sh
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, 'common_config.sh')
    
    if os.path.exists(config_file):
        # We could parse the bash file if needed, but for this script
        # we only use print_color which we've implemented directly
        pass

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Entry point"""
    # Load common config for compatibility (though not used in this script)
    load_common_config()
    
    # Run the tag generator
    generator = TagGenerator()
    generator.run()

if __name__ == "__main__":
    main()