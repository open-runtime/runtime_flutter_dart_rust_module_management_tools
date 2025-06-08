"""
Tests for async_git_utils.py
"""
import pytest
import asyncio
from unittest.mock import patch, Mock, MagicMock, AsyncMock, create_autospec
from pathlib import Path

from tooling.utils.async_git_utils import (
    AsyncGitResult, AsyncGitOperations, GitBatchProcessor,
    get_commits_async, get_files_content_async, analyze_commits_parallel
)


class TestAsyncGitResult:
    """Test AsyncGitResult dataclass"""
    
    def test_async_git_result_success(self):
        """Test successful result"""
        result = AsyncGitResult(returncode=0, stdout="output", stderr="")
        
        assert result.returncode == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.success is True
    
    def test_async_git_result_failure(self):
        """Test failed result"""
        result = AsyncGitResult(returncode=1, stdout="", stderr="error")
        
        assert result.returncode == 1
        assert result.stderr == "error"
        assert result.success is False


@pytest.mark.asyncio
class TestAsyncGitOperations:
    """Test AsyncGitOperations class"""
    
    def test_initialization(self):
        """Test AsyncGitOperations initialization"""
        ops = AsyncGitOperations()
        
        assert ops.cwd == Path.cwd()
        assert ops.timeout == 30
        assert ops._semaphore._value == 10
    
    def test_initialization_with_params(self):
        """Test initialization with custom parameters"""
        cwd = Path("/test/dir")
        ops = AsyncGitOperations(cwd=cwd, timeout=60)
        
        assert ops.cwd == cwd
        assert ops.timeout == 60
    
    @patch('asyncio.create_subprocess_exec')
    async def test_run_command_success(self, mock_subprocess):
        """Test running command successfully"""
        # Mock process
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"output\n", b"")
        mock_subprocess.return_value = mock_proc
        
        ops = AsyncGitOperations()
        result = await ops.run_command(["git", "status"])
        
        assert result.success
        assert result.stdout == "output"
        assert result.stderr == ""
        
        mock_subprocess.assert_called_once_with(
            "git", "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ops.cwd
        )
    
    @patch('asyncio.create_subprocess_exec')
    async def test_run_command_failure(self, mock_subprocess):
        """Test command failure"""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"error message\n")
        mock_subprocess.return_value = mock_proc
        
        ops = AsyncGitOperations()
        result = await ops.run_command(["git", "bad-command"])
        
        assert not result.success
        assert result.returncode == 1
        assert result.stderr == "error message"
    
    @patch('asyncio.create_subprocess_exec')
    async def test_run_command_timeout(self, mock_subprocess):
        """Test command timeout"""
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = asyncio.TimeoutError()
        mock_proc.kill = Mock()
        mock_subprocess.return_value = mock_proc
        
        ops = AsyncGitOperations(timeout=1)
        
        with pytest.raises(asyncio.TimeoutError):
            await ops.run_command(["git", "status"])
        
        mock_proc.kill.assert_called_once()
    
    @patch('asyncio.create_subprocess_exec')
    async def test_run_command_exception(self, mock_subprocess):
        """Test command with general exception"""
        mock_subprocess.side_effect = Exception("Process error")
        
        ops = AsyncGitOperations()
        
        with pytest.raises(Exception, match="Process error"):
            await ops.run_command(["git", "status"])
    
    @patch.object(AsyncGitOperations, 'get_commits_between')
    async def test_get_commits_batch(self, mock_get_commits):
        """Test getting commits for multiple ref ranges"""
        # Mock return values
        async def get_commits_side_effect(start, end):
            return [{"hash": f"{start}..{end}"}]
        
        mock_get_commits.side_effect = get_commits_side_effect
        
        ops = AsyncGitOperations()
        ref_pairs = [("v1.0", "v1.1"), ("v1.1", "v1.2")]
        
        results = await ops.get_commits_batch(ref_pairs)
        
        assert len(results) == 2
        assert results[0] == [{"hash": "v1.0..v1.1"}]
        assert results[1] == [{"hash": "v1.1..v1.2"}]
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_commits_between_with_range(self, mock_run):
        """Test getting commits between refs"""
        mock_run.return_value = AsyncGitResult(
            0,
            "abc123|John Doe|john@example.com|2025-06-07|feat: add feature|Body text",
            ""
        )
        
        ops = AsyncGitOperations()
        commits = await ops.get_commits_between("v1.0", "HEAD")
        
        assert len(commits) == 1
        assert commits[0]['hash'] == "abc123"
        assert commits[0]['author_name'] == "John Doe"
        assert commits[0]['subject'] == "feat: add feature"
        
        mock_run.assert_called_once_with(
            ["git", "log", "v1.0..HEAD", "--format=%H|%an|%ae|%ai|%s|%b"]
        )
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_commits_between_no_start(self, mock_run):
        """Test getting all commits up to ref"""
        mock_run.return_value = AsyncGitResult(0, "", "")
        
        ops = AsyncGitOperations()
        await ops.get_commits_between(None, "HEAD")
        
        mock_run.assert_called_once_with(
            ["git", "log", "HEAD", "--format=%H|%an|%ae|%ai|%s|%b"]
        )
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_commits_between_failure(self, mock_run):
        """Test getting commits with command failure"""
        mock_run.return_value = AsyncGitResult(1, "", "error")
        
        ops = AsyncGitOperations()
        commits = await ops.get_commits_between("v1.0", "HEAD")
        
        assert commits == []
    
    @patch.object(AsyncGitOperations, 'get_file_content')
    async def test_get_file_contents_batch(self, mock_get_content):
        """Test getting multiple file contents"""
        async def get_content_side_effect(file, ref):
            if "error" in file:
                raise IOError(f"Cannot read {file}")
            return f"Content of {file} at {ref}"
        
        mock_get_content.side_effect = get_content_side_effect
        
        ops = AsyncGitOperations()
        files = ["file1.txt", "error.txt", "file3.txt"]
        
        result = await ops.get_file_contents_batch(files, "HEAD")
        
        assert result["file1.txt"] == "Content of file1.txt at HEAD"
        assert result["error.txt"] == ""  # Error case
        assert result["file3.txt"] == "Content of file3.txt at HEAD"
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_file_content(self, mock_run):
        """Test getting single file content"""
        mock_run.return_value = AsyncGitResult(0, "File content", "")
        
        ops = AsyncGitOperations()
        content = await ops.get_file_content("test.txt", "v1.0")
        
        assert content == "File content"
        mock_run.assert_called_once_with(["git", "show", "v1.0:test.txt"])
    
    @patch.object(AsyncGitOperations, 'get_changed_files')
    async def test_get_changed_files_batch(self, mock_get_changed):
        """Test getting changed files for multiple ref ranges"""
        async def get_changed_side_effect(start, end):
            return [f"changed_{start}_{end}.txt"]
        
        mock_get_changed.side_effect = get_changed_side_effect
        
        ops = AsyncGitOperations()
        ref_pairs = [(None, "HEAD"), ("v1.0", "v1.1")]
        
        results = await ops.get_changed_files_batch(ref_pairs)
        
        assert len(results) == 2
        assert results[0] == ["changed_None_HEAD.txt"]
        assert results[1] == ["changed_v1.0_v1.1.txt"]
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_changed_files(self, mock_run):
        """Test getting changed files"""
        mock_run.return_value = AsyncGitResult(0, "file1.txt\nfile2.txt", "")
        
        ops = AsyncGitOperations()
        files = await ops.get_changed_files("v1.0", "HEAD")
        
        assert files == ["file1.txt", "file2.txt"]
        mock_run.assert_called_once_with(
            ["git", "diff", "--name-only", "v1.0..HEAD"]
        )
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_tags(self, mock_run):
        """Test getting tags"""
        mock_run.return_value = AsyncGitResult(0, "v1.0.0\nv1.1.0\nv2.0.0", "")
        
        ops = AsyncGitOperations()
        tags = await ops.get_tags()
        
        assert tags == ["v1.0.0", "v1.1.0", "v2.0.0"]
        mock_run.assert_called_once_with(["git", "tag", "-l"])
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_tags_with_pattern(self, mock_run):
        """Test getting tags with pattern"""
        mock_run.return_value = AsyncGitResult(0, "v1.0.0\nv1.1.0", "")
        
        ops = AsyncGitOperations()
        tags = await ops.get_tags(pattern="v1.*")
        
        assert tags == ["v1.0.0", "v1.1.0"]
        mock_run.assert_called_once_with(["git", "tag", "-l", "v1.*"])
    
    @patch.object(AsyncGitOperations, 'is_tracked')
    async def test_parallel_status_check(self, mock_is_tracked):
        """Test checking status for multiple paths"""
        async def is_tracked_side_effect(path):
            # Only return True if path starts with "tracked" to avoid "untracked" matching
            return path.startswith("tracked")
        
        mock_is_tracked.side_effect = is_tracked_side_effect
        
        ops = AsyncGitOperations()
        paths = ["tracked_file.txt", "untracked_file.txt", "tracked_dir/file.txt"]
        
        result = await ops.parallel_status_check(paths)
        
        assert result["tracked_file.txt"] is True
        assert result["untracked_file.txt"] is False
        assert result["tracked_dir/file.txt"] is True
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_is_tracked(self, mock_run):
        """Test checking if file is tracked"""
        mock_run.return_value = AsyncGitResult(0, "file.txt", "")
        
        ops = AsyncGitOperations()
        tracked = await ops.is_tracked("file.txt")
        
        assert tracked is True
        mock_run.assert_called_once_with(
            ["git", "ls-files", "--error-unmatch", "file.txt"]
        )
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_status(self, mock_run):
        """Test getting git status"""
        mock_run.return_value = AsyncGitResult(0, "On branch main", "")
        
        ops = AsyncGitOperations()
        status = await ops.get_status()
        
        assert status == "On branch main"
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_diff(self, mock_run):
        """Test getting git diff"""
        mock_run.return_value = AsyncGitResult(0, "diff content", "")
        
        ops = AsyncGitOperations()
        
        # Test regular diff
        diff = await ops.get_diff()
        assert diff == "diff content"
        mock_run.assert_called_with(["git", "diff"])
        
        # Test cached diff
        diff = await ops.get_diff(cached=True)
        mock_run.assert_called_with(["git", "diff", "--cached"])
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_branches(self, mock_run):
        """Test getting branches"""
        mock_run.return_value = AsyncGitResult(0, "* main\n  feature\n  develop", "")
        
        ops = AsyncGitOperations()
        branches = await ops.get_branches()
        
        assert branches == ["main", "feature", "develop"]
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_branches_remote(self, mock_run):
        """Test getting remote branches"""
        mock_run.return_value = AsyncGitResult(0, "origin/main\norigin/feature", "")
        
        ops = AsyncGitOperations()
        branches = await ops.get_branches(remote=True)
        
        assert branches == ["origin/main", "origin/feature"]
        mock_run.assert_called_once_with(["git", "branch", "-r"])
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_checkout_success(self, mock_run):
        """Test successful checkout"""
        mock_run.return_value = AsyncGitResult(0, "Switched to branch 'feature'", "")
        
        ops = AsyncGitOperations()
        await ops.checkout("feature")
        
        mock_run.assert_called_once_with(["git", "checkout", "feature"])
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_checkout_failure(self, mock_run):
        """Test checkout failure"""
        mock_run.return_value = AsyncGitResult(1, "", "error: pathspec 'invalid' did not match")
        
        ops = AsyncGitOperations()
        
        with pytest.raises(RuntimeError, match="Failed to checkout"):
            await ops.checkout("invalid")
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_pull(self, mock_run):
        """Test git pull"""
        mock_run.return_value = AsyncGitResult(0, "Already up to date.", "")
        
        ops = AsyncGitOperations()
        await ops.pull()
        
        mock_run.assert_called_once_with(["git", "pull", "origin"])
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_push_with_branch(self, mock_run):
        """Test git push with branch"""
        mock_run.return_value = AsyncGitResult(0, "Everything up-to-date", "")
        
        ops = AsyncGitOperations()
        await ops.push(remote="upstream", branch="feature")
        
        mock_run.assert_called_once_with(["git", "push", "upstream", "feature"])


@pytest.mark.asyncio
class TestGitBatchProcessor:
    """Test GitBatchProcessor class"""
    
    def test_initialization(self):
        """Test GitBatchProcessor initialization"""
        processor = GitBatchProcessor()
        
        assert processor.batch_size == 50
        assert isinstance(processor.git, AsyncGitOperations)
        assert processor.git_ops is processor.git
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_file_statuses(self, mock_run):
        """Test getting file statuses"""
        # Mock different status results
        mock_run.side_effect = [
            AsyncGitResult(0, "M file1.txt", ""),
            AsyncGitResult(0, "", ""),  # unmodified
            AsyncGitResult(1, "", "error")  # error
        ]
        
        processor = GitBatchProcessor()
        files = ["file1.txt", "file2.txt", "file3.txt"]
        
        statuses = await processor.get_file_statuses(files)
        
        assert statuses["file1.txt"] == "M file1.txt"
        assert statuses["file2.txt"] == "unmodified"
        assert statuses["file3.txt"] == "error"
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_file_diffs(self, mock_run):
        """Test getting file diffs"""
        mock_run.side_effect = [
            AsyncGitResult(0, "diff for file1", ""),
            AsyncGitResult(0, "diff for file2", ""),
            AsyncGitResult(1, "", "error")
        ]
        
        processor = GitBatchProcessor()
        files = ["file1.txt", "file2.txt", "file3.txt"]
        
        diffs = await processor.get_file_diffs(files)
        
        assert diffs["file1.txt"] == "diff for file1"
        assert diffs["file2.txt"] == "diff for file2"
        assert diffs["file3.txt"] == ""  # Error case
    
    @patch.object(AsyncGitOperations, 'run_command')
    async def test_get_file_histories(self, mock_run):
        """Test getting file histories"""
        mock_run.side_effect = [
            AsyncGitResult(0, "abc123 commit 1\ndef456 commit 2", ""),
            AsyncGitResult(0, "789xyz commit 3", ""),
        ]
        
        processor = GitBatchProcessor()
        files = ["file1.txt", "file2.txt"]
        
        histories = await processor.get_file_histories(files, limit=5)
        
        assert "abc123" in histories["file1.txt"]
        assert "789xyz" in histories["file2.txt"]
        
        # Check command format
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert "-5" in cmd  # limit
            assert "--oneline" in cmd
    
    async def test_process_commits_in_batches(self):
        """Test processing commits in batches"""
        commits = [f"commit{i}" for i in range(150)]  # More than batch size
        
        async def processor_func(batch):
            # Simple processor that returns uppercased commits
            return [c.upper() for c in batch]
        
        processor = GitBatchProcessor(batch_size=50)
        results = await processor.process_commits_in_batches(commits, processor_func)
        
        assert len(results) == 150
        assert results[0] == "COMMIT0"
        assert results[-1] == "COMMIT149"
    
    @patch.object(AsyncGitOperations, 'run_command')
    @patch.object(AsyncGitOperations, 'get_tags')
    @patch.object(AsyncGitOperations, 'get_commits_between')
    async def test_analyze_repository_parallel(self, mock_commits, mock_tags, mock_run):
        """Test analyzing repository in parallel"""
        # Mock return values
        mock_run.side_effect = [
            AsyncGitResult(0, "* main\n  feature", ""),  # branches
            AsyncGitResult(0, "M file.txt", ""),  # status
            AsyncGitResult(0, "origin https://github.com/user/repo", "")  # remotes
        ]
        mock_tags.return_value = ["v1.0", "v1.1"]
        mock_commits.return_value = [{"hash": "abc123"}]
        
        processor = GitBatchProcessor()
        analysis = await processor.analyze_repository_parallel()
        
        assert analysis['branches'] is not None
        assert analysis['tags'] == ["v1.0", "v1.1"]
        assert analysis['recent_commits'] == [{"hash": "abc123"}]
        assert analysis['status'] is not None
        assert analysis['remotes'] is not None


@pytest.mark.asyncio
class TestConvenienceFunctions:
    """Test convenience functions"""
    
    @patch.object(AsyncGitOperations, 'get_commits_between')
    async def test_get_commits_async(self, mock_get_commits):
        """Test get_commits_async convenience function"""
        mock_get_commits.return_value = [{"hash": "abc123"}]
        
        commits = await get_commits_async("v1.0", "HEAD")
        
        assert commits == [{"hash": "abc123"}]
        mock_get_commits.assert_called_once_with("v1.0", "HEAD")
    
    @patch.object(AsyncGitOperations, 'get_file_contents_batch')
    async def test_get_files_content_async(self, mock_get_contents):
        """Test get_files_content_async convenience function"""
        mock_get_contents.return_value = {
            "file1.txt": "content1",
            "file2.txt": "content2"
        }
        
        files = ["file1.txt", "file2.txt"]
        contents = await get_files_content_async(files, "v1.0")
        
        assert contents == mock_get_contents.return_value
        mock_get_contents.assert_called_once_with(files, "v1.0")
    
    @patch.object(GitBatchProcessor, 'process_commits_in_batches')
    async def test_analyze_commits_parallel(self, mock_process):
        """Test analyze_commits_parallel convenience function"""
        mock_process.return_value = ["result1", "result2"]
        
        async def analyzer(commits):
            return [f"analyzed_{c}" for c in commits]
        
        commits = ["commit1", "commit2"]
        results = await analyze_commits_parallel(commits, analyzer)
        
        assert results == ["result1", "result2"]
        mock_process.assert_called_once() 