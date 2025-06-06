"""
Git utility functions for common operations.

This module provides a unified interface for git operations used across
CLI tools, with proper error handling and dependency injection.

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import subprocess
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from functools import lru_cache

from tooling.core.logging import get_logger
from tooling.cli.cli_utils import run_command


@dataclass
class GitCommandResult:
    """Result of a git command execution."""
    returncode: int
    stdout: str
    stderr: str
    
    @property
    def success(self) -> bool:
        """Check if command was successful."""
        return self.returncode == 0


class GitError(Exception):
    """Base exception for git operations."""
    pass


class NotGitRepositoryError(GitError):
    """Raised when not in a git repository."""
    pass


class GitOperations:
    """
    Provides common git operations with proper error handling.
    
    This class encapsulates git command execution and provides
    high-level methods for common git operations.
    """
    
    def __init__(self, logger=None, cwd: Optional[Path] = None, timeout: int = 30):
        """
        Initialize GitOperations.
        
        Args:
            logger: Logger instance (optional, will create default if not provided)
            cwd: Working directory for git commands (defaults to current directory)
            timeout: Command timeout in seconds
        """
        self.logger = logger or get_logger("git_utils")
        self.cwd = cwd or Path.cwd()
        self.timeout = timeout
        self._is_repo_cache = None
        
    def run_command(self, cmd: List[str], check: bool = True) -> GitCommandResult:
        """
        Run a git command and return the result.
        
        Args:
            cmd: Command arguments (e.g., ['git', 'status'])
            check: Whether to raise exception on non-zero return code
            
        Returns:
            GitCommandResult with returncode, stdout, and stderr
            
        Raises:
            GitError: If command fails and check=True
        """
        self.logger.debug(f"Running git command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.cwd,
                timeout=self.timeout
            )
            
            git_result = GitCommandResult(
                returncode=result.returncode,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip()
            )
            
            if check and not git_result.success:
                self.logger.error(
                    "Git command failed",
                    command=' '.join(cmd),
                    returncode=git_result.returncode,
                    stderr=git_result.stderr
                )
                raise GitError(f"Command failed: {' '.join(cmd)}\n{git_result.stderr}")
                
            return git_result
            
        except subprocess.TimeoutExpired:
            self.logger.error("Git command timed out", command=' '.join(cmd))
            raise GitError(f"Command timed out: {' '.join(cmd)}")
        except Exception as e:
            self.logger.error("Git command failed", command=' '.join(cmd), error=str(e))
            raise GitError(f"Command failed: {' '.join(cmd)}\n{str(e)}")
    
    def is_git_repository(self) -> bool:
        """
        Check if current directory is in a git repository.
        
        Returns:
            True if in a git repository, False otherwise
        """
        if self._is_repo_cache is not None:
            return self._is_repo_cache
            
        result = self.run_command(["git", "rev-parse", "--git-dir"], check=False)
        self._is_repo_cache = result.success
        return self._is_repo_cache
    
    def ensure_git_repository(self) -> None:
        """
        Ensure we're in a git repository.
        
        Raises:
            NotGitRepositoryError: If not in a git repository
        """
        if not self.is_git_repository():
            raise NotGitRepositoryError("Not in a git repository")
    
    def get_current_branch(self) -> str:
        """
        Get the current git branch name.
        
        Returns:
            Current branch name
            
        Raises:
            GitError: If unable to determine branch
        """
        self.ensure_git_repository()
        
        # Try symbolic ref first (normal branches)
        result = self.run_command(
            ["git", "symbolic-ref", "--short", "HEAD"],
            check=False
        )
        
        if result.success:
            return result.stdout
            
        # Fall back to rev-parse for detached HEAD
        result = self.run_command(["git", "rev-parse", "--short", "HEAD"])
        return result.stdout
    
    def get_latest_tag(self, pattern: Optional[str] = None) -> Optional[str]:
        """
        Get the latest tag in the repository.
        
        Args:
            pattern: Optional pattern to filter tags (e.g., 'v*')
            
        Returns:
            Latest tag name or None if no tags found
        """
        self.ensure_git_repository()
        
        cmd = ["git", "describe", "--tags", "--abbrev=0"]
        if pattern:
            cmd.extend(["--match", pattern])
            
        result = self.run_command(cmd, check=False)
        return result.stdout if result.success else None
    
    def get_all_tags(self, pattern: Optional[str] = None) -> List[str]:
        """
        Get all tags in the repository.
        
        Args:
            pattern: Optional pattern to filter tags
            
        Returns:
            List of tag names
        """
        self.ensure_git_repository()
        
        cmd = ["git", "tag", "-l"]
        if pattern:
            cmd.append(pattern)
            
        result = self.run_command(cmd)
        return result.stdout.splitlines() if result.stdout else []
    
    def tag_exists(self, tag: str) -> bool:
        """
        Check if a specific tag exists.
        
        Args:
            tag: Tag name to check
            
        Returns:
            True if tag exists, False otherwise
        """
        return tag in self.get_all_tags()
    
    def is_working_directory_clean(self) -> bool:
        """
        Check if the working directory is clean (no uncommitted changes).
        
        Returns:
            True if clean, False if there are uncommitted changes
        """
        self.ensure_git_repository()
        
        result = self.run_command(["git", "status", "--porcelain"])
        return not bool(result.stdout)
    
    def get_uncommitted_changes(self) -> Dict[str, List[str]]:
        """
        Get details about uncommitted changes.
        
        Returns:
            Dictionary with 'staged', 'unstaged', and 'untracked' file lists
        """
        self.ensure_git_repository()
        
        result = self.run_command(["git", "status", "--porcelain"])
        
        changes = {
            'staged': [],
            'unstaged': [],
            'untracked': []
        }
        
        for line in result.stdout.splitlines():
            if not line:
                continue
                
            status = line[:2]
            filepath = line[3:]
            
            if status[0] in 'MADRC':
                changes['staged'].append(filepath)
            if status[1] in 'MD':
                changes['unstaged'].append(filepath)
            if status == '??':
                changes['untracked'].append(filepath)
                
        return changes
    
    def get_commit_messages(
        self,
        from_ref: Optional[str] = None,
        to_ref: str = "HEAD",
        format_string: str = "%H|%an|%ae|%ai|%s|%b"
    ) -> List[Dict[str, str]]:
        """
        Get commit messages between two refs.
        
        Args:
            from_ref: Starting ref (exclusive), None for all commits
            to_ref: Ending ref (inclusive), defaults to HEAD
            format_string: Git log format string
            
        Returns:
            List of commit dictionaries with parsed fields
        """
        self.ensure_git_repository()
        
        if from_ref:
            rev_range = f"{from_ref}..{to_ref}"
        else:
            rev_range = to_ref
            
        cmd = ["git", "log", rev_range, f"--format={format_string}"]
        result = self.run_command(cmd)
        
        commits = []
        for line in result.stdout.splitlines():
            if not line:
                continue
                
            parts = line.split('|', 5)
            if len(parts) >= 5:
                commit = {
                    'hash': parts[0],
                    'author_name': parts[1],
                    'author_email': parts[2],
                    'date': parts[3],
                    'subject': parts[4],
                    'body': parts[5] if len(parts) > 5 else ''
                }
                commits.append(commit)
                
        return commits
    
    def get_changed_files(
        self,
        from_ref: Optional[str] = None,
        to_ref: str = "HEAD"
    ) -> List[str]:
        """
        Get list of files changed between two refs.
        
        Args:
            from_ref: Starting ref (exclusive), None for uncommitted changes
            to_ref: Ending ref (inclusive)
            
        Returns:
            List of changed file paths
        """
        self.ensure_git_repository()
        
        if from_ref:
            cmd = ["git", "diff", "--name-only", f"{from_ref}..{to_ref}"]
        else:
            cmd = ["git", "diff", "--name-only", to_ref]
            
        result = self.run_command(cmd)
        return result.stdout.splitlines() if result.stdout else []
    
    def get_file_diff(
        self,
        filepath: str,
        from_ref: Optional[str] = None,
        to_ref: str = "HEAD"
    ) -> str:
        """
        Get diff for a specific file.
        
        Args:
            filepath: Path to the file
            from_ref: Starting ref (exclusive)
            to_ref: Ending ref (inclusive)
            
        Returns:
            Diff output as string
        """
        self.ensure_git_repository()
        
        if from_ref:
            cmd = ["git", "diff", f"{from_ref}..{to_ref}", "--", filepath]
        else:
            cmd = ["git", "diff", to_ref, "--", filepath]
            
        result = self.run_command(cmd, check=False)
        return result.stdout
    
    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """
        Get the URL for a git remote.
        
        Args:
            remote: Remote name (defaults to 'origin')
            
        Returns:
            Remote URL or None if not found
        """
        self.ensure_git_repository()
        
        result = self.run_command(
            ["git", "config", "--get", f"remote.{remote}.url"],
            check=False
        )
        return result.stdout if result.success else None
    
    def get_github_url(self) -> Optional[str]:
        """
        Get the GitHub repository URL from git remote.
        
        Returns:
            GitHub repository URL (e.g., https://github.com/owner/repo) or None
        """
        url = self.get_remote_url()
        if not url:
            return None
            
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
    
    def create_tag(
        self,
        tag_name: str,
        message: Optional[str] = None,
        ref: str = "HEAD"
    ) -> None:
        """
        Create a new git tag.
        
        Args:
            tag_name: Name of the tag
            message: Optional tag message (creates annotated tag if provided)
            ref: Git ref to tag (defaults to HEAD)
            
        Raises:
            GitError: If tag creation fails
        """
        self.ensure_git_repository()
        
        if self.tag_exists(tag_name):
            raise GitError(f"Tag {tag_name} already exists")
            
        cmd = ["git", "tag"]
        
        if message:
            cmd.extend(["-a", tag_name, "-m", message])
        else:
            cmd.append(tag_name)
            
        cmd.append(ref)
        
        self.run_command(cmd)
        self.logger.info("Created tag", tag=tag_name, ref=ref)
    
    def push_tag(self, tag_name: str, remote: str = "origin", force: bool = False) -> None:
        """
        Push a tag to remote.
        
        Args:
            tag_name: Name of the tag to push
            remote: Remote name (defaults to 'origin')
            force: Whether to force push
            
        Raises:
            GitError: If push fails
        """
        self.ensure_git_repository()
        
        cmd = ["git", "push", remote, tag_name]
        if force:
            cmd.insert(2, "--force")
            
        self.run_command(cmd)
        self.logger.info("Pushed tag", tag=tag_name, remote=remote, forced=force)


def check_git_repo() -> bool:
    """Check if we're in a git repository"""
    code, _, _ = run_command(['git', 'rev-parse', '--git-dir'])
    return code == 0


def check_git_state() -> bool:
    """Check git state (detached HEAD, rebase, etc.)"""
    # Check for detached HEAD
    code, _, _ = run_command(['git', 'symbolic-ref', '-q', 'HEAD'])
    if code != 0:
        print("Warning: You are in 'detached HEAD' state")
        return False
    
    # Get git directory
    code, git_dir, _ = run_command(['git', 'rev-parse', '--git-dir'])
    if code != 0:
        return False
    
    git_path = Path(git_dir)
    
    # Check for rebase in progress
    if (git_path / "rebase-merge").exists() or (git_path / "rebase-apply").exists():
        print("Error: Rebase in progress. Please complete or abort the rebase.")
        return False
    
    # Check for merge in progress
    if (git_path / "MERGE_HEAD").exists():
        print("Error: Merge in progress. Please complete or abort the merge.")
        return False
    
    # Check for cherry-pick in progress
    if (git_path / "CHERRY_PICK_HEAD").exists():
        print("Error: Cherry-pick in progress. Please complete or abort the cherry-pick.")
        return False
    
    return True


def check_remote_sync() -> bool:
    """Check if current branch is up to date with remote"""
    # Get current branch
    code, branch, _ = run_command(['git', 'branch', '--show-current'])
    if code != 0:
        return False
    
    # Fetch latest from remote
    run_command(['git', 'fetch', 'origin', branch, '--quiet'])
    
    # Check if we're behind
    code, behind_str, _ = run_command(['git', 'rev-list', '--count', f'HEAD..origin/{branch}'])
    if code == 0:
        behind = int(behind_str) if behind_str.isdigit() else 0
        if behind > 0:
            print(f"Warning: Your branch is {behind} commits behind origin/{branch}")
            print(f"Consider pulling latest changes: git pull origin {branch}")
            return False
    
    # Check if we're ahead
    code, ahead_str, _ = run_command(['git', 'rev-list', '--count', f'origin/{branch}..HEAD'])
    if code == 0:
        ahead = int(ahead_str) if ahead_str.isdigit() else 0
        if ahead > 0:
            print(f"Info: Your branch is {ahead} commits ahead of origin/{branch}")
    
    return True


def get_current_branch() -> Optional[str]:
    """Get current git branch name"""
    code, branch, _ = run_command(['git', 'branch', '--show-current'])
    return branch if code == 0 else None


def get_git_root() -> Optional[Path]:
    """Get git repository root directory"""
    code, root, _ = run_command(['git', 'rev-parse', '--show-toplevel'])
    return Path(root) if code == 0 else None


def has_uncommitted_changes() -> bool:
    """Check if there are uncommitted changes"""
    code, _, _ = run_command(['git', 'diff-index', '--quiet', 'HEAD', '--'])
    return code != 0


def get_latest_tag() -> Optional[str]:
    """Get the latest git tag"""
    code, tag, _ = run_command(['git', 'describe', '--tags', '--abbrev=0'])
    return tag if code == 0 else None


def get_commits_since_tag(tag: str) -> List[str]:
    """Get list of commits since a tag"""
    code, output, _ = run_command(['git', 'log', f'{tag}..HEAD', '--oneline'])
    if code == 0 and output:
        return output.strip().split('\n')
    return []


def get_staged_files() -> List[str]:
    """Get list of staged files"""
    code, output, _ = run_command(['git', 'diff', '--cached', '--name-only'])
    if code == 0 and output:
        return output.strip().split('\n')
    return []


def get_staged_diff() -> str:
    """Get diff of staged changes"""
    code, output, _ = run_command(['git', 'diff', '--cached'])
    return output if code == 0 else ""


def get_diff_for_files(files: List[str]) -> str:
    """Get diff for specific files"""
    if not files:
        return ""
    cmd = ['git', 'diff', 'HEAD', '--'] + files
    code, output, _ = run_command(cmd)
    return output if code == 0 else ""


def create_tag(tag_name: str, message: str = '') -> None:
    """Create a git tag"""
    cmd = ['git', 'tag']
    if message:
        cmd.extend(['-a', tag_name, '-m', message])
    else:
        cmd.append(tag_name)
    
    code, _, err = run_command(cmd)
    if code != 0:
        raise Exception(f"Failed to create tag: {err}")


def push_tag(tag_name: str) -> None:
    """Push a tag to remote"""
    code, _, err = run_command(['git', 'push', 'origin', tag_name])
    if code != 0:
        raise Exception(f"Failed to push tag: {err}")


def get_commit_messages_since_tag(tag: str) -> List[str]:
    """Get commit messages since the given tag"""
    code, output, _ = run_command(['git', 'log', f'{tag}..HEAD', '--pretty=format:%s'])
    if code == 0 and output:
        return output.strip().split('\n')
    return []


def get_remote_url(remote: str = "origin") -> Optional[str]:
    """Get the URL for a git remote"""
    code, url, _ = run_command(['git', 'config', '--get', f'remote.{remote}.url'])
    return url if code == 0 else None


def get_commits_since_branch(branch: str) -> List[str]:
    """Get list of commit messages since branching from another branch"""
    code, output, _ = run_command(['git', 'log', f'{branch}..HEAD', '--pretty=format:%s'])
    if code == 0 and output:
        return output.strip().split('\n')
    return []


def get_changed_files(from_ref: Optional[str] = None) -> List[str]:
    """Get list of changed files"""
    if from_ref:
        cmd = ['git', 'diff', '--name-only', f'{from_ref}..HEAD']
    else:
        # Get both staged and unstaged changes
        cmd = ['git', 'diff', '--name-only', 'HEAD']
    
    code, output, _ = run_command(cmd)
    files = output.strip().split('\n') if code == 0 and output else []
    
    # Also get untracked files
    code, untracked, _ = run_command(['git', 'ls-files', '--others', '--exclude-standard'])
    if code == 0 and untracked:
        files.extend(untracked.strip().split('\n'))
    
    return [f for f in files if f]  # Filter out empty strings