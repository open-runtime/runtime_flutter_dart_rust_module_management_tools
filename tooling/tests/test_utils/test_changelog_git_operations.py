"""
Tests for changelog git operations
"""
import pytest
from unittest.mock import patch, Mock, MagicMock
import subprocess
from pathlib import Path

from tooling.utils.changelog.git_operations import ChangelogGitOps
from tooling.core.models import GitCommit


class TestChangelogGitOps:
    """Test ChangelogGitOps class"""
    
    @patch('subprocess.run')
    def test_get_commits_between_success(self, mock_run):
        """Test successful get_commits_between"""
        # Mock git log output
        mock_output = """abc123
abc
John Doe
john@example.com
2025-06-07
10:30AM EST
feat: Add new feature (#123)

This is a longer description
of the commit

file1.py
file2.py
--END--
def456
def
Jane Smith
jane@example.com
2025-06-06
02:15PM PST
fix: Fix bug

bug.py
--END--
"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=mock_output,
            stderr=""
        )
        
        commits = ChangelogGitOps.get_commits_between("v1.0.0", "HEAD")
        
        assert len(commits) == 2
        
        # Check first commit
        assert commits[0].hash == "abc123"
        assert commits[0].short_hash == "abc"
        assert commits[0].author_name == "John Doe"
        assert commits[0].author_email == "john@example.com"
        assert commits[0].commit_date == "2025-06-07"
        assert commits[0].commit_time == "10:30AM EST"
        assert commits[0].message == "feat: Add new feature (#123)"
        assert commits[0].pr_number == 123
        # Files should include the actual files, not description lines
        assert "file1.py" in commits[0].files
        assert "file2.py" in commits[0].files
        
        # Check second commit
        assert commits[1].hash == "def456"
        assert commits[1].message == "fix: Fix bug"
        assert "bug.py" in commits[1].files
    
    @patch('subprocess.run')
    def test_get_commits_between_with_path_glob(self, mock_run):
        """Test get_commits_between with path filter"""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        ChangelogGitOps.get_commits_between("v1.0.0", "HEAD", "*.py")
        
        # Check command includes path glob
        cmd = mock_run.call_args[0][0]
        assert '--' in cmd
        assert '*.py' in cmd
    
    @patch('subprocess.run')
    def test_get_commits_between_no_start_ref(self, mock_run):
        """Test get_commits_between without start ref (all history)"""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        
        ChangelogGitOps.get_commits_between(None, "HEAD")
        
        # Check command doesn't have range
        cmd = mock_run.call_args[0][0]
        assert 'HEAD' in cmd
        assert '..' not in ' '.join(cmd)
    
    @patch('subprocess.run')
    def test_get_commits_between_error(self, mock_run):
        """Test get_commits_between with git error"""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
        
        commits = ChangelogGitOps.get_commits_between("v1.0.0", "HEAD")
        assert commits == []
    
    @patch('subprocess.run')
    def test_get_commits_between_timeout(self, mock_run):
        """Test get_commits_between with timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired(['git'], 30)
        
        commits = ChangelogGitOps.get_commits_between("v1.0.0", "HEAD")
        assert commits == []
    
    def test_parse_git_log_empty(self):
        """Test parsing empty git log"""
        commits = ChangelogGitOps._parse_git_log("")
        assert commits == []
    
    def test_parse_git_log_malformed(self):
        """Test parsing malformed git log"""
        malformed = """abc123
short
--END--
"""
        commits = ChangelogGitOps._parse_git_log(malformed)
        assert commits == []
    
    def test_parse_git_log_no_pr_number(self):
        """Test parsing commit without PR number"""
        log_output = """abc123
abc
John Doe
john@example.com
2025-06-07
10:30AM EST
feat: Add feature without PR

file1.py
--END--
"""
        commits = ChangelogGitOps._parse_git_log(log_output)
        assert len(commits) == 1
        assert commits[0].pr_number is None
    
    @patch('subprocess.run')
    def test_get_remote_url_https(self, mock_run):
        """Test get_remote_url with HTTPS URL"""
        # Clear cache
        ChangelogGitOps.get_remote_url.cache_clear()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="https://github.com/user/repo.git\n",
            stderr=""
        )
        
        url = ChangelogGitOps.get_remote_url()
        assert url == "https://github.com/user/repo"
    
    @patch('subprocess.run')
    def test_get_remote_url_ssh(self, mock_run):
        """Test get_remote_url with SSH URL"""
        # Clear cache
        ChangelogGitOps.get_remote_url.cache_clear()
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout="git@github.com:user/repo.git\n",
            stderr=""
        )
        
        url = ChangelogGitOps.get_remote_url()
        assert url == "https://github.com/user/repo"
    
    @patch('subprocess.run')
    def test_get_remote_url_error(self, mock_run):
        """Test get_remote_url with error"""
        # Clear cache
        ChangelogGitOps.get_remote_url.cache_clear()
        
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
        
        url = ChangelogGitOps.get_remote_url()
        assert url is None
    
    @patch('subprocess.run')
    def test_get_file_at_ref_success(self, mock_run):
        """Test get_file_at_ref success"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="File contents\nLine 2",
            stderr=""
        )
        
        content = ChangelogGitOps.get_file_at_ref("README.md", "v1.0.0")
        assert content == "File contents\nLine 2"
        
        # Check command
        cmd = mock_run.call_args[0][0]
        assert 'git' in cmd
        assert 'show' in cmd
        assert 'v1.0.0:README.md' in cmd
    
    @patch('subprocess.run')
    def test_get_file_at_ref_error(self, mock_run):
        """Test get_file_at_ref with error"""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
        
        content = ChangelogGitOps.get_file_at_ref("README.md")
        assert content is None
    
    @patch('subprocess.run')
    def test_get_diff_for_files_success(self, mock_run):
        """Test get_diff_for_files success"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py b/file.py\n+added line",
            stderr=""
        )
        
        diff = ChangelogGitOps.get_diff_for_files(["file.py"], "v1.0.0", "HEAD")
        assert "diff --git" in diff
        assert "+added line" in diff
    
    @patch('subprocess.run')
    def test_get_diff_for_files_empty_list(self, mock_run):
        """Test get_diff_for_files with empty file list"""
        diff = ChangelogGitOps.get_diff_for_files([], "v1.0.0")
        assert diff == ""
        mock_run.assert_not_called()
    
    @patch('subprocess.run')
    def test_find_last_changelog_commit_found(self, mock_run):
        """Test find_last_changelog_commit when found"""
        # First call returns log output
        mock_run.side_effect = [
            Mock(returncode=0, stdout="abc123 Update changelog\ndef456 Another commit"),
            Mock(returncode=0, stdout="Update changelog\n\nCHANGELOG.md"),  # First commit check
        ]
        
        commit = ChangelogGitOps.find_last_changelog_commit()
        assert commit == "abc123"
    
    @patch('subprocess.run')
    def test_find_last_changelog_commit_not_found(self, mock_run):
        """Test find_last_changelog_commit when not found"""
        mock_run.return_value = Mock(returncode=0, stdout="")
        
        commit = ChangelogGitOps.find_last_changelog_commit()
        assert commit is None
    
    @patch('subprocess.run')
    def test_is_meaningful_changelog_commit_true(self, mock_run):
        """Test _is_meaningful_changelog_commit returns True"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Sync changelog updates\n\nCHANGELOG.md\nREADME.md"
        )
        
        result = ChangelogGitOps._is_meaningful_changelog_commit("abc123")
        assert result is True
    
    @patch('subprocess.run')
    def test_is_meaningful_changelog_commit_automated(self, mock_run):
        """Test _is_meaningful_changelog_commit skips automated commits"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Automated changelog update\n\nCHANGELOG.md"
        )
        
        result = ChangelogGitOps._is_meaningful_changelog_commit("abc123")
        assert result is False
    
    @patch('subprocess.run')
    def test_is_meaningful_changelog_commit_no_changelog_files(self, mock_run):
        """Test _is_meaningful_changelog_commit without changelog files"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Update documentation\n\nREADME.md\ndocs/guide.md"
        )
        
        result = ChangelogGitOps._is_meaningful_changelog_commit("abc123")
        assert result is False 