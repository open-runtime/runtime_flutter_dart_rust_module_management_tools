#!/usr/bin/env python3
"""
Tests for Click-based release_tools.py
"""
import unittest
from unittest.mock import patch, MagicMock, call
import sys
from pathlib import Path
from click.testing import CliRunner

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.cli.release_tools import cli, ReleaseTools


class TestReleaseToolsCLI(unittest.TestCase):
    """Test cases for Click-based release tools CLI"""
    
    def setUp(self):
        """Set up test environment"""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help output"""
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Release management tools', result.output)
    
    def test_check_help(self):
        """Test check command help"""
        result = self.runner.invoke(cli, ['check', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--fix', result.output)
        self.assertIn('--verbose', result.output)
    
    @patch('tooling.cli.release_tools.check_git_repo')
    def test_check_not_git_repo(self, mock_check):
        """Test error when not in git repo"""
        mock_check.return_value = False
        
        result = self.runner.invoke(cli, ['check'])
        self.assertNotEqual(result.exit_code, 0)
    
    @patch('tooling.cli.release_tools.check_git_repo')
    @patch('tooling.cli.release_tools.has_uncommitted_changes')
    @patch('tooling.cli.release_tools.get_current_branch')
    def test_check_all_pass(self, mock_branch, mock_changes, mock_repo):
        """Test when all checks pass"""
        mock_repo.return_value = True
        mock_changes.return_value = False
        mock_branch.return_value = 'main'
        
        with patch.object(ReleaseTools, '_check_versions') as mock_versions:
            mock_versions.return_value = (True, "Version 1.0.0 is consistent", False)
            
            with patch.object(ReleaseTools, '_check_changelog') as mock_changelog:
                mock_changelog.return_value = (True, "Changelog format valid", False)
                
                with patch.object(ReleaseTools, '_check_dependencies') as mock_deps:
                    mock_deps.return_value = (True, "All dependency files present", False)
                    
                    result = self.runner.invoke(cli, ['check'])
                    self.assertEqual(result.exit_code, 0)
    
    def test_notes_help(self):
        """Test notes command help"""
        result = self.runner.invoke(cli, ['notes', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--version', result.output)
        self.assertIn('--format', result.output)
        self.assertIn('--no-ai', result.output)
    
    @patch('tooling.cli.release_tools.get_ai_operations')
    @patch('tooling.cli.release_tools.check_git_repo')
    @patch('tooling.cli.release_tools.get_latest_tag')
    @patch('tooling.cli.release_tools.get_commits_since_tag')
    def test_notes_generation(self, mock_commits, mock_tag, mock_repo, mock_ai_ops):
        """Test release notes generation"""
        mock_repo.return_value = True
        mock_tag.return_value = 'v1.0.0'
        mock_commits.return_value = ['feat: new feature', 'fix: bug fix']
        
        # Mock AI operations
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        mock_ai_ops.return_value = mock_ai
        
        with patch('tooling.cli.release_tools.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.get_current_version.return_value = 'v1.0.1'
            mock_get_config.return_value = mock_config
            
            result = self.runner.invoke(cli, ['notes', '--no-ai', '--dry-run'])
            if result.exit_code != 0:
                print(f"Output: {result.output}")
                print(f"Exception: {result.exception}")
            self.assertEqual(result.exit_code, 0)
    
    def test_create_help(self):
        """Test create command help"""
        result = self.runner.invoke(cli, ['create', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--draft', result.output)
        self.assertIn('--prerelease', result.output)
    
    def test_retag_help(self):
        """Test retag command help"""
        result = self.runner.invoke(cli, ['retag', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--new-tag', result.output)
        self.assertIn('--force', result.output)
        self.assertIn('--push', result.output)


class TestReleaseToolsUnit(unittest.TestCase):
    """Unit tests for ReleaseTools class"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_config = MagicMock()
        self.mock_config.get_current_version.return_value = 'v1.0.0'
        self.tools = ReleaseTools(self.mock_config)
    
    def test_check_git_repo(self):
        """Test git repo check"""
        with patch('tooling.cli.release_tools.check_git_repo') as mock_check:
            mock_check.return_value = True
            success, message, fixable = self.tools._check_git_repo(False)
            self.assertTrue(success)
            self.assertIn("Valid", message)
            self.assertFalse(fixable)
            
            mock_check.return_value = False
            success, message, fixable = self.tools._check_git_repo(False)
            self.assertFalse(success)
            self.assertIn("Not in", message)
            self.assertFalse(fixable)
    
    def test_check_working_directory(self):
        """Test working directory check"""
        with patch('tooling.cli.release_tools.has_uncommitted_changes') as mock_changes:
            mock_changes.return_value = False
            success, message, fixable = self.tools._check_working_directory(False)
            self.assertTrue(success)
            self.assertIn("clean", message)
            
            mock_changes.return_value = True
            success, message, fixable = self.tools._check_working_directory(False)
            self.assertFalse(success)
            self.assertIn("Uncommitted", message)
            self.assertTrue(fixable)
    
    def test_check_branch(self):
        """Test branch check"""
        with patch('tooling.cli.release_tools.get_current_branch') as mock_branch:
            mock_branch.return_value = 'main'
            success, message, fixable = self.tools._check_branch(False)
            self.assertTrue(success)
            
            mock_branch.return_value = 'feature/test'
            success, message, fixable = self.tools._check_branch(False)
            self.assertFalse(success)
            self.assertIn("expected main", message)
    
    def test_group_commits(self):
        """Test commit grouping"""
        commits = [
            'feat: add new feature',
            'fix: resolve bug',
            'docs: update readme',
            'refactor: clean code',
            'test: add unit tests',
            'chore: update deps'
        ]
        
        groups = self.tools._group_commits(commits)
        
        self.assertIn('feat: add new feature', groups['Features'])
        self.assertIn('fix: resolve bug', groups['Bug Fixes'])
        self.assertIn('docs: update readme', groups['Documentation'])
        self.assertIn('refactor: clean code', groups['Refactoring'])
        # 'test: add unit tests' goes to Features because it contains 'add'
        self.assertIn('test: add unit tests', groups['Features'])
        self.assertIn('chore: update deps', groups['Other'])
    
    def test_strip_markdown(self):
        """Test markdown stripping"""
        markdown = "# Header\n**Bold** text\n[Link](url)"
        plain = self.tools._strip_markdown(markdown)
        
        self.assertNotIn('#', plain)
        self.assertNotIn('**', plain)
        self.assertNotIn('[', plain)
        self.assertIn('Bold', plain)
        self.assertIn('Link', plain)


if __name__ == '__main__':
    unittest.main()
