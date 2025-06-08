"""
Tests for async file and git operations.
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import tempfile
import shutil

from tooling.utils.async_file_utils import AsyncFileOperations, FileBatchProcessor
from tooling.utils.async_git_utils import AsyncGitOperations, GitBatchProcessor, AsyncGitResult


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def async_file_ops():
    """Create AsyncFileOperations instance"""
    return AsyncFileOperations()


@pytest.fixture
def async_git_ops():
    """Create AsyncGitOperations instance"""
    return AsyncGitOperations()


class TestAsyncFileOperations:
    """Test async file operations"""
    
    @pytest.mark.asyncio
    async def test_read_file(self, async_file_ops, temp_dir):
        """Test async file reading"""
        # Create test file
        test_file = temp_dir / "test.txt"
        test_content = "Hello, async world!"
        test_file.write_text(test_content)
        
        # Read file
        content = await async_file_ops.read_file(str(test_file))
        assert content == test_content
    
    @pytest.mark.asyncio
    async def test_read_file_not_found(self, async_file_ops, temp_dir):
        """Test reading non-existent file"""
        non_existent = temp_dir / "missing.txt"
        
        with pytest.raises(FileNotFoundError):
            await async_file_ops.read_file(str(non_existent))
    
    @pytest.mark.asyncio
    async def test_write_file(self, async_file_ops, temp_dir):
        """Test async file writing"""
        test_file = temp_dir / "output.txt"
        test_content = "Async write test"
        
        await async_file_ops.write_file(str(test_file), test_content)
        
        # Verify file was written
        assert test_file.exists()
        assert test_file.read_text() == test_content
    
    @pytest.mark.asyncio
    async def test_read_files_batch(self, async_file_ops, temp_dir):
        """Test batch file reading"""
        # Create multiple test files
        files = {}
        for i in range(5):
            file_path = temp_dir / f"file{i}.txt"
            content = f"Content {i}"
            file_path.write_text(content)
            files[str(file_path)] = content
        
        # Read all files
        results = await async_file_ops.read_files_batch(list(files.keys()))
        
        assert len(results) == 5
        # Results will have Path keys, not string keys
        for str_path, expected_content in files.items():
            path_obj = Path(str_path)
            assert path_obj in results
            assert results[path_obj] == expected_content
    
    @pytest.mark.asyncio
    async def test_write_files_batch(self, async_file_ops, temp_dir):
        """Test batch file writing"""
        files_data = {
            str(temp_dir / "out1.txt"): "Content 1",
            str(temp_dir / "out2.txt"): "Content 2",
            str(temp_dir / "out3.txt"): "Content 3",
        }
        
        results = await async_file_ops.write_files_batch(files_data)
        
        # Verify all files were written
        for path, expected_content in files_data.items():
            assert Path(path).exists()
            assert Path(path).read_text() == expected_content
        
        # Verify status results have Path keys
        assert len(results) == 3
        for str_path in files_data.keys():
            path_obj = Path(str_path)
            assert path_obj in results
            assert results[path_obj] is True
    
    @pytest.mark.asyncio
    async def test_copy_file(self, async_file_ops, temp_dir):
        """Test async file copying"""
        source = temp_dir / "source.txt"
        dest = temp_dir / "dest.txt"
        content = "Copy me!"
        
        source.write_text(content)
        
        await async_file_ops.copy_file(str(source), str(dest))
        
        assert dest.exists()
        assert dest.read_text() == content
    
    @pytest.mark.asyncio
    async def test_move_file(self, async_file_ops, temp_dir):
        """Test async file moving"""
        source = temp_dir / "source.txt"
        dest = temp_dir / "dest.txt"
        content = "Move me!"
        
        source.write_text(content)
        
        await async_file_ops.move_file(str(source), str(dest))
        
        assert not source.exists()
        assert dest.exists()
        assert dest.read_text() == content
    
    @pytest.mark.asyncio
    async def test_delete_file(self, async_file_ops, temp_dir):
        """Test async file deletion"""
        test_file = temp_dir / "delete_me.txt"
        test_file.write_text("Delete this")
        
        await async_file_ops.delete_file(str(test_file))
        
        assert not test_file.exists()
    
    @pytest.mark.asyncio
    async def test_exists(self, async_file_ops, temp_dir):
        """Test async file existence check"""
        existing = temp_dir / "exists.txt"
        existing.write_text("I exist")
        non_existing = temp_dir / "missing.txt"
        
        assert await async_file_ops.exists(str(existing)) is True
        assert await async_file_ops.exists(str(non_existing)) is False
    
    @pytest.mark.asyncio
    async def test_get_size(self, async_file_ops, temp_dir):
        """Test getting file size"""
        test_file = temp_dir / "sized.txt"
        content = "12345"  # 5 bytes
        test_file.write_text(content)
        
        size = await async_file_ops.get_size(str(test_file))
        assert size == 5
    
    @pytest.mark.asyncio
    async def test_list_directory(self, async_file_ops, temp_dir):
        """Test async directory listing"""
        # Create some files and subdirs
        (temp_dir / "file1.txt").write_text("1")
        (temp_dir / "file2.txt").write_text("2")
        (temp_dir / "subdir").mkdir()
        (temp_dir / "subdir" / "file3.txt").write_text("3")
        
        files = await async_file_ops.list_directory(str(temp_dir))
        
        assert len(files) == 3  # 2 files + 1 dir
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "subdir" in files
    
    @pytest.mark.asyncio
    async def test_walk_directory(self, async_file_ops, temp_dir):
        """Test async directory walking"""
        # Create nested structure
        (temp_dir / "a").mkdir()
        (temp_dir / "a" / "b").mkdir()
        (temp_dir / "a" / "file1.txt").write_text("1")
        (temp_dir / "a" / "b" / "file2.txt").write_text("2")
        
        all_files = []
        async for root, dirs, files in async_file_ops.walk_directory(str(temp_dir)):
            for file in files:
                all_files.append(Path(root) / file)
        
        assert len(all_files) == 2
        assert any("file1.txt" in str(f) for f in all_files)
        assert any("file2.txt" in str(f) for f in all_files)


class TestFileBatchProcessor:
    """Test file batch processor"""
    
    @pytest.mark.asyncio
    async def test_process_files(self, temp_dir):
        """Test batch file processing"""
        processor = FileBatchProcessor(max_concurrent=2)
        
        # Create test files
        files = []
        for i in range(5):
            file_path = temp_dir / f"process{i}.txt"
            file_path.write_text(f"Process {i}")
            files.append(str(file_path))
        
        # Define processing function
        async def process_func(file_path: str) -> str:
            content = Path(file_path).read_text()
            return content.upper()
        
        results = await processor.process_files(files, process_func)
        
        assert len(results) == 5
        for i, (path, result) in enumerate(results.items()):
            assert result == f"PROCESS {i}"
    
    @pytest.mark.asyncio
    async def test_process_files_with_errors(self, temp_dir):
        """Test batch processing with some errors"""
        processor = FileBatchProcessor(max_concurrent=2)
        
        files = [
            str(temp_dir / "exists.txt"),
            str(temp_dir / "missing.txt"),
        ]
        
        # Only create the first file
        Path(files[0]).write_text("exists")
        
        async def process_func(file_path: str) -> str:
            return Path(file_path).read_text()
        
        results = await processor.process_files(files, process_func)
        
        assert results[files[0]] == "exists"
        assert results[files[1]] is None  # Error case


class TestAsyncGitOperations:
    """Test async git operations"""
    
    @pytest.mark.asyncio
    async def test_run_command(self, async_git_ops):
        """Test running git command"""
        with patch('asyncio.create_subprocess_exec') as mock_create:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"output", b""))
            mock_process.returncode = 0
            mock_create.return_value = mock_process
            
            result = await async_git_ops.run_command(['git', 'status'])
            
            assert result.stdout == "output"
            assert result.stderr == ""
            assert result.returncode == 0
            assert result.success is True
            mock_create.assert_called_once()
            assert 'git' in mock_create.call_args[0]
            assert 'status' in mock_create.call_args[0]
    
    @pytest.mark.asyncio
    async def test_run_command_error(self, async_git_ops):
        """Test git command with error"""
        with patch('asyncio.create_subprocess_exec') as mock_create:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_process.returncode = 1
            mock_create.return_value = mock_process
            
            result = await async_git_ops.run_command(['git', 'invalid'])
            
            assert result.stdout == ""
            assert result.stderr == "error"
            assert result.returncode == 1
            assert result.success is False
    
    @pytest.mark.asyncio
    async def test_get_status(self, async_git_ops):
        """Test getting git status"""
        expected_status = "On branch main\nnothing to commit"
        
        mock_result = AsyncGitResult(returncode=0, stdout=expected_status, stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)):
            status = await async_git_ops.get_status()
            assert status == expected_status
    
    @pytest.mark.asyncio
    async def test_get_diff(self, async_git_ops):
        """Test getting git diff"""
        expected_diff = "+added line\n-removed line"
        
        mock_result = AsyncGitResult(returncode=0, stdout=expected_diff, stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)):
            diff = await async_git_ops.get_diff()
            assert diff == expected_diff
    
    @pytest.mark.asyncio
    async def test_get_log(self, async_git_ops):
        """Test getting git log"""
        expected_log = "commit abc123\nAuthor: Test"
        
        mock_result = AsyncGitResult(returncode=0, stdout=expected_log, stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)):
            log = await async_git_ops.get_log(limit=10)
            assert log == expected_log
    
    @pytest.mark.asyncio
    async def test_get_branches(self, async_git_ops):
        """Test getting git branches"""
        branch_output = "* main\n  feature\n  develop"
        
        mock_result = AsyncGitResult(returncode=0, stdout=branch_output, stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)):
            branches = await async_git_ops.get_branches()
            
            assert len(branches) == 3
            assert "main" in branches
            assert "feature" in branches
            assert "develop" in branches
    
    @pytest.mark.asyncio
    async def test_get_remotes(self, async_git_ops):
        """Test getting git remotes"""
        remote_output = "origin\nupstream"
        
        mock_result = AsyncGitResult(returncode=0, stdout=remote_output, stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)):
            remotes = await async_git_ops.get_remotes()
            
            assert len(remotes) == 2
            assert "origin" in remotes
            assert "upstream" in remotes
    
    @pytest.mark.asyncio
    async def test_get_tags(self, async_git_ops):
        """Test getting git tags"""
        tag_output = "v1.0.0\nv1.1.0\nv2.0.0"
        
        mock_result = AsyncGitResult(returncode=0, stdout=tag_output, stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)):
            tags = await async_git_ops.get_tags()
            
            assert len(tags) == 3
            assert "v1.0.0" in tags
            assert "v2.0.0" in tags
    
    @pytest.mark.asyncio
    async def test_checkout(self, async_git_ops):
        """Test git checkout"""
        mock_result = AsyncGitResult(returncode=0, stdout="", stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)) as mock_run:
            await async_git_ops.checkout("feature-branch")
            mock_run.assert_called_once_with(['git', 'checkout', 'feature-branch'])
    
    @pytest.mark.asyncio
    async def test_pull(self, async_git_ops):
        """Test git pull"""
        mock_result = AsyncGitResult(returncode=0, stdout="", stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)) as mock_run:
            await async_git_ops.pull()
            mock_run.assert_called_once_with(['git', 'pull', 'origin'])
    
    @pytest.mark.asyncio
    async def test_push(self, async_git_ops):
        """Test git push"""
        mock_result = AsyncGitResult(returncode=0, stdout="", stderr="")
        with patch.object(async_git_ops, 'run_command', new=AsyncMock(return_value=mock_result)) as mock_run:
            await async_git_ops.push("origin", "main")
            mock_run.assert_called_once_with(['git', 'push', 'origin', 'main'])


class TestGitBatchProcessor:
    """Test git batch processor"""
    
    @pytest.mark.asyncio
    async def test_get_file_statuses(self):
        """Test getting file statuses in batch"""
        processor = GitBatchProcessor()
        
        files = ["file1.py", "file2.py", "file3.py"]
        
        # Mock git operations
        async def mock_run_command(cmd):
            file = cmd[-1]  # Last argument is the file
            result = AsyncGitResult(
                returncode=0,
                stdout=f"M  {file}" if "file1" in file else "",
                stderr=""
            )
            return result
        
        with patch.object(processor.git_ops, 'run_command', new=AsyncMock(side_effect=mock_run_command)):
            statuses = await processor.get_file_statuses(files)
            
            assert len(statuses) == 3
            for file in files:
                assert file in statuses
                if "file1" in file:
                    assert "M" in statuses[file]
    
    @pytest.mark.asyncio
    async def test_get_file_diffs(self):
        """Test getting file diffs in batch"""
        processor = GitBatchProcessor()
        
        files = ["file1.py", "file2.py"]
        
        # Mock git operations
        async def mock_run_command(cmd):
            if "file1.py" in cmd:
                return AsyncGitResult(returncode=0, stdout="+added to file1", stderr="")
            else:
                return AsyncGitResult(returncode=0, stdout="+added to file2", stderr="")
        
        with patch.object(processor.git_ops, 'run_command', new=AsyncMock(side_effect=mock_run_command)):
            diffs = await processor.get_file_diffs(files)
            
            assert len(diffs) == 2
            assert "+added to file1" in diffs["file1.py"]
            assert "+added to file2" in diffs["file2.py"]
    
    @pytest.mark.asyncio
    async def test_get_file_histories(self):
        """Test getting file histories in batch"""
        processor = GitBatchProcessor()
        
        files = ["file1.py"]
        
        # Mock git operations
        mock_result = AsyncGitResult(
            returncode=0,
            stdout="commit abc123\nAuthor: Test\n\nInitial commit",
            stderr=""
        )
        
        with patch.object(processor.git_ops, 'run_command', new=AsyncMock(return_value=mock_result)):
            histories = await processor.get_file_histories(files, limit=5)
            
            assert len(histories) == 1
            assert "commit abc123" in histories["file1.py"]
            assert "Initial commit" in histories["file1.py"] 