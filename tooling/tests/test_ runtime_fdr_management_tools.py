"""
Tests for runtime_fdr_management_tools.py main CLI entry point
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import sys
from pathlib import Path
from click.testing import CliRunner
import os

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tooling.runtime_fdr_management_tools import cli, show_welcome, show_version, run_command, COMMANDS


class TestRTCLI:
    """Test the main runtime_fdr_management_tools.py CLI"""
    
    def test_cli_no_args(self):
        """Test CLI with no arguments"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.show_welcome') as mock_welcome:
            result = runner.invoke(cli, [])
            assert result.exit_code == 0
            mock_welcome.assert_called_once()
    
    def test_cli_version_flag(self):
        """Test CLI with --version flag"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.show_version') as mock_version:
            result = runner.invoke(cli, ['--version'])
            assert result.exit_code == 0
            mock_version.assert_called_once()
    
    def test_cli_interactive_flag(self):
        """Test CLI with --interactive flag"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.launch_interactive_mode') as mock_interactive:
            result = runner.invoke(cli, ['--interactive'])
            assert result.exit_code == 0
            mock_interactive.assert_called_once()
    
    def test_cli_help(self):
        """Test CLI help output"""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "Runtime Tools" in result.output
        assert "Your Development Assistant" in result.output
    
    @patch('tooling.runtime_fdr_management_tools.console')
    def test_show_welcome(self, mock_console):
        """Test show_welcome function"""
        show_welcome()
        
        # Should print title panel
        assert mock_console.print.call_count >= 3  # Title, table, tips
        
        # Check that Panel objects were created
        calls = mock_console.print.call_args_list
        # The first call should be a Panel
        assert len(calls) >= 3
    
    @patch('tooling.runtime_fdr_management_tools.console')
    def test_show_version(self, mock_console):
        """Test show_version function"""
        show_version()
        
        # Should print version panel
        mock_console.print.assert_called_once()
    
    def test_commit_command(self):
        """Test commit command"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.run_command') as mock_run:
            result = runner.invoke(cli, ['commit'])
            assert result.exit_code == 0
            mock_run.assert_called_once_with('commit', [])
    
    def test_release_command(self):
        """Test release command"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.run_command') as mock_run:
            result = runner.invoke(cli, ['release'])
            assert result.exit_code == 0
            mock_run.assert_called_once_with('release', [])
    
    def test_changelog_command(self):
        """Test changelog command"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.run_command') as mock_run:
            result = runner.invoke(cli, ['changelog'])
            assert result.exit_code == 0
            mock_run.assert_called_once_with('changelog', [])
    
    def test_version_command(self):
        """Test version command"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.run_command') as mock_run:
            result = runner.invoke(cli, ['version'])
            assert result.exit_code == 0
            mock_run.assert_called_once_with('version', [])
    
    def test_pr_command(self):
        """Test pr command"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.run_command') as mock_run:
            result = runner.invoke(cli, ['pr'])
            assert result.exit_code == 0
            mock_run.assert_called_once_with('pr', [])
    
    def test_setup_command(self):
        """Test setup command"""
        runner = CliRunner()
        with patch('tooling.runtime_fdr_management_tools.run_command') as mock_run:
            result = runner.invoke(cli, ['setup'])
            assert result.exit_code == 0
            mock_run.assert_called_once_with('setup', [])
    
    @patch('tooling.runtime_fdr_management_tools.import_module')
    @patch('tooling.runtime_fdr_management_tools.console')
    def test_run_command_success(self, mock_console, mock_import):
        """Test run_command with successful execution"""
        # Setup mock module
        mock_module = Mock()
        mock_class = Mock()
        mock_instance = Mock()
        mock_instance.main.return_value = 0
        mock_class.return_value = mock_instance
        mock_module.CommitTools = mock_class
        mock_import.return_value = mock_module
        
        # Run command
        result = run_command('commit', ['--help'])
        
        # Verify
        assert result == 0
        mock_import.assert_called_once_with('tooling.cli.commit_tools')
        mock_instance.main.assert_called_once_with(['--help'])
    
    @patch('tooling.runtime_fdr_management_tools.import_module')
    @patch('tooling.runtime_fdr_management_tools.console')
    def test_run_command_no_main_method(self, mock_console, mock_import):
        """Test run_command when tool has run() instead of main()"""
        # Setup mock module
        mock_module = Mock()
        mock_class = Mock()
        mock_instance = Mock(spec=['run'])  # Specify that it only has 'run' method
        mock_instance.run.return_value = 0
        mock_class.return_value = mock_instance
        mock_module.CommitTools = mock_class
        mock_import.return_value = mock_module
        
        # Run command
        result = run_command('commit', ['--help'])
        
        # Verify
        assert result == 0
        mock_instance.run.assert_called_once_with(['--help'])
    
    @patch('tooling.runtime_fdr_management_tools.console')
    def test_run_command_unknown(self, mock_console):
        """Test run_command with unknown command"""
        result = run_command('unknown', [])
        
        assert result == 1
        mock_console.print.assert_called_once()
        assert "Unknown command" in str(mock_console.print.call_args)
    
    @patch('tooling.runtime_fdr_management_tools.import_module')
    @patch('tooling.runtime_fdr_management_tools.console')
    def test_run_command_import_error(self, mock_console, mock_import):
        """Test run_command with import error"""
        mock_import.side_effect = ImportError("Module not found")
        
        result = run_command('commit', [])
        
        assert result == 1
        assert mock_console.print.call_count >= 1
        assert "Error running commit" in str(mock_console.print.call_args_list)
    
    @patch('tooling.runtime_fdr_management_tools.import_module')
    @patch('tooling.runtime_fdr_management_tools.console')
    @patch.dict(os.environ, {'DEBUG': '1'})
    def test_run_command_error_debug(self, mock_console, mock_import):
        """Test run_command with error in debug mode"""
        mock_import.side_effect = Exception("Test error")
        
        result = run_command('commit', [])
        
        assert result == 1
        mock_console.print_exception.assert_called_once()
    
    def test_install_completion_zsh(self):
        """Test install completion for zsh"""
        runner = CliRunner()
        with patch.dict(os.environ, {'SHELL': '/bin/zsh'}):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = runner.invoke(cli, ['install-completion'])
                
                assert result.exit_code == 0
                mock_open.assert_called_once()
                mock_file.write.assert_called()
                assert "zsh_source" in mock_file.write.call_args[0][0]
    
    def test_install_completion_bash(self):
        """Test install completion for bash"""
        runner = CliRunner()
        with patch.dict(os.environ, {'SHELL': '/bin/bash'}):
            with patch('builtins.open', create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file
                
                result = runner.invoke(cli, ['install-completion'])
                
                assert result.exit_code == 0
                assert "bash_source" in mock_file.write.call_args[0][0]
    
    def test_install_completion_fish(self):
        """Test install completion for fish"""
        runner = CliRunner()
        with patch.dict(os.environ, {'SHELL': '/usr/local/bin/fish'}):
            with patch('subprocess.run') as mock_run:
                result = runner.invoke(cli, ['install-completion'])
                
                assert result.exit_code == 0
                mock_run.assert_called_once()
                assert "fish_source" in mock_run.call_args[0][0]
    
    def test_install_completion_unsupported(self):
        """Test install completion for unsupported shell"""
        runner = CliRunner()
        with patch.dict(os.environ, {'SHELL': '/bin/sh'}):
            result = runner.invoke(cli, ['install-completion'])
            
            assert result.exit_code == 0
            assert "not supported" in result.output
    
    def test_commands_registry(self):
        """Test COMMANDS registry structure"""
        assert 'commit' in COMMANDS
        assert 'release' in COMMANDS
        assert 'changelog' in COMMANDS
        assert 'version' in COMMANDS
        assert 'pr' in COMMANDS
        assert 'setup' in COMMANDS
        
        # Check command structure
        for cmd, info in COMMANDS.items():
            assert 'module' in info
            assert 'class' in info
            assert 'description' in info
            assert info['module'].startswith('tooling.cli.')
    
    @patch('tooling.cli.interactive_mode.InteractiveMode')
    def test_launch_interactive_mode(self, mock_interactive_class):
        """Test launching interactive mode"""
        from tooling.runtime_fdr_management_tools import launch_interactive_mode
        
        mock_instance = Mock()
        mock_interactive_class.return_value = mock_instance
        
        launch_interactive_mode()
        
        mock_interactive_class.assert_called_once()
        mock_instance.run.assert_called_once() 