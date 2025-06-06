"""
Tests for git utility functions.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from tooling.utils.git_utils import (
    GitOperations, GitCommandResult, GitError, NotGitRepositoryError
)


class TestGitCommandResult(unittest.TestCase):
    """Test GitCommandResult class."""
    
    def test_success_property(self):
        """Test success property."""
        # Successful result
        result = GitCommandResult(returncode=0, stdout="output", stderr="")
        self.assertTrue(result.success)
        
        # Failed result
        result = GitCommandResult(returncode=1, stdout="", stderr="error")
        self.assertFalse(result.success)


class TestGitOperations(unittest.TestCase):
    """Test GitOperations class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_logger = Mock()
        # Use a mock path to avoid Path.cwd() issues
        self.mock_cwd = Path("/tmp/test_git")
        self.git = GitOperations(logger=self.mock_logger, cwd=self.mock_cwd)
    
    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="success output",
            stderr=""
        )
        
        result = self.git.run_command(["git", "status"])
        
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "success output")
        self.assertEqual(result.stderr, "")
        self.assertTrue(result.success)
        
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_run_command_failure_with_check(self, mock_run):
        """Test command failure with check=True."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="command failed"
        )
        
        with self.assertRaises(GitError) as context:
            self.git.run_command(["git", "invalid"], check=True)
            
        self.assertIn("command failed", str(context.exception))
    
    @patch('subprocess.run')
    def test_run_command_failure_without_check(self, mock_run):
        """Test command failure with check=False."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="command failed"
        )
        
        result = self.git.run_command(["git", "invalid"], check=False)
        
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "command failed")
        self.assertFalse(result.success)
    
    def test_is_git_repository(self):
        """Test is_git_repository method."""
        # Mock successful git rev-parse
        with patch.object(self.git, 'run_command') as mock_run:
            mock_run.return_value = GitCommandResult(0, "/path/to/.git", "")
            
            self.assertTrue(self.git.is_git_repository())
            
            # Test caching
            self.assertTrue(self.git.is_git_repository())
            mock_run.assert_called_once()  # Should only be called once due to caching
    
    def test_ensure_git_repository(self):
        """Test ensure_git_repository method."""
        # Success case
        with patch.object(self.git, 'is_git_repository', return_value=True):
            self.git.ensure_git_repository()  # Should not raise
        
        # Failure case
        with patch.object(self.git, 'is_git_repository', return_value=False):
            with self.assertRaises(NotGitRepositoryError):
                self.git.ensure_git_repository()
    
    def test_get_current_branch(self):
        """Test get_current_branch method."""
        with patch.object(self.git, 'ensure_git_repository'):
            # Normal branch
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(0, "main", "")
                
                branch = self.git.get_current_branch()
                self.assertEqual(branch, "main")
            
            # Detached HEAD
            with patch.object(self.git, 'run_command') as mock_run:
                # First call fails (symbolic-ref)
                # Second call succeeds (rev-parse)
                mock_run.side_effect = [
                    GitCommandResult(1, "", "fatal: ref HEAD is not a symbolic ref"),
                    GitCommandResult(0, "abc123", "")
                ]
                
                branch = self.git.get_current_branch()
                self.assertEqual(branch, "abc123")
    
    def test_get_latest_tag(self):
        """Test get_latest_tag method."""
        with patch.object(self.git, 'ensure_git_repository'):
            # Tag found
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(0, "v1.2.3", "")
                
                tag = self.git.get_latest_tag()
                self.assertEqual(tag, "v1.2.3")
            
            # No tags
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(1, "", "fatal: No tags")
                
                tag = self.git.get_latest_tag()
                self.assertIsNone(tag)
    
    def test_get_all_tags(self):
        """Test get_all_tags method."""
        with patch.object(self.git, 'ensure_git_repository'):
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(0, "v1.0.0\nv1.1.0\nv1.2.0", "")
                
                tags = self.git.get_all_tags()
                self.assertEqual(tags, ["v1.0.0", "v1.1.0", "v1.2.0"])
    
    def test_is_working_directory_clean(self):
        """Test is_working_directory_clean method."""
        with patch.object(self.git, 'ensure_git_repository'):
            # Clean directory
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(0, "", "")
                
                self.assertTrue(self.git.is_working_directory_clean())
            
            # Dirty directory
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(0, "M file.txt", "")
                
                self.assertFalse(self.git.is_working_directory_clean())
    
    def test_get_uncommitted_changes(self):
        """Test get_uncommitted_changes method."""
        with patch.object(self.git, 'ensure_git_repository'):
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(
                    0,
                    "M  staged.txt\n M unstaged.txt\n?? untracked.txt",
                    ""
                )
                
                changes = self.git.get_uncommitted_changes()
                
                self.assertEqual(changes['staged'], ['staged.txt'])
                self.assertEqual(changes['unstaged'], ['unstaged.txt'])
                self.assertEqual(changes['untracked'], ['untracked.txt'])
    
    def test_get_commit_messages(self):
        """Test get_commit_messages method."""
        with patch.object(self.git, 'ensure_git_repository'):
            with patch.object(self.git, 'run_command') as mock_run:
                mock_run.return_value = GitCommandResult(
                    0,
                    "abc123|John Doe|john@example.com|2024-01-01 12:00:00|feat: add feature|Full body",
                    ""
                )
                
                commits = self.git.get_commit_messages()
                
                self.assertEqual(len(commits), 1)
                self.assertEqual(commits[0]['hash'], 'abc123')
                self.assertEqual(commits[0]['author_name'], 'John Doe')
                self.assertEqual(commits[0]['subject'], 'feat: add feature')
    
    def test_get_github_url(self):
        """Test get_github_url method."""
        # SSH URL
        with patch.object(self.git, 'get_remote_url') as mock_get_url:
            mock_get_url.return_value = "git@github.com:owner/repo.git"
            
            url = self.git.get_github_url()
            self.assertEqual(url, "https://github.com/owner/repo")
        
        # HTTPS URL
        with patch.object(self.git, 'get_remote_url') as mock_get_url:
            mock_get_url.return_value = "https://github.com/owner/repo.git"
            
            url = self.git.get_github_url()
            self.assertEqual(url, "https://github.com/owner/repo")
        
        # No remote
        with patch.object(self.git, 'get_remote_url') as mock_get_url:
            mock_get_url.return_value = None
            
            url = self.git.get_github_url()
            self.assertIsNone(url)
    
    def test_create_tag(self):
        """Test create_tag method."""
        with patch.object(self.git, 'ensure_git_repository'):
            with patch.object(self.git, 'tag_exists', return_value=False):
                with patch.object(self.git, 'run_command') as mock_run:
                    mock_run.return_value = GitCommandResult(0, "", "")
                    
                    # Simple tag
                    self.git.create_tag("v1.2.3")
                    mock_run.assert_called_with(["git", "tag", "v1.2.3", "HEAD"])
                    
                    # Annotated tag
                    self.git.create_tag("v1.2.3", message="Release v1.2.3")
                    mock_run.assert_called_with(
                        ["git", "tag", "-a", "v1.2.3", "-m", "Release v1.2.3", "HEAD"]
                    )
    
    def test_create_tag_already_exists(self):
        """Test create_tag when tag already exists."""
        with patch.object(self.git, 'ensure_git_repository'):
            with patch.object(self.git, 'tag_exists', return_value=True):
                with self.assertRaises(GitError) as context:
                    self.git.create_tag("v1.2.3")
                
                self.assertIn("already exists", str(context.exception))


if __name__ == '__main__':
    unittest.main()