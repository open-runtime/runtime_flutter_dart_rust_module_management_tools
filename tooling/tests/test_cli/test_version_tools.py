#!/usr/bin/env python3
"""
Tests for Click-based version_tools.py
"""
import unittest
from unittest.mock import patch, MagicMock, call
import sys
from pathlib import Path
from click.testing import CliRunner

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.cli.version_tools import cli, VersionTools


class TestVersionToolsCLI(unittest.TestCase):
    """Test cases for Click-based version tools CLI"""
    
    def setUp(self):
        """Set up test environment"""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help output"""
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Version management tools', result.output)
    
    def test_get_patch_tag_help(self):
        """Test get-patch-tag command help"""
        result = self.runner.invoke(cli, ['get-patch-tag', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--prefix', result.output)
        self.assertIn('--dry-run', result.output)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_get_patch_tag_not_git_repo(self, mock_check):
        """Test error when not in git repo"""
        mock_check.return_value = False
        
        result = self.runner.invoke(cli, ['get-patch-tag'])
        self.assertNotEqual(result.exit_code, 0)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    @patch('tooling.cli.version_tools.get_latest_tag')
    def test_get_patch_tag_no_tags(self, mock_tag, mock_check):
        """Test when no tags exist"""
        mock_check.return_value = True
        mock_tag.return_value = None
        
        result = self.runner.invoke(cli, ['get-patch-tag', '--dry-run'])
        self.assertEqual(result.exit_code, 0)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    @patch('tooling.cli.version_tools.get_latest_tag')
    def test_get_patch_tag_success(self, mock_tag, mock_check):
        """Test successful patch tag generation"""
        mock_check.return_value = True
        mock_tag.return_value = 'v1.2.3'
        
        result = self.runner.invoke(cli, ['get-patch-tag', '--dry-run'])
        self.assertEqual(result.exit_code, 0)
    
    def test_update_help(self):
        """Test update command help"""
        result = self.runner.invoke(cli, ['update', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--major', result.output)
        self.assertIn('--minor', result.output)
        self.assertIn('--patch', result.output)
    
    def test_update_no_files(self):
        """Test update with no files specified"""
        result = self.runner.invoke(cli, ['update', '--patch'])
        self.assertNotEqual(result.exit_code, 0)
    
    @patch('tooling.cli.version_tools.get_version_from_file')
    @patch('tooling.cli.version_tools.update_version_in_file')
    def test_update_patch_version(self, mock_update, mock_get):
        """Test updating patch version"""
        mock_get.return_value = '1.2.3'
        
        with self.runner.isolated_filesystem():
            Path('test.txt').touch()
            result = self.runner.invoke(cli, ['update', '--patch', 'test.txt'])
            self.assertEqual(result.exit_code, 0)
            mock_update.assert_called_once_with('test.txt', '1.2.4')
    
    @patch('tooling.cli.version_tools.check_git_repo')
    @patch('tooling.cli.version_tools.get_latest_tag')
    @patch('tooling.cli.version_tools.get_commit_messages_since_tag')
    def test_prepare_patch_dry_run(self, mock_commits, mock_tag, mock_check):
        """Test prepare-patch in dry run mode"""
        mock_check.return_value = True
        mock_tag.return_value = 'v1.2.3'
        mock_commits.return_value = ['fix: bug fix', 'feat: new feature']
        
        result = self.runner.invoke(cli, ['prepare-patch', '--dry-run'])
        self.assertEqual(result.exit_code, 0)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    @patch('tooling.cli.version_tools.get_latest_tag')
    @patch('subprocess.run')
    def test_push_patch_tag_not_exist(self, mock_run, mock_tag, mock_check):
        """Test push-patch when tag doesn't exist"""
        mock_check.return_value = True
        mock_tag.return_value = 'v1.2.3'
        mock_run.return_value = MagicMock(stdout='', returncode=0)
        
        result = self.runner.invoke(cli, ['push-patch', '--tag', 'v1.2.4'])
        self.assertNotEqual(result.exit_code, 0)


class TestVersionToolsUnit(unittest.TestCase):
    """Unit tests for VersionTools class"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_config = MagicMock()
        self.tools = VersionTools(self.mock_config)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    @patch('tooling.cli.version_tools.get_latest_tag')
    def test_get_patch_tag_logic(self, mock_tag, mock_check):
        """Test patch tag calculation logic"""
        mock_check.return_value = True
        mock_tag.return_value = 'v1.2.3'
        
        # Capture print output
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            result = self.tools.get_patch_tag('v', False)
        
        output = f.getvalue().strip()
        self.assertEqual(result, 0)
        self.assertIn('v1.2.4', output)
    
    @patch('tooling.cli.version_tools.get_version_from_file')
    @patch('tooling.cli.version_tools.update_version_in_file')
    def test_update_version_logic(self, mock_update, mock_get):
        """Test version update logic"""
        mock_get.return_value = '1.0.0'
        
        # Test major update
        result = self.tools.update_version(
            None, True, False, False, ['test.txt'], False
        )
        self.assertEqual(result, 0)
        mock_update.assert_called_with('test.txt', '2.0.0')
        
        # Test minor update
        mock_update.reset_mock()
        result = self.tools.update_version(
            None, False, True, False, ['test.txt'], False
        )
        self.assertEqual(result, 0)
        mock_update.assert_called_with('test.txt', '1.1.0')
        
        # Test specific version
        mock_update.reset_mock()
        result = self.tools.update_version(
            '3.0.0', False, False, False, ['test.txt'], False
        )
        self.assertEqual(result, 0)
        mock_update.assert_called_with('test.txt', '3.0.0')
    
    def test_update_version_multiple_flags(self):
        """Test error when multiple version flags specified"""
        result = self.tools.update_version(
            '1.0.0', True, False, False, ['test.txt'], False
        )
        self.assertNotEqual(result, 0)


if __name__ == '__main__':
    unittest.main() 