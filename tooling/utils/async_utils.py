"""
Enhanced async utilities for parallel processing and performance optimization.
Provides improved async operations for Git, file I/O, and network requests.
"""
import asyncio
import aiofiles
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass
from datetime import datetime
import json
import time
from concurrent.futures import ThreadPoolExecutor

from tooling.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CommandResult:
    """Result of a command execution"""
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    duration: float = 0.0
    command: List[str] = None


class AsyncGitOperations:
    """Enhanced async Git operations with connection pooling and caching"""
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._command_cache: Dict[str, CommandResult] = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def run_command(self, 
                         cmd: List[str], 
                         cwd: Optional[Path] = None,
                         timeout: int = 30,
                         use_cache: bool = True) -> CommandResult:
        """Run a command asynchronously with caching"""
        start_time = time.time()
        
        # Check cache
        cache_key = f"{' '.join(cmd)}:{cwd}"
        if use_cache and cache_key in self._command_cache:
            cached = self._command_cache[cache_key]
            if time.time() - cached.duration < self.cache_ttl:
                return cached
        
        async with self.semaphore:
            try:
                # Run in thread pool to avoid blocking
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), 
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    return CommandResult(
                        success=False,
                        stderr="Command timed out",
                        returncode=-1,
                        duration=time.time() - start_time,
                        command=cmd
                    )
                
                result = CommandResult(
                    success=proc.returncode == 0,
                    stdout=stdout.decode('utf-8', errors='replace') if stdout else "",
                    stderr=stderr.decode('utf-8', errors='replace') if stderr else "",
                    returncode=proc.returncode,
                    duration=time.time() - start_time,
                    command=cmd
                )
                
                # Cache successful results
                if use_cache and result.success:
                    self._command_cache[cache_key] = result
                
                return result
                
            except Exception as e:
                logger.error(f"Command failed: {' '.join(cmd)}: {e}")
                return CommandResult(
                    success=False,
                    stderr=str(e),
                    returncode=-1,
                    duration=time.time() - start_time,
                    command=cmd
                )
    
    async def run_commands_batch(self, 
                               commands: List[Tuple[List[str], Optional[Path]]],
                               timeout: int = 30) -> List[CommandResult]:
        """Run multiple commands in parallel"""
        tasks = []
        for cmd, cwd in commands:
            task = self.run_command(cmd, cwd, timeout)
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    async def get_commits_batch(self,
                              repos: List[Tuple[str, str]],  # (org, repo) pairs
                              since: datetime,
                              author: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get commits from multiple repos in parallel"""
        results = {}
        since_str = since.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        commands = []
        for org, repo in repos:
            cmd = ['gh', 'api', f'/repos/{org}/{repo}/commits']
            cmd.extend(['-F', f'since={since_str}'])
            if author:
                cmd.extend(['-F', f'author={author}'])
            cmd.extend(['-F', 'per_page=100'])
            
            commands.append((cmd, None))
        
        # Execute batch
        command_results = await self.run_commands_batch(commands)
        
        # Process results
        for (org, repo), result in zip(repos, command_results):
            key = f"{org}/{repo}"
            if result.success:
                try:
                    commits = json.loads(result.stdout)
                    results[key] = commits if isinstance(commits, list) else []
                except json.JSONDecodeError:
                    results[key] = []
            else:
                results[key] = []
        
        return results
    
    async def clone_repos_parallel(self,
                                 repos: List[Tuple[str, str, Path]],  # (org, repo, dest_path)
                                 shallow: bool = True,
                                 depth: int = 50) -> Dict[str, Path]:
        """Clone multiple repositories in parallel"""
        cloned = {}
        
        commands = []
        for org, repo, dest_path in repos:
            if dest_path.exists():
                cloned[f"{org}/{repo}"] = dest_path
                continue
            
            cmd = ['gh', 'repo', 'clone', f"{org}/{repo}", str(dest_path)]
            if shallow:
                cmd.extend(['--', '--depth', str(depth)])
            
            commands.append((cmd, None))
        
        # Execute clones
        results = await self.run_commands_batch(commands, timeout=120)
        
        # Process results
        for (org, repo, dest_path), result in zip(repos, results):
            if result.success:
                cloned[f"{org}/{repo}"] = dest_path
                logger.info(f"Cloned {org}/{repo}")
            else:
                logger.warning(f"Failed to clone {org}/{repo}: {result.stderr}")
        
        return cloned
    
    def clear_cache(self):
        """Clear command cache"""
        self._command_cache.clear()
    
    def __del__(self):
        """Cleanup executor"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


class AsyncFileOperations:
    """Enhanced async file operations with batching and optimization"""
    
    def __init__(self, max_concurrent: int = 20):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
    
    async def read_file(self, path: Path, encoding: str = 'utf-8') -> Optional[str]:
        """Read file asynchronously"""
        async with self.semaphore:
            try:
                async with aiofiles.open(path, mode='r', encoding=encoding) as f:
                    return await f.read()
            except Exception as e:
                logger.debug(f"Error reading {path}: {e}")
                return None
    
    async def write_file(self, path: Path, content: str, encoding: str = 'utf-8') -> bool:
        """Write file asynchronously"""
        async with self.semaphore:
            try:
                # Ensure parent directory exists
                path.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(path, mode='w', encoding=encoding) as f:
                    await f.write(content)
                return True
            except Exception as e:
                logger.error(f"Error writing {path}: {e}")
                return False
    
    async def read_files_batch(self, 
                             paths: List[Path], 
                             encoding: str = 'utf-8') -> Dict[Path, Optional[str]]:
        """Read multiple files in parallel"""
        tasks = []
        for path in paths:
            task = self.read_file(path, encoding)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        return {path: content for path, content in zip(paths, results)}
    
    async def write_files_batch(self,
                              files: Dict[Path, str],
                              encoding: str = 'utf-8') -> Dict[Path, bool]:
        """Write multiple files in parallel"""
        tasks = []
        paths = []
        
        for path, content in files.items():
            task = self.write_file(path, content, encoding)
            tasks.append(task)
            paths.append(path)
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        return {path: success for path, success in zip(paths, results)}
    
    async def copy_file(self, src: Path, dst: Path) -> bool:
        """Copy file asynchronously"""
        try:
            content = await self.read_file(src, encoding=None)
            if content is not None:
                return await self.write_file(dst, content, encoding=None)
            return False
        except Exception as e:
            logger.error(f"Error copying {src} to {dst}: {e}")
            return False
    
    async def list_files(self, 
                        directory: Path, 
                        pattern: str = "*",
                        recursive: bool = True) -> List[Path]:
        """List files in directory asynchronously"""
        async with self.semaphore:
            try:
                if recursive:
                    return await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        lambda: list(directory.rglob(pattern))
                    )
                else:
                    return await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        lambda: list(directory.glob(pattern))
                    )
            except Exception as e:
                logger.error(f"Error listing files in {directory}: {e}")
                return []
    
    async def get_file_stats(self, paths: List[Path]) -> Dict[Path, Dict[str, Any]]:
        """Get file statistics for multiple files"""
        async def get_stats(path: Path) -> Dict[str, Any]:
            try:
                stat = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    path.stat
                )
                return {
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'created': datetime.fromtimestamp(stat.st_ctime),
                    'exists': True
                }
            except:
                return {'exists': False}
        
        tasks = [get_stats(path) for path in paths]
        results = await asyncio.gather(*tasks)
        
        return {path: stats for path, stats in zip(paths, results)}
    
    def __del__(self):
        """Cleanup executor"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


class AsyncNetworkOperations:
    """Async network operations with connection pooling and retry"""
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._session = None
    
    async def _get_session(self):
        """Get or create aiohttp session"""
        if self._session is None:
            import aiohttp
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session
    
    async def fetch(self, 
                   url: str, 
                   method: str = 'GET',
                   headers: Optional[Dict[str, str]] = None,
                   data: Optional[Any] = None,
                   timeout: int = 30) -> Tuple[int, str]:
        """Fetch URL with retry logic"""
        async with self.semaphore:
            session = await self._get_session()
            
            for attempt in range(3):
                try:
                    async with session.request(
                        method,
                        url,
                        headers=headers,
                        json=data if method in ['POST', 'PUT'] else None,
                        timeout=aiohttp.ClientTimeout(total=timeout)
                    ) as response:
                        content = await response.text()
                        return response.status, content
                        
                except asyncio.TimeoutError:
                    if attempt == 2:
                        return 0, "Timeout"
                    await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    if attempt == 2:
                        return 0, str(e)
                    await asyncio.sleep(2 ** attempt)
            
            return 0, "Failed after retries"
    
    async def fetch_batch(self,
                         urls: List[str],
                         method: str = 'GET',
                         headers: Optional[Dict[str, str]] = None) -> List[Tuple[str, int, str]]:
        """Fetch multiple URLs in parallel"""
        tasks = []
        for url in urls:
            task = self.fetch(url, method, headers)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        output = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                output.append((url, 0, str(result)))
            else:
                status, content = result
                output.append((url, status, content))
        
        return output
    
    async def close(self):
        """Close network session"""
        if self._session:
            await self._session.close()
            self._session = None
    
    def __del__(self):
        """Cleanup session"""
        if self._session and not self._session.closed:
            asyncio.create_task(self._session.close())


class AsyncTaskQueue:
    """Async task queue with priority and rate limiting"""
    
    def __init__(self, 
                 max_concurrent: int = 10,
                 rate_limit: Optional[int] = None):  # requests per minute
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.workers = []
        self.results = {}
        self._stop = False
        self._request_times = []
    
    async def add_task(self, 
                      coro: Callable,
                      args: tuple = (),
                      kwargs: dict = None,
                      priority: int = 0,
                      task_id: Optional[str] = None) -> str:
        """Add task to queue"""
        kwargs = kwargs or {}
        task_id = task_id or f"task_{time.time()}"
        
        await self.queue.put((priority, task_id, coro, args, kwargs))
        return task_id
    
    async def _worker(self):
        """Worker coroutine"""
        while not self._stop:
            try:
                # Get task with timeout
                priority, task_id, coro, args, kwargs = await asyncio.wait_for(
                    self.queue.get(), 
                    timeout=1.0
                )
                
                # Rate limiting
                if self.rate_limit:
                    await self._enforce_rate_limit()
                
                # Execute task
                try:
                    result = await coro(*args, **kwargs)
                    self.results[task_id] = (True, result)
                except Exception as e:
                    logger.error(f"Task {task_id} failed: {e}")
                    self.results[task_id] = (False, e)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting"""
        if not self.rate_limit:
            return
        
        current_time = time.time()
        
        # Remove old timestamps
        self._request_times = [
            t for t in self._request_times 
            if current_time - t < 60
        ]
        
        # Check if we need to wait
        if len(self._request_times) >= self.rate_limit:
            wait_time = 60 - (current_time - self._request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        self._request_times.append(current_time)
    
    async def start(self):
        """Start worker tasks"""
        self._stop = False
        self.workers = [
            asyncio.create_task(self._worker())
            for _ in range(self.max_concurrent)
        ]
    
    async def stop(self):
        """Stop workers"""
        self._stop = True
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []
    
    async def wait_for_completion(self) -> Dict[str, Tuple[bool, Any]]:
        """Wait for all tasks to complete"""
        while not self.queue.empty():
            await asyncio.sleep(0.1)
        
        # Give workers time to finish current tasks
        await asyncio.sleep(0.5)
        
        return self.results
    
    def get_result(self, task_id: str) -> Optional[Tuple[bool, Any]]:
        """Get result for specific task"""
        return self.results.get(task_id)


class ParallelProcessor:
    """High-level parallel processing utilities"""
    
    @staticmethod
    async def map_async(func: Callable,
                       items: List[Any],
                       max_concurrent: int = 10,
                       return_exceptions: bool = False) -> List[Any]:
        """Parallel map with concurrency limit"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_item(item):
            async with semaphore:
                if asyncio.iscoroutinefunction(func):
                    return await func(item)
                else:
                    return await asyncio.get_event_loop().run_in_executor(
                        None, func, item
                    )
        
        tasks = [process_item(item) for item in items]
        return await asyncio.gather(*tasks, return_exceptions=return_exceptions)
    
    @staticmethod
    async def chunk_process(func: Callable,
                          items: List[Any],
                          chunk_size: int = 100,
                          max_concurrent: int = 10) -> List[Any]:
        """Process items in chunks"""
        results = []
        
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i+chunk_size]
            chunk_results = await ParallelProcessor.map_async(
                func, chunk, max_concurrent
            )
            results.extend(chunk_results)
            
            # Small delay between chunks
            if i + chunk_size < len(items):
                await asyncio.sleep(0.1)
        
        return results
    
    @staticmethod
    async def pipeline(stages: List[Callable],
                      items: List[Any],
                      max_concurrent: int = 10) -> List[Any]:
        """Process items through pipeline of stages"""
        current_items = items
        
        for stage in stages:
            current_items = await ParallelProcessor.map_async(
                stage, current_items, max_concurrent
            )
        
        return current_items


# Singleton instances
_git_ops: Optional[AsyncGitOperations] = None
_file_ops: Optional[AsyncFileOperations] = None
_net_ops: Optional[AsyncNetworkOperations] = None


def get_async_git_ops() -> AsyncGitOperations:
    """Get or create async git operations"""
    global _git_ops
    if _git_ops is None:
        _git_ops = AsyncGitOperations()
    return _git_ops


def get_async_file_ops() -> AsyncFileOperations:
    """Get or create async file operations"""
    global _file_ops
    if _file_ops is None:
        _file_ops = AsyncFileOperations()
    return _file_ops


def get_async_net_ops() -> AsyncNetworkOperations:
    """Get or create async network operations"""
    global _net_ops
    if _net_ops is None:
        _net_ops = AsyncNetworkOperations()
    return _net_ops