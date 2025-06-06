#!/usr/bin/env python3
"""
CLI utilities for common functionality across all CLI tools.

This module provides shared utilities for CLI tools including:
- Standardized argument parser creation
- Consistent error handling
- Output formatting utilities with Rich
- Common argument patterns
"""

import argparse
import sys
import os
import functools
from pathlib import Path
from typing import Optional, Any, Union, Callable, List, Tuple
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box
import random
import time

# Use new import helper
from tooling.core.imports import setup_imports
setup_imports()

from tooling.core.logging import setup_logging, get_logger, ProgressLogger
from tooling.core.base_config import get_config

# Create a shared console instance
console = Console()

class Colors:
    """ANSI color codes for terminal output (kept for backward compatibility)"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    GRAY = '\033[0;90m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color
    
    # Rich styles for new output
    HEADER = "bold magenta"
    SUCCESS = "bold green"
    ERROR = "bold red"
    WARNING = "bold yellow"
    INFO = "bold blue"
    
    _enabled = True
    
    @classmethod
    def disable(cls):
        """Disable color output"""
        cls._enabled = False
        console.no_color = True
    
    @classmethod
    def enable(cls):
        """Enable color output"""
        cls._enabled = True
        console.no_color = False


def create_parser(tool_name: str, description: str, epilog: Optional[str] = None) -> argparse.ArgumentParser:
    """Create a standardized argument parser with common arguments"""
    parser = argparse.ArgumentParser(
        prog=tool_name,
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add common arguments automatically
    add_common_arguments(parser)
    
    return parser


def handle_errors(func: Callable) -> Callable:
    """Decorator for consistent error handling across all CLI tools"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Operation cancelled by user[/yellow]")
            return 130  # Standard exit code for SIGINT
        except SystemExit as e:
            # Let SystemExit pass through (from argparse, etc.)
            raise
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            config = get_config()
            if config.debug or config.verbose:
                console.print_exception(show_locals=True)
            return 1
    return wrapper


def setup_cli_logging(
    tool_name: str,
    args: argparse.Namespace
) -> Any:
    """
    Setup logging for CLI tools based on parsed arguments.
    
    Args:
        tool_name: Name of the tool for logging context
        args: Parsed arguments containing verbose/debug/quiet/json flags
        
    Returns:
        Configured logger instance
    """
    # Determine log level from arguments
    if hasattr(args, 'quiet') and args.quiet:
        level = "ERROR"
    elif hasattr(args, 'debug') and args.debug:
        level = "DEBUG"
    elif hasattr(args, 'verbose') and args.verbose:
        level = "INFO"
    else:
        config = get_config()
        level = config.log_level.value
    
    # Setup logging
    logger = setup_logging(
        tool_name=tool_name,
        level=level,
        json_output=getattr(args, 'json', False)
    )
    
    logger.debug(f"Initialized {tool_name} with log level: {level}")
    return logger


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """
    Add common arguments to a CLI tool parser.
    
    Args:
        parser: ArgumentParser to add arguments to
    """
    # Output options
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
    output_group.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    # Configuration options
    config_group = parser.add_argument_group('configuration')
    config_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    config_group.add_argument(
        '--config',
        type=str,
        help='Path to configuration file'
    )


def add_git_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common git-related arguments"""
    git_group = parser.add_argument_group('git options')
    git_group.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip git hooks'
    )
    git_group.add_argument(
        '--staged',
        action='store_true',
        help='Only consider staged files'
    )


def add_ai_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common AI-related arguments"""
    ai_group = parser.add_argument_group('AI options')
    ai_group.add_argument(
        '--model',
        type=str,
        help='Override the AI model to use'
    )
    ai_group.add_argument(
        '--max-tokens',
        type=int,
        help='Maximum tokens for AI response'
    )
    ai_group.add_argument(
        '--temperature',
        type=float,
        help='Temperature for AI generation (0.0-1.0)'
    )


# Legacy output functions (kept for backward compatibility)
def print_color(color: str, text: str) -> None:
    """Print colored text to console (legacy function - use console.print instead)"""
    if Colors._enabled and color.startswith('\033'):
        # Old ANSI style
        print(f"{color}{text}{Colors.NC}")
    else:
        # New Rich style
        console.print(text, style=color)


def print_error(message: str) -> None:
    """Print error message with Rich formatting"""
    # Rich console doesn't support file parameter, use stderr console
    error_console = Console(stderr=True)
    error_console.print(f"[red]✗ {message}[/red]")


def print_success(message: str) -> None:
    """Print success message with Rich formatting"""
    console.print(f"[green]✓ {message}[/green]")


def print_warning(message: str) -> None:
    """Print warning message with Rich formatting"""
    console.print(f"[yellow]⚠ {message}[/yellow]")


def print_info(message: str) -> None:
    """Print info message with Rich formatting"""
    console.print(f"[blue]ℹ {message}[/blue]")


def print_header(title: str, style: str = "bold magenta") -> None:
    """Print a formatted header with Rich"""
    console.rule(f"[{style}]{title}[/{style}]", style=style)


def print_section(title: str, content: str, style: str = "blue") -> None:
    """Print a section with title and content in a panel"""
    panel = Panel(
        content,
        title=f"[{style}]{title}[/{style}]",
        border_style=style,
        padding=(1, 2)
    )
    console.print(panel)


# New Rich-based output functions
def create_table(title: str, columns: List[Tuple[str, dict]] = None) -> Table:
    """
    Create a Rich table with standard styling.
    
    Args:
        title: Table title
        columns: List of (name, kwargs) tuples for columns
        
    Returns:
        Configured Table instance
    """
    table = Table(
        title=title,
        box=box.ROUNDED,
        title_style="bold cyan",
        header_style="bold"
    )
    
    if columns:
        for name, kwargs in columns:
            table.add_column(name, **kwargs)
    
    return table


def show_diff(old_text: str, new_text: str, title: str = "Changes") -> None:
    """Show a diff between old and new text with syntax highlighting"""
    from rich.syntax import Syntax
    
    # Create diff
    import difflib
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile="before",
        tofile="after"
    )
    
    diff_text = ''.join(diff)
    
    # Show with syntax highlighting
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
    
    panel = Panel(
        syntax,
        title=f"[yellow]{title}[/yellow]",
        border_style="yellow"
    )
    console.print(panel)


def confirm(prompt: str, default: bool = False) -> bool:
    """
    Interactive confirmation prompt with Rich.
    
    Args:
        prompt: Question to ask
        default: Default answer if user just presses Enter
        
    Returns:
        True if user confirmed, False otherwise
    """
    from rich.prompt import Confirm
    
    # Check if in dry-run mode
    config = get_config()
    if config.dry_run:
        console.print(f"[dim]DRY RUN: Would ask: {prompt}[/dim]")
        return False
    
    return Confirm.ask(prompt, default=default)


def prompt(message: str, default: Optional[str] = None, password: bool = False) -> str:
    """
    Interactive text prompt with Rich.
    
    Args:
        message: Prompt message
        default: Default value
        password: Hide input for passwords
        
    Returns:
        User input
    """
    from rich.prompt import Prompt
    return Prompt.ask(message, default=default, password=password)


def select_choice(message: str, choices: List[str], default: Optional[str] = None) -> str:
    """
    Interactive choice selection with Rich.
    
    Args:
        message: Prompt message
        choices: List of choices
        default: Default choice
        
    Returns:
        Selected choice
    """
    from rich.prompt import Prompt
    
    # Show choices
    console.print(f"\n[cyan]{message}[/cyan]")
    for i, choice in enumerate(choices, 1):
        console.print(f"  {i}. {choice}")
    
    # Get selection
    while True:
        selection = Prompt.ask("\nSelect", default=str(choices.index(default) + 1) if default else None)
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except (ValueError, IndexError):
            pass
        console.print("[red]Invalid selection, please try again[/red]")


# Backward compatibility helpers
def confirm_action(prompt: str, default: bool = False) -> bool:
    """Legacy function - use confirm() instead"""
    return confirm(prompt, default)


def select_choice_legacy(message: str, choices: List[str]) -> Optional[str]:
    """Legacy function - use select_choice() instead"""
    try:
        return select_choice(message, choices)
    except KeyboardInterrupt:
        return None


class CLIProgressLogger(ProgressLogger):
    """
    Enhanced progress logger for CLI tools with Rich visual feedback.
    """
    
    def __init__(self, logger: Any, task_name: str, show_progress: bool = True):
        super().__init__(logger, task_name)
        config = get_config()
        self.show_progress = show_progress and not config.debug
        self.progress = None
        self.task_id = None
        
    def __enter__(self):
        if self.show_progress:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeRemainingColumn(),
                console=console,
                transient=True
            )
            self.progress.__enter__()
            self.task_id = self.progress.add_task(f"{self.task_name}...", total=None)
        return super().__enter__()
        
    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        if self.progress:
            if exc_type:
                self.progress.update(self.task_id, description=f"[red]✗ {self.task_name} failed[/red]")
            else:
                self.progress.update(self.task_id, description=f"[green]✓ {self.task_name} complete[/green]")
            self.progress.stop()
            self.progress.__exit__(None, None, None)
        super().__exit__(exc_type, exc_val, exc_tb)
    
    def update(self, completed: int, total: int, message: str = ""):
        """Update progress bar"""
        if self.progress and self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=completed,
                total=total,
                description=message or self.task_name
            )


def run_command(cmd: List[str], capture_output: bool = True, timeout: int = 30, 
               show_progress: bool = True) -> Tuple[int, str, str]:
    """Run command with timeout and optional progress display
    
    Args:
        cmd: Command and arguments as list
        capture_output: Whether to capture stdout/stderr
        timeout: Command timeout in seconds
        show_progress: Whether to show progress indicator
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    import subprocess
    
    if show_progress and not capture_output:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console
        ) as progress:
            task = progress.add_task(f"Running {cmd[0]}...", total=None)
            
            try:
                result = subprocess.run(cmd, timeout=timeout)
                if result.returncode == 0:
                    progress.update(task, description=f"[green]✓ {cmd[0]} complete[/green]")
                else:
                    progress.update(task, description=f"[red]✗ {cmd[0]} failed[/red]")
                return result.returncode, "", ""
            except subprocess.TimeoutExpired:
                progress.update(task, description=f"[red]✗ {cmd[0]} timed out[/red]")
                return -1, "", f"Command timed out after {timeout} seconds"
            except FileNotFoundError:
                progress.update(task, description=f"[red]✗ {cmd[0]} not found[/red]")
                return -1, "", f"Command not found: {cmd[0]}"
            except Exception as e:
                progress.update(task, description=f"[red]✗ {cmd[0]} error[/red]")
                return -1, "", str(e)
    else:
        # Original behavior for capture_output
        try:
            if capture_output:
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=timeout
                )
                return result.returncode, result.stdout.strip(), result.stderr.strip()
            else:
                result = subprocess.run(cmd, timeout=timeout)
                return result.returncode, "", ""
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout} seconds"
        except FileNotFoundError:
            return -1, "", f"Command not found: {cmd[0]}"
        except Exception as e:
            return -1, "", str(e)


# Animation utilities for fun user experience
def show_spinner(message: str, duration: float = 2.0):
    """Show a spinner animation for a specified duration"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console
    ) as progress:
        task = progress.add_task(message, total=None)
        time.sleep(duration)
        progress.update(task, description=f"[green]✓ {message.replace('...', '')} complete[/green]")


def show_countdown(message: str, seconds: int = 3):
    """Show a countdown timer"""
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task(message, total=seconds)
        for i in range(seconds):
            progress.update(task, completed=i)
            time.sleep(1)
        progress.update(task, completed=seconds, description="[green]✓ Ready![/green]")


# Export all functions
__all__ = [
    'Colors',
    'console',
    'create_parser',
    'handle_errors',
    'setup_cli_logging',
    'add_common_arguments',
    'print_color',
    'print_error',
    'print_success',
    'print_warning',
    'print_info',
    'print_header',
    'print_section',
    'create_table',
    'show_diff',
    'confirm',
    'prompt',
    'select_choice',
    'CLIProgressLogger',
    'run_command',
    'show_spinner',
    'show_countdown',
]

# Example usage
if __name__ == "__main__":
    # Test the utilities
    parser = create_parser("test_tool", "Test CLI utilities")
    args = parser.parse_args()
    
    logger = setup_cli_logging("test_tool", args)
    
    print_header("CLI Utilities Test")
    print_info("This is an info message")
    print_success("This is a success message")
    print_warning("This is a warning message")
    print_error("This is an error message")
    
    print_section("Testing Progress Logger")
    with CLIProgressLogger(logger, "Processing data"):
        time.sleep(1)
    
    logger.info("Test completed")