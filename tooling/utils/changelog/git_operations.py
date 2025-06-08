"""
Git operations specific to changelog management.
"""
import re
import subprocess
from typing import List, Optional, Tuple
from functools import lru_cache

from tooling.core.models import GitCommit


class ChangelogGitOps:
    """Git operations for changelog generation."""
    
    @staticmethod
    def get_commits_between(start: Optional[str], end: str = "HEAD", 
                          path_glob: Optional[str] = None) -> List[GitCommit]:
        """Get commits between two refs, optionally filtered by path
        
        Args:
            start: Starting ref (exclusive), None for all history
            end: Ending ref (inclusive)
            path_glob: Optional glob pattern to filter files
            
        Returns:
            List of GitCommit objects
        """
        cmd = [
            'git', 'log',
            '--pretty=format:%H%n%h%n%an%n%ae%n%ad%n%s%n%b%n--END--',
            '--date=format:%Y-%m-%d%n%I:%M%p %Z',
            '--name-only'
        ]
        
        if start:
            cmd.append(f'{start}..{end}')
        else:
            cmd.append(end)
        
        if path_glob:
            cmd.extend(['--', path_glob])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return []
            
            return ChangelogGitOps._parse_git_log(result.stdout)
            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return []
    
    @staticmethod
    def _parse_git_log(log_output: str) -> List[GitCommit]:
        """Parse git log output into GitCommit objects"""
        commits = []
        entries = log_output.strip().split('--END--\n')
        
        for entry in entries:
            if not entry.strip():
                continue
            
            lines = entry.strip().split('\n')
            if len(lines) < 7:  # Minimum required lines
                continue
            
            # Parse commit data
            commit_hash = lines[0]
            short_hash = lines[1]
            author_name = lines[2]
            author_email = lines[3]
            commit_date = lines[4]
            commit_time = lines[5]
            
            # Find where message ends and files begin
            message_lines = []
            files = []
            in_files = False
            
            for i in range(6, len(lines)):
                line = lines[i]
                # Empty line after message indicates start of file list
                if not line.strip() and not in_files:
                    in_files = True
                elif in_files and line.strip():
                    files.append(line.strip())
                elif not in_files:
                    message_lines.append(line)
            
            message = '\n'.join(message_lines).strip()
            
            # Extract PR number if present
            pr_match = re.search(r'#(\d+)', message)
            pr_number = int(pr_match.group(1)) if pr_match else None
            
            commit = GitCommit(
                hash=commit_hash,
                short_hash=short_hash,
                message=message,
                author_name=author_name,
                author_email=author_email,
                commit_date=commit_date,
                commit_time=commit_time,
                files=files,
                pr_number=pr_number
            )
            
            commits.append(commit)
        
        return commits
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_remote_url() -> Optional[str]:
        """Get the remote repository URL"""
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                url = result.stdout.strip()
                # Convert SSH to HTTPS format
                if url.startswith('git@github.com:'):
                    url = url.replace('git@github.com:', 'https://github.com/')
                # Remove .git suffix
                if url.endswith('.git'):
                    url = url[:-4]
                return url
                
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        return None
    
    @staticmethod
    def get_file_at_ref(file_path: str, ref: str = "HEAD") -> Optional[str]:
        """Get file contents at a specific ref"""
        try:
            result = subprocess.run(
                ['git', 'show', f'{ref}:{file_path}'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return result.stdout
                
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        return None
    
    @staticmethod
    def get_diff_for_files(files: List[str], start_ref: str, end_ref: str = "HEAD") -> str:
        """Get unified diff for specific files between two refs"""
        if not files:
            return ""
        
        cmd = ['git', 'diff', start_ref, end_ref, '--'] + files
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout
                
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        return ""
    
    @staticmethod
    def find_last_changelog_commit() -> Optional[str]:
        """Find the last commit that modified changelog files"""
        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', '--grep=changelog', '-i', '-n', '10',
                 '--', '**/CHANGELOG.md', 'CHANGELOG.md'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                # Parse commit hashes
                for line in result.stdout.strip().split('\n'):
                    if line:
                        commit_hash = line.split()[0]
                        # Verify it's a meaningful changelog update
                        if ChangelogGitOps._is_meaningful_changelog_commit(commit_hash):
                            return commit_hash
                            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        return None
    
    @staticmethod
    def _is_meaningful_changelog_commit(commit_hash: str) -> bool:
        """Check if a commit contains meaningful changelog changes"""
        try:
            result = subprocess.run(
                ['git', 'show', '--name-only', '--format=%s', commit_hash],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if not lines:
                    return False
                
                # Check commit message
                message = lines[0].lower()
                
                # Skip automated commits
                if any(word in message for word in ['automated', 'bot', 'ci']):
                    return False
                
                # Check for sync commits
                if 'sync' in message and 'changelog' in message:
                    return True
                
                # Check if changelog files were modified
                for line in lines[1:]:
                    if 'CHANGELOG.md' in line:
                        return True
                        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
        
        return False 