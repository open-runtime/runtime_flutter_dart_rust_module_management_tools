#!/usr/bin/env python3
"""
Unified setup tools for project initialization and configuration using Click and Rich.
Combines all setup functionality into one tool.
"""
import sys
import os
import subprocess
import platform
from pathlib import Path
from typing import Optional, List, Dict
import shutil

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box
from rich.tree import Tree

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.core.imports import setup_imports
setup_imports()

from tooling.core.logging import get_logger
from tooling.core.performance import track_performance
from tooling.cli.cli_utils import run_command

logger = get_logger(__name__)
console = Console()


class SetupTools:
    """Unified setup functionality"""
    
    def __init__(self):
        self.logger = logger
        self.platform = platform.system().lower()
    
    @track_performance("install_all")
    def install_all(
        self,
        skip_python: bool,
        skip_ai: bool,
        skip_permissions: bool,
        skip_api_keys: bool,
        dry_run: bool,
        upgrade: bool
    ) -> int:
        """Install all dependencies and tools"""
        try:
            console.print("[bold cyan]Installing all dependencies and tools[/bold cyan]\n")
            
            results = []
            
            # Install Python dependencies
            if not skip_python:
                with console.status("[bold blue]Installing Python dependencies..."):
                    result = self.install_python_deps(upgrade, dry_run)
                    results.append(("Python dependencies", result == 0))
            
            # Install AI tools
            if not skip_ai:
                with console.status("[bold blue]Installing AI tools..."):
                    result = self.install_ai_tools(skip_api_keys, dry_run)
                    results.append(("AI tools", result == 0))
            
            # Setup permissions
            if not skip_permissions:
                with console.status("[bold blue]Setting up permissions..."):
                    result = self.setup_permissions(False, dry_run)
                    results.append(("Permissions", result == 0))
            
            # Display summary
            self._display_summary(results)
            
            all_success = all(success for _, success in results)
            if all_success:
                console.print("\n[green]✓[/green] All setup completed successfully!")
                return 0
            else:
                console.print("\n[red]✗[/red] Some setup steps failed")
                return 1
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Setup failed: {e}", exc_info=True)
            return 1
    
    @track_performance("install_python_deps")
    def install_python_deps(self, upgrade: bool, dry_run: bool) -> int:
        """Install Python dependencies"""
        try:
            console.print("\n[bold cyan]Installing Python Dependencies[/bold cyan]")
            
            # Check for pip
            code, pip_version, _ = run_command([sys.executable, '-m', 'pip', '--version'])
            if code != 0:
                console.print("[red]✗[/red] pip is not installed")
                return 1
            
            pip_info = pip_version.split()[1] if pip_version else "unknown"
            console.print(f"[dim]Using pip {pip_info}[/dim]\n")
            
            # Install from requirements files
            req_files = [
                ('requirements.txt', 'Core dependencies'),
                ('requirements-dev.txt', 'Development dependencies'),
                ('requirements-shared.txt', 'Shared dependencies')
            ]
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                console=console
            ) as progress:
                for req_file, description in req_files:
                    if Path(req_file).exists():
                        task = progress.add_task(f"Installing {description}...", total=100)
                        
                        cmd = [sys.executable, '-m', 'pip', 'install', '-r', req_file]
                        if upgrade:
                            cmd.append('--upgrade')
                        
                        if dry_run:
                            console.print(f"[yellow]DRY RUN:[/yellow] Would run: {' '.join(cmd)}")
                            progress.update(task, completed=100)
                        else:
                            code, _, err = run_command(cmd)
                            progress.update(task, completed=100)
                            
                            if code != 0:
                                console.print(f"[red]✗[/red] Failed to install from {req_file}")
                                return 1
                            console.print(f"[green]✓[/green] Installed {description}")
            
            # Install the package itself in editable mode
            if Path('setup.py').exists() or Path('pyproject.toml').exists():
                console.print("\nInstalling package in editable mode...")
                
                if dry_run:
                    console.print("[yellow]DRY RUN:[/yellow] Would install package in editable mode")
                else:
                    code, _, err = run_command([sys.executable, '-m', 'pip', 'install', '-e', '.'])
                    if code != 0:
                        console.print(f"[red]✗[/red] Failed to install package: {err}")
                        return 1
                    console.print("[green]✓[/green] Package installed")
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error installing Python dependencies:[/red] {e}")
            logger.error(f"Python dependency installation failed: {e}", exc_info=True)
            return 1
    
    @track_performance("install_ai_tools")
    def install_ai_tools(self, skip_api_keys: bool, dry_run: bool) -> int:
        """Install AI tools (gemini-cli, etc.)"""
        try:
            console.print("\n[bold cyan]Installing AI Tools[/bold cyan]")
            
            # Check for npm (needed for gemini-cli)
            code, npm_version, _ = run_command(['npm', '--version'])
            if code != 0:
                console.print("[yellow]⚠[/yellow] npm not found - skipping gemini-cli installation")
                console.print("[dim]Install Node.js/npm to use gemini-cli[/dim]")
            else:
                npm_ver = npm_version.strip() if npm_version else "unknown"
                console.print(f"[dim]Using npm {npm_ver}[/dim]\n")
                
                # Install gemini-cli
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task("Installing gemini-cli...", total=None)
                    
                    cmd = ['npm', 'install', '-g', '@genkit-ai/cli']
                    if dry_run:
                        console.print(f"[yellow]DRY RUN:[/yellow] Would run: {' '.join(cmd)}")
                    else:
                        code, _, err = run_command(cmd)
                        if code != 0:
                            console.print(f"[yellow]⚠[/yellow] Failed to install gemini-cli: {err}")
                        else:
                            console.print("[green]✓[/green] gemini-cli installed")
                    
                    progress.update(task, completed=True)
            
            # Setup API keys
            if not skip_api_keys:
                self._setup_api_keys()
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error installing AI tools:[/red] {e}")
            logger.error(f"AI tools installation failed: {e}", exc_info=True)
            return 1
    
    @track_performance("setup_permissions")
    def setup_permissions(self, create_symlinks: bool, dry_run: bool) -> int:
        """Setup file permissions for CLI tools"""
        try:
            console.print("\n[bold cyan]Setting Up Permissions[/bold cyan]")
            
            # Find all Python CLI scripts
            cli_dir = Path('tooling/cli')
            if not cli_dir.exists():
                cli_dir = Path('cli')  # Try relative path
            
            if not cli_dir.exists():
                console.print("[yellow]⚠[/yellow] CLI directory not found")
                return 0
            
            # Make scripts executable
            scripts = list(cli_dir.glob('*.py'))
            scripts = [s for s in scripts if not s.name.startswith('_')]
            
            if scripts:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=console
                ) as progress:
                    task = progress.add_task("Making scripts executable...", total=len(scripts))
                    
                    for script in scripts:
                        if dry_run:
                            console.print(f"[yellow]DRY RUN:[/yellow] Would make {script.name} executable")
                        else:
                            script.chmod(script.stat().st_mode | 0o111)
                        progress.advance(task)
                
                console.print(f"[green]✓[/green] Made {len(scripts)} scripts executable")
            
            # Create symlinks if requested
            if create_symlinks:
                self._create_symlinks(cli_dir, dry_run)
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error setting up permissions:[/red] {e}")
            logger.error(f"Permission setup failed: {e}", exc_info=True)
            return 1
    
    def _setup_api_keys(self):
        """Help setup API keys"""
        console.print("\n[bold]API Key Setup[/bold]")
        
        # Check for existing keys
        keys_to_check = [
            ('GEMINI_API_KEY', 'Gemini API', 'https://makersuite.google.com/app/apikey'),
            ('OPENAI_API_KEY', 'OpenAI API', 'https://platform.openai.com/api-keys'),
            ('ANTHROPIC_API_KEY', 'Anthropic API', 'https://console.anthropic.com/settings/keys')
        ]
        
        table = Table(title="API Key Status", box=box.ROUNDED)
        table.add_column("API", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Environment Variable")
        
        missing_keys = []
        for key_name, display_name, url in keys_to_check:
            if os.environ.get(key_name):
                table.add_row(display_name, "[green]✓ Found[/green]", key_name)
            else:
                table.add_row(display_name, "[red]✗ Missing[/red]", key_name)
                missing_keys.append((key_name, display_name, url))
        
        console.print(table)
        
        if missing_keys:
            console.print("\n[yellow]To set missing API keys:[/yellow]")
            console.print("Add them to your shell profile (~/.bashrc, ~/.zshrc, etc.):\n")
            
            for key_name, display_name, url in missing_keys:
                console.print(f"  export {key_name}='your-key-here'")
                console.print(f"  [dim]Get your key from: {url}[/dim]\n")
    
    def _create_symlinks(self, cli_dir: Path, dry_run: bool):
        """Create symlinks for CLI tools"""
        console.print("\n[bold]Creating Symlinks[/bold]")
        
        # Determine user bin directory
        user_bin = Path.home() / '.local' / 'bin'
        if not user_bin.exists():
            if dry_run:
                console.print(f"[yellow]DRY RUN:[/yellow] Would create {user_bin}")
            else:
                user_bin.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]✓[/green] Created {user_bin}")
        
        # Create symlinks for unified tools
        tools = [
            ('version_tools.py', 'version_tools'),
            ('release_tools.py', 'release_tools'),
            ('commit_tools.py', 'commit_tools'),
            ('changelog_tools.py', 'changelog_tools'),
            ('pr_tools.py', 'pr_tools')
        ]
        
        created = 0
        for script_name, link_name in tools:
            script_path = cli_dir / script_name
            if script_path.exists():
                link_path = user_bin / link_name
                if dry_run:
                    console.print(f"[yellow]DRY RUN:[/yellow] Would create {link_name} -> {script_path.name}")
                else:
                    if link_path.exists():
                        link_path.unlink()
                    link_path.symlink_to(script_path.absolute())
                    created += 1
        
        if created > 0:
            console.print(f"\n[green]✓[/green] Created {created} symlinks in {user_bin}")
            console.print(f"\n[yellow]ℹ[/yellow] Add {user_bin} to your PATH to use the tools globally:")
            console.print(f"  export PATH=\"$PATH:{user_bin}\"")
    
    def _display_summary(self, results: List[tuple]):
        """Display installation summary"""
        console.print("\n[bold]Installation Summary[/bold]")
        
        table = Table(box=box.SIMPLE)
        table.add_column("Component", style="cyan")
        table.add_column("Status", justify="center")
        
        for component, success in results:
            status = "[green]✓ Success[/green]" if success else "[red]✗ Failed[/red]"
            table.add_row(component, status)
        
        console.print(table)


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.pass_context
def cli(ctx, debug):
    """Setup and installation tools for project initialization."""
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug


@cli.command('all')
@click.option('--skip-python', is_flag=True, help='Skip Python dependency installation')
@click.option('--skip-ai', is_flag=True, help='Skip AI tools installation')
@click.option('--skip-permissions', is_flag=True, help='Skip permission setup')
@click.option('--skip-api-keys', is_flag=True, help='Skip API key setup')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
@click.option('--upgrade', is_flag=True, help='Upgrade existing packages')
def install_all(skip_python, skip_ai, skip_permissions, skip_api_keys, dry_run, upgrade):
    """Install everything (Python deps, AI tools, permissions)."""
    tools = SetupTools()
    result = tools.install_all(skip_python, skip_ai, skip_permissions, skip_api_keys, dry_run, upgrade)
    sys.exit(result)


@cli.command('python')
@click.option('--upgrade', is_flag=True, help='Upgrade existing packages')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def install_python(upgrade, dry_run):
    """Install Python dependencies."""
    tools = SetupTools()
    result = tools.install_python_deps(upgrade, dry_run)
    sys.exit(result)


@cli.command('ai')
@click.option('--skip-api-keys', is_flag=True, help='Skip API key setup')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def install_ai(skip_api_keys, dry_run):
    """Install AI tools (gemini-cli, etc.)."""
    tools = SetupTools()
    result = tools.install_ai_tools(skip_api_keys, dry_run)
    sys.exit(result)


@cli.command('permissions')
@click.option('--create-symlinks', is_flag=True, help='Create symlinks in ~/.local/bin')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def setup_permissions(create_symlinks, dry_run):
    """Setup file permissions for CLI tools."""
    tools = SetupTools()
    result = tools.setup_permissions(create_symlinks, dry_run)
    sys.exit(result)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main() 