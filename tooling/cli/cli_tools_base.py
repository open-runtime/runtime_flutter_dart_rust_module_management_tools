"""
Base class for all CLI tools.

Provides a standardized interface for creating CLI tools with:
- Rich UI integration
- Configuration management
- Error handling
- Plugin support
"""
import argparse
import sys
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import click

from tooling.core.config_manager import get_config, RuntimeConfig
from tooling.core.plugin_system import trigger_hook
from tooling.cli.cli_utils import (
    create_parser, handle_errors, setup_cli_logging,
    console, print_header, print_success, print_error
)


class CLITool(ABC):
    """Base class for all CLI tools"""
    
    def __init__(self):
        self.console = console
        self.config = get_config()
        self.logger = None
        self.args = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name for identification"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for help text"""
        pass
    
    @abstractmethod
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments to parser"""
        pass
    
    @abstractmethod
    def execute(self) -> int:
        """Execute the tool's main functionality"""
        pass
    
    def setup_parser(self) -> argparse.ArgumentParser:
        """Create and configure argument parser"""
        parser = create_parser(
            tool_name=self.name,
            description=self.description,
            epilog=self.get_epilog()
        )
        
        # Add tool-specific arguments
        self.add_arguments(parser)
        
        return parser
    
    def get_epilog(self) -> Optional[str]:
        """Get epilog text for help (can be overridden)"""
        return None
    
    def validate_args(self) -> bool:
        """Validate parsed arguments (can be overridden)"""
        return True
    
    def pre_execute(self) -> None:
        """Hook called before execute (can be overridden)"""
        # Trigger plugin hook
        trigger_hook(f'before_{self.name}', self.args)
    
    def post_execute(self, result: int) -> None:
        """Hook called after execute (can be overridden)"""
        # Trigger plugin hook
        trigger_hook(f'after_{self.name}', self.args, result)
    
    @handle_errors
    def main(self, argv: List[str] = None) -> int:
        """Main entry point for the tool"""
        # Parse arguments
        parser = self.setup_parser()
        self.args = parser.parse_args(argv)
        
        # Setup logging
        self.logger = setup_cli_logging(self.name, self.args)
        
        # Handle color settings
        if hasattr(self.args, 'no_color') and self.args.no_color:
            self.console.no_color = True
        
        # Validate arguments
        if not self.validate_args():
            return 1
        
        # Pre-execution hook
        self.pre_execute()
        
        # Execute main functionality
        result = self.execute()
        
        # Post-execution hook
        self.post_execute(result)
        
        return result
    
    def run(self, argv: List[str] = None) -> int:
        """Alias for main() for compatibility"""
        return self.main(argv)
    
    # Helper methods for common operations
    
    def show_banner(self, title: Optional[str] = None, subtitle: Optional[str] = None):
        """Show a banner with tool information"""
        if not title:
            title = self.name.replace('_', ' ').title()
        
        panel = Panel(
            f"[bold cyan]{title}[/bold cyan]\n" +
            (f"[dim]{subtitle or self.description}[/dim]" if subtitle or self.description else ""),
            box=box.DOUBLE,
            padding=(1, 2),
            style="bright_blue"
        )
        self.console.print(panel)
    
    def create_status_table(self, title: str = "Status") -> Table:
        """Create a standard status table"""
        table = Table(
            title=title,
            box=self.config.get_table_style(),
            title_style="bold cyan",
            header_style="bold"
        )
        return table
    
    def confirm_action(self, message: str, default: bool = False) -> bool:
        """Confirm an action with the user"""
        if self.config.development.dry_run:
            self.console.print(f"[yellow]DRY RUN: Would ask: {message}[/yellow]")
            return False
        
        from rich.prompt import Confirm
        return Confirm.ask(message, default=default)
    
    def select_option(self, message: str, choices: List[str], 
                     default: Optional[str] = None) -> str:
        """Let user select from options"""
        from tooling.cli.cli_utils import select_choice
        return select_choice(message, choices, default)
    
    def get_input(self, message: str, default: Optional[str] = None,
                  password: bool = False) -> str:
        """Get text input from user"""
        from rich.prompt import Prompt
        return Prompt.ask(message, default=default, password=password)
    
    def show_progress(self, message: str, task_func: Callable, *args, **kwargs):
        """Show progress while executing a task"""
        from rich.progress import Progress, SpinnerColumn, TextColumn
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=self.console
        ) as progress:
            task = progress.add_task(message, total=None)
            
            try:
                result = task_func(*args, **kwargs)
                progress.update(task, description=f"[green]✓ {message.replace('...', '')} complete[/green]")
                return result
            except Exception as e:
                progress.update(task, description=f"[red]✗ {message.replace('...', '')} failed[/red]")
                raise


class ClickCLITool(CLITool):
    """Base class for Click-based CLI tools"""
    
    @abstractmethod
    def get_click_command(self) -> click.Command:
        """Return the Click command for this tool"""
        pass
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Not used for Click tools"""
        pass
    
    def execute(self) -> int:
        """Execute Click command"""
        cmd = self.get_click_command()
        
        # Convert argparse args to Click context
        ctx = click.Context(cmd)
        
        # Execute
        try:
            cmd.invoke(ctx)
            return 0
        except click.ClickException as e:
            e.show()
            return e.exit_code
        except Exception as e:
            print_error(str(e))
            return 1


class InteractiveCLITool(CLITool):
    """Base class for interactive CLI tools"""
    
    def __init__(self):
        super().__init__()
        self.session = None
    
    @abstractmethod
    def get_commands(self) -> Dict[str, Callable]:
        """Return available interactive commands"""
        pass
    
    def setup_session(self):
        """Setup interactive session"""
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from pathlib import Path
        
        history_file = Path.home() / f'.{self.name}_history'
        self.session = PromptSession(
            history=FileHistory(str(history_file))
        )
    
    def execute(self) -> int:
        """Run interactive loop"""
        self.setup_session()
        self.show_banner()
        
        commands = self.get_commands()
        
        while True:
            try:
                # Get input
                command = self.session.prompt(f"{self.name}> ")
                
                if not command.strip():
                    continue
                
                # Parse command
                parts = command.strip().split()
                cmd_name = parts[0]
                cmd_args = parts[1:] if len(parts) > 1 else []
                
                # Handle built-in commands
                if cmd_name in ['exit', 'quit', 'q']:
                    break
                elif cmd_name in ['help', 'h', '?']:
                    self.show_help(commands)
                    continue
                
                # Handle tool commands
                if cmd_name in commands:
                    result = commands[cmd_name](*cmd_args)
                    if result is False:  # Allow commands to exit
                        break
                else:
                    self.console.print(f"[red]Unknown command: {cmd_name}[/red]")
                    self.console.print("[dim]Type 'help' for available commands[/dim]")
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'exit' to quit[/yellow]")
                continue
            except EOFError:
                break
        
        self.console.print("\n[cyan]Goodbye! 👋[/cyan]")
        return 0
    
    def show_help(self, commands: Dict[str, Callable]):
        """Show help for interactive commands"""
        table = Table(
            title="Available Commands",
            box=box.ROUNDED,
            title_style="bold yellow"
        )
        
        table.add_column("Command", style="green")
        table.add_column("Description", style="white")
        
        # Built-in commands
        table.add_row("help", "Show this help")
        table.add_row("exit", "Exit interactive mode")
        
        # Tool commands
        for cmd_name, cmd_func in commands.items():
            desc = cmd_func.__doc__ or "No description"
            table.add_row(cmd_name, desc.strip().split('\n')[0])
        
        self.console.print(table)


# Example implementation
class ExampleTool(CLITool):
    """Example tool showing how to use the base class"""
    
    @property
    def name(self) -> str:
        return "example"
    
    @property
    def description(self) -> str:
        return "Example tool demonstrating the base class"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            'name',
            nargs='?',
            default='World',
            help='Name to greet'
        )
        parser.add_argument(
            '--excited',
            action='store_true',
            help='Show excitement'
        )
    
    def execute(self) -> int:
        # Show banner
        self.show_banner()
        
        # Get name
        name = self.args.name
        
        # Show greeting
        greeting = f"Hello, {name}!"
        if self.args.excited:
            greeting += " 🎉"
        
        self.console.print(f"[cyan]{greeting}[/cyan]")
        
        # Show status
        if self.confirm_action("Show status table?", default=True):
            table = self.create_status_table()
            table.add_column("Property")
            table.add_column("Value")
            
            table.add_row("Name", name)
            table.add_row("Excited", "Yes" if self.args.excited else "No")
            table.add_row("Config Theme", self.config.ui.theme)
            
            self.console.print(table)
        
        print_success("Example completed!")
        return 0 