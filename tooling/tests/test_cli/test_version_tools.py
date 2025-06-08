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
    
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_get_patch_tag_exception(self, mock_check):
        """Test get_patch_tag exception handling"""
        mock_check.side_effect = Exception("Test error")
        
        result = self.tools.get_patch_tag('v', False)
        self.assertEqual(result, 1)
    
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
    
    @patch('tooling.cli.version_tools.get_version_from_file')
    def test_update_version_no_version_found(self, mock_get):
        """Test update when no version found in file"""
        mock_get.return_value = None
        
        result = self.tools.update_version(
            None, False, False, True, ['test.txt'], False
        )
        # Returns 1 when there are errors
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.get_version_from_file')
    def test_update_version_file_error(self, mock_get):
        """Test update with file read error"""
        mock_get.side_effect = Exception("Read error")
        
        result = self.tools.update_version(
            None, False, False, True, ['test.txt'], False
        )
        # Returns 1 when there are errors
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.console')
    def test_update_version_general_exception(self, mock_console):
        """Test update_version with general exception"""
        # Force an exception by not providing required arguments
        result = self.tools.update_version(
            None, True, True, True, ['test.txt'], False  # Multiple flags
        )
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_prepare_patch_not_git_repo(self, mock_check):
        """Test prepare_patch when not in git repo"""
        mock_check.return_value = False
        
        result = self.tools.prepare_patch('v', None, False, False)
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.get_commit_messages_since_tag')
    @patch('tooling.cli.version_tools.get_latest_tag')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_prepare_patch_many_commits(self, mock_check, mock_tag, mock_commits):
        """Test prepare_patch with many commits"""
        mock_check.return_value = True
        mock_tag.return_value = 'v1.0.0'
        # Create more than 10 commits to test truncation
        mock_commits.return_value = [f'commit {i}' for i in range(15)]
        
        result = self.tools.prepare_patch('v', None, False, True)  # dry run
        self.assertEqual(result, 0)
    
    @patch('tooling.cli.version_tools.push_tag')
    @patch('tooling.cli.version_tools.create_tag')
    @patch('tooling.cli.version_tools.Confirm')
    @patch('tooling.cli.version_tools.get_commit_messages_since_tag')
    @patch('tooling.cli.version_tools.get_latest_tag')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_prepare_patch_create_and_push(self, mock_check, mock_tag, mock_commits,
                                          mock_confirm, mock_create, mock_push):
        """Test prepare_patch creating and pushing tag"""
        mock_check.return_value = True
        mock_tag.return_value = 'v1.0.0'
        mock_commits.return_value = ['fix: bug']
        mock_confirm.ask.return_value = True
        
        result = self.tools.prepare_patch('v', 'Custom message', True, False)
        self.assertEqual(result, 0)
        mock_create.assert_called_once()
        mock_push.assert_called_once()
    
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_prepare_patch_exception(self, mock_check):
        """Test prepare_patch exception handling"""
        mock_check.side_effect = Exception("Test error")
        
        result = self.tools.prepare_patch('v', None, False, False)
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_not_git_repo(self, mock_check):
        """Test push_patch when not in git repo"""
        mock_check.return_value = False
        
        result = self.tools.push_patch(None, 'v', False, False)
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.get_latest_tag')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_no_tag(self, mock_check, mock_tag):
        """Test push_patch with no tag specified or found"""
        mock_check.return_value = True
        mock_tag.return_value = None
        
        result = self.tools.push_patch(None, 'v', False, False)
        self.assertEqual(result, 1)
    
    @patch('subprocess.run')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_tag_not_exists(self, mock_check, mock_run):
        """Test push_patch when tag doesn't exist locally"""
        mock_check.return_value = True
        # Empty stdout means tag doesn't exist
        mock_run.return_value = MagicMock(stdout='', returncode=0)
        
        result = self.tools.push_patch('v1.0.0', 'v', False, False)
        self.assertEqual(result, 1)
    
    @patch('subprocess.run')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_success(self, mock_check, mock_run):
        """Test successful push_patch"""
        mock_check.return_value = True
        # First call checks tag exists, second pushes
        mock_run.side_effect = [
            MagicMock(stdout='v1.0.0\n', returncode=0),
            MagicMock(stdout='', stderr='', returncode=0)
        ]
        
        result = self.tools.push_patch('v1.0.0', 'v', False, False)
        self.assertEqual(result, 0)
        self.assertEqual(mock_run.call_count, 2)
    
    @patch('subprocess.run')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_force(self, mock_check, mock_run):
        """Test push_patch with force flag"""
        mock_check.return_value = True
        mock_run.side_effect = [
            MagicMock(stdout='v1.0.0\n', returncode=0),
            MagicMock(stdout='', stderr='', returncode=0)
        ]
        
        result = self.tools.push_patch('v1.0.0', 'v', True, False)
        self.assertEqual(result, 0)
        # Check that --force was in the command
        push_call = mock_run.call_args_list[1]
        self.assertIn('--force', push_call[0][0])
    
    @patch('subprocess.run')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_failed(self, mock_check, mock_run):
        """Test push_patch when push fails"""
        mock_check.return_value = True
        mock_run.side_effect = [
            MagicMock(stdout='v1.0.0\n', returncode=0),
            MagicMock(stdout='', stderr='Push failed', returncode=1)
        ]
        
        result = self.tools.push_patch('v1.0.0', 'v', False, False)
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_exception(self, mock_check):
        """Test push_patch exception handling"""
        mock_check.side_effect = Exception("Test error")
        
        result = self.tools.push_patch('v1.0.0', 'v', False, False)
        self.assertEqual(result, 1)
    
    @patch('tooling.cli.version_tools.update_version_in_file')
    @patch('tooling.cli.version_tools.get_version_from_file')
    def test_update_version_dry_run(self, mock_get, mock_update):
        """Test update_version in dry run mode"""
        mock_get.return_value = '1.0.0'
        
        result = self.tools.update_version(
            '2.0.0', False, False, False, ['test.txt'], True
        )
        self.assertEqual(result, 0)
        # Should not update in dry run
        mock_update.assert_not_called()
    
    def test_update_version_no_flags(self):
        """Test update_version with no version specification"""
        result = self.tools.update_version(
            None, False, False, False, ['test.txt'], False
        )
        self.assertEqual(result, 1)
    
    @patch('subprocess.run')
    @patch('tooling.cli.version_tools.check_git_repo')
    def test_push_patch_dry_run(self, mock_check, mock_run):
        """Test push_patch in dry run mode"""
        mock_check.return_value = True
        mock_run.return_value = MagicMock(stdout='v1.0.0\n', returncode=0)
        
        result = self.tools.push_patch('v1.0.0', 'v', False, True)
        self.assertEqual(result, 0)
        # Should only check tag exists, not push
        self.assertEqual(mock_run.call_count, 1)


def test_main():
    """Test main entry point"""
    from tooling.cli.version_tools import main
    
    with patch('tooling.cli.version_tools.cli') as mock_cli:
        main()
        mock_cli.assert_called_once()


if __name__ == '__main__':
    unittest.main() 