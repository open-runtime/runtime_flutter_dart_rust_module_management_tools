"""Tests for git_operations module"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path

from tooling.core.git_operations import GitOperations, Commit


class TestGitOperations(unittest.TestCase):
    """Test GitOperations class"""
    
    def test_commit_dataclass(self):
        """Test Commit dataclass properties"""
        commit = Commit(
            hash="abc123",
            short_hash="abc",
            message="feat(core): add new feature",
            author="Test User",
            author_email="test@example.com",
            date=datetime.now(),
            files=["file1.py", "file2.py"],
            pr_number=42
        )
        
        self.assertEqual(commit.conventional_type, "feat")
        self.assertEqual(commit.scope, "core")
        self.assertEqual(commit.pr_number, 42)
    
    def test_commit_without_conventional_format(self):
        """Test Commit without conventional format"""
        commit = Commit(
            hash="def456",
            short_hash="def",
            message="Regular commit message",
            author="Test User",
            author_email="test@example.com",
            date=datetime.now(),
            files=[]
        )
        
        self.assertIsNone(commit.conventional_type)
        self.assertIsNone(commit.scope)
    
    @patch('subprocess.run')
    def test_get_commits_since_tag(self, mock_run):
        """Test getting commits since a tag"""
        # Mock git log output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123|abc|feat: test commit|Test User|test@example.com|2024-01-01T12:00:00+00:00\n"
        )
        
        commits = GitOperations.get_commits_since_tag("v1.0.0")
        
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0].hash, "abc123")
        self.assertEqual(commits[0].message, "feat: test commit")
        self.assertEqual(commits[0].author, "Test User")
    
    @patch('subprocess.run')
    def test_get_commits_since_tag_with_path(self, mock_run):
        """Test getting commits since a tag for specific path"""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        
        GitOperations.get_commits_since_tag("v1.0.0", "src/")
        
        # Check that path was added to command
        call_args = mock_run.call_args[0][0]
        self.assertIn('--', call_args)
        self.assertIn('src/', call_args)
    
    @patch('subprocess.run')
    def test_create_commit_with_message(self, mock_run):
        """Test creating a commit"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = GitOperations.create_commit_with_message("test: commit message")
        
        self.assertTrue(result)
        # Should have called git add and git commit
        self.assertEqual(mock_run.call_count, 2)
    
    @patch('subprocess.run')
    def test_create_commit_failure(self, mock_run):
        """Test commit creation failure"""
        # First call succeeds (git add), second fails (git commit)
        mock_run.side_effect = [
            MagicMock(returncode=0),
            MagicMock(returncode=1, stderr="error")
        ]
        
        result = GitOperations.create_commit_with_message("test: commit message")
        
        self.assertFalse(result)
    
    @patch('subprocess.run')
    def test_get_changed_files(self, mock_run):
        """Test getting changed files"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="M  file1.py\nA  file2.py\nD  file3.py\n"
        )
        
        files = GitOperations.get_changed_files()
        
        self.assertEqual(len(files), 3)
        self.assertEqual(files[0], Path("file1.py"))
        self.assertEqual(files[1], Path("file2.py"))
        self.assertEqual(files[2], Path("file3.py"))
    
    @patch('subprocess.run')
    def test_get_changed_files_staged_only(self, mock_run):
        """Test getting staged files only"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="file1.py\nfile2.py\n"
        )
        
        files = GitOperations.get_changed_files(staged_only=True)
        
        self.assertEqual(len(files), 2)
        call_args = mock_run.call_args[0][0]
        self.assertIn('--cached', call_args)
    
    @patch('subprocess.run')
    def test_get_last_tag(self, mock_run):
        """Test getting the last tag"""
        mock_run.return_value = MagicMock(returncode=0, stdout="v1.2.3\n")
        
        tag = GitOperations.get_last_tag()
        
        self.assertEqual(tag, "v1.2.3")
    
    @patch('subprocess.run')
    def test_get_last_tag_no_tags(self, mock_run):
        """Test getting last tag when no tags exist"""
        mock_run.return_value = MagicMock(returncode=1)
        
        tag = GitOperations.get_last_tag()
        
        self.assertIsNone(tag)
    
    @patch('subprocess.run')
    def test_push_to_remote(self, mock_run):
        """Test pushing to remote"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = GitOperations.push_to_remote("main", tags=True)
        
        self.assertTrue(result)
        call_args = mock_run.call_args[0][0]
        self.assertIn('main', call_args)
        self.assertIn('--tags', call_args)
    
    @patch('subprocess.run')
    def test_create_tag(self, mock_run):
        """Test creating a tag"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = GitOperations.create_tag("v1.0.0", "Release version 1.0.0")
        
        self.assertTrue(result)
        call_args = mock_run.call_args[0][0]
        self.assertIn('-a', call_args)
        self.assertIn('v1.0.0', call_args)
        self.assertIn('-m', call_args)
    
    @patch('subprocess.run')
    def test_get_commit_count_between(self, mock_run):
        """Test getting commit count between refs"""
        mock_run.return_value = MagicMock(returncode=0, stdout="42\n")
        
        count = GitOperations.get_commit_count_between("v1.0.0", "v2.0.0")
        
        self.assertEqual(count, 42)
    
    @patch('subprocess.run')
    def test_is_ancestor(self, mock_run):
        """Test checking if one commit is ancestor of another"""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = GitOperations.is_ancestor("abc123", "def456")
        
        self.assertTrue(result)
        call_args = mock_run.call_args[0][0]
        self.assertIn('--is-ancestor', call_args)
    
    @patch('subprocess.run')
    def test_stash_operations(self, mock_run):
        """Test stash and stash pop"""
        mock_run.return_value = MagicMock(returncode=0)
        
        # Test stash
        result = GitOperations.stash_changes("WIP changes")
        self.assertTrue(result)
        
        # Test stash pop
        result = GitOperations.stash_pop()
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main() 