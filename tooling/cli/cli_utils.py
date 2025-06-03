#!/usr/bin/env python3
"""
CLI utilities for common functionality across all CLI tools.

This module provides shared utilities for CLI tools including:
- Logging setup
- Output formatting
- Common argument parsing

Author: Tsavo Knott, 2025
License: MIT
"""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional, Any

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tooling.core.logging import setup_logging, get_logger, ProgressLogger
    from tooling.core.common_config import Colors
except ImportError:
    from core.logging import setup_logging, get_logger, ProgressLogger
    from core.common_config import Colors


def setup_cli_logging(
    tool_name: str,
    verbose: bool = False,
    debug: bool = False,
    quiet: bool = False,
    json_output: bool = False
) -> Any:
    """
    Setup logging for CLI tools with common configuration.
    
    Args:
        tool_name: Name of the tool for logging context
        verbose: Enable verbose output (INFO level)
        debug: Enable debug output (DEBUG level)
        quiet: Suppress non-error output (ERROR level)
        json_output: Output logs in JSON format
        
    Returns:
        Configured logger instance
    """
    # Determine log level
    if quiet:
        level = "ERROR"
    elif debug:
        level = "DEBUG"
    elif verbose:
        level = "INFO"
    else:
        level = "WARNING"
    
    # Setup logging
    logger = setup_logging(
        tool_name=tool_name,
        level=level,
        json_output=json_output
    )
    
    logger.debug(f"Initialized {tool_name} with log level: {level}")
    return logger


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add common arguments to a CLI tool parser.
    
    Args:
        parser: ArgumentParser to add arguments to
    """
    output_group = parser.add_argument_group('output options')
    output_group.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    output_group.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug output (includes verbose)'
    )
    output_group.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress non-error output'
    )
    output_group.add_argument(
        '--json',
        action='store_true',
        help='Output logs in JSON format'
    )


def print_info(message: str, color: str = Colors.BLUE) -> None:
    """Print an info message with color."""
    print(f"{color}{message}{Colors.NC}")


def print_success(message: str) -> None:
    """Print a success message in green."""
    print(f"{Colors.GREEN}✓ {message}{Colors.NC}")


def print_error(message: str) -> None:
    """Print an error message in red."""
    print(f"{Colors.RED}✗ {message}{Colors.NC}", file=sys.stderr)


def print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.NC}")


def print_header(title: str, width: int = 60) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.PURPLE}{'=' * width}{Colors.NC}")
    print(f"{Colors.PURPLE}{title.center(width)}{Colors.NC}")
    print(f"{Colors.PURPLE}{'=' * width}{Colors.NC}\n")


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{Colors.YELLOW}▶ {title}{Colors.NC}")
    print(f"{Colors.GRAY}{'─' * (len(title) + 2)}{Colors.NC}")


class CLIProgressLogger(ProgressLogger):
    """
    Enhanced progress logger for CLI tools with visual feedback.
    """
    
    def __init__(self, logger: Any, task_name: str, show_progress: bool = True):
        super().__init__(logger, task_name)
        self.show_progress = show_progress
        
    def __enter__(self):
        if self.show_progress:
            print(f"{Colors.BLUE}⏳ {self.task_name}...{Colors.NC}", end='', flush=True)
        return super().__enter__()
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.show_progress:
            if exc_type:
                print(f"\r{Colors.RED}✗ {self.task_name} failed{Colors.NC}")
            else:
                print(f"\r{Colors.GREEN}✓ {self.task_name} complete{Colors.NC}")
        return super().__exit__(exc_type, exc_val, exc_tb)


def confirm_action(prompt: str, default: bool = False) -> bool:
    """
    Ask user for confirmation.
    
    Args:
        prompt: The question to ask
        default: Default value if user just presses enter
        
    Returns:
        True if user confirms, False otherwise
    """
    if default:
        prompt += " [Y/n]: "
        valid_yes = ['y', 'yes', '']
    else:
        prompt += " [y/N]: "
        valid_yes = ['y', 'yes']
    
    response = input(prompt).lower().strip()
    return response in valid_yes


# Example usage
if __name__ == "__main__":
    # Test the utilities
    parser = argparse.ArgumentParser(description="Test CLI utilities")
    add_common_arguments(parser)
    args = parser.parse_args()
    
    logger = setup_cli_logging(
        "test_tool",
        verbose=args.verbose,
        debug=args.debug,
        quiet=args.quiet,
        json_output=args.json
    )
    
    print_header("CLI Utilities Test")
    print_info("This is an info message")
    print_success("This is a success message")
    print_warning("This is a warning message")
    print_error("This is an error message")
    
    print_section("Testing Progress Logger")
    with CLIProgressLogger(logger, "Processing data"):
        import time
        time.sleep(1)
    
    logger.info("Test completed")