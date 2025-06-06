#!/usr/bin/env python3
"""
Runtime Tools - Unified CLI for Development Operations

A beautiful, interactive command-line interface for managing the
runtime_flutter_dart_rust_module_management_tools project.

Cross-platform support for macOS, Linux, and Windows.
"""
import click
import sys
import os
import platform
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from importlib import import_module

# Platform-specific setup
if platform.system() == 'Windows':
    # Enable ANSI colors on Windows
    import colorama
    colorama.init()

# Add tooling to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tooling.core.imports import setup_imports
setup_imports()

console = Console()

# Command registry
COMMANDS = {
    'commit': {
        'module': 'tooling.cli.commit_tools',
        'class': 'CommitTools',
        'description': '🚀 Generate smart commit messages with AI'
    },
    'release': {
        'module': 'tooling.cli.release_tools', 
        'class': 'ReleaseTools',
        'description': '📦 Manage releases and versioning'
    },
    'changelog': {
        'module': 'tooling.cli.changelog_tools',
        'class': 'ChangelogTools',
        'description': '📝 Sync and manage changelogs'
    },
    'version': {
        'module': 'tooling.cli.version_tools',
        'class': 'VersionTools',
        'description': '🏷️  Version management tools'
    },
    'pr': {
        'module': 'tooling.cli.pr_tools',
        'class': 'PRTools',
        'description': '🔀 Pull request management'
    },
    'setup': {
        'module': 'tooling.cli.setup_tools',
        'class': 'SetupTools',
        'description': '🔧 Setup and configuration'
    }
}

@click.group(invoke_without_command=True)
@click.option('--interactive', '-i', is_flag=True, help='Launch interactive mode')
@click.option('--version', '-v', is_flag=True, help='Show version')
@click.pass_context
def cli(ctx, interactive, version):
    """
    🚀 Runtime Tools - Your Development Assistant
    
    A unified interface for all development operations.
    """
    if ctx.invoked_subcommand is None:
        if version:
            show_version()
        elif interactive:
            launch_interactive_mode()
        else:
            show_welcome()

def show_welcome():
    """Show welcome screen with available commands"""
    # Create title panel
    title = Text("Runtime Tools", style="bold magenta")
    subtitle = Text("Your Development Assistant", style="italic cyan")
    
    title_panel = Panel(
        Text.from_markup(f"{title}\n{subtitle}", justify="center"),
        box=box.DOUBLE,
        padding=(1, 2),
        style="bright_blue"
    )
    console.print(title_panel)
    
    # Create commands table
    table = Table(
        title="Available Commands",
        box=box.ROUNDED,
        title_style="bold yellow",
        header_style="bold cyan"
    )
    
    table.add_column("Command", style="green", width=12)
    table.add_column("Description", style="white")
    table.add_column("Usage", style="dim")
    
    for cmd, info in COMMANDS.items():
        table.add_row(
            cmd,
            info['description'],
            f"rt {cmd} --help"
        )
    
    console.print(table)
    
    # Show tips
    console.print("\n[bold yellow]💡 Tips:[/bold yellow]")
    console.print("  • Use [cyan]rt -i[/cyan] for interactive mode")
    console.print("  • Use [cyan]rt <command> --help[/cyan] for command help")
    console.print("  • Install completions: [cyan]rt --install-completion[/cyan]")

def show_version():
    """Show version information"""
    import tooling
    version_info = Panel(
        f"[bold green]Runtime Tools[/bold green]\n"
        f"Version: [cyan]1.0.0[/cyan]\n"
        f"Python: [cyan]{sys.version.split()[0]}[/cyan]\n"
        f"Path: [dim]{Path(__file__).parent}[/dim]",
        title="Version Info",
        box=box.ROUNDED
    )
    console.print(version_info)

def launch_interactive_mode():
    """Launch interactive shell mode"""
    from tooling.cli.interactive_mode import InteractiveMode
    mode = InteractiveMode(console, COMMANDS)
    mode.run()

# Register all commands
@cli.command()
@click.pass_context
def commit(ctx):
    """🚀 Generate smart commit messages with AI"""
    run_command('commit', ctx.args)

@cli.command()
@click.pass_context
def release(ctx):
    """📦 Manage releases and versioning"""
    run_command('release', ctx.args)

@cli.command()
@click.pass_context
def changelog(ctx):
    """📝 Sync and manage changelogs"""
    run_command('changelog', ctx.args)

@cli.command()
@click.pass_context
def version(ctx):
    """🏷️ Version management tools"""
    run_command('version', ctx.args)

@cli.command()
@click.pass_context
def pr(ctx):
    """🔀 Pull request management"""
    run_command('pr', ctx.args)

@cli.command()
@click.pass_context
def setup(ctx):
    """🔧 Setup and configuration"""
    run_command('setup', ctx.args)

def run_command(command: str, args: list):
    """Run a command by importing and executing its module"""
    cmd_info = COMMANDS.get(command)
    if not cmd_info:
        console.print(f"[red]Unknown command: {command}[/red]")
        return 1
    
    try:
        # Import the module
        module = import_module(cmd_info['module'])
        
        # Get the class
        cmd_class = getattr(module, cmd_info['class'])
        
        # Create instance and run
        cmd_instance = cmd_class()
        
        # If it has a main method, use that
        if hasattr(cmd_instance, 'main'):
            return cmd_instance.main(args)
        else:
            # Otherwise try to run it directly
            return cmd_instance.run(args)
            
    except Exception as e:
        console.print(f"[red]Error running {command}: {e}[/red]")
        if os.environ.get('DEBUG'):
            console.print_exception()
        return 1

@cli.command()
def install_completion():
    """Install shell completion for bash/zsh/fish"""
    import subprocess
    
    shell = os.environ.get('SHELL', '').split('/')[-1]
    
    if shell == 'zsh':
        completion_path = Path.home() / '.zshrc'
        completion_cmd = 'eval "$(_RT_COMPLETE=zsh_source rt)"'
    elif shell == 'bash':
        completion_path = Path.home() / '.bashrc'
        completion_cmd = 'eval "$(_RT_COMPLETE=bash_source rt)"'
    elif shell == 'fish':
        completion_path = Path.home() / '.config/fish/completions/rt.fish'
        completion_cmd = '_RT_COMPLETE=fish_source rt'
        subprocess.run(completion_cmd, shell=True, capture_output=True)
        console.print(f"[green]✓ Installed fish completions to {completion_path}[/green]")
        return
    else:
        console.print(f"[yellow]Shell {shell} not supported. Supported: bash, zsh, fish[/yellow]")
        return
    
    # Add to shell config
    with open(completion_path, 'a') as f:
        f.write(f'\n# Runtime Tools completion\n{completion_cmd}\n')
    
    console.print(f"[green]✓ Added completion to {completion_path}[/green]")
    console.print(f"[yellow]Restart your shell or run: source {completion_path}[/yellow]")

if __name__ == '__main__':
    cli() 