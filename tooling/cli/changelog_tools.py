#!/usr/bin/env python3
"""
Unified changelog management tools using Click and Rich.
"""
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
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
from rich.tree import Tree

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.core.imports import setup_imports
setup_imports()

from tooling.core.base_config import get_config
from tooling.utils.changelog_utils import (
    parse_changelog, validate_changelog_file, extract_version_content,
    ChangelogParser, ChangelogValidator, ChangelogGenerator,
    ChangelogSection, ChangelogEntry
)
from tooling.utils.git_utils import check_git_repo, get_commits_since_tag
from tooling.utils.file_utils import find_files_by_pattern
from tooling.core.logging import get_logger
from tooling.core.performance import track_performance
from tooling.core.ai_operations import get_ai_operations

logger = get_logger(__name__)
console = Console()


class ChangelogTools:
    """Unified changelog management functionality"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logger
        self.ai_ops = get_ai_operations(self.config)
        self.parser = ChangelogParser()
        self.validator = ChangelogValidator()
        self.generator = ChangelogGenerator()
    
    @track_performance("validate_changelogs")
    def validate(
        self,
        files: List[str],
        fix: bool,
        strict: bool,
        verbose: bool
    ) -> int:
        """Validate changelog files"""
        try:
            # Find changelog files if none specified
            if not files:
                files = self._find_changelog_files()
                if not files:
                    console.print("[yellow]⚠[/yellow] No changelog files found")
                    return 0
            
            console.print(f"[bold cyan]Validating {len(files)} changelog files[/bold cyan]\n")
            
            all_valid = True
            results = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                for file_path in files:
                    task = progress.add_task(f"Validating {file_path}...", total=None)
                    
                    try:
                        errors = self.validator.validate_file(file_path)
                        
                        if errors:
                            all_valid = False
                            if fix:
                                progress.update(task, description=f"Fixing {file_path}...")
                                fixed_count = self._fix_changelog_issues(file_path, errors)
                                if fixed_count > 0:
                                    # Re-validate after fixes
                                    errors = self.validator.validate_file(file_path)
                        
                        results.append((file_path, errors))
                        progress.update(task, completed=True)
                        
                    except Exception as e:
                        results.append((file_path, [str(e)]))
                        all_valid = False
                        progress.update(task, completed=True)
            
            # Display results
            self._display_validation_results(results, verbose)
            
            if all_valid:
                console.print("\n[green]✓[/green] All changelogs are valid!")
                return 0
            else:
                error_count = sum(len(errors) for _, errors in results)
                console.print(f"\n[red]✗[/red] Found {error_count} validation errors")
                if not fix:
                    console.print("[yellow]ℹ[/yellow] Run with --fix to automatically fix some issues")
                return 1
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Changelog validation failed: {e}", exc_info=True)
            return 1
    
    def _display_validation_results(self, results: List[tuple], verbose: bool):
        """Display validation results in a table"""
        table = Table(title="Changelog Validation Results", box=box.ROUNDED)
        table.add_column("File", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Issues", style="dim")
        
        for file_path, errors in results:
            status = "[green]✓ Valid[/green]" if not errors else "[red]✗ Invalid[/red]"
            
            if errors and verbose:
                # Show all errors
                issues = "\n".join(f"• {error}" for error in errors[:5])
                if len(errors) > 5:
                    issues += f"\n... and {len(errors) - 5} more"
            elif errors:
                # Show count only
                issues = f"{len(errors)} issues"
            else:
                issues = "-"
            
            table.add_row(Path(file_path).name, status, issues)
        
        console.print(table)
    
    @track_performance("sync_changelogs")
    def sync(
        self,
        source: Optional[str],
        target_pattern: str,
        version: Optional[str],
        dry_run: bool,
        force: bool,
        auto_commit: bool = False,
        skip_validation: bool = False
    ) -> int:
        """Sync changelog entries across multiple files"""
        try:
            # Special handling for package changelogs sync
            if target_pattern == "packages" or target_pattern == "all":
                return self._sync_package_changelogs(version, dry_run, auto_commit, skip_validation)
            
            # Original sync logic for custom patterns
            if not source:
                source = "CHANGELOG.md"
            
            if not Path(source).exists():
                console.print(f"[red]✗[/red] Source file '{source}' not found")
                return 1
            
            # Find target files
            target_files = self._find_files_by_pattern(target_pattern)
            if not target_files:
                console.print(f"[yellow]⚠[/yellow] No files matching pattern '{target_pattern}'")
                return 0
            
            # Remove source from targets if present
            target_files = [f for f in target_files if f != source]
            
            console.print(f"[cyan]Source:[/cyan] {source}")
            console.print(f"[cyan]Targets:[/cyan] {len(target_files)} files\n")
            
            # Parse source changelog
            source_changelog = self.parser.parse_file(source)
            
            # Determine version to sync
            if not version:
                # Try to get version from git tags
                try:
                    result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], 
                                         capture_output=True, text=True)
                    if result.returncode == 0:
                        version = result.stdout.strip().lstrip('v')
                except:
                    pass
            
            if not version:
                console.print("[red]✗[/red] Could not determine version to sync")
                return 1
            
            version_section = source_changelog.get_version(version)
            if not version_section:
                console.print(f"[red]✗[/red] Version {version} not found in source changelog")
                return 1
            
            # Display what will be synced
            panel = Panel(
                version_section.format(),
                title=f"Syncing Version {version}",
                border_style="blue"
            )
            console.print(panel)
            
            if dry_run:
                console.print("\n[yellow]DRY RUN:[/yellow] Would update:")
                for target in target_files:
                    console.print(f"  • {target}")
                return 0
            
            # Sync to each target
            updated = 0
            errors = []
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                for target_file in target_files:
                    task = progress.add_task(f"Updating {Path(target_file).name}...", total=None)
                    
                    try:
                        if self._sync_version_to_file(version_section, target_file, force):
                            updated += 1
                        progress.update(task, completed=True)
                    except Exception as e:
                        errors.append((target_file, str(e)))
                        progress.update(task, completed=True)
            
            # Display results
            if errors:
                console.print("\n[red]Errors:[/red]")
                for file_path, error in errors:
                    console.print(f"  • {file_path}: {error}")
            
            console.print(f"\n[green]✓[/green] Updated {updated}/{len(target_files)} files")
            
            # Auto-commit if requested
            if auto_commit and updated > 0 and not dry_run:
                self._auto_commit_changes(target_files, version)
            
            return 0 if not errors else 1
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"Changelog sync failed: {e}", exc_info=True)
            return 1
    
    def _sync_package_changelogs(self, version: Optional[str], dry_run: bool, auto_commit: bool, skip_validation: bool) -> int:
        """Sync changelogs across dart, flutter, and rust packages"""
        console.print("[bold cyan]Synchronizing Package Changelogs[/bold cyan]\n")
        
        # Get current version if not specified
        if not version:
            dart_pubspec = Path('dart/pubspec.yaml')
            if dart_pubspec.exists():
                from tooling.utils import extract_yaml_value
                version = extract_yaml_value(str(dart_pubspec), 'version')
            
            if not version:
                console.print("[red]✗[/red] Could not determine version")
                return 1
        
        console.print(f"Current version: [green]{version}[/green]")
        
        # Extract latest changelog section
        source_path = Path('CHANGELOG.md')
        if not source_path.exists():
            console.print("[red]✗[/red] Root CHANGELOG.md not found")
            return 1
        
        source_changelog = self.parser.parse_file(str(source_path))
        version_section = source_changelog.get_version(version)
        
        if not version_section:
            console.print(f"[red]✗[/red] Version {version} not found in changelog")
            return 1
        
        # Define packages to update
        packages = [
            ("dart", "dart/CHANGELOG.md", "dart"),
            ("flutter", "flutter/CHANGELOG.md", "flutter"),
            ("rust", "dart/rust/CHANGELOG.md", "rust")
        ]
        
        # Track changes
        changes = []
        
        # Update each package
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            for package_name, changelog_path, package_type in packages:
                task = progress.add_task(f"Updating {package_name} changelog...", total=None)
                
                # Format content for this package
                formatted_content = self._format_package_section(version_section, package_type)
                
                if dry_run:
                    console.print(f"\n[yellow]DRY RUN: Would update {changelog_path}[/yellow]")
                    console.print(Panel(formatted_content, title=f"{package_name} changelog update", border_style="yellow"))
                else:
                    # Update the changelog
                    if self._update_package_changelog(changelog_path, version, formatted_content):
                        changes.append(changelog_path)
                        console.print(f"[green]✓[/green] Updated {changelog_path}")
                    else:
                        console.print(f"[dim]No changes needed for {changelog_path}[/dim]")
                
                progress.update(task, completed=True)
        
        # Summary
        console.print(f"\n[bold]Summary:[/bold]")
        if changes:
            console.print(f"[green]✓[/green] Updated {len(changes)} changelog(s)")
            for change in changes:
                console.print(f"  - {change}", "dim")
        else:
            console.print("[yellow]No changelogs were updated[/yellow]")
        
        # Auto-commit if requested
        if auto_commit and changes and not dry_run:
            console.print("\n[bold]Committing changes...[/bold]")
            commit_msg = f"chore: sync changelogs for version {version}"
            
            try:
                import subprocess
                subprocess.run(['git', 'add'] + changes, check=True)
                subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
                console.print(f"[green]✓[/green] Changes committed: {commit_msg}")
                console.print("[dim]Run 'git push' to push changes to remote[/dim]")
            except Exception as e:
                console.print(f"[red]Error committing changes: {e}[/red]")
        
        return 0
    
    def _format_package_section(self, version_section, package_type: str) -> str:
        """Format changelog section with package-specific content"""
        content = version_section.format()
        lines = content.strip().split('\n')
        
        # Skip the version header line if present
        if lines and lines[0].startswith('## '):
            lines = lines[1:]
        
        # Remove empty lines at the beginning
        while lines and not lines[0].strip():
            lines.pop(0)
        
        # Add package-specific header if needed
        if package_type == 'dart':
            header = "### Dart Package Updates"
        elif package_type == 'flutter':
            header = "### Flutter Package Updates" 
        elif package_type == 'rust':
            header = "### Rust FFI Updates"
        else:
            header = None
        
        if header and not any(header in line for line in lines):
            lines.insert(0, f"\n{header}\n")
        
        return '\n'.join(lines)
    
    def _update_package_changelog(self, changelog_path: str, version: str, content: str) -> bool:
        """Update a package's CHANGELOG.md with new content"""
        changelog_path = Path(changelog_path)
        
        # Create changelog if it doesn't exist
        if not changelog_path.exists():
            console.print(f"Creating {changelog_path}", "yellow")
            changelog_path.parent.mkdir(parents=True, exist_ok=True)
            header = f"# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
            changelog_path.write_text(header)
        
        # Read existing content
        existing_content = changelog_path.read_text()
        
        # Check if version already exists
        if f"## [{version}]" in existing_content or f"## {version}" in existing_content:
            console.print(f"Version {version} already exists in {changelog_path}", "yellow")
            return False
        
        # Find where to insert (after header, before first version)
        lines = existing_content.split('\n')
        insert_index = 0
        
        # Skip header lines
        for i, line in enumerate(lines):
            if line.startswith('## '):
                insert_index = i
                break
            elif i > 0 and not line.strip() and i + 1 < len(lines) and lines[i + 1].startswith('## '):
                insert_index = i + 1
                break
        else:
            # No existing versions, add at the end
            insert_index = len(lines)
            # Ensure there's a blank line before
            if insert_index > 0 and lines[insert_index - 1].strip():
                lines.insert(insert_index, '')
                insert_index += 1
        
        # Format the new section
        date_str = datetime.now().strftime('%Y-%m-%d')
        new_section = f"## [{version}] - {date_str}\n{content}"
        
        # Insert the new section
        for line in reversed(new_section.split('\n')):
            lines.insert(insert_index, line)
        
        # Ensure proper spacing
        if insert_index + len(new_section.split('\n')) < len(lines):
            if lines[insert_index + len(new_section.split('\n'))].strip():
                lines.insert(insert_index + len(new_section.split('\n')), '')
        
        # Write back
        new_content = '\n'.join(lines)
        changelog_path.write_text(new_content)
        
        return True
    
    def _auto_commit_changes(self, files: List[str], version: str):
        """Auto-commit changelog changes"""
        try:
            import subprocess
            subprocess.run(['git', 'add'] + files, check=True)
            subprocess.run(['git', 'commit', '-m', f'chore: sync changelogs for version {version}'], check=True)
            console.print(f"[green]✓[/green] Changes committed")
        except Exception as e:
            console.print(f"[yellow]Failed to commit changes: {e}[/yellow]")
    
    def _find_changelog_files(self) -> List[str]:
        """Find all changelog files in the project"""
        patterns = ['CHANGELOG.md', 'CHANGELOG.rst', 'HISTORY.md', 'NEWS.md']
        files = []
        
        for pattern in patterns:
            files.extend(find_files_by_pattern(pattern))
        
        # Also look for changelogs in subdirectories
        files.extend(find_files_by_pattern('**/CHANGELOG.md'))
        
        return list(set(files))  # Remove duplicates
    
    def _find_files_by_pattern(self, pattern: str) -> List[str]:
        """Find files matching a pattern"""
        return find_files_by_pattern(pattern)
    
    def _fix_changelog_issues(self, file_path: str, errors: List[str]) -> int:
        """Attempt to fix common changelog issues"""
        fixed = 0
        
        # This is a simplified implementation
        # In a real implementation, we would parse the errors and apply specific fixes
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Fix common issues
            original = content
            
            # Ensure changelog has a header
            if not content.strip().startswith('# Changelog'):
                content = '# Changelog\n\n' + content
                fixed += 1
            
            # Fix version headers (ensure they use ## prefix)
            import re
            content = re.sub(r'^#\s+(\d+\.\d+\.\d+)', r'## \1', content, flags=re.MULTILINE)
            
            # Save if changed
            if content != original:
                with open(file_path, 'w') as f:
                    f.write(content)
                fixed += 1
            
        except Exception as e:
            logger.error(f"Failed to fix {file_path}: {e}")
        
        return fixed
    
    def _sync_version_to_file(self, version_section, target_file: str, force: bool) -> bool:
        """Sync a version section to a target file"""
        try:
            # Parse target changelog
            target_changelog = self.parser.parse_file(target_file)
            
            # Check if version already exists
            existing = target_changelog.get_version(version_section.version)
            if existing and not force:
                console.print(f"[yellow]⚠[/yellow] Version {version_section.version} already exists in {Path(target_file).name}")
                return False
            
            # Add or replace version
            if existing:
                target_changelog.versions.remove(existing)
            
            target_changelog.add_version(version_section)
            
            # Write back
            with open(target_file, 'w') as f:
                f.write(target_changelog.format())
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to sync to {target_file}: {e}")
    
    def _get_commits_between_tags(self, from_tag: Optional[str], to_tag: str) -> List[Dict[str, Any]]:
        """Get commits between two tags"""
        cmd = ['git', 'log']
        
        if from_tag:
            cmd.append(f'{from_tag}..{to_tag}')
        else:
            cmd.append(to_tag)
        
        cmd.extend(['--pretty=format:%H|%an|%ae|%ai|%s|%b', '--reverse'])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []
        
        commits = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('|', 5)
            if len(parts) >= 5:
                commits.append({
                    'hash': parts[0],
                    'author_name': parts[1],
                    'author_email': parts[2],
                    'date': parts[3],
                    'subject': parts[4],
                    'body': parts[5] if len(parts) > 5 else ''
                })
        
        return commits
    
    def _generate_entries_from_commits(self, commits: List[Dict[str, Any]]) -> List[ChangelogEntry]:
        """Generate changelog entries from commits"""
        entries = []
        
        for commit in commits:
            entry = self.generator.generate_entry_from_commit(commit)
            if entry:
                entries.append(entry)
        
        return entries
    
    def _generate_ai_entries(self, commits: List[Dict[str, Any]]) -> List[ChangelogEntry]:
        """Generate changelog entries using AI"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Generating with AI...", total=None)
                
                # Format commits for AI
                commit_messages = [c['subject'] for c in commits]
                
                response = self.ai_ops.analyze_commits_for_changelog(commit_messages)
                progress.update(task, completed=True)
                
                if response and response.entries:
                    return response.entries
                    
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            console.print(f"[yellow]⚠[/yellow] AI generation failed, using conventional analysis")
        
        return self._generate_entries_from_commits(commits)
    
    def _group_entries(self, entries: List[ChangelogEntry], group_by: str) -> Dict[str, List[ChangelogEntry]]:
        """Group entries by specified criteria"""
        grouped = {}
        
        if group_by == "section":
            grouped = self.generator.group_entries_by_section(entries)
        elif group_by == "author":
            for entry in entries:
                author = entry.author or "Unknown"
                if author not in grouped:
                    grouped[author] = []
                grouped[author].append(entry)
        else:  # type
            for entry in entries:
                # Extract type from conventional commit
                import re
                match = re.match(r'^(\w+):', entry.text)
                commit_type = match.group(1) if match else "other"
                
                if commit_type not in grouped:
                    grouped[commit_type] = []
                grouped[commit_type].append(entry)
        
        return grouped
    
    def _format_entries_markdown(self, grouped: Dict[str, List[ChangelogEntry]]) -> str:
        """Format entries as markdown"""
        lines = ["# Changelog Entries\n"]
        
        for group, entries in grouped.items():
            if isinstance(group, ChangelogSection):
                lines.append(f"## {group.value}\n")
            else:
                lines.append(f"## {group}\n")
            
            for entry in entries:
                lines.append(entry.format())
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_entries_json(self, grouped: Dict[str, List[ChangelogEntry]], commits: List[Dict[str, Any]]) -> str:
        """Format entries as JSON"""
        import json
        
        data = {
            "commit_count": len(commits),
            "entry_count": sum(len(entries) for entries in grouped.values()),
            "groups": {}
        }
        
        for group, entries in grouped.items():
            group_name = group.value if isinstance(group, ChangelogSection) else str(group)
            data["groups"][group_name] = [
                {
                    "text": entry.text,
                    "section": entry.section.value if entry.section else None,
                    "author": entry.author,
                    "pr_number": entry.pr_number,
                    "commit_hash": entry.commit_hash
                }
                for entry in entries
            ]
        
        return json.dumps(data, indent=2)
    
    def _display_entries_tree(self, grouped: Dict[str, List[ChangelogEntry]]):
        """Display entries as a tree"""
        tree = Tree("📝 Changelog Entries")
        
        for group, entries in grouped.items():
            if isinstance(group, ChangelogSection):
                group_name = f"[bold cyan]{group.value}[/bold cyan]"
            else:
                group_name = f"[bold yellow]{group}[/bold yellow]"
            
            branch = tree.add(group_name)
            
            for entry in entries:
                text = entry.text
                if entry.pr_number:
                    text += f" [dim]#{entry.pr_number}[/dim]"
                if entry.author:
                    text += f" [dim]@{entry.author}[/dim]"
                
                branch.add(text)


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, debug, verbose):
    """Changelog management tools for maintaining project history."""
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug
    ctx.obj['verbose'] = verbose


@cli.command('validate')
@click.argument('files', nargs=-1)
@click.option('--fix', is_flag=True, help='Automatically fix issues where possible')
@click.option('--strict', is_flag=True, help='Enable strict validation')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed error messages')
def validate(files, fix, strict, verbose):
    """Validate changelog format and content."""
    config = get_config()
    tools = ChangelogTools(config)
    result = tools.validate(list(files), fix, strict, verbose)
    sys.exit(result)


@cli.command('sync')
@click.option('--source', '-s', help='Source changelog file (default: CHANGELOG.md)')
@click.option('--target', '-t', required=True, help='Target file pattern (e.g., "**/CHANGELOG.md")')
@click.option('--version', '-v', help='Specific version to sync')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
@click.option('--force', '-f', is_flag=True, help='Overwrite existing entries')
def sync(source, target, version, dry_run, force):
    """Sync changelog entries across multiple files."""
    config = get_config()
    tools = ChangelogTools(config)
    result = tools.sync(source, target, version, dry_run, force)
    sys.exit(result)


@cli.command('analyze')
@click.option('--from-tag', '-f', help='Starting tag (exclusive)')
@click.option('--to-tag', '-t', default='HEAD', help='Ending tag (inclusive, default: HEAD)')
@click.option('--output', '-o', help='Output file')
@click.option('--format', type=click.Choice(['markdown', 'json', 'tree']), default='tree', help='Output format')
@click.option('--group-by', type=click.Choice(['section', 'type', 'author']), default='section', help='Group entries by')
@click.option('--no-ai', is_flag=True, help='Disable AI analysis')
def analyze(from_tag, to_tag, output, format, group_by, no_ai):
    """Analyze commits and suggest changelog entries."""
    config = get_config()
    tools = ChangelogTools(config)
    result = tools.analyze(from_tag, to_tag, output, format, group_by, not no_ai)
    sys.exit(result)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main() 