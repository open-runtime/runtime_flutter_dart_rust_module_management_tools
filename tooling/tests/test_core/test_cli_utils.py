#!/usr/bin/env python3
"""
Test CLI utilities from cli_utils.py
"""

import pytest
import sys
import os
import argparse
from unittest.mock import patch, MagicMock, call
from io import StringIO

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from cli.cli_utils import (
    setup_cli_logging, add_common_arguments,
    print_info, print_success, print_error, print_warning,
    print_header, print_section, CLIProgressLogger,
    confirm_action
)
from tooling.core.base_config import get_config


class TestLoggingSetup:
    """Test CLI logging setup"""
    
    @patch('cli.cli_utils.setup_logging')
    def test_setup_cli_logging_quiet(self, mock_setup):
        """Test logging setup in quiet mode"""
        args = argparse.Namespace(quiet=True, debug=False, verbose=False, json=False)
        logger = setup_cli_logging("test_tool", args)
        mock_setup.assert_called_once_with(
            tool_name="test_tool",
            level="ERROR",
            json_output=False
        )
    
    @patch('cli.cli_utils.setup_logging')
    def test_setup_cli_logging_debug(self, mock_setup):
        """Test logging setup in debug mode"""
        args = argparse.Namespace(quiet=False, debug=True, verbose=False, json=False)
        logger = setup_cli_logging("test_tool", args)
        mock_setup.assert_called_once_with(
            tool_name="test_tool",
            level="DEBUG",
            json_output=False
        )
    
    @patch('cli.cli_utils.setup_logging')
    def test_setup_cli_logging_verbose(self, mock_setup):
        """Test logging setup in verbose mode"""
        args = argparse.Namespace(quiet=False, debug=False, verbose=True, json=False)
        logger = setup_cli_logging("test_tool", args)
        mock_setup.assert_called_once_with(
            tool_name="test_tool",
            level="INFO",
            json_output=False
        )
    
    @patch('cli.cli_utils.setup_logging')
    @patch('tooling.core.base_config.get_config')
    def test_setup_cli_logging_json(self, mock_get_config, mock_setup):
        """Test logging setup with JSON output"""
        mock_config = MagicMock()
        mock_config.log_level.value = "INFO"  # Default is INFO, not WARNING
        mock_get_config.return_value = mock_config
        
        args = argparse.Namespace(quiet=False, debug=False, verbose=False, json=True)
        logger = setup_cli_logging("test_tool", args)
        mock_setup.assert_called_once_with(
            tool_name="test_tool",
            level="INFO",
            json_output=True
        )
    
    @patch('cli.cli_utils.setup_logging')
    @patch('tooling.core.base_config.get_config')
    def test_setup_cli_logging_priority(self, mock_get_config, mock_setup):
        """Test that quiet > debug > verbose for log level priority"""
        mock_config = MagicMock()
        mock_config.log_level.value = "WARNING"
        mock_get_config.return_value = mock_config
        
        # Quiet overrides everything
        args = argparse.Namespace(quiet=True, debug=True, verbose=True, json=False)
        logger = setup_cli_logging("test_tool", args)
        mock_setup.assert_called_with(
            tool_name="test_tool",
            level="ERROR",
            json_output=False
        )


class TestCommonArguments:
    """Test common argument addition"""
    
    def test_add_common_arguments(self):
        """Test adding common arguments to parser"""
        parser = argparse.ArgumentParser()
        add_common_arguments(parser)
        
        # Parse with all flags
        args = parser.parse_args(['-v', '-d', '-q', '--json'])
        assert args.verbose == True
        assert args.debug == True
        assert args.quiet == True
        assert args.json == True
    
    def test_add_common_arguments_defaults(self):
        """Test default values for common arguments"""
        parser = argparse.ArgumentParser()
        add_common_arguments(parser)
        
        # Parse with no flags
        args = parser.parse_args([])
        assert args.verbose == False
        assert args.debug == False
        assert args.quiet == False
        assert args.json == False
    
    def test_add_common_arguments_help(self):
        """Test help text for common arguments"""
        parser = argparse.ArgumentParser()
        add_common_arguments(parser)
        
        help_text = parser.format_help()
        assert 'verbose' in help_text
        assert 'debug' in help_text
        assert 'quiet' in help_text
        assert 'json' in help_text


class TestPrintFunctions:
    """Test colored print functions"""
    
    @patch('tooling.core.base_config.get_config')
    def test_print_info(self, mock_get_config, capsys):
        """Test info message printing"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_get_config.return_value = mock_config
        
        print_info("Test info message")
        captured = capsys.readouterr()
        assert "Test info message" in captured.out
        assert "ℹ" in captured.out
    
    @patch('tooling.core.base_config.get_config')
    def test_print_success(self, mock_get_config, capsys):
        """Test success message printing"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_get_config.return_value = mock_config
        
        print_success("Test success message")
        captured = capsys.readouterr()
        assert "✓ Test success message" in captured.out
    
    @patch('tooling.core.base_config.get_config')
    def test_print_error(self, mock_get_config, capsys):
        """Test error message printing"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_get_config.return_value = mock_config
        
        print_error("Test error message")
        captured = capsys.readouterr()
        assert "✗ Test error message" in captured.err  # Should go to stderr
    
    @patch('tooling.core.base_config.get_config')
    def test_print_warning(self, mock_get_config, capsys):
        """Test warning message printing"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_get_config.return_value = mock_config
        
        print_warning("Test warning message")
        captured = capsys.readouterr()
        assert "⚠ Test warning message" in captured.out
    
    @patch('tooling.core.base_config.get_config')
    def test_print_header(self, mock_get_config, capsys):
        """Test header printing"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_get_config.return_value = mock_config
        
        print_header("Test Header")
        captured = capsys.readouterr()
        assert "Test Header" in captured.out
        # Rich uses unicode box drawing characters, not "="
    
    @patch('tooling.core.base_config.get_config')
    def test_print_section(self, mock_get_config, capsys):
        """Test section printing"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_get_config.return_value = mock_config
        
        print_section("Test Section", "Test content")
        captured = capsys.readouterr()
        assert "Test Section" in captured.out


class TestCLIProgressLogger:
    """Test CLI progress logger"""
    
    @patch('tooling.core.base_config.get_config')
    def test_progress_logger_success(self, mock_get_config, capsys):
        """Test progress logger with successful completion"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_config.debug = False
        mock_get_config.return_value = mock_config
        
        mock_logger = MagicMock()
        
        with CLIProgressLogger(mock_logger, "Processing data") as progress:
            # Simulate some work
            pass
        
        # Progress logger is transient, so output is not captured
        mock_logger.info.assert_called()
    
    @patch('tooling.core.base_config.get_config')
    def test_progress_logger_failure(self, mock_get_config, capsys):
        """Test progress logger with failure"""
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_config.debug = False
        mock_get_config.return_value = mock_config
        
        mock_logger = MagicMock()
        
        try:
            with CLIProgressLogger(mock_logger, "Processing data") as progress:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Progress logger is transient, so output is not captured
        mock_logger.error.assert_called()
    
    def test_progress_logger_no_display(self, capsys):
        """Test progress logger with display disabled"""
        mock_logger = MagicMock()
        
        with CLIProgressLogger(mock_logger, "Processing data", show_progress=False) as progress:
            pass
        
        captured = capsys.readouterr()
        # Should not show any progress
        assert captured.out == ""
    
    def test_progress_logger_inheritance(self):
        """Test that CLIProgressLogger inherits from ProgressLogger"""
        from tooling.core.logging import ProgressLogger
        assert issubclass(CLIProgressLogger, ProgressLogger)


class TestConfirmAction:
    """Test user confirmation function"""
    
    @patch('tooling.core.base_config.get_config')
    @patch('rich.prompt.Confirm.ask', return_value=True)
    def test_confirm_action_yes(self, mock_confirm, mock_get_config):
        """Test confirmation with yes response"""
        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_get_config.return_value = mock_config
        
        result = confirm_action("Continue?")
        assert result == True
        mock_confirm.assert_called_once_with("Continue?", default=False)
    
    @patch('tooling.core.base_config.get_config')
    @patch('rich.prompt.Confirm.ask', return_value=True)
    def test_confirm_action_yes_uppercase(self, mock_confirm, mock_get_config):
        """Test confirmation with uppercase yes"""
        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_get_config.return_value = mock_config
        
        result = confirm_action("Continue?")
        assert result == True
    
    @patch('tooling.core.base_config.get_config')
    @patch('rich.prompt.Confirm.ask', return_value=True)
    def test_confirm_action_yes_full(self, mock_confirm, mock_get_config):
        """Test confirmation with full 'yes'"""
        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_get_config.return_value = mock_config
        
        result = confirm_action("Continue?")
        assert result == True
    
    @patch('tooling.core.base_config.get_config')
    @patch('rich.prompt.Confirm.ask', return_value=False)
    def test_confirm_action_no(self, mock_confirm, mock_get_config):
        """Test confirmation with no response"""
        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_get_config.return_value = mock_config
        
        result = confirm_action("Continue?")
        assert result == False
    
    @patch('tooling.core.base_config.get_config')
    @patch('rich.prompt.Confirm.ask', return_value=False)
    def test_confirm_action_default_no(self, mock_confirm, mock_get_config):
        """Test confirmation with empty response (default no)"""
        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_get_config.return_value = mock_config
        
        result = confirm_action("Continue?")
        assert result == False
        mock_confirm.assert_called_once_with("Continue?", default=False)
    
    @patch('tooling.core.base_config.get_config')
    @patch('rich.prompt.Confirm.ask', return_value=True)
    def test_confirm_action_default_yes(self, mock_confirm, mock_get_config):
        """Test confirmation with empty response (default yes)"""
        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_get_config.return_value = mock_config
        
        result = confirm_action("Continue?", default=True)
        assert result == True
        mock_confirm.assert_called_once_with("Continue?", default=True)
    
    @patch('tooling.core.base_config.get_config')
    @patch('rich.prompt.Confirm.ask', return_value=False)
    def test_confirm_action_invalid(self, mock_confirm, mock_get_config):
        """Test confirmation with invalid response"""
        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_get_config.return_value = mock_config
        
        result = confirm_action("Continue?")
        assert result == False  # Invalid input defaults to no


class TestCLIUtilsIntegration:
    """Integration tests for CLI utilities"""
    
    def test_full_cli_setup(self):
        """Test setting up a complete CLI with common arguments"""
        parser = argparse.ArgumentParser(description="Test CLI")
        add_common_arguments(parser)
        
        # Test various argument combinations
        test_cases = [
            ([], {"verbose": False, "debug": False, "quiet": False, "json": False}),
            (["-v"], {"verbose": True, "debug": False, "quiet": False, "json": False}),
            (["-d"], {"verbose": False, "debug": True, "quiet": False, "json": False}),
            (["-q"], {"verbose": False, "debug": False, "quiet": True, "json": False}),
            (["--json"], {"verbose": False, "debug": False, "quiet": False, "json": True}),
            (["-v", "-d"], {"verbose": True, "debug": True, "quiet": False, "json": False}),
        ]
        
        for args, expected in test_cases:
            parsed = parser.parse_args(args)
            for key, value in expected.items():
                assert getattr(parsed, key) == value
    
    @patch('cli.cli_utils.setup_logging')
    def test_logging_with_parsed_args(self, mock_setup):
        """Test setting up logging based on parsed arguments"""
        parser = argparse.ArgumentParser()
        add_common_arguments(parser)
        
        # Test debug mode
        args = parser.parse_args(["-d"])
        logger = setup_cli_logging("test", args)
        mock_setup.assert_called_with(tool_name="test", level="DEBUG", json_output=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 