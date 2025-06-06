#!/usr/bin/env python3
"""
Tests for Click-based pr_tools.py
"""
import unittest
from unittest.mock import patch, MagicMock, call
import sys
from pathlib import Path
from click.testing import CliRunner

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.cli.pr_tools import cli, PRTools


class TestPRToolsCLI(unittest.TestCase):
    """Test cases for Click-based PR tools CLI"""
    
    def setUp(self):
        """Set up test environment"""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help output"""
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Pull request management tools', result.output)
    
    def test_create_help(self):
        """Test create command help"""
        result = self.runner.invoke(cli, ['create', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--title', result.output)
        self.assertIn('--body', result.output)
        self.assertIn('--draft', result.output)
    
    @patch('tooling.cli.pr_tools.check_git_repo')
    def test_create_not_git_repo(self, mock_check):
        """Test create when not in git repo"""
        mock_check.return_value = False
        
        result = self.runner.invoke(cli, ['create'])
        self.assertNotEqual(result.exit_code, 0)
    
    @patch('tooling.cli.pr_tools.check_git_repo')
    @patch('tooling.cli.pr_tools.get_current_branch')
    def test_create_same_branch(self, mock_branch, mock_check):
        """Test create when current branch equals base"""
        mock_check.return_value = True
        mock_branch.return_value = 'main'
        
        result = self.runner.invoke(cli, ['create', '--base', 'main'])
        self.assertNotEqual(result.exit_code, 0)
    
    def test_list_help(self):
        """Test list command help"""
        result = self.runner.invoke(cli, ['list', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--state', result.output)
        self.assertIn('--author', result.output)
        self.assertIn('--format', result.output)
    
    @patch('tooling.cli.pr_tools.get_remote_url')
    def test_list_no_remote(self, mock_remote):
        """Test list when no remote found"""
        mock_remote.return_value = None
        
        result = self.runner.invoke(cli, ['list'])
        self.assertNotEqual(result.exit_code, 0)
    
    def test_open_help(self):
        """Test open command help"""
        result = self.runner.invoke(cli, ['open', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--web', result.output)
        self.assertIn('PR_NUMBER', result.output)


class TestPRToolsUnit(unittest.TestCase):
    """Unit tests for PRTools class"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_config = MagicMock()
        self.tools = PRTools(self.mock_config)
    
    def test_parse_remote_url_https(self):
        """Test parsing HTTPS GitHub URL"""
        url = "https://github.com/owner/repo.git"
        result = self.tools._parse_remote_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['owner'], 'owner')
        self.assertEqual(result['repo'], 'repo')
    
    def test_parse_remote_url_ssh(self):
        """Test parsing SSH GitHub URL"""
        url = "git@github.com:owner/repo.git"
        result = self.tools._parse_remote_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['owner'], 'owner')
        self.assertEqual(result['repo'], 'repo')
    
    def test_parse_remote_url_invalid(self):
        """Test parsing invalid URL"""
        url = "not-a-github-url"
        result = self.tools._parse_remote_url(url)
        
        self.assertIsNone(result)
    
    def test_generate_default_body(self):
        """Test generating default PR body"""
        commits = ["feat: add feature", "fix: fix bug"]
        files = ["src/main.py", "src/utils.py", "tests/test_main.py"]
        
        body = self.tools._generate_default_body(commits, files)
        
        self.assertIn("## Summary", body)
        self.assertIn("## Changes", body)
        self.assertIn("### Commits (2)", body)
        self.assertIn("feat: add feature", body)
        self.assertIn("### Files Changed (3)", body)
        self.assertIn("## Checklist", body)
    
    def test_generate_default_body_many_commits(self):
        """Test generating body with many commits"""
        commits = [f"commit {i}" for i in range(20)]
        files = []
        
        body = self.tools._generate_default_body(commits, files)
        
        self.assertIn("### Commits (20)", body)
        self.assertIn("commit 0", body)
        self.assertIn("commit 9", body)
        self.assertNotIn("commit 10", body)  # Should be truncated
        self.assertIn("... and 10 more", body)
    
    @patch('tooling.cli.pr_tools.shutil.which')
    @patch('subprocess.run')
    def test_fetch_prs_github_success(self, mock_run, mock_which):
        """Test fetching PRs with GitHub CLI"""
        mock_which.return_value = '/usr/bin/gh'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"number": 1, "title": "Test PR"}]'
        )
        
        repo_info = {'owner': 'test', 'repo': 'repo'}
        prs = self.tools._fetch_prs_github(repo_info, 'open', None, None, None, 10)
        
        self.assertEqual(len(prs), 1)
        self.assertEqual(prs[0]['number'], 1)
        self.assertEqual(prs[0]['title'], 'Test PR')
    
    @patch('tooling.cli.pr_tools.shutil.which')
    def test_fetch_prs_no_gh_cli(self, mock_which):
        """Test fetching PRs without GitHub CLI"""
        mock_which.return_value = None
        
        repo_info = {'owner': 'test', 'repo': 'repo'}
        prs = self.tools._fetch_prs_github(repo_info, 'open', None, None, None, 10)
        
        self.assertEqual(prs, [])
    
    @patch('tooling.cli.pr_tools.shutil.which')
    @patch('subprocess.run')
    def test_create_pr_github_success(self, mock_run, mock_which):
        """Test creating PR with GitHub CLI"""
        mock_which.return_value = '/usr/bin/gh'
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='https://github.com/owner/repo/pull/123'
        )
        
        repo_info = {'owner': 'test', 'repo': 'repo'}
        result = self.tools._create_pr_github(
            repo_info, 'feature', 'main', 'Test PR', 'Body',
            False, [], [], []
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result['url'], 'https://github.com/owner/repo/pull/123')
        self.assertEqual(result['number'], '123')


if __name__ == '__main__':
    unittest.main() 