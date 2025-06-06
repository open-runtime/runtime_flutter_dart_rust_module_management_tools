#!/usr/bin/env python3
"""
Test script to verify logging integration across the tooling suite.
"""

import sys
import os
import tempfile
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logging import setup_logging, get_logger, ProgressLogger, log_context
try:
    from tooling.cli.cli_utils import Colors, run_command
except ImportError:
    from cli.cli_utils import Colors, run_command

# Create a mock config for testing
def get_mock_config():
    """Create a mock config object for testing"""
    config = MagicMock()
    config.log_level = "INFO"
    config.json_output = False
    config.debug = False
    config.use_color = True
    config.verbose = False
    config.quiet = False
    return config

def print_color(color, message):
    """Print colored text"""
    print(f"{color}{message}{Colors.NC}")

def print_header(title):
    """Print a header"""
    print_color(Colors.PURPLE, f"\n{'='*60}")
    print_color(Colors.PURPLE, title)
    print_color(Colors.PURPLE, f"{'='*60}\n")
from cli.cli_utils import setup_cli_logging, print_info, print_success, print_error, print_warning

def test_basic_logging():
    """Test basic logging functionality"""
    print("\n=== Testing Basic Logging ===")
    
    # Create a temporary project structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project structure
        project_dir = Path(tmpdir)
        (project_dir / "tooling").mkdir()
        (project_dir / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'")
        (project_dir / "dart").mkdir()
        (project_dir / "flutter").mkdir()
        (project_dir / "dart" / "pubspec.yaml").write_text("name: test_dart\nversion: 0.0.1")
        (project_dir / "flutter" / "pubspec.yaml").write_text("name: test_flutter\nversion: 0.0.1")
        
        # Change to project directory
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        try:
            # Setup logging - should work now with proper project structure
            logger = setup_logging(tool_name="test_tool", level="DEBUG")
            
            # Test different log levels
            logger.debug("Debug message", extra_data="debug_value")
            logger.info("Info message", status="active")
            logger.warning("Warning message", threshold=90)
            logger.error("Error message", code=404)
        finally:
            os.chdir(original_cwd)

def test_json_logging():
    """Test JSON output mode"""
    print("\n=== Testing JSON Logging ===")
    
    # Create a temporary project structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project structure
        project_dir = Path(tmpdir)
        (project_dir / "tooling").mkdir()
        (project_dir / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'")
        (project_dir / "dart").mkdir()
        (project_dir / "flutter").mkdir()
        (project_dir / "dart" / "pubspec.yaml").write_text("name: test_dart\nversion: 0.0.1")
        (project_dir / "flutter" / "pubspec.yaml").write_text("name: test_flutter\nversion: 0.0.1")
        
        # Change to project directory
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        try:
            logger = setup_logging(tool_name="test_json", level="INFO", json_output=True)
            logger.info("json_test", operation="test", result="success")
        finally:
            os.chdir(original_cwd)

def test_file_logging():
    """Test file logging"""
    print("\n=== Testing File Logging ===")
    
    # Create a temporary project structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project structure
        project_dir = Path(tmpdir)
        (project_dir / "tooling").mkdir()
        (project_dir / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'")
        (project_dir / "dart").mkdir()
        (project_dir / "flutter").mkdir()
        (project_dir / "dart" / "pubspec.yaml").write_text("name: test_dart\nversion: 0.0.1")
        (project_dir / "flutter" / "pubspec.yaml").write_text("name: test_flutter\nversion: 0.0.1")
        
        # Create log file in temp directory
        log_file = project_dir / "test.log"
        
        # Change to project directory
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        
        try:
            logger = setup_logging(tool_name="test_file", level="DEBUG", log_file=log_file)
            logger.info("file_logging_test", file_path=str(log_file))
            
            # Read and display log file
            print(f"\nLog file contents ({log_file}):")
            with open(log_file, 'r') as f:
                print(f.read())
        finally:
            os.chdir(original_cwd)

def test_cli_utils_integration():
    """Test cli_utils print functions with logging"""
    print("\n=== Testing Common Config Integration ===")
    
    # Use print functions that now integrate with logging
    print_header("Test Section")
    print_color(Colors.GREEN, "Success: Feature implemented")
    print_color(Colors.YELLOW, "Warning: Check configuration")
    print_color(Colors.RED, "Error: Missing dependency")
    print_color(Colors.BLUE, "Info: Processing complete")

def test_cli_utils():
    """Test CLI utilities"""
    print("\n=== Testing CLI Utils ===")
    
    # Setup CLI logging with proper args
    args = argparse.Namespace(verbose=True, debug=True, quiet=False, json=False)
    
    with patch('tooling.core.base_config.get_config') as mock_get_config:
        mock_config = MagicMock()
        mock_config.should_use_color = False
        mock_get_config.return_value = mock_config
        mock_config.log_level = MagicMock()
        mock_config.log_level.value = 'INFO'
        with patch('tooling.core.logging.load_config', return_value=get_mock_config()):
            logger = setup_cli_logging("test_cli", args)
            
            # Test print utilities
            print_info("This is an info message")
            print_success("Operation completed successfully")
            print_warning("This might cause issues")
            print_error("Something went wrong")
            
            # Test with logger
            logger.info("cli_test", operation="validate", result="passed")

def test_progress_logger():
    """Test progress logger context manager"""
    print("\n=== Testing Progress Logger ===")
    
    logger = get_logger("progress_test")
    
    with ProgressLogger(logger, "Database Migration") as progress:
        progress.update("Creating tables", count=5)
        progress.update("Migrating data", records=1000)
        progress.update("Building indexes", percent=75)

def test_log_context():
    """Test context variables"""
    print("\n=== Testing Log Context ===")
    
    logger = get_logger("context_test")
    
    with log_context(user_id=123, request_id="abc-def"):
        logger.info("processing_request", action="update")
        logger.info("request_complete", status="success")

def test_run_command_logging():
    """Test command execution with logging"""
    print("\n=== Testing Command Logging ===")
    
    # This will log the command execution
    code, stdout, stderr = run_command(['echo', 'Hello from logged command'])
    print(f"Command result: {stdout}")

def main():
    """Run all tests"""
    print("Testing Logging Integration")
    print("=" * 50)
    
    # Run all tests
    test_basic_logging()
    test_json_logging()
    test_file_logging()
    test_cli_utils_integration()
    test_cli_utils()
    test_progress_logger()
    test_log_context()
    test_run_command_logging()
    
    print("\n" + "=" * 50)
    print("All tests completed!")

if __name__ == "__main__":
    main() 