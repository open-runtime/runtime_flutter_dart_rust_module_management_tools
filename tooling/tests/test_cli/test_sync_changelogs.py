"""
Tests for sync_changelogs.py wrapper
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.cli.sync_changelogs import main


class TestSyncChangelogsWrapper:
    """Test the sync_changelogs.py wrapper"""
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py'])
    def test_main_no_args(self, mock_get_config, mock_changelog_tools):
        """Test main with no arguments"""
        # Setup mocks
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        mock_tools = Mock()
        mock_tools.sync.return_value = 0
        mock_changelog_tools.return_value = mock_tools
        
        # Run main
        result = main()
        
        # Verify calls
        mock_get_config.assert_called_once_with(
            verbose=False,
            quiet=False,
            dry_run=False
        )
        mock_changelog_tools.assert_called_once_with(mock_config)
        mock_tools.sync.assert_called_once_with(
            source=None,
            target_pattern="packages",
            version=None,
            dry_run=False,
            force=False,
            auto_commit=False,
            skip_validation=False
        )
        assert result == 0
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py', '--dry-run'])
    def test_main_dry_run(self, mock_get_config, mock_changelog_tools):
        """Test main with dry run"""
        # Setup mocks
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        mock_tools = Mock()
        mock_tools.sync.return_value = 0
        mock_changelog_tools.return_value = mock_tools
        
        # Run main
        result = main()
        
        # Verify dry run passed
        mock_get_config.assert_called_once_with(
            verbose=False,
            quiet=False,
            dry_run=True
        )
        mock_tools.sync.assert_called_once()
        call_args = mock_tools.sync.call_args[1]
        assert call_args['dry_run'] is True
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py', '--auto-commit'])
    def test_main_auto_commit(self, mock_get_config, mock_changelog_tools):
        """Test main with auto commit"""
        # Setup mocks
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        mock_tools = Mock()
        mock_tools.sync.return_value = 0
        mock_changelog_tools.return_value = mock_tools
        
        # Run main
        result = main()
        
        # Verify auto commit passed
        mock_tools.sync.assert_called_once()
        call_args = mock_tools.sync.call_args[1]
        assert call_args['auto_commit'] is True
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py', '--skip-validation'])
    def test_main_skip_validation(self, mock_get_config, mock_changelog_tools):
        """Test main with skip validation"""
        # Setup mocks
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        mock_tools = Mock()
        mock_tools.sync.return_value = 0
        mock_changelog_tools.return_value = mock_tools
        
        # Run main
        result = main()
        
        # Verify skip validation passed
        mock_tools.sync.assert_called_once()
        call_args = mock_tools.sync.call_args[1]
        assert call_args['skip_validation'] is True
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py', '-v', '-q'])
    def test_main_verbose_quiet(self, mock_get_config, mock_changelog_tools):
        """Test main with verbose and quiet flags"""
        # Setup mocks
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        mock_tools = Mock()
        mock_tools.sync.return_value = 0
        mock_changelog_tools.return_value = mock_tools
        
        # Run main
        result = main()
        
        # Verify config called with verbose and quiet
        mock_get_config.assert_called_once_with(
            verbose=True,
            quiet=True,
            dry_run=False
        )
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py', '--dry-run', '--auto-commit', '--skip-validation', '-v'])
    def test_main_all_flags(self, mock_get_config, mock_changelog_tools):
        """Test main with all flags"""
        # Setup mocks
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        mock_tools = Mock()
        mock_tools.sync.return_value = 0
        mock_changelog_tools.return_value = mock_tools
        
        # Run main
        result = main()
        
        # Verify all flags passed correctly
        mock_get_config.assert_called_once_with(
            verbose=True,
            quiet=False,
            dry_run=True
        )
        mock_tools.sync.assert_called_once_with(
            source=None,
            target_pattern="packages",
            version=None,
            dry_run=True,
            force=False,
            auto_commit=True,
            skip_validation=True
        )
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py'])
    def test_main_sync_failure(self, mock_get_config, mock_changelog_tools):
        """Test main when sync fails"""
        # Setup mocks
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        mock_tools = Mock()
        mock_tools.sync.return_value = 1  # Failure
        mock_changelog_tools.return_value = mock_tools
        
        # Run main
        result = main()
        
        # Should return error code
        assert result == 1
    
    @patch('tooling.cli.sync_changelogs.ChangelogTools')
    @patch('tooling.cli.sync_changelogs.get_config')
    @patch('sys.argv', ['sync_changelogs.py', '--help'])
    def test_main_help(self, mock_get_config, mock_changelog_tools):
        """Test main with help flag"""
        # Help causes SystemExit
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Should exit with 0 for help
        assert exc_info.value.code == 0
        
        # Should not create tools
        mock_changelog_tools.assert_not_called()
        mock_get_config.assert_not_called() 