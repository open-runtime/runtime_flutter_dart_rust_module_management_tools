"""
Tests for git_utils.py
"""
import pytest
from unittest.mock import patch, Mock, MagicMock, call
import subprocess
from pathlib import Path

from tooling.utils.git_utils import (
    GitCommandResult, GitError, NotGitRepositoryError, GitOperations,
    check_git_repo, check_git_state, check_remote_sync, get_current_branch,
    get_git_root, has_uncommitted_changes, get_latest_tag, get_commits_since_tag,
    get_staged_files, get_staged_diff, get_diff_for_files, create_tag,
    push_tag, get_commit_messages_since_tag, get_remote_url,
    get_commits_since_branch, get_changed_files
)


class TestGitCommandResult:
    """Test GitCommandResult dataclass"""
    
    def test_git_command_result_success(self):
        """Test successful git command result"""
        result = GitCommandResult(returncode=0, stdout="output", stderr="")
        
        assert result.returncode == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.success is True
    
    def test_git_command_result_failure(self):
        """Test failed git command result"""
        result = GitCommandResult(returncode=1, stdout="", stderr="error")
        
        assert result.returncode == 1
        assert result.stderr == "error"
        assert result.success is False


class TestGitOperations:
    """Test GitOperations class"""
    
    def test_initialization(self):
        """Test GitOperations initialization"""
        git_ops = GitOperations()
        
        assert git_ops.cwd == Path.cwd()
        assert git_ops.timeout == 30
        assert git_ops._is_repo_cache is None
    
    def test_initialization_with_params(self):
        """Test GitOperations initialization with parameters"""
        logger = Mock()
        cwd = Path("/test/dir")
        
        git_ops = GitOperations(logger=logger, cwd=cwd, timeout=60)
        
        assert git_ops.logger == logger
        assert git_ops.cwd == cwd
        assert git_ops.timeout == 60
    
    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test running a successful command"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="success\n",
            stderr=""
        )
        
        git_ops = GitOperations()
        result = git_ops.run_command(["git", "status"])
        
        assert result.success
        assert result.stdout == "success"
        assert result.stderr == ""
        
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "status"]
    
    @patch('subprocess.run')
    def test_run_command_failure_with_check(self, mock_run):
        """Test running a failed command with check=True"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error message"
        )
        
        git_ops = GitOperations()
        
        with pytest.raises(GitError) as exc:
            git_ops.run_command(["git", "bad-command"], check=True)
        
        assert "Command failed" in str(exc.value)
        assert "error message" in str(exc.value)
    
    @patch('subprocess.run')
    def test_run_command_failure_no_check(self, mock_run):
        """Test running a failed command with check=False"""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="error"
        )
        
        git_ops = GitOperations()
        result = git_ops.run_command(["git", "bad-command"], check=False)
        
        assert not result.success
        assert result.returncode == 1
        assert result.stderr == "error"
    
    @patch('subprocess.run')
    def test_run_command_timeout(self, mock_run):
        """Test command timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(["git"], 30)
        
        git_ops = GitOperations()
        
        with pytest.raises(GitError) as exc:
            git_ops.run_command(["git", "status"])
        
        assert "Command timed out" in str(exc.value)
    
    @patch('subprocess.run')
    def test_is_git_repository_true(self, mock_run):
        """Test is_git_repository returns True"""
        mock_run.return_value = Mock(returncode=0, stdout=".git", stderr="")
        
        git_ops = GitOperations()
        assert git_ops.is_git_repository() is True
        
        # Test caching
        assert git_ops.is_git_repository() is True
        assert mock_run.call_count == 1  # Should use cache
    
    @patch('subprocess.run')
    def test_is_git_repository_false(self, mock_run):
        """Test is_git_repository returns False"""
        mock_run.return_value = Mock(returncode=128, stdout="", stderr="not a git repo")
        
        git_ops = GitOperations()
        assert git_ops.is_git_repository() is False
    
    @patch.object(GitOperations, 'is_git_repository')
    def test_ensure_git_repository_success(self, mock_is_repo):
        """Test ensure_git_repository when in repo"""
        mock_is_repo.return_value = True
        
        git_ops = GitOperations()
        git_ops.ensure_git_repository()  # Should not raise
    
    @patch.object(GitOperations, 'is_git_repository')
    def test_ensure_git_repository_failure(self, mock_is_repo):
        """Test ensure_git_repository when not in repo"""
        mock_is_repo.return_value = False
        
        git_ops = GitOperations()
        
        with pytest.raises(NotGitRepositoryError):
            git_ops.ensure_git_repository()
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_current_branch_normal(self, mock_ensure, mock_run):
        """Test getting current branch name"""
        mock_run.return_value = GitCommandResult(0, "main", "")
        
        git_ops = GitOperations()
        branch = git_ops.get_current_branch()
        
        assert branch == "main"
        mock_ensure.assert_called_once()
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_current_branch_detached_head(self, mock_ensure, mock_run):
        """Test getting current branch in detached HEAD state"""
        # First call fails (symbolic-ref)
        # Second call succeeds (rev-parse)
        mock_run.side_effect = [
            GitCommandResult(1, "", "fatal: ref HEAD is not a symbolic ref"),
            GitCommandResult(0, "abc123", "")
        ]
        
        git_ops = GitOperations()
        branch = git_ops.get_current_branch()
        
        assert branch == "abc123"
        assert mock_run.call_count == 2
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_latest_tag(self, mock_ensure, mock_run):
        """Test getting latest tag"""
        mock_run.return_value = GitCommandResult(0, "v1.2.3", "")
        
        git_ops = GitOperations()
        tag = git_ops.get_latest_tag()
        
        assert tag == "v1.2.3"
        mock_run.assert_called_once_with(
            ["git", "describe", "--tags", "--abbrev=0"],
            check=False
        )
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_latest_tag_with_pattern(self, mock_ensure, mock_run):
        """Test getting latest tag with pattern"""
        mock_run.return_value = GitCommandResult(0, "v2.0.0", "")
        
        git_ops = GitOperations()
        tag = git_ops.get_latest_tag(pattern="v2*")
        
        assert tag == "v2.0.0"
        mock_run.assert_called_once_with(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v2*"],
            check=False
        )
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_latest_tag_none_found(self, mock_ensure, mock_run):
        """Test getting latest tag when none found"""
        mock_run.return_value = GitCommandResult(128, "", "No tags found")
        
        git_ops = GitOperations()
        tag = git_ops.get_latest_tag()
        
        assert tag is None
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_all_tags(self, mock_ensure, mock_run):
        """Test getting all tags"""
        mock_run.return_value = GitCommandResult(0, "v1.0.0\nv1.1.0\nv2.0.0", "")
        
        git_ops = GitOperations()
        tags = git_ops.get_all_tags()
        
        assert tags == ["v1.0.0", "v1.1.0", "v2.0.0"]
    
    @patch.object(GitOperations, 'get_all_tags')
    def test_tag_exists(self, mock_get_tags):
        """Test checking if tag exists"""
        mock_get_tags.return_value = ["v1.0.0", "v1.1.0"]
        
        git_ops = GitOperations()
        
        assert git_ops.tag_exists("v1.0.0") is True
        assert git_ops.tag_exists("v2.0.0") is False
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_is_working_directory_clean(self, mock_ensure, mock_run):
        """Test checking if working directory is clean"""
        mock_run.return_value = GitCommandResult(0, "", "")
        
        git_ops = GitOperations()
        assert git_ops.is_working_directory_clean() is True
        
        # Test with uncommitted changes
        mock_run.return_value = GitCommandResult(0, "M file.py", "")
        assert git_ops.is_working_directory_clean() is False
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_uncommitted_changes(self, mock_ensure, mock_run):
        """Test getting uncommitted changes"""
        mock_run.return_value = GitCommandResult(
            0,
            "M  staged.py\n M unstaged.py\nMM both.py\n?? untracked.py",
            ""
        )
        
        git_ops = GitOperations()
        changes = git_ops.get_uncommitted_changes()
        
        assert "staged.py" in changes['staged']
        assert "both.py" in changes['staged']
        assert "unstaged.py" in changes['unstaged']
        assert "both.py" in changes['unstaged']
        assert "untracked.py" in changes['untracked']
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_commit_messages(self, mock_ensure, mock_run):
        """Test getting commit messages"""
        mock_run.return_value = GitCommandResult(
            0,
            "abc123|John Doe|john@example.com|2025-06-07 10:00:00|feat: add feature|Body text",
            ""
        )
        
        git_ops = GitOperations()
        commits = git_ops.get_commit_messages(from_ref="v1.0.0", to_ref="HEAD")
        
        assert len(commits) == 1
        assert commits[0]['hash'] == "abc123"
        assert commits[0]['author_name'] == "John Doe"
        assert commits[0]['subject'] == "feat: add feature"
        assert commits[0]['body'] == "Body text"
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_changed_files(self, mock_ensure, mock_run):
        """Test getting changed files"""
        mock_run.return_value = GitCommandResult(0, "file1.py\nfile2.py", "")
        
        git_ops = GitOperations()
        files = git_ops.get_changed_files(from_ref="v1.0.0")
        
        assert files == ["file1.py", "file2.py"]
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_file_diff(self, mock_ensure, mock_run):
        """Test getting file diff"""
        diff_output = "diff --git a/file.py b/file.py\n+added line"
        mock_run.return_value = GitCommandResult(0, diff_output, "")
        
        git_ops = GitOperations()
        diff = git_ops.get_file_diff("file.py", from_ref="v1.0.0")
        
        assert diff == diff_output
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_get_remote_url(self, mock_ensure, mock_run):
        """Test getting remote URL"""
        mock_run.return_value = GitCommandResult(
            0,
            "https://github.com/user/repo.git",
            ""
        )
        
        git_ops = GitOperations()
        url = git_ops.get_remote_url()
        
        assert url == "https://github.com/user/repo.git"
    
    @patch.object(GitOperations, 'get_remote_url')
    def test_get_github_url_ssh(self, mock_get_remote):
        """Test converting SSH URL to GitHub URL"""
        mock_get_remote.return_value = "git@github.com:owner/repo.git"
        
        git_ops = GitOperations()
        url = git_ops.get_github_url()
        
        assert url == "https://github.com/owner/repo"
    
    @patch.object(GitOperations, 'get_remote_url')
    def test_get_github_url_https(self, mock_get_remote):
        """Test handling HTTPS GitHub URL"""
        mock_get_remote.return_value = "https://github.com/owner/repo.git"
        
        git_ops = GitOperations()
        url = git_ops.get_github_url()
        
        assert url == "https://github.com/owner/repo"
    
    @patch.object(GitOperations, 'get_remote_url')
    def test_get_github_url_no_remote(self, mock_get_remote):
        """Test getting GitHub URL when no remote"""
        mock_get_remote.return_value = None
        
        git_ops = GitOperations()
        url = git_ops.get_github_url()
        
        assert url is None
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'tag_exists')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_create_tag_simple(self, mock_ensure, mock_exists, mock_run):
        """Test creating a simple tag"""
        mock_exists.return_value = False
        mock_run.return_value = GitCommandResult(0, "", "")
        
        git_ops = GitOperations()
        git_ops.create_tag("v1.0.0")
        
        mock_run.assert_called_once_with(["git", "tag", "v1.0.0", "HEAD"])
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'tag_exists')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_create_tag_annotated(self, mock_ensure, mock_exists, mock_run):
        """Test creating an annotated tag"""
        mock_exists.return_value = False
        mock_run.return_value = GitCommandResult(0, "", "")
        
        git_ops = GitOperations()
        git_ops.create_tag("v1.0.0", message="Release 1.0.0")
        
        mock_run.assert_called_once_with(
            ["git", "tag", "-a", "v1.0.0", "-m", "Release 1.0.0", "HEAD"]
        )
    
    @patch.object(GitOperations, 'tag_exists')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_create_tag_already_exists(self, mock_ensure, mock_exists):
        """Test creating tag that already exists"""
        mock_exists.return_value = True
        
        git_ops = GitOperations()
        
        with pytest.raises(GitError) as exc:
            git_ops.create_tag("v1.0.0")
        
        assert "already exists" in str(exc.value)
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_push_tag(self, mock_ensure, mock_run):
        """Test pushing a tag"""
        mock_run.return_value = GitCommandResult(0, "", "")
        
        git_ops = GitOperations()
        git_ops.push_tag("v1.0.0")
        
        mock_run.assert_called_once_with(["git", "push", "origin", "v1.0.0"])
    
    @patch.object(GitOperations, 'run_command')
    @patch.object(GitOperations, 'ensure_git_repository')
    def test_push_tag_force(self, mock_ensure, mock_run):
        """Test force pushing a tag"""
        mock_run.return_value = GitCommandResult(0, "", "")
        
        git_ops = GitOperations()
        git_ops.push_tag("v1.0.0", force=True)
        
        mock_run.assert_called_once_with(["git", "push", "--force", "origin", "v1.0.0"])


class TestStandaloneFunctions:
    """Test standalone git utility functions"""
    
    @patch('tooling.utils.git_utils.run_command')
    def test_check_git_repo_true(self, mock_run):
        """Test check_git_repo returns True"""
        mock_run.return_value = (0, ".git", "")
        
        assert check_git_repo() is True
    
    @patch('tooling.utils.git_utils.run_command')
    def test_check_git_repo_false(self, mock_run):
        """Test check_git_repo returns False"""
        mock_run.return_value = (128, "", "not a git repo")
        
        assert check_git_repo() is False
    
    @patch('tooling.utils.git_utils.run_command')
    @patch('pathlib.Path.exists')
    def test_check_git_state_detached_head(self, mock_exists, mock_run):
        """Test check_git_state with detached HEAD"""
        mock_run.return_value = (1, "", "")  # symbolic-ref fails
        
        assert check_git_state() is False
    
    @patch('tooling.utils.git_utils.run_command')
    @patch('pathlib.Path.exists')
    def test_check_git_state_rebase_in_progress(self, mock_exists, mock_run):
        """Test check_git_state with rebase in progress"""
        mock_run.side_effect = [
            (0, "refs/heads/main", ""),  # symbolic-ref succeeds
            (0, ".git", "")  # rev-parse succeeds
        ]
        
        # Mock rebase-merge directory exists
        def mock_exists_side_effect():
            # Return True if checking for rebase directories
            return True
        
        mock_exists.side_effect = mock_exists_side_effect
        
        assert check_git_state() is False
    
    @patch('tooling.utils.git_utils.run_command')
    @patch('pathlib.Path.exists')
    def test_check_git_state_clean(self, mock_exists, mock_run):
        """Test check_git_state when clean"""
        mock_run.side_effect = [
            (0, "refs/heads/main", ""),  # symbolic-ref
            (0, ".git", "")  # rev-parse
        ]
        mock_exists.return_value = False  # No special git files
        
        assert check_git_state() is True
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_current_branch_function(self, mock_run):
        """Test get_current_branch standalone function"""
        mock_run.return_value = (0, "feature-branch", "")
        
        branch = get_current_branch()
        assert branch == "feature-branch"
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_git_root(self, mock_run):
        """Test get_git_root function"""
        mock_run.return_value = (0, "/path/to/repo", "")
        
        root = get_git_root()
        assert root == Path("/path/to/repo")
    
    @patch('tooling.utils.git_utils.run_command')
    def test_has_uncommitted_changes_clean(self, mock_run):
        """Test has_uncommitted_changes when clean"""
        # Zero exit code means no changes
        mock_run.return_value = (0, "", "")
        
        assert has_uncommitted_changes() is False
    
    @patch('tooling.utils.git_utils.run_command')
    def test_has_uncommitted_changes_dirty(self, mock_run):
        """Test has_uncommitted_changes with changes"""
        # The function uses diff-index command, not status --porcelain
        mock_run.return_value = (1, "", "")  # Non-zero exit code means changes exist
        
        result = has_uncommitted_changes()
        assert result is True
        mock_run.assert_called_once_with(["git", "diff-index", "--quiet", "HEAD", "--"])
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_latest_tag_function(self, mock_run):
        """Test get_latest_tag standalone function"""
        mock_run.return_value = (0, "v1.2.3", "")
        
        tag = get_latest_tag()
        assert tag == "v1.2.3"
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_commits_since_tag(self, mock_run):
        """Test get_commits_since_tag function"""
        mock_run.return_value = (0, "abc123 First commit\ndef456 Second commit", "")
        
        commits = get_commits_since_tag("v1.0.0")
        assert len(commits) == 2
        assert commits[0] == "abc123 First commit"
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_staged_files(self, mock_run):
        """Test get_staged_files function"""
        mock_run.return_value = (0, "file1.py\nfile2.py", "")
        
        files = get_staged_files()
        assert files == ["file1.py", "file2.py"]
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_staged_diff(self, mock_run):
        """Test get_staged_diff function"""
        diff = "diff --git a/file.py b/file.py\n+added"
        mock_run.return_value = (0, diff, "")
        
        result = get_staged_diff()
        assert result == diff
    
    @patch('tooling.utils.git_utils.run_command')
    def test_create_tag_function(self, mock_run):
        """Test create_tag standalone function"""
        mock_run.return_value = (0, "", "")
        
        create_tag("v1.0.0", "Release message")
        
        # Should be called with tag command
        call_args = mock_run.call_args[0][0]
        assert "tag" in call_args
        assert "v1.0.0" in call_args
    
    @patch('tooling.utils.git_utils.run_command')
    def test_push_tag_function(self, mock_run):
        """Test push_tag standalone function"""
        mock_run.return_value = (0, "", "")
        
        push_tag("v1.0.0")
        
        call_args = mock_run.call_args[0][0]
        assert "push" in call_args
        assert "v1.0.0" in call_args
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_remote_url_function(self, mock_run):
        """Test get_remote_url standalone function"""
        mock_run.return_value = (0, "https://github.com/user/repo.git", "")
        
        url = get_remote_url()
        assert url == "https://github.com/user/repo.git"
    
    @patch('tooling.utils.git_utils.run_command')
    def test_get_changed_files_function(self, mock_run):
        """Test get_changed_files standalone function"""
        mock_run.return_value = (0, "file1.py\nfile2.py\nfile3.py", "")
        
        files = get_changed_files("v1.0.0")
        # The function may be called multiple times, just check the mock call
        mock_run.assert_called()
        
        # Verify the files are returned correctly
        expected_files = ["file1.py", "file2.py", "file3.py"]
        for f in expected_files:
            assert f in files