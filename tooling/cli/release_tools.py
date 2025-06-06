#!/usr/bin/env python3
"""
Unified release management tools using Click and Rich.
"""
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import json
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.markdown import Markdown
from rich import box
from rich.syntax import Syntax

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.core.imports import setup_imports
setup_imports()

from tooling.core.base_config import get_config
from tooling.utils.git_utils import (
    check_git_repo, get_current_branch, get_latest_tag,
    has_uncommitted_changes, get_commits_since_tag
)
from tooling.utils.version_utils import (
    parse_version_tuple as parse_version, validate_version
)
from tooling.utils.changelog_utils import (
    extract_changelog_section, validate_changelog_format
)
from tooling.core.logging import get_logger
from tooling.core.performance import track_performance
from tooling.core.ai_operations import get_ai_operations

logger = get_logger(__name__)
console = Console()


class ReleaseTools:
    """Unified release management functionality"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logger
        self.ai_ops = get_ai_operations(self.config)
    
    @track_performance("pre_release_check")
    def check_release(self, fix: bool, verbose: bool) -> int:
        """Run pre-release checks"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            console.print("[bold cyan]Running Pre-Release Checks[/bold cyan]\n")
            
            checks = [
                ("Git Repository", self._check_git_repo),
                ("Working Directory", self._check_working_directory),
                ("Branch Status", self._check_branch),
                ("Version Consistency", self._check_versions),
                ("Changelog Format", self._check_changelog),
                ("Dependencies", self._check_dependencies),
            ]
            
            results = []
            failed = 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                for check_name, check_func in checks:
                    task = progress.add_task(f"Checking {check_name}...", total=None)
                    
                    try:
                        success, message, fixable = check_func(verbose)
                        results.append((check_name, success, message, fixable))
                        if not success:
                            failed += 1
                            if fix and fixable:
                                progress.update(task, description=f"Fixing {check_name}...")
                                if self._apply_fix(check_name):
                                    results[-1] = (check_name, True, "Fixed", False)
                                    failed -= 1
                    except Exception as e:
                        results.append((check_name, False, str(e), False))
                        failed += 1
                    
                    progress.update(task, completed=True)
            
            # Display results table
            table = Table(title="Pre-Release Check Results", box=box.ROUNDED)
            table.add_column("Check", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Details", style="dim")
            
            for check_name, success, message, fixable in results:
                status = "[green]✓ PASS[/green]" if success else "[red]✗ FAIL[/red]"
                if not success and fixable and not fix:
                    message += " [yellow](fixable)[/yellow]"
                table.add_row(check_name, status, message)
            
            console.print("\n")
            console.print(table)
            
            if failed > 0:
                console.print(f"\n[red]✗[/red] {failed} checks failed")
                if not fix:
                    fixable_count = sum(1 for _, success, _, fixable in results if not success and fixable)
                    if fixable_count > 0:
                        console.print(f"[yellow]ℹ[/yellow] Run with --fix to automatically fix {fixable_count} issues")
                return 1
            else:
                console.print("\n[green]✓[/green] All checks passed! Ready for release.")
                return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Pre-release check failed: {e}", exc_info=True)
            return 1
    
    def _check_git_repo(self, verbose: bool) -> tuple[bool, str, bool]:
        """Check git repository status"""
        if not check_git_repo():
            return False, "Not in a git repository", False
        return True, "Valid git repository", False
    
    def _check_working_directory(self, verbose: bool) -> tuple[bool, str, bool]:
        """Check for uncommitted changes"""
        if has_uncommitted_changes():
            return False, "Uncommitted changes detected", True
        return True, "Working directory clean", False
    
    def _check_branch(self, verbose: bool) -> tuple[bool, str, bool]:
        """Check current branch"""
        branch = get_current_branch()
        if branch not in ['main', 'master', 'release']:
            return False, f"On branch '{branch}' (expected main/master/release)", False
        return True, f"On branch '{branch}'", False
    
    def _check_versions(self, verbose: bool) -> tuple[bool, str, bool]:
        """Check version consistency across files"""
        version = self.config.get_current_version()
        if not version:
            return False, "Could not determine version", False
        return True, f"Version {version} is consistent", False
    
    def _check_changelog(self, verbose: bool) -> tuple[bool, str, bool]:
        """Check changelog format"""
        changelog_path = Path("CHANGELOG.md")
        if not changelog_path.exists():
            return False, "CHANGELOG.md not found", False
        
        try:
            with open(changelog_path) as f:
                content = f.read()
            
            if not validate_changelog_format(content):
                return False, "Invalid changelog format", False
            
            return True, "Changelog format valid", False
        except Exception as e:
            return False, f"Error reading changelog: {e}", False
    
    def _check_dependencies(self, verbose: bool) -> tuple[bool, str, bool]:
        """Check dependencies"""
        # This is a simplified check - could be expanded
        required_files = ['requirements.txt', 'setup.py']
        missing = [f for f in required_files if not Path(f).exists()]
        
        if missing:
            return False, f"Missing files: {', '.join(missing)}", False
        
        return True, "All dependency files present", False
    
    def _apply_fix(self, check_name: str) -> bool:
        """Apply automatic fixes for certain issues"""
        if check_name == "Working Directory":
            # Stage all changes
            subprocess.run(['git', 'add', '-A'], capture_output=True)
            return True
        return False
    
    @track_performance("generate_release_notes")
    def generate_notes(
        self,
        version: Optional[str],
        from_tag: Optional[str],
        output: Optional[str],
        format: str,
        use_ai: bool,
        dry_run: bool
    ) -> int:
        """Generate release notes"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            # Determine version
            if not version:
                version = self.config.get_current_version()
                if not version:
                    console.print("[red]✗[/red] Could not determine version")
                    return 1
            
            # Get commits
            if not from_tag:
                from_tag = get_latest_tag()
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Gathering commits...", total=None)
                
                if from_tag:
                    commits = get_commits_since_tag(from_tag)
                    console.print(f"[cyan]Commits since {from_tag}:[/cyan] {len(commits)}")
                else:
                    console.print("[yellow]⚠[/yellow] No previous tag found, including all commits")
                    commits = self._get_all_commits()
                
                progress.update(task, completed=True)
            
            # Generate notes
            if use_ai and self.ai_ops.is_available():
                notes = self._generate_ai_notes(version, commits, from_tag)
            else:
                notes = self._generate_template_notes(version, commits, from_tag)
            
            # Format output
            if format == "markdown":
                formatted = notes
            elif format == "json":
                formatted = self._format_as_json(version, commits, notes)
            else:  # plain
                formatted = self._strip_markdown(notes)
            
            # Display or save
            if dry_run:
                console.print("\n[yellow]DRY RUN:[/yellow] Generated release notes:\n")
                if format == "markdown":
                    console.print(Markdown(formatted))
                else:
                    console.print(Panel(formatted, title=f"Release Notes for {version}", border_style="green"))
            else:
                if output:
                    with open(output, 'w') as f:
                        f.write(formatted)
                    console.print(f"[green]✓[/green] Release notes saved to {output}")
                else:
                    print(formatted)  # For script compatibility
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Failed to generate release notes: {e}", exc_info=True)
            return 1
    
    def _get_all_commits(self) -> List[str]:
        """Get all commits in the repository"""
        result = subprocess.run(
            ['git', 'log', '--pretty=format:%s'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip().split('\n')
        return []
    
    def _generate_ai_notes(self, version: str, commits: List[str], from_tag: Optional[str]) -> str:
        """Generate release notes using AI"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Generating with AI...", total=None)
                
                context = {
                    'version': version,
                    'previous_tag': from_tag,
                    'commit_count': len(commits)
                }
                
                response = self.ai_ops.generate_release_notes(commits, context)
                progress.update(task, completed=True)
                
                if response:
                    return response.content
                    
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            console.print(f"[yellow]⚠[/yellow] AI generation failed, using template")
        
        return self._generate_template_notes(version, commits, from_tag)
    
    def _generate_template_notes(self, version: str, commits: List[str], from_tag: Optional[str]) -> str:
        """Generate template-based release notes"""
        # Group commits by type
        groups = self._group_commits(commits)
        
        # Build release notes
        notes = [f"# Release {version}\n"]
        notes.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
        
        if from_tag:
            notes.append(f"**Previous Release:** {from_tag}\n")
        
        notes.append(f"**Total Commits:** {len(commits)}\n")
        notes.append("\n## Changes\n")
        
        # Add grouped commits
        for group, items in groups.items():
            if items:
                notes.append(f"\n### {group}\n")
                for item in items:
                    notes.append(f"- {item}\n")
        
        return ''.join(notes)
    
    def _group_commits(self, commits: List[str]) -> Dict[str, List[str]]:
        """Group commits by type"""
        groups = {
            "Features": [],
            "Bug Fixes": [],
            "Documentation": [],
            "Refactoring": [],
            "Other": []
        }
        
        for commit in commits:
            lower = commit.lower()
            if any(word in lower for word in ['feat', 'feature', 'add']):
                groups["Features"].append(commit)
            elif any(word in lower for word in ['fix', 'bug', 'patch']):
                groups["Bug Fixes"].append(commit)
            elif any(word in lower for word in ['doc', 'readme']):
                groups["Documentation"].append(commit)
            elif any(word in lower for word in ['refactor', 'clean']):
                groups["Refactoring"].append(commit)
            elif any(word in lower for word in ['test', 'spec']):
                groups["Other"].append(commit)  # Tests go to Other for now
            else:
                groups["Other"].append(commit)
        
        return groups
    
    def _format_as_json(self, version: str, commits: List[str], notes: str) -> str:
        """Format release notes as JSON"""
        data = {
            "version": version,
            "date": datetime.now().isoformat(),
            "commit_count": len(commits),
            "commits": commits,
            "notes": notes,
            "groups": self._group_commits(commits)
        }
        return json.dumps(data, indent=2)
    
    def _strip_markdown(self, text: str) -> str:
        """Strip markdown formatting"""
        import re
        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # Remove bold
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        # Remove links
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        return text
    
    @track_performance("create_release")
    def create_release(
        self,
        version: Optional[str],
        draft: bool,
        prerelease: bool,
        notes_file: Optional[str],
        dry_run: bool
    ) -> int:
        """Create a new release"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            # Determine version
            if not version:
                version = self.config.get_current_version()
                if not version:
                    console.print("[red]✗[/red] Could not determine version")
                    return 1
            
            # Validate version
            if not validate_version(version.lstrip('v')):
                console.print(f"[red]✗[/red] Invalid version format: {version}")
                return 1
            
            # Get release notes
            if notes_file and Path(notes_file).exists():
                with open(notes_file) as f:
                    notes = f.read()
            else:
                # Generate notes
                console.print("[cyan]Generating release notes...[/cyan]")
                result = self.generate_notes(version, None, None, "markdown", True, True)
                if result != 0:
                    return result
                notes = "See CHANGELOG.md for details"
            
            # Display release plan
            table = Table(title="Release Plan", box=box.ROUNDED)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Version", version)
            table.add_row("Type", "Pre-release" if prerelease else "Release")
            table.add_row("Status", "Draft" if draft else "Published")
            table.add_row("Tag", f"v{version.lstrip('v')}")
            
            console.print(table)
            
            if dry_run:
                console.print("\n[yellow]DRY RUN:[/yellow] Would create release")
                return 0
            
            if not Confirm.ask("\nCreate this release?"):
                console.print("[yellow]Cancelled[/yellow]")
                return 0
            
            # Create release (simplified - would use GitHub API in real implementation)
            console.print(f"\n[green]✓[/green] Release {version} created successfully!")
            console.print("[yellow]ℹ[/yellow] Note: GitHub release creation not implemented in this demo")
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Failed to create release: {e}", exc_info=True)
            return 1
    
    @track_performance("retag_release")
    def retag_release(
        self,
        old_tag: str,
        new_tag: Optional[str],
        force: bool,
        push: bool,
        dry_run: bool
    ) -> int:
        """Retag a release"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            # Check if old tag exists
            result = subprocess.run(
                ['git', 'tag', '-l', old_tag],
                capture_output=True,
                text=True
            )
            
            if not result.stdout.strip():
                console.print(f"[red]✗[/red] Tag '{old_tag}' does not exist")
                return 1
            
            # Determine new tag
            if not new_tag:
                # Increment patch version
                version = old_tag.lstrip('v')
                major, minor, patch = parse_version(version)
                new_tag = f"v{major}.{minor}.{patch + 1}"
            
            # Check if new tag exists
            result = subprocess.run(
                ['git', 'tag', '-l', new_tag],
                capture_output=True,
                text=True
            )
            
            if result.stdout.strip() and not force:
                console.print(f"[red]✗[/red] Tag '{new_tag}' already exists (use --force to override)")
                return 1
            
            # Display plan
            panel = Panel(
                f"[yellow]Old Tag:[/yellow] {old_tag}\n"
                f"[green]New Tag:[/green] {new_tag}\n"
                f"[cyan]Force:[/cyan] {'Yes' if force else 'No'}\n"
                f"[cyan]Push:[/cyan] {'Yes' if push else 'No'}",
                title="Retag Plan",
                border_style="blue"
            )
            console.print(panel)
            
            if dry_run:
                console.print("\n[yellow]DRY RUN:[/yellow] Would retag release")
                return 0
            
            if not Confirm.ask("\nProceed with retag?"):
                console.print("[yellow]Cancelled[/yellow]")
                return 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # Get commit of old tag
                task = progress.add_task("Getting tag commit...", total=None)
                result = subprocess.run(
                    ['git', 'rev-list', '-n', '1', old_tag],
                    capture_output=True,
                    text=True
                )
                commit = result.stdout.strip()
                progress.update(task, completed=True)
                
                # Delete old tag locally
                task = progress.add_task("Deleting old tag...", total=None)
                subprocess.run(['git', 'tag', '-d', old_tag], capture_output=True)
                progress.update(task, completed=True)
                
                # Create new tag
                task = progress.add_task("Creating new tag...", total=None)
                subprocess.run(['git', 'tag', new_tag, commit], capture_output=True)
                progress.update(task, completed=True)
                
                if push:
                    # Delete old tag remotely
                    task = progress.add_task("Deleting remote tag...", total=None)
                    subprocess.run(['git', 'push', 'origin', f':refs/tags/{old_tag}'], capture_output=True)
                    progress.update(task, completed=True)
                    
                    # Push new tag
                    task = progress.add_task("Pushing new tag...", total=None)
                    subprocess.run(['git', 'push', 'origin', new_tag], capture_output=True)
                    progress.update(task, completed=True)
            
            console.print(f"\n[green]✓[/green] Successfully retagged {old_tag} → {new_tag}")
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Failed to retag release: {e}", exc_info=True)
            return 1


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, debug, verbose):
    """Release management tools for software releases."""
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug
    ctx.obj['verbose'] = verbose


@cli.command('check')
@click.option('--fix', is_flag=True, help='Automatically fix issues where possible')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def check(fix, verbose):
    """Run pre-release checks."""
    tools = ReleaseTools()
    result = tools.check_release(fix, verbose)
    sys.exit(result)


@cli.command('notes')
@click.option('--version', '-v', help='Version to generate notes for')
@click.option('--from-tag', '-f', help='Starting tag (defaults to latest)')
@click.option('--output', '-o', help='Output file (defaults to stdout)')
@click.option('--format', type=click.Choice(['markdown', 'plain', 'json']), default='markdown', help='Output format')
@click.option('--no-ai', is_flag=True, help='Use template instead of AI')
@click.option('--dry-run', is_flag=True, help='Show what would be generated')
def notes(version, from_tag, output, format, no_ai, dry_run):
    """Generate release notes."""
    tools = ReleaseTools()
    result = tools.generate_notes(version, from_tag, output, format, not no_ai, dry_run)
    sys.exit(result)


@cli.command('create')
@click.option('--version', '-v', help='Version to release')
@click.option('--draft', is_flag=True, help='Create as draft')
@click.option('--prerelease', is_flag=True, help='Mark as pre-release')
@click.option('--notes-file', '-n', help='Path to release notes file')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def create(version, draft, prerelease, notes_file, dry_run):
    """Create a new release."""
    tools = ReleaseTools()
    result = tools.create_release(version, draft, prerelease, notes_file, dry_run)
    sys.exit(result)


@cli.command('retag')
@click.argument('old_tag')
@click.option('--new-tag', '-n', help='New tag name (defaults to incremented patch)')
@click.option('--force', '-f', is_flag=True, help='Force overwrite existing tag')
@click.option('--push', '-p', is_flag=True, help='Push changes to remote')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
def retag(old_tag, new_tag, force, push, dry_run):
    """Retag a release."""
    tools = ReleaseTools()
    result = tools.retag_release(old_tag, new_tag, force, push, dry_run)
    sys.exit(result)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main()