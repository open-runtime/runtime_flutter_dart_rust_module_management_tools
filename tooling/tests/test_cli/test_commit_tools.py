#!/usr/bin/env python3
"""
Tests for CLITool-based commit_tools.py
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import argparse

from tooling.cli.commit_tools import CommitTools, CommitMode


class TestCommitToolsCLI:
    """Test cases for commit tools CLI"""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_fdr_project):
        """Set up test environment"""
        self.project_root = mock_fdr_project
        # Mock config to avoid initialization errors
        mock_config = MagicMock()
        mock_config.use_color = True
        mock_config.quiet = False
        mock_config.verbose = False
        mock_config.debug = False
        mock_config.dry_run = False
        mock_config.project_root = self.project_root
        mock_config.development = MagicMock()
        mock_config.development.dry_run = False
        mock_config.development.debug = False
        mock_config.get_table_style.return_value = None
        
        with patch('tooling.cli.cli_tools_base.get_config', return_value=mock_config):
            self.tool = CommitTools()
            self.tool.config = mock_config
    
    def test_tool_properties(self):
        """Test tool properties"""
        assert self.tool.name == "commit"
        assert "Generate intelligent commit messages" in self.tool.description
    
    def test_add_arguments(self):
        """Test that arguments are added correctly"""
        parser = argparse.ArgumentParser()
        self.tool.add_arguments(parser)
        
        # Parse with no args to check defaults
        args = parser.parse_args([])
        assert hasattr(args, 'quick')
        assert hasattr(args, 'detailed')
        assert hasattr(args, 'interactive')
        assert hasattr(args, 'no_ai')
        assert hasattr(args, 'conventional')
        assert args.conventional is True  # Default
    
    @patch('tooling.cli.commit_tools.check_git_repo')
    def test_validate_args_not_git_repo(self, mock_check):
        """Test validation when not in git repo"""
        mock_check.return_value = False
        
        # Mock args
        self.tool.args = MagicMock()
        
        result = self.tool.validate_args()
        assert result is False
    
    @patch('tooling.cli.commit_tools.check_git_repo')
    @patch('tooling.cli.commit_tools.get_staged_files')
    def test_validate_args_no_staged_files(self, mock_files, mock_check):
        """Test validation when no files staged"""
        mock_check.return_value = True
        mock_files.return_value = []
        
        # Mock args
        self.tool.args = MagicMock()
        
        result = self.tool.validate_args()
        assert result is False
    
    @patch('tooling.cli.commit_tools.check_git_repo')
    @patch('tooling.cli.commit_tools.get_staged_files')
    def test_validate_args_success(self, mock_files, mock_check):
        """Test validation success"""
        mock_check.return_value = True
        mock_files.return_value = ['test.py']
        
        # Mock args
        self.tool.args = MagicMock()
        
        result = self.tool.validate_args()
        assert result is True
    
    @patch('tooling.cli.commit_tools.get_ai_operations')
    @patch('tooling.cli.commit_tools.check_git_repo')
    @patch('tooling.cli.commit_tools.get_staged_files')
    @patch('tooling.cli.commit_tools.get_staged_diff')
    def test_execute_with_template(self, mock_diff, mock_files, mock_check, mock_ai_ops):
        """Test execute with template (no AI)"""
        # Setup mocks
        mock_check.return_value = True
        mock_files.return_value = ['test.py']
        mock_diff.return_value = 'diff content'
        
        # Mock AI operations
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        mock_ai_ops.return_value = mock_ai
        
        # Mock args
        self.tool.args = MagicMock()
        self.tool.args.quick = False
        self.tool.args.detailed = False
        self.tool.args.interactive = False
        self.tool.args.no_ai = True
        self.tool.args.conventional = True
        self.tool.args.type = None
        self.tool.args.emoji = False
        self.tool.args.max_diff_size = 10000
        self.tool.args.auto_commit = False
        
        # Mock config
        self.tool.config = MagicMock()
        self.tool.config.development.dry_run = True
        self.tool.config.development.debug = False
        self.tool.config.get_table_style.return_value = None
        
        # Mock console methods
        self.tool.console = MagicMock()
        self.tool.show_progress = MagicMock(return_value="test: update files")
        
        result = self.tool.execute()
        assert result == 0
    
    @patch('tooling.cli.commit_tools.get_ai_operations')
    @patch('tooling.cli.commit_tools.check_git_repo')
    @patch('tooling.cli.commit_tools.get_staged_files')
    @patch('tooling.cli.commit_tools.get_staged_diff')
    @patch('tooling.cli.commit_tools.get_diff_for_files')
    def test_quick_mode(self, mock_diff_for_files, mock_diff, mock_files, mock_check, mock_ai_ops):
        """Test quick mode"""
        mock_check.return_value = True
        mock_files.return_value = ['file1.py', 'file2.py', 'file3.py', 'file4.py', 'file5.py', 'file6.py']
        mock_diff.return_value = 'diff content'
        mock_diff_for_files.return_value = 'diff content for files'
        
        # Mock AI operations
        mock_ai = MagicMock()
        mock_ai.is_available.return_value = False
        mock_ai_ops.return_value = mock_ai
        
        # Mock args
        self.tool.args = MagicMock()
        self.tool.args.quick = True
        self.tool.args.detailed = False
        self.tool.args.interactive = False
        self.tool.args.no_ai = True
        self.tool.args.conventional = True
        self.tool.args.type = None
        self.tool.args.emoji = False
        self.tool.args.max_diff_size = 10000
        self.tool.args.auto_commit = False
        
        # Mock config
        self.tool.config = MagicMock()
        self.tool.config.development.dry_run = True
        self.tool.config.development.debug = False
        self.tool.config.get_table_style.return_value = None
        
        # Mock console methods
        self.tool.console = MagicMock()
        self.tool.show_progress = MagicMock(return_value="test: quick update")
        
        result = self.tool.execute()
        assert result == 0
        
        # Verify quick mode was used (only first 5 files)
        mock_diff_for_files.assert_called_once()
        args = mock_diff_for_files.call_args[0][0]
        assert len(args) == 5  # Quick mode samples 5 files


class TestCommitToolsUnit:
    """Unit tests for CommitTools class"""
    
    @pytest.fixture(autouse=True)
    def setup(self, mock_fdr_project):
        """Set up test environment"""
        self.project_root = mock_fdr_project
        self.mock_config = MagicMock()
        self.mock_config.get_api_key.return_value = "test-key"
        self.mock_config.project_root = self.project_root
        self.mock_config.dry_run = False
        self.mock_config.debug = False
        self.mock_config.verbose = False
        self.mock_config.development = MagicMock()
        self.mock_config.development.dry_run = False
        self.mock_config.development.debug = False
        with patch('tooling.cli.cli_tools_base.get_config', return_value=self.mock_config):
            self.tools = CommitTools()
            self.tools.config = self.mock_config  # Override the config
            self.tools.console = MagicMock()  # Mock console for output
    
    def test_analyze_file_types(self):
        """Test file type analysis"""
        files = [
            'tooling/cli/test.py',
            'tooling/core/config.py',
            'tooling/utils/helper.py',
            'README.md',
            'other.txt'
        ]
        
        types = self.tools._analyze_file_types(files)
        assert 'cli' in types
        assert 'core' in types
        assert 'utils' in types
        assert 'docs' in types
        assert 'other' in types
    
    def test_guess_change_type(self):
        """Test change type guessing"""
        test_cases = [
            ('def test_something():', 'test'),
            ('# README update', 'docs'),
            ('fix: resolve bug', 'fix'),
            ('class NewFeature:', 'feat'),
            ('update config', 'chore')
        ]
        
        for diff, expected in test_cases:
            result = self.tools._guess_change_type(diff)
            assert result == expected
    
    def test_build_conventional_message(self):
        """Test conventional commit formatting"""
        # Test basic formatting
        msg = self.tools._build_conventional_message(
            commit_type="feat",
            scope="cli",
            breaking=False,
            description="Add new feature",
            body=""
        )
        assert msg == "feat(cli): Add new feature"
        
        # Test breaking change
        msg = self.tools._build_conventional_message(
            commit_type="feat",
            scope=None,
            breaking=True,
            description="Breaking change",
            body=""
        )
        assert msg == "feat!: Breaking change\n\nBREAKING CHANGE: This commit contains breaking changes."
        
        # Test with scope and breaking
        msg = self.tools._build_conventional_message(
            commit_type="feat",
            scope="core",
            breaking=True,
            description="Breaking change with scope",
            body=""
        )
        assert msg == "feat(core)!: Breaking change with scope\n\nBREAKING CHANGE: This commit contains breaking changes."
        
        # Test with body
        msg = self.tools._build_conventional_message(
            commit_type="docs",
            scope=None,
            breaking=False,
            description="Summary",
            body="Body text"
        )
        assert msg == "docs: Summary\n\nBody text"
    
    def test_generate_template_message(self):
        """Test template message generation"""
        files = ['tooling/cli/test.py']
        diffs = 'def new_function():\n    pass'
        
        # Mock args since the method expects them
        self.tools.args = MagicMock()
        self.tools.args.conventional = True
        
        message = self.tools._generate_template_message(files, diffs)
        assert 'cli' in message
        assert 'test.py' in message
        assert 'Changes:' in message
    
    def test_add_emoji(self):
        """Test emoji addition to commit messages"""
        # Test various commit types
        test_cases = [
            ("feat: new feature", "feat ✨: new feature"),
            ("fix: bug fix", "fix 🐛: bug fix"),
            ("docs: update readme", "docs 📚: update readme"),
            ("feat(cli): new command", "feat ✨(cli): new command"),
            ("feat!: breaking change", "feat ✨!: breaking change"),
        ]
        
        for input_msg, expected in test_cases:
            result = self.tools._add_emoji(input_msg)
            assert result == expected
    
    def test_get_file_type(self):
        """Test file type categorization"""
        test_cases = [
            ('tooling/cli/test.py', 'cli'),
            ('tooling/core/config.py', 'core'),
            ('tooling/utils/helper.py', 'utils'),
            ('tooling/tests/test_example.py', 'tests'),
            ('README.md', 'docs'),
            ('.gitignore', 'config'),
            ('random_file.txt', 'other'),
        ]
        
        for file_path, expected_type in test_cases:
            result = self.tools._get_file_type(file_path)
            assert result == expected_type 