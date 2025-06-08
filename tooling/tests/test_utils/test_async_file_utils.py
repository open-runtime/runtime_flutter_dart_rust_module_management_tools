"""
Tests for async_file_utils.py
"""
import pytest
import asyncio
from unittest.mock import patch, Mock, MagicMock, AsyncMock, mock_open
from pathlib import Path
import json
import yaml
import aiofiles

from tooling.utils.async_file_utils import (
    AsyncFileOperations, AsyncJSONOperations, AsyncYAMLOperations,
    FileBatchProcessor, read_files_async, write_files_async,
    process_directory_async
)


@pytest.mark.asyncio
class TestAsyncFileOperations:
    """Test AsyncFileOperations class"""
    
    def test_initialization(self):
        """Test AsyncFileOperations initialization"""
        ops = AsyncFileOperations()
        assert ops._semaphore._value == 20
        
        ops_custom = AsyncFileOperations(max_concurrent=5)
        assert ops_custom._semaphore._value == 5
    
    @patch('aiofiles.open')
    async def test_read_file_success(self, mock_aiofiles_open):
        """Test reading file successfully"""
        mock_file = AsyncMock()
        mock_file.read.return_value = "File content"
        mock_aiofiles_open.return_value.__aenter__.return_value = mock_file
        
        ops = AsyncFileOperations()
        content = await ops.read_file("test.txt")
        
        assert content == "File content"
        mock_aiofiles_open.assert_called_once_with(Path("test.txt"), 'r', encoding='utf-8')
    
    @patch('aiofiles.open')
    async def test_read_file_with_path_object(self, mock_aiofiles_open):
        """Test reading file with Path object"""
        mock_file = AsyncMock()
        mock_file.read.return_value = "Content"
        mock_aiofiles_open.return_value.__aenter__.return_value = mock_file
        
        ops = AsyncFileOperations()
        content = await ops.read_file(Path("test.txt"))
        
        assert content == "Content"
    
    @patch('aiofiles.open')
    async def test_read_file_error(self, mock_aiofiles_open):
        """Test read file with error"""
        mock_aiofiles_open.side_effect = IOError("Read error")
        
        ops = AsyncFileOperations()
        with pytest.raises(IOError):
            await ops.read_file("test.txt")
    
    @patch('pathlib.Path.parent')
    @patch('aiofiles.open')
    async def test_write_file_success(self, mock_aiofiles_open, mock_parent):
        """Test writing file successfully"""
        mock_file = AsyncMock()
        mock_aiofiles_open.return_value.__aenter__.return_value = mock_file
        mock_parent.mkdir = Mock()
        
        ops = AsyncFileOperations()
        await ops.write_file("test.txt", "Content")
        
        mock_file.write.assert_called_once_with("Content")
        mock_aiofiles_open.assert_called_once()
    
    @patch('aiofiles.open')
    async def test_write_file_error(self, mock_aiofiles_open):
        """Test write file with error"""
        mock_aiofiles_open.side_effect = IOError("Write error")
        
        ops = AsyncFileOperations()
        with pytest.raises(IOError):
            await ops.write_file("test.txt", "Content")
    
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_read_files_batch_success(self, mock_read):
        """Test reading multiple files in batch"""
        async def read_side_effect(path):
            return f"Content of {path}"
        
        mock_read.side_effect = read_side_effect
        
        ops = AsyncFileOperations()
        paths = ["file1.txt", "file2.txt", Path("file3.txt")]
        result = await ops.read_files_batch(paths)
        
        assert len(result) == 3
        assert result[Path("file1.txt")] == "Content of file1.txt"
        assert result[Path("file2.txt")] == "Content of file2.txt"
        assert result[Path("file3.txt")] == "Content of file3.txt"
    
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_read_files_batch_with_errors(self, mock_read):
        """Test reading files with some errors"""
        async def read_side_effect(path):
            if "error" in str(path):
                raise IOError(f"Cannot read {path}")
            return f"Content of {path}"
        
        mock_read.side_effect = read_side_effect
        
        ops = AsyncFileOperations()
        paths = ["file1.txt", "error.txt", "file3.txt"]
        result = await ops.read_files_batch(paths)
        
        assert result[Path("file1.txt")] == "Content of file1.txt"
        assert result[Path("error.txt")] == ""  # Error case returns empty string
        assert result[Path("file3.txt")] == "Content of file3.txt"
    
    @patch.object(AsyncFileOperations, 'write_file')
    async def test_write_files_batch_success(self, mock_write):
        """Test writing multiple files in batch"""
        mock_write.return_value = None
        
        ops = AsyncFileOperations()
        files = {
            "file1.txt": "Content 1",
            Path("file2.txt"): "Content 2"
        }
        
        result = await ops.write_files_batch(files)
        
        assert result[Path("file1.txt")] is True
        assert result[Path("file2.txt")] is True
        assert mock_write.call_count == 2
    
    @patch.object(AsyncFileOperations, 'write_file')
    async def test_write_files_batch_with_errors(self, mock_write):
        """Test writing files with some errors"""
        async def write_side_effect(path, content):
            if "error" in str(path):
                raise IOError(f"Cannot write {path}")
            return None
        
        mock_write.side_effect = write_side_effect
        
        ops = AsyncFileOperations()
        files = {
            "file1.txt": "Content 1",
            "error.txt": "Content 2",
            "file3.txt": "Content 3"
        }
        
        result = await ops.write_files_batch(files)
        
        assert result[Path("file1.txt")] is True
        assert result[Path("error.txt")] is False  # Error case
        assert result[Path("file3.txt")] is True
    
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_process_files_parallel_sync_processor(self, mock_read):
        """Test processing files with sync processor"""
        mock_read.return_value = "test content"
        
        def processor(content):
            return content.upper()
        
        ops = AsyncFileOperations()
        paths = [Path("file1.txt"), Path("file2.txt")]
        
        results = await ops.process_files_parallel(paths, processor)
        
        assert results == ["TEST CONTENT", "TEST CONTENT"]
    
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_process_files_parallel_async_processor(self, mock_read):
        """Test processing files with async processor"""
        mock_read.return_value = "test content"
        
        async def processor(content):
            await asyncio.sleep(0.01)
            return content.upper()
        
        ops = AsyncFileOperations()
        paths = [Path("file1.txt"), Path("file2.txt")]
        
        results = await ops.process_files_parallel(paths, processor)
        
        assert results == ["TEST CONTENT", "TEST CONTENT"]
    
    @patch('asyncio.get_event_loop')
    async def test_find_files(self, mock_get_loop):
        """Test finding files"""
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        
        async def mock_coro():
            return [Path("file1.py"), Path("file2.py")]
        
        mock_loop.run_in_executor.return_value = asyncio.create_task(mock_coro())
        
        ops = AsyncFileOperations()
        files = await ops.find_files(Path("."), "*.py")
        
        assert len(files) == 2
        mock_loop.run_in_executor.assert_called_once()
    
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_compute_checksums(self, mock_read):
        """Test computing checksums for files"""
        async def read_side_effect(path):
            return f"Content of {path}"
        
        mock_read.side_effect = read_side_effect
        
        ops = AsyncFileOperations()
        paths = [Path("file1.txt"), Path("file2.txt")]
        
        checksums = await ops.compute_checksums(paths)
        
        assert len(checksums) == 2
        # Checksums should be different for different content
        assert checksums[Path("file1.txt")] != checksums[Path("file2.txt")]
        # Should be valid SHA256 hashes (64 hex chars)
        for checksum in checksums.values():
            assert len(checksum) == 64
            assert all(c in "0123456789abcdef" for c in checksum)
    
    @patch.object(AsyncFileOperations, 'write_file')
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_copy_file(self, mock_read, mock_write):
        """Test copying file"""
        mock_read.return_value = "File content"
        
        ops = AsyncFileOperations()
        await ops.copy_file("source.txt", "dest.txt")
        
        mock_read.assert_called_once_with("source.txt")
        mock_write.assert_called_once_with("dest.txt", "File content")
    
    @patch.object(AsyncFileOperations, 'delete_file')
    @patch.object(AsyncFileOperations, 'copy_file')
    async def test_move_file(self, mock_copy, mock_delete):
        """Test moving file"""
        ops = AsyncFileOperations()
        await ops.move_file("source.txt", "dest.txt")
        
        mock_copy.assert_called_once_with("source.txt", "dest.txt")
        mock_delete.assert_called_once_with("source.txt")
    
    @patch('asyncio.get_event_loop')
    async def test_delete_file(self, mock_get_loop):
        """Test deleting file"""
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        
        async def mock_coro():
            return None
        
        mock_loop.run_in_executor.return_value = asyncio.create_task(mock_coro())
        
        ops = AsyncFileOperations()
        await ops.delete_file("test.txt")
        
        mock_loop.run_in_executor.assert_called_once()
    
    @patch('asyncio.get_event_loop')
    async def test_exists(self, mock_get_loop):
        """Test checking file existence"""
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        
        async def mock_coro():
            return True
        
        mock_loop.run_in_executor.return_value = asyncio.create_task(mock_coro())
        
        ops = AsyncFileOperations()
        exists = await ops.exists("test.txt")
        
        assert exists is True
    
    @patch('asyncio.get_event_loop')
    async def test_get_size(self, mock_get_loop):
        """Test getting file size"""
        mock_stat = Mock()
        mock_stat.st_size = 1024
        
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        
        async def mock_coro():
            return mock_stat
        
        mock_loop.run_in_executor.return_value = asyncio.create_task(mock_coro())
        
        ops = AsyncFileOperations()
        size = await ops.get_size("test.txt")
        
        assert size == 1024
    
    @patch('asyncio.get_event_loop')
    async def test_list_directory(self, mock_get_loop):
        """Test listing directory"""
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        
        async def mock_coro():
            return ["file1.txt", "file2.txt"]
        
        mock_loop.run_in_executor.return_value = asyncio.create_task(mock_coro())
        
        ops = AsyncFileOperations()
        files = await ops.list_directory("/test/dir")
        
        assert files == ["file1.txt", "file2.txt"]
    
    @patch('asyncio.get_event_loop')
    async def test_walk_directory(self, mock_get_loop):
        """Test walking directory tree"""
        walk_results = [
            ("/root", ["dir1"], ["file1.txt"]),
            ("/root/dir1", [], ["file2.txt"])
        ]
        
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        
        async def mock_coro():
            return walk_results
        
        mock_loop.run_in_executor.return_value = asyncio.create_task(mock_coro())
        
        ops = AsyncFileOperations()
        results = []
        async for root, dirs, files in ops.walk_directory("/root"):
            results.append((root, dirs, files))
        
        assert len(results) == 2
        assert results[0] == ("/root", ["dir1"], ["file1.txt"])
        assert results[1] == ("/root/dir1", [], ["file2.txt"])


@pytest.mark.asyncio
class TestAsyncJSONOperations:
    """Test AsyncJSONOperations class"""
    
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_read_json(self, mock_read):
        """Test reading JSON file"""
        mock_read.return_value = '{"key": "value", "number": 42}'
        
        ops = AsyncJSONOperations()
        data = await ops.read_json(Path("test.json"))
        
        assert data == {"key": "value", "number": 42}
    
    @patch.object(AsyncFileOperations, 'write_file')
    async def test_write_json(self, mock_write):
        """Test writing JSON file"""
        ops = AsyncJSONOperations()
        data = {"key": "value", "number": 42}
        
        await ops.write_json(Path("test.json"), data)
        
        mock_write.assert_called_once()
        written_content = mock_write.call_args[0][1]
        assert json.loads(written_content) == data
    
    @patch.object(AsyncFileOperations, 'read_files_batch')
    async def test_read_json_batch(self, mock_read_batch):
        """Test reading multiple JSON files"""
        mock_read_batch.return_value = {
            Path("file1.json"): '{"key1": "value1"}',
            Path("file2.json"): '{"key2": "value2"}',
            Path("invalid.json"): '{invalid json}',
            Path("empty.json"): ''
        }
        
        ops = AsyncJSONOperations()
        paths = [Path("file1.json"), Path("file2.json"), Path("invalid.json"), Path("empty.json")]
        
        result = await ops.read_json_batch(paths)
        
        assert result[Path("file1.json")] == {"key1": "value1"}
        assert result[Path("file2.json")] == {"key2": "value2"}
        assert result[Path("invalid.json")] is None  # Parse error
        assert result[Path("empty.json")] is None  # Empty content
    
    @patch('pathlib.Path.exists')
    @patch.object(AsyncJSONOperations, 'write_json')
    @patch.object(AsyncJSONOperations, 'read_json')
    async def test_update_json_files(self, mock_read, mock_write, mock_exists):
        """Test updating JSON files"""
        mock_exists.return_value = True
        mock_read.return_value = {"existing": "data"}
        
        ops = AsyncJSONOperations()
        updates = {
            Path("file1.json"): {"new": "value1"},
            Path("file2.json"): {"new": "value2"}
        }
        
        result = await ops.update_json_files(updates)
        
        assert result[Path("file1.json")] is True
        assert result[Path("file2.json")] is True
        
        # Check that data was merged
        for call in mock_write.call_args_list:
            path, data = call[0]
            assert "existing" in data
            assert "new" in data


@pytest.mark.asyncio
class TestAsyncYAMLOperations:
    """Test AsyncYAMLOperations class"""
    
    @patch.object(AsyncFileOperations, 'read_file')
    async def test_read_yaml(self, mock_read):
        """Test reading YAML file"""
        mock_read.return_value = "key: value\nnumber: 42"
        
        ops = AsyncYAMLOperations()
        data = await ops.read_yaml(Path("test.yaml"))
        
        assert data == {"key": "value", "number": 42}
    
    @patch.object(AsyncFileOperations, 'write_file')
    async def test_write_yaml(self, mock_write):
        """Test writing YAML file"""
        ops = AsyncYAMLOperations()
        data = {"key": "value", "number": 42}
        
        await ops.write_yaml(Path("test.yaml"), data)
        
        mock_write.assert_called_once()
        written_content = mock_write.call_args[0][1]
        assert yaml.safe_load(written_content) == data
    
    @patch.object(AsyncFileOperations, 'read_files_batch')
    async def test_read_yaml_batch(self, mock_read_batch):
        """Test reading multiple YAML files"""
        mock_read_batch.return_value = {
            Path("file1.yaml"): "key1: value1",
            Path("file2.yaml"): "key2: value2",
            Path("invalid.yaml"): "{invalid: yaml:",
            Path("empty.yaml"): ''
        }
        
        ops = AsyncYAMLOperations()
        paths = [Path("file1.yaml"), Path("file2.yaml"), Path("invalid.yaml"), Path("empty.yaml")]
        
        result = await ops.read_yaml_batch(paths)
        
        assert result[Path("file1.yaml")] == {"key1": "value1"}
        assert result[Path("file2.yaml")] == {"key2": "value2"}
        assert result[Path("invalid.yaml")] is None  # Parse error
        assert result[Path("empty.yaml")] is None  # Empty content


@pytest.mark.asyncio
class TestFileBatchProcessor:
    """Test FileBatchProcessor class"""
    
    def test_initialization(self):
        """Test FileBatchProcessor initialization"""
        processor = FileBatchProcessor()
        assert processor.batch_size == 100
        assert processor.max_concurrent == 20
        
        processor_custom = FileBatchProcessor(batch_size=50, max_concurrent=10)
        assert processor_custom.batch_size == 50
        assert processor_custom.max_concurrent == 10
    
    @patch('asyncio.get_event_loop')
    async def test_process_files_sync_processor(self, mock_get_loop):
        """Test processing files with sync processor"""
        def processor(path):
            return f"Processed {path}"
        
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop
        
        async def mock_executor(_, func, arg):
            return func(arg)
        
        mock_loop.run_in_executor.side_effect = mock_executor
        
        batch_processor = FileBatchProcessor()
        file_paths = ["file1.txt", "file2.txt"]
        
        results = await batch_processor.process_files(file_paths, processor)
        
        assert results["file1.txt"] == "Processed file1.txt"
        assert results["file2.txt"] == "Processed file2.txt"
    
    async def test_process_files_async_processor(self):
        """Test processing files with async processor"""
        async def processor(path):
            await asyncio.sleep(0.01)
            return f"Processed {path}"
        
        batch_processor = FileBatchProcessor()
        file_paths = ["file1.txt", "file2.txt"]
        
        results = await batch_processor.process_files(file_paths, processor)
        
        assert results["file1.txt"] == "Processed file1.txt"
        assert results["file2.txt"] == "Processed file2.txt"
    
    @patch.object(AsyncFileOperations, 'read_files_batch')
    @patch.object(AsyncFileOperations, 'find_files')
    async def test_process_large_directory(self, mock_find, mock_read_batch):
        """Test processing large directory"""
        # Mock finding files
        files = [Path(f"file{i}.txt") for i in range(250)]  # More than batch size
        mock_find.return_value = files
        
        # Mock reading batches
        async def read_batch_side_effect(batch):
            return {path: f"Content of {path}" for path in batch}
        
        mock_read_batch.side_effect = read_batch_side_effect
        
        def processor(path, content):
            return f"Processed {path}: {content}"
        
        batch_processor = FileBatchProcessor(batch_size=100)
        results = await batch_processor.process_large_directory(
            Path("/test"), processor, pattern="*.txt"
        )
        
        assert len(results) == 250
        # Should have been processed in 3 batches
        assert mock_read_batch.call_count == 3
    
    @patch.object(AsyncFileOperations, 'write_file')
    @patch.object(AsyncFileOperations, 'read_file')
    @patch.object(AsyncFileOperations, 'find_files')
    async def test_sync_files(self, mock_find, mock_read, mock_write):
        """Test syncing files between directories"""
        # Mock finding source files
        source_files = [
            Path("/source/file1.txt"),
            Path("/source/dir/file2.txt")
        ]
        mock_find.return_value = source_files
        
        # Mock reading files
        async def read_side_effect(path):
            return f"Content of {path}"
        
        mock_read.side_effect = read_side_effect
        
        batch_processor = FileBatchProcessor()
        stats = await batch_processor.sync_files(
            Path("/source"), Path("/target"), pattern="*.txt"
        )
        
        assert stats['total'] == 2
        assert stats['copied'] == 2
        assert stats['failed'] == 0
        
        # Check write calls
        assert mock_write.call_count == 2


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch.object(AsyncFileOperations, 'read_files_batch')
    async def test_read_files_async(self, mock_read_batch):
        """Test read_files_async convenience function"""
        mock_read_batch.return_value = {
            Path("file1.txt"): "Content 1",
            Path("file2.txt"): "Content 2"
        }
        
        paths = [Path("file1.txt"), Path("file2.txt")]
        result = await read_files_async(paths)
        
        assert result == mock_read_batch.return_value
    
    @patch.object(AsyncFileOperations, 'write_files_batch')
    async def test_write_files_async(self, mock_write_batch):
        """Test write_files_async convenience function"""
        mock_write_batch.return_value = {
            Path("file1.txt"): True,
            Path("file2.txt"): True
        }
        
        files = {Path("file1.txt"): "Content 1", Path("file2.txt"): "Content 2"}
        result = await write_files_async(files)
        
        assert result == mock_write_batch.return_value
    
    @patch.object(FileBatchProcessor, 'process_large_directory')
    async def test_process_directory_async(self, mock_process):
        """Test process_directory_async convenience function"""
        mock_process.return_value = ["result1", "result2"]
        
        def processor(path, content):
            return f"Processed {path}"
        
        result = await process_directory_async(Path("/test"), processor, "*.py")
        
        assert result == ["result1", "result2"]
        mock_process.assert_called_once_with(Path("/test"), processor, "*.py") 