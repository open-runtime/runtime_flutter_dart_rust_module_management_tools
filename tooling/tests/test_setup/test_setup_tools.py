#!/usr/bin/env python3
"""
Tests for Click-based setup_tools.py
"""
import unittest
from unittest.mock import patch, MagicMock, call
import sys
from pathlib import Path
from click.testing import CliRunner

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.setup.setup_tools import cli, SetupTools


class TestSetupToolsCLI(unittest.TestCase):
    """Test cases for Click-based setup tools CLI"""
    
    def setUp(self):
        """Set up test environment"""
        self.runner = CliRunner()
    
    def test_cli_help(self):
        """Test CLI help output"""
        result = self.runner.invoke(cli, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('Setup and installation tools', result.output)
    
    def test_all_help(self):
        """Test all command help"""
        result = self.runner.invoke(cli, ['all', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--skip-python', result.output)
        self.assertIn('--skip-ai', result.output)
        self.assertIn('--dry-run', result.output)
    
    def test_python_help(self):
        """Test python command help"""
        result = self.runner.invoke(cli, ['python', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--upgrade', result.output)
        self.assertIn('--dry-run', result.output)
    
    def test_ai_help(self):
        """Test ai command help"""
        result = self.runner.invoke(cli, ['ai', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--skip-api-keys', result.output)
    
    def test_permissions_help(self):
        """Test permissions command help"""
        result = self.runner.invoke(cli, ['permissions', '--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('--create-symlinks', result.output)


class TestSetupToolsUnit(unittest.TestCase):
    """Unit tests for SetupTools class"""
    
    def setUp(self):
        """Set up test environment"""
        self.tools = SetupTools()
    
    @patch('tooling.setup.setup_tools.run_command')
    def test_install_python_deps_no_pip(self, mock_run):
        """Test Python deps installation when pip is missing"""
        mock_run.return_value = (1, '', 'pip not found')
        
        result = self.tools.install_python_deps(upgrade=False, dry_run=False)
        
        self.assertEqual(result, 1)
    
    @patch('tooling.setup.setup_tools.run_command')
    @patch('tooling.setup.setup_tools.Path')
    def test_install_python_deps_success(self, mock_path_class, mock_run):
        """Test successful Python deps installation"""
        # Mock pip check
        mock_run.side_effect = [
            (0, 'pip 21.0.0', ''),  # pip --version
            (0, '', ''),  # install requirements.txt
            (0, '', ''),  # install -e .
        ]
        
        # Mock Path instances
        mock_path_instance = MagicMock()
        mock_path_class.return_value = mock_path_instance
        
        # Mock file existence
        def exists_side_effect():
            # Check what path we're checking
            path_str = str(mock_path_class.call_args[0][0])
            if path_str == 'requirements.txt':
                return True
            elif path_str == 'setup.py':
                return True
            return False
        
        mock_path_instance.exists.side_effect = exists_side_effect
        
        result = self.tools.install_python_deps(upgrade=False, dry_run=False)
        
        self.assertEqual(result, 0)
        self.assertEqual(mock_run.call_count, 3)
    
    @patch('tooling.setup.setup_tools.run_command')
    def test_install_python_deps_dry_run(self, mock_run):
        """Test Python deps installation in dry run mode"""
        # Only pip check should run
        mock_run.return_value = (0, 'pip 21.0.0', '')
        
        with patch('tooling.setup.setup_tools.Path.exists', return_value=True):
            result = self.tools.install_python_deps(upgrade=False, dry_run=True)
        
        self.assertEqual(result, 0)
        # Only pip --version should be called
        self.assertEqual(mock_run.call_count, 1)
    
    @patch('tooling.setup.setup_tools.run_command')
    def test_install_ai_tools_no_npm(self, mock_run):
        """Test AI tools installation when npm is missing"""
        mock_run.return_value = (1, '', 'npm not found')
        
        with patch.object(self.tools, '_setup_api_keys'):
            result = self.tools.install_ai_tools(skip_api_keys=False, dry_run=False)
        
        self.assertEqual(result, 0)  # Should succeed but skip npm install
    
    @patch('tooling.setup.setup_tools.run_command')
    @patch('os.environ.get')
    def test_setup_api_keys(self, mock_env, mock_run):
        """Test API key setup display"""
        # Mock environment variables
        mock_env.side_effect = lambda key, default=None: {
            'GEMINI_API_KEY': 'test-key',
            'OPENAI_API_KEY': None,
            'ANTHROPIC_API_KEY': None
        }.get(key, default)
        
        # This should not raise an exception
        self.tools._setup_api_keys()
    
    @patch('tooling.setup.setup_tools.Path')
    def test_setup_permissions_success(self, mock_path_class):
        """Test successful permission setup"""
        # Create mock path instances
        mock_cli_dir = MagicMock()
        mock_cli_dir.exists.return_value = True
        
        # Mock scripts
        mock_script1 = MagicMock()
        mock_script1.name = 'script1.py'
        mock_script1.stat.return_value = MagicMock(st_mode=0o644)
        
        mock_script2 = MagicMock()
        mock_script2.name = 'script2.py'
        mock_script2.stat.return_value = MagicMock(st_mode=0o644)
        
        mock_scripts = [mock_script1, mock_script2]
        mock_cli_dir.glob.return_value = mock_scripts
        
        # Configure Path() to return our mock
        mock_path_class.return_value = mock_cli_dir
        
        result = self.tools.setup_permissions(create_symlinks=False, dry_run=False)
        
        self.assertEqual(result, 0)
        # Check that chmod was called on each script
        mock_script1.chmod.assert_called_once()
        mock_script2.chmod.assert_called_once()
    
    @patch('tooling.setup.setup_tools.Path.exists')
    def test_setup_permissions_no_cli_dir(self, mock_exists):
        """Test permission setup when CLI directory doesn't exist"""
        mock_exists.return_value = False
        
        result = self.tools.setup_permissions(create_symlinks=False, dry_run=False)
        
        self.assertEqual(result, 0)  # Should succeed with warning
    
    @patch('tooling.setup.setup_tools.SetupTools.install_python_deps')
    @patch('tooling.setup.setup_tools.SetupTools.install_ai_tools')
    @patch('tooling.setup.setup_tools.SetupTools.setup_permissions')
    def test_install_all_success(self, mock_perms, mock_ai, mock_python):
        """Test install all with all components succeeding"""
        mock_python.return_value = 0
        mock_ai.return_value = 0
        mock_perms.return_value = 0
        
        result = self.tools.install_all(
            skip_python=False,
            skip_ai=False,
            skip_permissions=False,
            skip_api_keys=False,
            dry_run=False,
            upgrade=False
        )
        
        self.assertEqual(result, 0)
        mock_python.assert_called_once()
        mock_ai.assert_called_once()
        mock_perms.assert_called_once()
    
    @patch('tooling.setup.setup_tools.SetupTools.install_python_deps')
    @patch('tooling.setup.setup_tools.SetupTools.install_ai_tools')
    def test_install_all_partial_failure(self, mock_ai, mock_python):
        """Test install all with some components failing"""
        mock_python.return_value = 0
        mock_ai.return_value = 1  # Fail AI tools
        
        result = self.tools.install_all(
            skip_python=False,
            skip_ai=False,
            skip_permissions=True,
            skip_api_keys=False,
            dry_run=False,
            upgrade=False
        )
        
        self.assertEqual(result, 1)  # Should fail overall


if __name__ == '__main__':
    unittest.main() 