"""
High-level git operations used across CLI tools.
Provides a centralized interface for common git operations.
"""
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from tooling.core.logging import get_logger
from tooling.utils.git_utils import (
    check_git_repo, check_git_state, check_remote_sync,
    get_current_branch, get_git_root
)

logger = get_logger(__name__)


@dataclass
class Commit:
    """Represents a git commit with metadata"""
    hash: str
    short_hash: str
    message: str
    author: str
    author_email: str
    date: datetime
    files: List[str]
    pr_number: Optional[int] = None
    
    @property
    def conventional_type(self) -> Optional[str]:
        """Extract conventional commit type if present"""
        match = re.match(r'^(\w+)(?:\([^)]+\))?:', self.message)
        return match.group(1) if match else None
    
    @property
    def scope(self) -> Optional[str]:
        """Extract conventional commit scope if present"""
        match = re.match(r'^\w+\(([^)]+)\):', self.message)
        return match.group(1) if match else None


class GitOperations:
    """High-level git operations used across tools"""
    
    @staticmethod
    def get_commits_since_tag(tag: str, path: Optional[str] = None) -> List[Commit]:
        """Get all commits since a specific tag"""
        logger.debug(f"Getting commits since tag: {tag}")
        
        cmd = ['git', 'log', f'{tag}..HEAD', '--pretty=format:%H|%h|%s|%an|%ae|%ad', '--date=iso']
        if path:
            cmd.extend(['--', path])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to get commits: {result.stderr}")
            return []
        
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('|')
            if len(parts) >= 6:
                commit = Commit(
                    hash=parts[0],
                    short_hash=parts[1],
                    message=parts[2],
                    author=parts[3],
                    author_email=parts[4],
                    date=datetime.fromisoformat(parts[5]),
                    files=GitOperations._get_commit_files(parts[0])
                )
                
                # Extract PR number if present
                pr_match = re.search(r'#(\d+)', commit.message)
                if pr_match:
                    commit.pr_number = int(pr_match.group(1))
                
                commits.append(commit)
        
        logger.debug(f"Found {len(commits)} commits since {tag}")
        return commits
    
    @staticmethod
    def _get_commit_files(commit_hash: str) -> List[str]:
        """Get list of files changed in a commit"""
        cmd = ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', commit_hash]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return [f for f in result.stdout.strip().split('\n') if f]
        return []
    
    @staticmethod
    def create_commit_with_message(message: str, add_all: bool = True) -> bool:
        """Create a commit with the given message"""
        logger.info("Creating commit")
        
        if add_all:
            # Stage all changes
            result = subprocess.run(['git', 'add', '.'], capture_output=True)
            if result.returncode != 0:
                logger.error("Failed to stage changes")
                return False
        
        # Create commit
        result = subprocess.run(
            ['git', 'commit', '-m', message],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Commit created successfully")
            return True
        else:
            logger.error(f"Failed to create commit: {result.stderr}")
            return False
    
    @staticmethod
    def get_changed_files(staged_only: bool = False) -> List[Path]:
        """Get all changed files in working directory"""
        if staged_only:
            cmd = ['git', 'diff', '--cached', '--name-only']
        else:
            cmd = ['git', 'status', '--porcelain']
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []
        
        files = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            if staged_only:
                files.append(Path(line))
            else:
                # Parse git status output
                if len(line) > 3:
                    file_path = line[3:].strip()
                    # Handle renamed files
                    if ' -> ' in file_path:
                        file_path = file_path.split(' -> ')[1]
                    files.append(Path(file_path))
        
        return files
    
    @staticmethod
    def get_file_diff(file_path: Path, staged: bool = False) -> str:
        """Get diff for a specific file"""
        cmd = ['git', 'diff']
        if staged:
            cmd.append('--cached')
        cmd.append(str(file_path))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else ""
    
    @staticmethod
    def get_last_tag() -> Optional[str]:
        """Get the most recent tag"""
        result = subprocess.run(
            ['git', 'describe', '--tags', '--abbrev=0'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    @staticmethod
    def get_tags_for_commit(commit_hash: str) -> List[str]:
        """Get all tags pointing to a specific commit"""
        result = subprocess.run(
            ['git', 'tag', '--points-at', commit_hash],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return [tag for tag in result.stdout.strip().split('\n') if tag]
        return []
    
    @staticmethod
    def push_to_remote(branch: Optional[str] = None, tags: bool = False) -> bool:
        """Push changes to remote"""
        cmd = ['git', 'push', 'origin']
        
        if branch:
            cmd.append(branch)
        
        if tags:
            cmd.append('--tags')
        
        logger.info(f"Pushing to remote: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Push successful")
            return True
        else:
            logger.error(f"Push failed: {result.stderr}")
            return False
    
    @staticmethod
    def create_tag(tag_name: str, message: Optional[str] = None) -> bool:
        """Create a new tag"""
        cmd = ['git', 'tag']
        
        if message:
            cmd.extend(['-a', tag_name, '-m', message])
        else:
            cmd.append(tag_name)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Created tag: {tag_name}")
            return True
        else:
            logger.error(f"Failed to create tag: {result.stderr}")
            return False
    
    @staticmethod
    def get_commit_count_between(start_ref: str, end_ref: str = "HEAD") -> int:
        """Get number of commits between two refs"""
        cmd = ['git', 'rev-list', '--count', f'{start_ref}..{end_ref}']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            try:
                return int(result.stdout.strip())
            except ValueError:
                return 0
        return 0
    
    @staticmethod
    def get_merge_base(ref1: str, ref2: str) -> Optional[str]:
        """Find merge base between two refs"""
        cmd = ['git', 'merge-base', ref1, ref2]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    
    @staticmethod
    def is_ancestor(ancestor_ref: str, descendant_ref: str) -> bool:
        """Check if one commit is an ancestor of another"""
        cmd = ['git', 'merge-base', '--is-ancestor', ancestor_ref, descendant_ref]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    @staticmethod
    def get_file_at_revision(file_path: Path, revision: str) -> Optional[str]:
        """Get file content at a specific revision"""
        cmd = ['git', 'show', f'{revision}:{file_path}']
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return result.stdout
        return None
    
    @staticmethod
    def stash_changes(message: Optional[str] = None) -> bool:
        """Stash current changes"""
        cmd = ['git', 'stash', 'push']
        if message:
            cmd.extend(['-m', message])
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    @staticmethod
    def stash_pop() -> bool:
        """Pop the most recent stash"""
        result = subprocess.run(['git', 'stash', 'pop'], capture_output=True)
        return result.returncode == 0 