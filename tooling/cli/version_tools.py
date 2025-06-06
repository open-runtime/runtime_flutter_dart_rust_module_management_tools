#!/usr/bin/env python3
"""
Unified version management tools using Click and Rich.
"""
import sys
import os
from pathlib import Path
from typing import Optional, Tuple, List
import subprocess
import re

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich import box

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.core.imports import setup_imports
setup_imports()

from tooling.core.base_config import get_config
from tooling.utils.git_utils import (
    check_git_repo, get_current_branch, get_latest_tag,
    create_tag, push_tag, get_commit_messages_since_tag
)
from tooling.utils.version_utils import (
    parse_version_tuple as parse_version, format_version, increment_version,
    get_version_from_file, update_version_in_file
)
from tooling.core.logging import get_logger
from tooling.core.performance import track_performance

logger = get_logger(__name__)
console = Console()


class VersionTools:
    """Unified version management functionality"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logger
    
    @track_performance("get_patch_tag")
    def get_patch_tag(self, prefix: str, dry_run: bool) -> int:
        """Get the next patch version tag"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            # Get latest tag
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Finding latest tag...", total=None)
                latest_tag = get_latest_tag(prefix)
                progress.update(task, completed=True)
            
            if not latest_tag:
                console.print(f"[yellow]⚠[/yellow] No tags found with prefix '{prefix}'")
                console.print(f"[cyan]Next tag:[/cyan] {prefix}0.0.1")
                return 0
            
            # Parse version
            version_str = latest_tag.replace(prefix, '')
            major, minor, patch = parse_version(version_str)
            
            # Increment patch
            new_patch = patch + 1
            new_tag = f"{prefix}{major}.{minor}.{new_patch}"
            
            # Display info
            table = Table(title="Version Information", box=box.ROUNDED)
            table.add_column("Item", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Current Tag", latest_tag)
            table.add_row("Next Tag", new_tag)
            table.add_row("Version", f"{major}.{minor}.{patch} → {major}.{minor}.{new_patch}")
            console.print(table)
            
            if dry_run:
                console.print("\n[yellow]DRY RUN:[/yellow] Would output:", new_tag)
            else:
                print(new_tag)  # For script compatibility
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Failed to get patch tag: {e}", exc_info=True)
            return 1
    
    @track_performance("update_version")
    def update_version(
        self,
        version: Optional[str],
        major: bool,
        minor: bool,
        patch: bool,
        files: List[str],
        dry_run: bool
    ) -> int:
        """Update version in files"""
        try:
            # Determine version update type
            if sum([bool(version), major, minor, patch]) != 1:
                console.print("[red]✗[/red] Specify exactly one of: --version, --major, --minor, --patch")
                return 1
            
            # Process each file
            updated_files = []
            errors = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                for file_path in files:
                    task = progress.add_task(f"Processing {file_path}...", total=None)
                    
                    try:
                        # Get current version
                        current = get_version_from_file(file_path)
                        if not current:
                            errors.append((file_path, "No version found"))
                            progress.update(task, completed=True)
                            continue
                        
                        # Calculate new version
                        if version:
                            new_version = version
                        else:
                            curr_major, curr_minor, curr_patch = parse_version(current)
                            if major:
                                new_version = f"{curr_major + 1}.0.0"
                            elif minor:
                                new_version = f"{curr_major}.{curr_minor + 1}.0"
                            else:  # patch
                                new_version = f"{curr_major}.{curr_minor}.{curr_patch + 1}"
                        
                        # Update file
                        if not dry_run:
                            update_version_in_file(file_path, new_version)
                        
                        updated_files.append((file_path, current, new_version))
                        progress.update(task, completed=True)
                        
                    except Exception as e:
                        errors.append((file_path, str(e)))
                        progress.update(task, completed=True)
            
            # Display results
            if updated_files:
                table = Table(title="Updated Versions", box=box.ROUNDED)
                table.add_column("File", style="cyan")
                table.add_column("Old Version", style="yellow")
                table.add_column("New Version", style="green")
                
                for file_path, old_ver, new_ver in updated_files:
                    table.add_row(file_path, old_ver, new_ver)
                
                console.print(table)
                
                if dry_run:
                    console.print("\n[yellow]DRY RUN:[/yellow] No files were actually updated")
                else:
                    console.print(f"\n[green]✓[/green] Updated {len(updated_files)} files")
            
            if errors:
                console.print("\n[red]Errors:[/red]")
                for file_path, error in errors:
                    console.print(f"  • {file_path}: {error}")
                return 1
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Failed to update version: {e}", exc_info=True)
            return 1
    
    @track_performance("prepare_patch")
    def prepare_patch(
        self,
        prefix: str,
        message: Optional[str],
        push: bool,
        dry_run: bool
    ) -> int:
        """Prepare a new patch release"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            # Get next version
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Calculating next version...", total=None)
                
                latest_tag = get_latest_tag(prefix)
                if not latest_tag:
                    new_tag = f"{prefix}0.0.1"
                    major, minor, patch = 0, 0, 1
                else:
                    version_str = latest_tag.replace(prefix, '')
                    major, minor, patch = parse_version(version_str)
                    patch += 1
                    new_tag = f"{prefix}{major}.{minor}.{patch}"
                
                progress.update(task, completed=True)
            
            # Get commit messages since last tag
            if latest_tag:
                commits = get_commit_messages_since_tag(latest_tag)
                if commits:
                    console.print(f"\n[cyan]Commits since {latest_tag}:[/cyan]")
                    for commit in commits[:10]:  # Show first 10
                        console.print(f"  • {commit}")
                    if len(commits) > 10:
                        console.print(f"  ... and {len(commits) - 10} more")
            
            # Prepare tag message
            if not message:
                message = f"Release {new_tag}"
                if latest_tag and commits:
                    message += f"\n\nChanges since {latest_tag}:\n"
                    message += "\n".join(f"- {c}" for c in commits[:20])
            
            # Display plan
            panel = Panel(
                f"[green]New Tag:[/green] {new_tag}\n"
                f"[green]Message:[/green] {message.split(chr(10))[0]}...",
                title="Patch Release Plan",
                border_style="green"
            )
            console.print(panel)
            
            if dry_run:
                console.print("\n[yellow]DRY RUN:[/yellow] Would create tag", new_tag)
                return 0
            
            # Create tag
            if Confirm.ask("\nCreate this tag?"):
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task("Creating tag...", total=None)
                    create_tag(new_tag, message)
                    progress.update(task, completed=True)
                
                console.print(f"[green]✓[/green] Created tag {new_tag}")
                
                if push:
                    task = progress.add_task("Pushing tag...", total=None)
                    push_tag(new_tag)
                    progress.update(task, completed=True)
                    console.print(f"[green]✓[/green] Pushed tag to remote")
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Failed to prepare patch: {e}", exc_info=True)
            return 1
    
    @track_performance("push_patch")
    def push_patch(self, tag: Optional[str], prefix: str, force: bool, dry_run: bool) -> int:
        """Push a patch tag to remote"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            # Determine tag to push
            if not tag:
                tag = get_latest_tag(prefix)
                if not tag:
                    console.print(f"[red]✗[/red] No tags found with prefix '{prefix}'")
                    return 1
            
            # Check if tag exists
            result = subprocess.run(
                ['git', 'tag', '-l', tag],
                capture_output=True,
                text=True
            )
            
            if not result.stdout.strip():
                console.print(f"[red]✗[/red] Tag '{tag}' does not exist")
                return 1
            
            # Display info
            console.print(f"[cyan]Pushing tag:[/cyan] {tag}")
            
            if dry_run:
                console.print("\n[yellow]DRY RUN:[/yellow] Would push tag", tag)
                return 0
            
            # Push tag
            cmd = ['git', 'push', 'origin', tag]
            if force:
                cmd.insert(2, '--force')
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Pushing to remote...", total=None)
                result = subprocess.run(cmd, capture_output=True, text=True)
                progress.update(task, completed=True)
            
            if result.returncode == 0:
                console.print(f"[green]✓[/green] Successfully pushed {tag}")
            else:
                console.print(f"[red]✗[/red] Failed to push: {result.stderr}")
                return 1
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Failed to push patch: {e}", exc_info=True)
            return 1


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, debug, verbose):
    """Version management tools for semantic versioning."""
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug
    ctx.obj['verbose'] = verbose


@cli.command('get-patch-tag')
@click.option('--prefix', '-p', default='v', help='Tag prefix (default: v)')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def get_patch_tag(prefix, dry_run):
    """Get the next patch version tag."""
    tools = VersionTools()
    result = tools.get_patch_tag(prefix, dry_run)
    sys.exit(result)


@cli.command('update')
@click.option('--version', '-v', help='Set specific version')
@click.option('--major', is_flag=True, help='Increment major version')
@click.option('--minor', is_flag=True, help='Increment minor version')
@click.option('--patch', is_flag=True, help='Increment patch version')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
@click.argument('files', nargs=-1, required=True)
def update(version, major, minor, patch, dry_run, files):
    """Update version in files."""
    tools = VersionTools()
    result = tools.update_version(version, major, minor, patch, list(files), dry_run)
    sys.exit(result)


@cli.command('prepare-patch')
@click.option('--prefix', '-p', default='v', help='Tag prefix (default: v)')
@click.option('--message', '-m', help='Tag message')
@click.option('--push', is_flag=True, help='Push tag after creation')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def prepare_patch(prefix, message, push, dry_run):
    """Prepare a new patch release."""
    tools = VersionTools()
    result = tools.prepare_patch(prefix, message, push, dry_run)
    sys.exit(result)


@cli.command('push-patch')
@click.option('--tag', '-t', help='Specific tag to push')
@click.option('--prefix', '-p', default='v', help='Tag prefix for latest (default: v)')
@click.option('--force', '-f', is_flag=True, help='Force push')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def push_patch(tag, prefix, force, dry_run):
    """Push patch tag to remote."""
    tools = VersionTools()
    result = tools.push_patch(tag, prefix, force, dry_run)
    sys.exit(result)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main() 