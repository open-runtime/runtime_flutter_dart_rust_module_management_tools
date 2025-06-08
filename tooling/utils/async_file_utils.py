"""
Async file utilities for improved I/O performance.
"""
import asyncio
import aiofiles
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, Union
import json
import yaml
import hashlib
import os

from tooling.core.logging import get_logger

logger = get_logger(__name__)


class AsyncFileOperations:
    """Async file operations for better performance"""
    
    def __init__(self, max_concurrent: int = 20):
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def read_file(self, path: Union[str, Path], encoding: str = 'utf-8') -> str:
        """Read file asynchronously"""
        async with self._semaphore:
            try:
                # Convert string to Path if needed
                if isinstance(path, str):
                    path = Path(path)
                async with aiofiles.open(path, 'r', encoding=encoding) as f:
                    return await f.read()
            except Exception as e:
                logger.error(f"Failed to read {path}: {e}")
                raise
    
    async def write_file(self, path: Union[str, Path], content: str, encoding: str = 'utf-8') -> None:
        """Write file asynchronously"""
        async with self._semaphore:
            try:
                # Convert string to Path if needed
                if isinstance(path, str):
                    path = Path(path)
                # Ensure directory exists
                path.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(path, 'w', encoding=encoding) as f:
                    await f.write(content)
            except Exception as e:
                logger.error(f"Failed to write {path}: {e}")
                raise
    
    async def read_files_batch(self, paths: List[Union[str, Path]]) -> Dict[Path, str]:
        """Read multiple files in parallel"""
        tasks = []
        path_objects = []
        for path in paths:
            if isinstance(path, str):
                path = Path(path)
            path_objects.append(path)
            task = self.read_file(path)
            tasks.append(task)
        
        contents = await asyncio.gather(*tasks, return_exceptions=True)
        
        result = {}
        for path, content in zip(path_objects, contents):
            if isinstance(content, Exception):
                logger.warning(f"Failed to read {path}: {content}")
                result[path] = ""
            else:
                result[path] = content
        
        return result
    
    async def write_files_batch(self, files: Dict[Union[str, Path], str]) -> Dict[Path, bool]:
        """Write multiple files in parallel"""
        tasks = []
        paths = []
        
        for path, content in files.items():
            if isinstance(path, str):
                path = Path(path)
            task = self.write_file(path, content)
            tasks.append(task)
            paths.append(path)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        status = {}
        for path, result in zip(paths, results):
            status[path] = not isinstance(result, Exception)
            if isinstance(result, Exception):
                logger.error(f"Failed to write {path}: {result}")
        
        return status
    
    async def process_files_parallel(
        self,
        paths: List[Path],
        processor: Callable[[str], Any],
        max_concurrent: Optional[int] = None
    ) -> List[Any]:
        """Process multiple files in parallel with a processor function"""
        if max_concurrent:
            semaphore = asyncio.Semaphore(max_concurrent)
        else:
            semaphore = self._semaphore
        
        async def process_file(path: Path):
            async with semaphore:
                content = await self.read_file(path)
                # If processor is async, await it
                if asyncio.iscoroutinefunction(processor):
                    return await processor(content)
                else:
                    # Run sync processor in thread pool
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, processor, content)
        
        tasks = [process_file(path) for path in paths]
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    async def find_files(
        self,
        root: Path,
        pattern: str = "*",
        recursive: bool = True
    ) -> List[Path]:
        """Find files matching pattern asynchronously"""
        loop = asyncio.get_event_loop()
        
        def _find_files():
            if recursive:
                return list(root.rglob(pattern))
            else:
                return list(root.glob(pattern))
        
        # Run in thread pool to avoid blocking
        return await loop.run_in_executor(None, _find_files)
    
    async def compute_checksums(self, paths: List[Path]) -> Dict[Path, str]:
        """Compute checksums for multiple files in parallel"""
        async def compute_checksum(path: Path) -> str:
            content = await self.read_file(path)
            return hashlib.sha256(content.encode()).hexdigest()
        
        tasks = [compute_checksum(path) for path in paths]
        checksums = await asyncio.gather(*tasks, return_exceptions=True)
        
        result = {}
        for path, checksum in zip(paths, checksums):
            if isinstance(checksum, Exception):
                logger.warning(f"Failed to compute checksum for {path}: {checksum}")
                result[path] = ""
            else:
                result[path] = checksum
        
        return result
    
    async def copy_file(self, src: Union[str, Path], dst: Union[str, Path]) -> None:
        """Copy file asynchronously"""
        content = await self.read_file(src)
        await self.write_file(dst, content)
    
    async def move_file(self, src: Union[str, Path], dst: Union[str, Path]) -> None:
        """Move file asynchronously"""
        await self.copy_file(src, dst)
        await self.delete_file(src)
    
    async def delete_file(self, path: Union[str, Path]) -> None:
        """Delete file asynchronously"""
        if isinstance(path, str):
            path = Path(path)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, path.unlink)
    
    async def exists(self, path: Union[str, Path]) -> bool:
        """Check if file exists asynchronously"""
        if isinstance(path, str):
            path = Path(path)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, path.exists)
    
    async def get_size(self, path: Union[str, Path]) -> int:
        """Get file size asynchronously"""
        if isinstance(path, str):
            path = Path(path)
        
        loop = asyncio.get_event_loop()
        stat_result = await loop.run_in_executor(None, path.stat)
        return stat_result.st_size
    
    async def list_directory(self, path: Union[str, Path]) -> List[str]:
        """List directory contents asynchronously"""
        if isinstance(path, str):
            path = Path(path)
        
        loop = asyncio.get_event_loop()
        
        def _list_dir():
            return [item.name for item in path.iterdir()]
        
        return await loop.run_in_executor(None, _list_dir)
    
    async def walk_directory(self, path: Union[str, Path]):
        """Walk directory tree asynchronously (async generator)"""
        if isinstance(path, str):
            path = Path(path)
        
        loop = asyncio.get_event_loop()
        
        # Get the walk results in executor
        def _walk():
            results = []
            for root, dirs, files in os.walk(path):
                results.append((root, dirs[:], files[:]))
            return results
        
        walk_results = await loop.run_in_executor(None, _walk)
        
        # Yield results as async generator
        for root, dirs, files in walk_results:
            yield root, dirs, files


class AsyncJSONOperations:
    """Async JSON file operations"""
    
    def __init__(self):
        self.file_ops = AsyncFileOperations()
    
    async def read_json(self, path: Path) -> Any:
        """Read JSON file asynchronously"""
        content = await self.file_ops.read_file(path)
        return json.loads(content)
    
    async def write_json(self, path: Path, data: Any, indent: int = 2) -> None:
        """Write JSON file asynchronously"""
        content = json.dumps(data, indent=indent)
        await self.file_ops.write_file(path, content)
    
    async def read_json_batch(self, paths: List[Path]) -> Dict[Path, Any]:
        """Read multiple JSON files in parallel"""
        contents = await self.file_ops.read_files_batch(paths)
        
        result = {}
        for path, content in contents.items():
            try:
                result[path] = json.loads(content) if content else None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from {path}: {e}")
                result[path] = None
        
        return result
    
    async def update_json_files(self, updates: Dict[Path, Dict[str, Any]]) -> Dict[Path, bool]:
        """Update multiple JSON files in parallel"""
        async def update_file(path: Path, updates: Dict[str, Any]):
            try:
                # Read existing data
                data = await self.read_json(path) if path.exists() else {}
                # Update data
                data.update(updates)
                # Write back
                await self.write_json(path, data)
                return True
            except Exception as e:
                logger.error(f"Failed to update {path}: {e}")
                return False
        
        tasks = []
        paths = []
        for path, update_data in updates.items():
            task = update_file(path, update_data)
            tasks.append(task)
            paths.append(path)
        
        results = await asyncio.gather(*tasks)
        return dict(zip(paths, results))


class AsyncYAMLOperations:
    """Async YAML file operations"""
    
    def __init__(self):
        self.file_ops = AsyncFileOperations()
    
    async def read_yaml(self, path: Path) -> Any:
        """Read YAML file asynchronously"""
        content = await self.file_ops.read_file(path)
        return yaml.safe_load(content)
    
    async def write_yaml(self, path: Path, data: Any) -> None:
        """Write YAML file asynchronously"""
        content = yaml.dump(data, default_flow_style=False)
        await self.file_ops.write_file(path, content)
    
    async def read_yaml_batch(self, paths: List[Path]) -> Dict[Path, Any]:
        """Read multiple YAML files in parallel"""
        contents = await self.file_ops.read_files_batch(paths)
        
        result = {}
        for path, content in contents.items():
            try:
                result[path] = yaml.safe_load(content) if content else None
            except yaml.YAMLError as e:
                logger.error(f"Failed to parse YAML from {path}: {e}")
                result[path] = None
        
        return result


class FileBatchProcessor:
    """Process files in optimized batches"""
    
    def __init__(self, batch_size: int = 100, max_concurrent: int = 20):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.file_ops = AsyncFileOperations(max_concurrent=max_concurrent)
    
    async def process_files(
        self,
        file_paths: List[str],
        processor: Callable[[str], Any]
    ) -> Dict[str, Any]:
        """Process a list of files with a processor function"""
        results = {}
        
        # Convert to Path objects
        paths = [Path(p) for p in file_paths]
        
        # Process files
        for path in paths:
            try:
                if asyncio.iscoroutinefunction(processor):
                    result = await processor(str(path))
                else:
                    # Run sync processor in thread pool
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, processor, str(path))
                results[str(path)] = result
            except Exception as e:
                logger.error(f"Failed to process {path}: {e}")
                results[str(path)] = None
        
        return results
    
    async def process_large_directory(
        self,
        directory: Path,
        processor: Callable[[Path, str], Any],
        pattern: str = "*",
        recursive: bool = True
    ) -> List[Any]:
        """Process all files in directory in batches"""
        # Find all files
        files = await self.file_ops.find_files(directory, pattern, recursive)
        
        # Process in batches
        results = []
        for i in range(0, len(files), self.batch_size):
            batch = files[i:i + self.batch_size]
            
            # Read batch
            contents = await self.file_ops.read_files_batch(batch)
            
            # Process batch
            batch_tasks = []
            for path, content in contents.items():
                if asyncio.iscoroutinefunction(processor):
                    task = processor(path, content)
                else:
                    # Run sync processor in thread pool
                    loop = asyncio.get_event_loop()
                    task = loop.run_in_executor(None, processor, path, content)
                batch_tasks.append(task)
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            results.extend(batch_results)
        
        return results
    
    async def sync_files(
        self,
        source_dir: Path,
        target_dir: Path,
        pattern: str = "*"
    ) -> Dict[str, int]:
        """Sync files from source to target directory in parallel"""
        # Find source files
        source_files = await self.file_ops.find_files(source_dir, pattern, recursive=True)
        
        # Prepare copy operations
        copy_tasks = []
        for source_file in source_files:
            relative_path = source_file.relative_to(source_dir)
            target_file = target_dir / relative_path
            
            async def copy_file(src: Path, dst: Path):
                content = await self.file_ops.read_file(src)
                await self.file_ops.write_file(dst, content)
            
            copy_tasks.append(copy_file(source_file, target_file))
        
        # Execute copies in parallel
        results = await asyncio.gather(*copy_tasks, return_exceptions=True)
        
        # Count results
        stats = {
            'copied': sum(1 for r in results if not isinstance(r, Exception)),
            'failed': sum(1 for r in results if isinstance(r, Exception)),
            'total': len(results)
        }
        
        return stats


# Convenience functions for migration
async def read_files_async(paths: List[Path]) -> Dict[Path, str]:
    """Read multiple files asynchronously"""
    ops = AsyncFileOperations()
    return await ops.read_files_batch(paths)


async def write_files_async(files: Dict[Path, str]) -> Dict[Path, bool]:
    """Write multiple files asynchronously"""
    ops = AsyncFileOperations()
    return await ops.write_files_batch(files)


async def process_directory_async(
    directory: Path,
    processor: Callable[[Path, str], Any],
    pattern: str = "*.py"
) -> List[Any]:
    """Process all files in directory asynchronously"""
    processor_obj = FileBatchProcessor()
    return await processor_obj.process_large_directory(directory, processor, pattern) 