"""
Tests for subprocess_helper.py
"""
import pytest
from unittest.mock import patch, Mock, MagicMock, call
import subprocess
import sys
from pathlib import Path

from tooling.utils.subprocess_helper import (
    run_cli_tool, _try_installed_command, _try_module_execution,
    _try_direct_execution, call_tool
)


class TestSubprocessHelper:
    """Test subprocess helper functions"""
    
    @patch('subprocess.run')
    def test_run_cli_tool_installed_command_success(self, mock_run):
        """Test run_cli_tool when installed command works"""
        mock_run.return_value = Mock(returncode=0)
        
        result = run_cli_tool('smart_commit', ['--help'])
        
        # Should try installed command first
        mock_run.assert_called_once_with(
            ['runtime_fdr_management_tools-commit', '--help'],
            check=True
        )
        assert result.returncode == 0
    
    @patch('subprocess.run')
    def test_run_cli_tool_fallback_to_module(self, mock_run):
        """Test run_cli_tool falls back to module execution"""
        # First call fails (installed command), second succeeds (module)
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, ['cmd']),
            Mock(returncode=0)
        ]
        
        result = run_cli_tool('smart_commit', ['--help'])
        
        # Should have tried both methods
        assert mock_run.call_count == 2
        
        # Check second call was module execution
        second_call = mock_run.call_args_list[1]
        assert sys.executable in second_call[0][0]
        assert '-m' in second_call[0][0]
        assert 'tooling.cli.smart_commit' in second_call[0][0]
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_run_cli_tool_fallback_to_direct(self, mock_exists, mock_run):
        """Test run_cli_tool falls back to direct execution"""
        # Mock file exists
        mock_exists.return_value = True
        
        # First two calls fail, third succeeds
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, ['cmd']),
            subprocess.CalledProcessError(1, ['cmd']),
            Mock(returncode=0)
        ]
        
        result = run_cli_tool('smart_commit', ['--help'])
        
        # Should have tried all three methods
        assert mock_run.call_count == 3
        
        # Check third call was direct execution
        third_call = mock_run.call_args_list[2]
        assert sys.executable in third_call[0][0]
        assert 'smart_commit.py' in str(third_call[0][0])
    
    @patch('subprocess.run')
    def test_run_cli_tool_all_methods_fail(self, mock_run):
        """Test run_cli_tool when all methods fail"""
        # Mock all subprocess calls to fail
        mock_run.side_effect = subprocess.CalledProcessError(1, ['cmd'])
        
        # The function will try methods and eventually raise an error
        with pytest.raises((subprocess.CalledProcessError, FileNotFoundError, RuntimeError)):
            run_cli_tool('smart_commit', ['--help'])
    
    @patch('subprocess.run')
    def test_run_cli_tool_with_kwargs(self, mock_run):
        """Test run_cli_tool passes kwargs correctly"""
        mock_run.return_value = Mock(returncode=0, stdout="output")
        
        result = run_cli_tool('smart_commit', capture_output=True, text=True)
        
        # Check kwargs were passed
        _, kwargs = mock_run.call_args
        assert kwargs['capture_output'] is True
        assert kwargs['text'] is True
    
    @patch('subprocess.run')
    def test_try_installed_command_known_tool(self, mock_run):
        """Test _try_installed_command with known tool mapping"""
        mock_run.return_value = Mock(returncode=0)
        
        _try_installed_command('sync_changelogs', ['--help'])
        
        mock_run.assert_called_once_with(
            ['runtime_fdr_management_tools-changelog', '--help'],
            check=True
        )
    
    @patch('subprocess.run')
    def test_try_installed_command_unknown_tool(self, mock_run):
        """Test _try_installed_command with unknown tool"""
        mock_run.return_value = Mock(returncode=0)
        
        _try_installed_command('unknown_tool', ['--help'])
        
        # Should use default naming convention
        mock_run.assert_called_once_with(
            ['runtime_fdr_management_tools-unknown-tool', '--help'],
            check=True
        )
    
    @patch('subprocess.run')
    def test_try_module_execution(self, mock_run):
        """Test _try_module_execution"""
        mock_run.return_value = Mock(returncode=0)
        
        _try_module_execution('smart_commit', ['--help'], capture_output=True)
        
        mock_run.assert_called_once_with(
            [sys.executable, '-m', 'tooling.cli.smart_commit', '--help'],
            check=True,
            capture_output=True
        )
    
    def test_try_direct_execution_not_found(self):
        """Test _try_direct_execution when script not found"""
        # This test verifies the FileNotFoundError behavior
        # Since we know smart_commit.py doesn't exist in the actual file system
        with pytest.raises(FileNotFoundError) as exc:
            _try_direct_execution('nonexistent_tool', [])
        
        assert "Could not find script: nonexistent_tool.py" in str(exc.value)
    
    @patch('subprocess.run')
    @patch('pathlib.Path.exists')
    def test_try_direct_execution_found_in_project_root(self, mock_exists, mock_run):
        """Test _try_direct_execution finds script in project root"""
        # First path doesn't exist, second does
        mock_exists.side_effect = [False, True]
        mock_run.return_value = Mock(returncode=0)
        
        _try_direct_execution('smart_commit', ['--help'])
        
        # Should have checked both paths
        assert mock_exists.call_count == 2
        
        # Check it tried to run the script
        args = mock_run.call_args[0][0]
        assert sys.executable == args[0]
        assert 'smart_commit.py' in args[1]
    
    @patch('pathlib.Path.exists')
    def test_try_direct_execution_not_found(self, mock_exists):
        """Test _try_direct_execution when script not found"""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError) as exc:
            _try_direct_execution('nonexistent', [])
        
        assert "Could not find script: nonexistent.py" in str(exc.value)
    
    @patch('subprocess.run')
    def test_call_tool_convenience_function(self, mock_run):
        """Test call_tool convenience function"""
        mock_run.return_value = Mock(returncode=0, stdout="v1.2.3")
        
        result = call_tool('get_new_patch_tag', '--format', 'json', capture_output=True)
        
        # Should have called run_cli_tool with correct args
        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]
        
        # Check it's trying to run the right tool
        # The command could be runtime_fdr_management_tools-next-tag based on command_map
        assert any('next-tag' in str(arg) or 'get_new_patch_tag' in str(arg) for arg in call_args)
        assert '--format' in call_args
        assert 'json' in call_args
    
    @patch('subprocess.run')
    def test_call_tool_with_no_args(self, mock_run):
        """Test call_tool with no arguments"""
        mock_run.return_value = Mock(returncode=0)
        
        call_tool('validate_changelogs')
        
        # Should still work without args
        mock_run.assert_called()
    
    def test_command_map_completeness(self):
        """Test that command map covers common tools"""
        from tooling.utils.subprocess_helper import _try_installed_command
        
        # Get the command map by inspecting the function
        import inspect
        source = inspect.getsource(_try_installed_command)
        
        # Check some key mappings exist
        assert 'smart_commit' in source
        assert 'sync_changelogs' in source
        assert 'release' in source
        assert 'validate_changelogs' in source 