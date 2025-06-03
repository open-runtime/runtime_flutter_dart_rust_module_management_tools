#!/usr/bin/env python3
"""
Unit tests for main_router.py functionality
"""

import sys
import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, call, Mock
import subprocess
from io import StringIO

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tooling.cli.main_router import (
    discover_commands, get_file_description, get_command_groups,
    list_commands, show_examples, show_all_help, ALIASES
)

# Import Colors for test output
try:
    from tooling.core.common_config import Colors
except ImportError:
    from core.common_config import Colors


def print_test_result(message, success=True):
    """Helper function to print colored test results"""
    color = Colors.GREEN if success else Colors.RED
    symbol = "✓" if success else "✗"
    print(f"{color}{symbol} {message}{Colors.NC}")


class TestMainRouter(unittest.TestCase):
    """Test cases for main_router functionality"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="test_router_")
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_command_discovery(self):
        """Test automatic command discovery"""
        # Create a mock logger
        mock_logger = Mock()
        mock_logger.debug = Mock()
        
        # Commands should be discovered from the CLI directory
        commands = discover_commands(mock_logger)
        
        # Check that we have commands
        self.assertIsInstance(commands, dict)
        self.assertGreater(len(commands), 0)
        
        # Check for some expected commands
        expected_commands = [
            'smart_commit_fast', 'smart_commit', 'sync_changelogs',
            'release', 'validate_changelogs', 'setup_ai_tools'
        ]
        
        for cmd in expected_commands:
            self.assertIn(cmd, commands, f"Expected command '{cmd}' not found")
            self.assertIn('module', commands[cmd])
            self.assertIn('description', commands[cmd])
            self.assertIn('file', commands[cmd])
        
        print_test_result("Command discovery test passed")
    
    def test_get_file_description(self):
        """Test extracting descriptions from Python files"""
        # Create test Python file with docstring
        test_file = Path("test_command.py")
        test_file.write_text('"""\ntest_command.py - Test command description\n\nMore details here.\n"""\n')
        
        description = get_file_description(test_file)
        self.assertEqual(description, "Test command description")
        
        # Test file without docstring
        test_file.write_text("# No docstring here\nimport sys\n")
        description = get_file_description(test_file)
        self.assertEqual(description, "Run test_command tool")
        
        print_test_result("File description extraction test passed")
    
    def test_aliases(self):
        """Test command aliases"""
        # Check that aliases are properly defined
        self.assertIsInstance(ALIASES, dict)
        
        # Test some common aliases
        self.assertEqual(ALIASES.get('commit'), 'smart_commit_fast')
        self.assertEqual(ALIASES.get('c'), 'smart_commit_fast')
        self.assertEqual(ALIASES.get('r'), 'release')
        self.assertEqual(ALIASES.get('validate'), 'validate_changelogs')
        
        # Get commands to verify aliases
        mock_logger = Mock()
        commands = discover_commands(mock_logger)
        
        # Ensure all aliases point to valid commands
        for alias, command in ALIASES.items():
            self.assertIn(command, commands, 
                         f"Alias '{alias}' points to non-existent command '{command}'")
        
        print_test_result("Aliases test passed")
    
    def test_command_groups(self):
        """Test command grouping by category"""
        # Set up COMMANDS global for get_command_groups
        import tooling.cli.main_router as main_router
        mock_logger = Mock()
        main_router.COMMANDS = discover_commands(mock_logger)
        
        groups = get_command_groups()
        
        # Check that we have expected groups
        expected_groups = [
            "Commit Management", "Changelog Management", "Release Management",
            "Version Management", "GitHub Integration", 
            "Setup & Configuration"
        ]
        
        for group in expected_groups:
            self.assertIn(group, groups, f"Expected group '{group}' not found")
            self.assertIsInstance(groups[group], list)
            self.assertGreater(len(groups[group]), 0, 
                             f"Group '{group}' should have commands")
        
        # Check command categorization
        self.assertIn('smart_commit_fast', groups["Commit Management"])
        self.assertIn('sync_changelogs', groups["Changelog Management"])
        self.assertIn('release', groups["Release Management"])
        # Validation commands are in their respective categories
        self.assertIn('validate_changelogs', groups["Changelog Management"])
        self.assertIn('pre_release_check', groups["Release Management"])
        
        print_test_result("Command grouping test passed")
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_list_commands(self, mock_stdout):
        """Test command listing functionality"""
        # Set up COMMANDS global
        import tooling.cli.main_router as main_router
        mock_logger = Mock()
        main_router.COMMANDS = discover_commands(mock_logger)
        
        # Test basic listing
        list_commands(detailed=False, logger=mock_logger)
        output = mock_stdout.getvalue()
        
        # Check for expected content
        self.assertIn("Commit Management", output)
        self.assertIn("smart_commit_fast", output)
        self.assertIn("aliases:", output)
        
        # Test detailed listing
        mock_stdout.truncate(0)
        mock_stdout.seek(0)
        list_commands(detailed=True, logger=mock_logger)
        output = mock_stdout.getvalue()
        
        self.assertIn("Usage: runtime_fdr_tools", output)
        self.assertIn("Also: runtime_fdr_tools", output)
        
        print_test_result("Command listing test passed")
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_examples(self, mock_stdout):
        """Test examples display"""
        mock_logger = Mock()
        show_examples(mock_logger)
        output = mock_stdout.getvalue()
        
        # Check for expected sections
        self.assertIn("Usage Examples:", output)
        self.assertIn("Daily Development", output)
        self.assertIn("Release Workflow", output)
        self.assertIn("Using Aliases", output)
        
        # Check for specific examples
        self.assertIn("runtime_fdr_tools smart_commit_fast", output)
        self.assertIn("runtime_fdr_tools release", output)
        self.assertIn("runtime_fdr_tools commit", output)
        
        print_test_result("Examples display test passed")
    
    @patch('subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_all_help(self, mock_stdout, mock_run):
        """Test the --help-all functionality"""
        # Mock subprocess responses for help commands
        help_response = MagicMock()
        help_response.returncode = 0
        help_response.stdout = """usage: runtime_fdr_tools test_command [-h] [--option VALUE]

Test command description

optional arguments:
  -h, --help         show this help message and exit
  --option VALUE     An example option
  --another ANOTHER  Another option
  --verbose          Enable verbose output
"""
        mock_run.return_value = help_response
        
        # Set up COMMANDS global
        import tooling.cli.main_router as main_router
        mock_logger = Mock()
        main_router.COMMANDS = discover_commands(mock_logger)
        
        # Run show_all_help
        show_all_help(mock_logger)
        output = mock_stdout.getvalue()
        
        # Check header
        self.assertIn("RUNTIME FDR TOOLS - COMPLETE COMMAND REFERENCE", output)
        self.assertIn("=" * 80, output)
        
        # Check command groups
        self.assertIn("Commit Management", output)
        self.assertIn("Changelog Management", output)
        
        # Check command display
        self.assertIn("● smart_commit_fast", output)
        self.assertIn("(aliases:", output)
        
        # Check help extraction
        self.assertIn("usage: runtime_fdr_tools", output)
        self.assertIn("Options:", output)
        
        # Check footer
        self.assertIn("For detailed help on any command, run:", output)
        self.assertIn("runtime_fdr_tools <command> --help", output)
        
        print_test_result("Show all help test passed")
    
    @patch('subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_show_all_help_error_handling(self, mock_stdout, mock_run):
        """Test error handling in show_all_help"""
        # Set up COMMANDS global
        import tooling.cli.main_router as main_router
        mock_logger = Mock()
        main_router.COMMANDS = discover_commands(mock_logger)
        
        # Test timeout handling
        mock_run.side_effect = subprocess.TimeoutExpired('cmd', 5)
        show_all_help(mock_logger)
        output = mock_stdout.getvalue()
        self.assertIn("(Help timeout)", output)
        
        # Test general error handling
        mock_stdout.truncate(0)
        mock_stdout.seek(0)
        mock_run.side_effect = Exception("Test error")
        show_all_help(mock_logger)
        output = mock_stdout.getvalue()
        self.assertIn("(Error getting help:", output)
        
        print_test_result("Help error handling test passed")
    
    def test_command_consistency(self):
        """Test that all commands have consistent metadata"""
        mock_logger = Mock()
        commands = discover_commands(mock_logger)
        
        for cmd_name, cmd_info in commands.items():
            # Check required fields
            self.assertIn('module', cmd_info, f"Command '{cmd_name}' missing 'module'")
            self.assertIn('description', cmd_info, f"Command '{cmd_name}' missing 'description'")
            self.assertIn('file', cmd_info, f"Command '{cmd_name}' missing 'file'")
            
            # Check that module matches command name
            self.assertEqual(cmd_info['module'], cmd_name,
                           f"Command '{cmd_name}' module mismatch")
            
            # Check that description is not empty
            self.assertTrue(cmd_info['description'],
                          f"Command '{cmd_name}' has empty description")
        
        print_test_result("Command consistency test passed")


class TestMainRouterIntegration(unittest.TestCase):
    """Integration tests for main_router functionality"""
    
    @patch('subprocess.run')
    def test_run_command_function(self, mock_run):
        """Test the run_command function (imported from main_router)"""
        from tooling.cli.main_router import run_command
        import tooling.cli.main_router as main_router
        
        # Set up COMMANDS global
        mock_logger = Mock()
        main_router.COMMANDS = discover_commands(mock_logger)
        
        # Mock successful command execution
        mock_run.return_value = MagicMock(returncode=0)
        
        # Test running a valid command
        with self.assertRaises(SystemExit) as cm:
            run_command('smart_commit_fast', ['--help'], mock_logger)
        
        # Should exit with the command's return code
        self.assertEqual(cm.exception.code, 0)
        
        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertTrue(args[0].endswith('python') or args[0].endswith('python3'))
        self.assertTrue(args[1].endswith('smart_commit_fast.py'))
        self.assertEqual(args[2], '--help')
        
        print_test_result("Run command integration test passed")
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_invalid_command_handling(self, mock_stdout):
        """Test handling of invalid commands"""
        from tooling.cli.main_router import run_command
        import tooling.cli.main_router as main_router
        
        # Set up COMMANDS global
        mock_logger = Mock()
        main_router.COMMANDS = discover_commands(mock_logger)
        
        # Test invalid command
        with self.assertRaises(SystemExit) as cm:
            run_command('nonexistent_command', [], mock_logger)
        
        # Should exit with error code
        self.assertEqual(cm.exception.code, 1)
        
        # Check error message
        output = mock_stdout.getvalue()
        self.assertIn("Unknown command 'nonexistent_command'", output)
        self.assertIn("Available commands:", output)
        
        print_test_result("Invalid command handling test passed")


class TestMainRouterCLI(unittest.TestCase):
    """Test the CLI argument parsing"""
    
    @patch('sys.argv', ['runtime_fdr_tools', '--help-all'])
    @patch('tooling.cli.main_router.show_all_help')
    def test_help_all_argument(self, mock_show_all_help):
        """Test that --help-all argument triggers show_all_help"""
        from tooling.cli.main_router import main
        
        # Run main
        main()
        
        # Verify show_all_help was called
        mock_show_all_help.assert_called_once()
        
        print_test_result("--help-all argument test passed")
    
    @patch('sys.argv', ['runtime_fdr_tools', '--list'])
    @patch('tooling.cli.main_router.list_commands')
    def test_list_argument(self, mock_list_commands):
        """Test that --list argument triggers list_commands"""
        from tooling.cli.main_router import main
        
        # Run main
        main()
        
        # Verify list_commands was called with detailed=True and a logger
        # Check that it was called once
        mock_list_commands.assert_called_once()
        # Check the arguments
        args, kwargs = mock_list_commands.call_args
        self.assertEqual(kwargs.get('detailed'), True)
        self.assertIn('logger', kwargs)
        
        print_test_result("--list argument test passed")
    
    @patch('sys.argv', ['runtime_fdr_tools', '--examples'])
    @patch('tooling.cli.main_router.show_examples')
    def test_examples_argument(self, mock_show_examples):
        """Test that --examples argument triggers show_examples"""
        from tooling.cli.main_router import main
        
        # Run main
        main()
        
        # Verify show_examples was called
        mock_show_examples.assert_called_once()
        
        print_test_result("--examples argument test passed")


if __name__ == "__main__":
    unittest.main(verbosity=2) 