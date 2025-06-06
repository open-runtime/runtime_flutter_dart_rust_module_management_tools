"""
Interactive mode for Runtime Tools.

Provides a rich, interactive shell experience with:
- Command completion
- History navigation
- Smart suggestions
- Beautiful output
"""
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from pathlib import Path
import os
import sys
import shlex
from typing import Dict, Any, List
import asyncio
from datetime import datetime

# Command suggestions based on context
SMART_SUGGESTIONS = {
    'start': [
        ('commit', 'Create a new commit with AI-generated message'),
        ('status', 'Check repository status'),
        ('setup', 'Configure your environment')
    ],
    'after_commit': [
        ('push', 'Push your changes to remote'),
        ('pr create', 'Create a pull request'),
        ('changelog sync', 'Update changelogs')
    ],
    'after_changes': [
        ('commit', 'Commit your changes'),
        ('diff', 'Review changes'),
        ('test', 'Run tests')
    ],
    'before_release': [
        ('version check', 'Check version consistency'),
        ('changelog validate', 'Validate changelog entries'),
        ('release check', 'Run pre-release checks')
    ]
}

class SmartCompleter(Completer):
    """Smart command completer with context awareness"""
    
    def __init__(self, commands: Dict[str, Any]):
        self.commands = commands
        self.base_commands = list(commands.keys())
        self.sub_commands = {
            'commit': ['generate', 'quick', 'detailed', '--help'],
            'release': ['check', 'notes', 'create', 'retag', '--help'],
            'changelog': ['validate', 'analyze', 'sync', '--help'],
            'version': ['get-tag', 'update', 'prepare-patch', 'push-patch', '--help'],
            'pr': ['create', 'open', 'list', '--help'],
            'setup': ['all', 'python', 'ai', 'permissions', '--help']
        }
    
    def get_completions(self, document, complete_event):
        """Get context-aware completions"""
        text = document.text_before_cursor
        words = text.split()
        
        if not words:
            # Show base commands
            for cmd in self.base_commands:
                yield Completion(cmd, start_position=0, 
                               display_meta=self.commands[cmd]['description'])
        elif len(words) == 1:
            # Complete base command
            for cmd in self.base_commands:
                if cmd.startswith(words[0]):
                    yield Completion(cmd, start_position=-len(words[0]),
                                   display_meta=self.commands[cmd]['description'])
        elif len(words) == 2 and words[0] in self.sub_commands:
            # Complete sub-command
            for sub in self.sub_commands[words[0]]:
                if sub.startswith(words[1]):
                    yield Completion(sub, start_position=-len(words[1]))

class InteractiveMode:
    """Interactive shell mode for Runtime Tools"""
    
    def __init__(self, console: Console, commands: Dict[str, Any]):
        self.console = console
        self.commands = commands
        self.history_file = Path.home() / '.runtime_tools_history'
        self.context = 'start'
        self.last_command = None
        
        # Create prompt session with history
        self.session = PromptSession(
            history=FileHistory(str(self.history_file)),
            completer=SmartCompleter(commands),
            style=self._create_style()
        )
    
    def _create_style(self):
        """Create custom style for prompt"""
        return Style.from_dict({
            'prompt': '#00aa00 bold',
            'path': '#0087ff',
            'branch': '#ff6600',
            'time': '#666666',
        })
    
    def _get_prompt(self):
        """Get dynamic prompt with git info"""
        try:
            # Get current branch
            import subprocess
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                  capture_output=True, text=True)
            branch = result.stdout.strip() if result.returncode == 0 else 'main'
            
            # Get current time
            time_str = datetime.now().strftime('%H:%M')
            
            # Build prompt
            return HTML(
                f'<time>{time_str}</time> '
                f'<prompt>runtime</prompt> '
                f'<branch>[{branch}]</branch> '
                f'<prompt>❯</prompt> '
            )
        except:
            return HTML('<prompt>runtime ❯</prompt> ')
    
    def _show_suggestions(self):
        """Show smart suggestions based on context"""
        suggestions = SMART_SUGGESTIONS.get(self.context, [])
        if suggestions:
            table = Table(box=None, show_header=False, padding=(0, 2))
            table.add_column("Command", style="cyan")
            table.add_column("Description", style="dim")
            
            for cmd, desc in suggestions[:3]:
                table.add_row(f"💡 {cmd}", desc)
            
            self.console.print("\n[yellow]Suggested commands:[/yellow]")
            self.console.print(table)
    
    def _update_context(self, command: str):
        """Update context based on executed command"""
        if command.startswith('commit'):
            self.context = 'after_commit'
        elif command.startswith(('add', 'modify', 'delete')):
            self.context = 'after_changes'
        elif command.startswith('release'):
            self.context = 'before_release'
        elif command in ['status', 'st']:
            # Check if there are changes
            import subprocess
            result = subprocess.run(['git', 'status', '--porcelain'], 
                                  capture_output=True, text=True)
            if result.stdout.strip():
                self.context = 'after_changes'
    
    async def _execute_command(self, command: str):
        """Execute a command with progress indication"""
        parts = shlex.split(command)
        if not parts:
            return
        
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        # Handle special commands
        if cmd in ['exit', 'quit', 'q']:
            return False
        elif cmd in ['help', 'h', '?']:
            self._show_help()
            return True
        elif cmd == 'clear':
            self.console.clear()
            return True
        elif cmd == 'status':
            self._show_status()
            return True
        
        # Handle runtime commands
        if cmd in self.commands:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
                console=self.console
            ) as progress:
                task = progress.add_task(f"Running {cmd}...", total=None)
                
                try:
                    # Import and run the command
                    from importlib import import_module
                    module = import_module(self.commands[cmd]['module'])
                    cmd_class = getattr(module, self.commands[cmd]['class'])
                    instance = cmd_class()
                    
                    # Run with args
                    if hasattr(instance, 'main'):
                        result = instance.main(args)
                    else:
                        result = instance.run(args)
                    
                    if result == 0:
                        self.console.print(f"[green]✓ {cmd} completed successfully[/green]")
                    else:
                        self.console.print(f"[red]✗ {cmd} failed with code {result}[/red]")
                        
                except Exception as e:
                    self.console.print(f"[red]Error: {e}[/red]")
                    if os.environ.get('DEBUG'):
                        self.console.print_exception()
                
                progress.update(task, completed=True)
        else:
            # Try to run as shell command
            try:
                import subprocess
                result = subprocess.run(command, shell=True, text=True)
                if result.returncode != 0:
                    self.console.print(f"[yellow]Command exited with code {result.returncode}[/yellow]")
            except Exception as e:
                self.console.print(f"[red]Unknown command: {cmd}[/red]")
                self.console.print("[dim]Type 'help' for available commands[/dim]")
        
        return True
    
    def _show_help(self):
        """Show interactive help"""
        help_panel = Panel(
            Markdown("""
# Runtime Tools Interactive Mode

## Available Commands

### Runtime Commands
- **commit** - Generate AI-powered commit messages
- **release** - Manage releases and versioning  
- **changelog** - Sync and manage changelogs
- **version** - Version management tools
- **pr** - Pull request management
- **setup** - Setup and configuration

### Shell Commands
- **status** - Show repository status
- **clear** - Clear the screen
- **help** - Show this help
- **exit/quit** - Exit interactive mode

### Tips
- Use TAB for command completion
- Use ↑/↓ for command history
- Commands support standard shell syntax
- Set DEBUG=1 for verbose output
            """),
            title="Help",
            border_style="blue"
        )
        self.console.print(help_panel)
    
    def _show_status(self):
        """Show repository status with rich formatting"""
        import subprocess
        
        # Get git status
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True)
        
        if not result.stdout.strip():
            self.console.print("[green]✓ Working directory clean[/green]")
            return
        
        # Parse status
        staged = []
        modified = []
        untracked = []
        
        for line in result.stdout.strip().split('\n'):
            if line.startswith('A '):
                staged.append(line[3:])
            elif line.startswith('M '):
                modified.append(line[3:])
            elif line.startswith('??'):
                untracked.append(line[3:])
        
        # Show status table
        table = Table(title="Repository Status", box=None)
        table.add_column("Type", style="bold")
        table.add_column("Files", style="cyan")
        
        if staged:
            table.add_row("Staged", "\n".join(staged))
        if modified:
            table.add_row("Modified", "\n".join(modified))
        if untracked:
            table.add_row("Untracked", "\n".join(untracked))
        
        self.console.print(table)
    
    def run(self):
        """Run the interactive mode"""
        # Show welcome
        welcome = Panel(
            "[bold cyan]Welcome to Runtime Tools Interactive Mode![/bold cyan]\n\n"
            "Type [green]help[/green] for available commands\n"
            "Type [red]exit[/red] to quit",
            box=Panel.ASCII,
            padding=(1, 2)
        )
        self.console.print(welcome)
        
        # Show initial suggestions
        self._show_suggestions()
        
        # Main loop
        while True:
            try:
                # Get input
                command = self.session.prompt(self._get_prompt())
                
                if not command.strip():
                    continue
                
                # Execute command
                result = asyncio.run(self._execute_command(command.strip()))
                
                if result is False:
                    break
                
                # Update context
                self._update_context(command)
                self.last_command = command
                
                # Show suggestions if appropriate
                if self.context != 'start':
                    self._show_suggestions()
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'exit' to quit[/yellow]")
                continue
            except EOFError:
                break
        
        # Goodbye
        self.console.print("\n[cyan]Thanks for using Runtime Tools! 👋[/cyan]") 