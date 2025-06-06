"""
Async Git utilities for improved performance through parallelization.
"""
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any
import re
from dataclasses import dataclass

from tooling.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AsyncGitResult:
    """Result from async git operation"""
    returncode: int
    stdout: str
    stderr: str
    
    @property
    def success(self) -> bool:
        return self.returncode == 0


class AsyncGitOperations:
    """Async git operations for better performance"""
    
    def __init__(self, cwd: Optional[Path] = None, timeout: int = 30):
        self.cwd = cwd or Path.cwd()
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(10)  # Limit concurrent git operations
    
    async def run_command(self, cmd: List[str]) -> AsyncGitResult:
        """Run git command asynchronously"""
        async with self._semaphore:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.cwd
                )
                
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.timeout
                )
                
                return AsyncGitResult(
                    returncode=proc.returncode or 0,
                    stdout=stdout.decode('utf-8').strip(),
                    stderr=stderr.decode('utf-8').strip()
                )
                
            except asyncio.TimeoutError:
                logger.error(f"Command timed out: {' '.join(cmd)}")
                if proc:
                    proc.kill()
                raise
            except Exception as e:
                logger.error(f"Command failed: {' '.join(cmd)}, error: {e}")
                raise
    
    async def get_commits_batch(self, ref_pairs: List[Tuple[str, str]]) -> List[List[Dict[str, str]]]:
        """Get commits for multiple ref ranges in parallel"""
        tasks = []
        for start, end in ref_pairs:
            task = self.get_commits_between(start, end)
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    async def get_commits_between(self, start: Optional[str], end: str = "HEAD") -> List[Dict[str, str]]:
        """Get commits between two refs asynchronously"""
        if start:
            rev_range = f"{start}..{end}"
        else:
            rev_range = end
        
        cmd = ["git", "log", rev_range, "--format=%H|%an|%ae|%ai|%s|%b"]
        result = await self.run_command(cmd)
        
        if not result.success:
            return []
        
        commits = []
        for line in result.stdout.splitlines():
            if not line:
                continue
            
            parts = line.split('|', 5)
            if len(parts) >= 5:
                commits.append({
                    'hash': parts[0],
                    'author_name': parts[1],
                    'author_email': parts[2],
                    'date': parts[3],
                    'subject': parts[4],
                    'body': parts[5] if len(parts) > 5 else ''
                })
        
        return commits
    
    async def get_file_contents_batch(self, files: List[str], ref: str = "HEAD") -> Dict[str, str]:
        """Get contents of multiple files in parallel"""
        tasks = []
        for file in files:
            task = self.get_file_content(file, ref)
            tasks.append(task)
        
        contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        result = {}
        for file, content in zip(files, contents):
            if isinstance(content, Exception):
                logger.warning(f"Failed to get content for {file}: {content}")
                result[file] = ""
            else:
                result[file] = content
        
        return result
    
    async def get_file_content(self, file_path: str, ref: str = "HEAD") -> str:
        """Get content of a file at specific ref"""
        cmd = ["git", "show", f"{ref}:{file_path}"]
        result = await self.run_command(cmd)
        
        if result.success:
            return result.stdout
        return ""
    
    async def get_changed_files_batch(self, ref_pairs: List[Tuple[Optional[str], str]]) -> List[List[str]]:
        """Get changed files for multiple ref ranges in parallel"""
        tasks = []
        for start, end in ref_pairs:
            task = self.get_changed_files(start, end)
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
    
    async def get_changed_files(self, from_ref: Optional[str], to_ref: str = "HEAD") -> List[str]:
        """Get list of changed files between refs"""
        if from_ref:
            cmd = ["git", "diff", "--name-only", f"{from_ref}..{to_ref}"]
        else:
            cmd = ["git", "diff", "--name-only", to_ref]
        
        result = await self.run_command(cmd)
        
        if result.success and result.stdout:
            return result.stdout.splitlines()
        return []
    
    async def get_tags(self, pattern: Optional[str] = None) -> List[str]:
        """Get all tags matching pattern"""
        cmd = ["git", "tag", "-l"]
        if pattern:
            cmd.append(pattern)
        
        result = await self.run_command(cmd)
        
        if result.success and result.stdout:
            return result.stdout.splitlines()
        return []
    
    async def parallel_status_check(self, paths: List[str]) -> Dict[str, bool]:
        """Check git status for multiple paths in parallel"""
        tasks = []
        for path in paths:
            task = self.is_tracked(path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return dict(zip(paths, results))
    
    async def is_tracked(self, path: str) -> bool:
        """Check if a file is tracked by git"""
        cmd = ["git", "ls-files", "--error-unmatch", path]
        result = await self.run_command(cmd)
        return result.success


class GitBatchProcessor:
    """Process multiple git operations efficiently in batches"""
    
    def __init__(self, batch_size: int = 50):
        self.batch_size = batch_size
        self.git = AsyncGitOperations()
    
    async def process_commits_in_batches(
        self,
        commits: List[str],
        processor_func,
        max_concurrent: int = 5
    ) -> List[Any]:
        """Process commits in batches with concurrency control"""
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Split into batches
        batches = [
            commits[i:i + self.batch_size]
            for i in range(0, len(commits), self.batch_size)
        ]
        
        async def process_batch(batch):
            async with semaphore:
                return await processor_func(batch)
        
        # Process all batches concurrently
        batch_results = await asyncio.gather(*[
            process_batch(batch) for batch in batches
        ])
        
        # Flatten results
        for batch_result in batch_results:
            results.extend(batch_result)
        
        return results
    
    async def analyze_repository_parallel(self) -> Dict[str, Any]:
        """Analyze repository using parallel operations"""
        # Run multiple analyses in parallel
        tasks = {
            'branches': self.git.run_command(["git", "branch", "-r"]),
            'tags': self.git.get_tags(),
            'recent_commits': self.git.get_commits_between(None, "HEAD~100"),
            'status': self.git.run_command(["git", "status", "--porcelain"]),
            'remotes': self.git.run_command(["git", "remote", "-v"])
        }
        
        results = await asyncio.gather(*[
            task for task in tasks.values()
        ], return_exceptions=True)
        
        analysis = {}
        for (key, _), result in zip(tasks.items(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to get {key}: {result}")
                analysis[key] = None
            else:
                analysis[key] = result
        
        return analysis


# Convenience functions for migration
async def get_commits_async(start: Optional[str], end: str = "HEAD") -> List[Dict[str, str]]:
    """Async version of get_commits"""
    git = AsyncGitOperations()
    return await git.get_commits_between(start, end)


async def get_files_content_async(files: List[str], ref: str = "HEAD") -> Dict[str, str]:
    """Get multiple file contents in parallel"""
    git = AsyncGitOperations()
    return await git.get_file_contents_batch(files, ref)


async def analyze_commits_parallel(commits: List[str], analyzer_func) -> List[Any]:
    """Analyze commits in parallel"""
    processor = GitBatchProcessor()
    return await processor.process_commits_in_batches(commits, analyzer_func) 