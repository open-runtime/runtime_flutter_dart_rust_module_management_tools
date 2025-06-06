#!/usr/bin/env python3
"""
Tests for Click-based changelog_tools.py
"""
import unittest
from unittest.mock import patch, MagicMock, call, mock_open
import sys
from pathlib import Path
from click.testing import CliRunner

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.cli.changelog_tools import cli, ChangelogTools
from tooling.utils.changelog_utils import ChangelogSection, ChangelogEntry, ChangelogVersion


class TestChangelogToolsCLI(unittest.TestCase):
    """Test cases for Click-based changelog tools CLI"""
    
    def setUp(self):
        """Set up test environment"""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help output"""
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Changelog management tools', result.output)
    
    def test_validate_help(self):
        """Test validate command help"""
        result = self.runner.invoke(cli, ['validate', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--fix', result.output)
        self.assertIn('--strict', result.output)
        self.assertIn('--verbose', result.output)
    
    @patch('tooling.cli.changelog_tools.ChangelogTools._find_changelog_files')
    def test_validate_no_files(self, mock_find):
        """Test validate when no files found"""
        mock_find.return_value = []
        
        result = self.runner.invoke(cli, ['validate'])
        self.assertEqual(result.exit_code, 0)
        # Rich output may not be captured, just check exit code
    
    @patch('tooling.cli.changelog_tools.ChangelogValidator.validate_file')
    def test_validate_success(self, mock_validate):
        """Test successful validation"""
        mock_validate.return_value = []  # No errors
        
        with self.runner.isolated_filesystem():
            Path('CHANGELOG.md').touch()
            result = self.runner.invoke(cli, ['validate', 'CHANGELOG.md'])
            self.assertEqual(result.exit_code, 0)
    
    @patch('tooling.cli.changelog_tools.ChangelogValidator.validate_file')
    def test_validate_with_errors(self, mock_validate):
        """Test validation with errors"""
        mock_validate.return_value = ['Error 1', 'Error 2']
        
        with self.runner.isolated_filesystem():
            Path('CHANGELOG.md').touch()
            result = self.runner.invoke(cli, ['validate', 'CHANGELOG.md'])
            self.assertNotEqual(result.exit_code, 0)
    
    def test_sync_help(self):
        """Test sync command help"""
        result = self.runner.invoke(cli, ['sync', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--source', result.output)
        self.assertIn('--target', result.output)
        self.assertIn('--version', result.output)
    
    @patch('tooling.cli.changelog_tools.Path.exists')
    def test_sync_source_not_found(self, mock_exists):
        """Test sync when source file not found"""
        mock_exists.return_value = False
        
        result = self.runner.invoke(cli, ['sync', '--target', '*.md'])
        self.assertNotEqual(result.exit_code, 0)
    
    def test_analyze_help(self):
        """Test analyze command help"""
        result = self.runner.invoke(cli, ['analyze', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--from-tag', result.output)
        self.assertIn('--to-tag', result.output)
        self.assertIn('--format', result.output)
        self.assertIn('--group-by', result.output)
    
    @patch('tooling.cli.changelog_tools.check_git_repo')
    def test_analyze_not_git_repo(self, mock_check):
        """Test analyze when not in git repo"""
        mock_check.return_value = False
        
        result = self.runner.invoke(cli, ['analyze'])
        self.assertNotEqual(result.exit_code, 0)


class TestChangelogToolsUnit(unittest.TestCase):
    """Unit tests for ChangelogTools class"""
    
    def setUp(self):
        """Set up test environment"""
        self.mock_config = MagicMock()
        self.mock_config.get_current_version.return_value = 'v1.0.0'
        self.tools = ChangelogTools(self.mock_config)
    
    def test_find_changelog_files(self):
        """Test finding changelog files"""
        with patch('tooling.cli.changelog_tools.find_files_by_pattern') as mock_find:
            mock_find.side_effect = [
                ['CHANGELOG.md'],
                [],
                ['docs/HISTORY.md'],
                [],
                ['sub/CHANGELOG.md']
            ]
            
            files = self.tools._find_changelog_files()
            
            # Should have called for different patterns
            self.assertEqual(mock_find.call_count, 5)
            # Should return unique files
            self.assertEqual(len(files), 3)
    
    def test_fix_changelog_issues(self):
        """Test fixing changelog issues"""
        content = "## 1.0.0\nSome content"
        expected = "# Changelog\n\n## 1.0.0\nSome content"
        
        with patch('builtins.open', mock_open(read_data=content)) as mock_file:
            fixed = self.tools._fix_changelog_issues('test.md', ['Missing header'])
            
            # Should have written the fixed content
            handle = mock_file()
            handle.write.assert_called_with(expected)
            self.assertGreater(fixed, 0)
    
    def test_group_entries_by_section(self):
        """Test grouping entries by section"""
        entries = [
            ChangelogEntry(text="Feature 1", section=ChangelogSection.ADDED),
            ChangelogEntry(text="Fix 1", section=ChangelogSection.FIXED),
            ChangelogEntry(text="Feature 2", section=ChangelogSection.ADDED),
        ]
        
        grouped = self.tools._group_entries(entries, "section")
        
        self.assertIn(ChangelogSection.ADDED, grouped)
        self.assertIn(ChangelogSection.FIXED, grouped)
        self.assertEqual(len(grouped[ChangelogSection.ADDED]), 2)
        self.assertEqual(len(grouped[ChangelogSection.FIXED]), 1)
    
    def test_group_entries_by_author(self):
        """Test grouping entries by author"""
        entries = [
            ChangelogEntry(text="Change 1", section=ChangelogSection.ADDED, author="alice"),
            ChangelogEntry(text="Change 2", section=ChangelogSection.FIXED, author="bob"),
            ChangelogEntry(text="Change 3", section=ChangelogSection.ADDED, author="alice"),
        ]
        
        grouped = self.tools._group_entries(entries, "author")
        
        self.assertIn("alice", grouped)
        self.assertIn("bob", grouped)
        self.assertEqual(len(grouped["alice"]), 2)
        self.assertEqual(len(grouped["bob"]), 1)
    
    def test_format_entries_markdown(self):
        """Test formatting entries as markdown"""
        grouped = {
            ChangelogSection.ADDED: [
                ChangelogEntry(text="New feature", section=ChangelogSection.ADDED)
            ],
            ChangelogSection.FIXED: [
                ChangelogEntry(text="Bug fix", section=ChangelogSection.FIXED)
            ]
        }
        
        markdown = self.tools._format_entries_markdown(grouped)
        
        self.assertIn("# Changelog Entries", markdown)
        self.assertIn("## Added", markdown)
        self.assertIn("## Fixed", markdown)
        self.assertIn("- New feature", markdown)
        self.assertIn("- Bug fix", markdown)
    
    @patch('subprocess.run')
    def test_get_commits_between_tags(self, mock_run):
        """Test getting commits between tags"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="abc123|John Doe|john@example.com|2024-01-01|feat: new feature|Body text"
        )
        
        commits = self.tools._get_commits_between_tags('v1.0.0', 'v1.1.0')
        
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]['hash'], 'abc123')
        self.assertEqual(commits[0]['author_name'], 'John Doe')
        self.assertEqual(commits[0]['subject'], 'feat: new feature')


if __name__ == '__main__':
    unittest.main() 