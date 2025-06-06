#!/usr/bin/env python3
"""
Synchronize changelogs across dart, flutter, and rust packages
"""
import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import re
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich import box

# Add parent directory to path
parent_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(parent_dir))

# Try direct imports first, then relative imports
try:
    from tooling.utils import (
        extract_changelog_section,
        extract_yaml_value,
        extract_toml_value,
        check_git_state,
        git_commit_and_push,
        detect_package_names,
        PackageNames
    )
    from tooling.core.logging import get_logger, setup_logging
    from tooling.core.base_config import get_config
except ImportError:
    # Fallback to relative imports
    from utils import (
        extract_changelog_section,
        extract_yaml_value,
        extract_toml_value,
        check_git_state,
        git_commit_and_push,
        detect_package_names,
        PackageNames
    )
    from core.logging import get_logger, setup_logging
    from core.base_config import get_config

logger = get_logger(__name__)
console = Console()


class ChangelogSynchronizer:
    """Handles synchronization of changelogs across packages"""
    
    def __init__(self, skip_validation: bool = False, verbose: bool = False, quiet: bool = False):
        self.skip_validation = skip_validation
        self.verbose = verbose
        self.quiet = quiet
        self.console = console
        self.names = None
        self.current_version = None
        
    def _print(self, message: str, style: str = None, highlight: bool = False):
        """Print message unless in quiet mode"""
        if not self.quiet:
            if style:
                self.console.print(f"[{style}]{message}[/{style}]", highlight=highlight)
            else:
                self.console.print(message, highlight=highlight)
    
    def detect_names(self) -> PackageNames:
        """Detect package names from project structure"""
        try:
            return detect_package_names(self.skip_validation)
        except Exception as e:
            logger.error(f"Failed to detect package names: {e}")
            sys.exit(1)
    
    def get_current_version(self) -> str:
        """Get current version from dart/pubspec.yaml"""
        dart_pubspec = Path('dart/pubspec.yaml')
        if not dart_pubspec.exists():
            self._print("Error: dart/pubspec.yaml not found", "red")
            sys.exit(1)
        
        version = extract_yaml_value(str(dart_pubspec), 'version')
        if not version:
            self._print("Error: Could not extract version from dart/pubspec.yaml", "red")
            sys.exit(1)
        
        return version
    
    def extract_latest_changelog(self) -> Tuple[str, str]:
        """Extract the latest version section from root CHANGELOG.md"""
        changelog_path = Path('CHANGELOG.md')
        if not changelog_path.exists():
            self._print("Error: CHANGELOG.md not found in root directory", "red")
            sys.exit(1)
        
        content = changelog_path.read_text()
        
        # Find the first version section
        version_pattern = r'^## \[([^\]]+)\]'
        match = re.search(version_pattern, content, re.MULTILINE)
        
        if not match:
            self._print("Error: No version sections found in CHANGELOG.md", "red")
            sys.exit(1)
        
        version = match.group(1)
        
        # Extract content for this version
        section_content = extract_changelog_section(str(changelog_path), version)
        if not section_content:
            self._print(f"Error: Could not extract content for version {version}", "red")
            sys.exit(1)
        
        return version, section_content
    
    def format_package_section(self, section_content: str, package_type: str) -> str:
        """Format changelog section with package-specific header"""
        lines = section_content.strip().split('\n')
        
        # Skip the version header line if present
        if lines and lines[0].startswith('## '):
            lines = lines[1:]
        
        # Remove empty lines at the beginning
        while lines and not lines[0].strip():
            lines.pop(0)
        
        # Add package-specific content if needed
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
    
    def update_package_changelog(self, package_path: str, version: str, content: str) -> bool:
        """Update a package's CHANGELOG.md with new content"""
        changelog_path = Path(package_path)
        
        # Create changelog if it doesn't exist
        if not changelog_path.exists():
            self._print(f"Creating {changelog_path}", "yellow")
            changelog_path.parent.mkdir(parents=True, exist_ok=True)
            header = f"# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
            changelog_path.write_text(header)
        
        # Read existing content
        existing_content = changelog_path.read_text()
        
        # Check if version already exists
        if f"## [{version}]" in existing_content or f"## {version}" in existing_content:
            self._print(f"Version {version} already exists in {changelog_path}", "yellow")
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
    
    def show_diff(self, file_path: str, original: str, updated: str):
        """Show diff between original and updated content"""
        if self.quiet:
            return
            
        import difflib
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"{file_path} (before)",
            tofile=f"{file_path} (after)",
            n=3
        )
        
        diff_text = ''.join(diff)
        if diff_text:
            self._print(f"\n[bold]Changes to {file_path}:[/bold]")
            syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
            self.console.print(syntax)
    
    def sync_changelogs(self, dry_run: bool = False, auto_commit: bool = False) -> int:
        """Main synchronization logic"""
        self._print("[bold cyan]Synchronizing Changelogs[/bold cyan]\n")
        
        # Detect package names
        self.names = self.detect_names()
        
        # Get current version
        self.current_version = self.get_current_version()
        self._print(f"Current version: [green]{self.current_version}[/green]")
        
        # Extract latest changelog section
        version, section_content = self.extract_latest_changelog()
        self._print(f"Syncing changelog for version: [green]{version}[/green]\n")
        
        # If versions don't match, warn but continue
        if version != self.current_version:
            self._print(f"[yellow]Warning: Changelog version ({version}) doesn't match current version ({self.current_version})[/yellow]\n")
        
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
            transient=True,
            console=self.console
        ) as progress:
            for package_name, changelog_path, package_type in packages:
                task = progress.add_task(f"Updating {package_name} changelog...", total=None)
                
                # Format content for this package
                formatted_content = self.format_package_section(section_content, package_type)
                
                if dry_run:
                    self._print(f"\n[yellow]DRY RUN: Would update {changelog_path}[/yellow]")
                    self._print(Panel(formatted_content, title=f"{package_name} changelog update", border_style="yellow"))
                else:
                    # Store original content for diff
                    original_content = ""
                    if Path(changelog_path).exists():
                        original_content = Path(changelog_path).read_text()
                    
                    # Update the changelog
                    if self.update_package_changelog(changelog_path, version, formatted_content):
                        changes.append(changelog_path)
                        self._print(f"[green]✓[/green] Updated {changelog_path}")
                        
                        # Show diff if verbose
                        if self.verbose and Path(changelog_path).exists():
                            new_content = Path(changelog_path).read_text()
                            self.show_diff(changelog_path, original_content, new_content)
                    else:
                        self._print(f"[dim]No changes needed for {changelog_path}[/dim]")
                
                progress.update(task, completed=True)
        
        # Summary
        self._print(f"\n[bold]Summary:[/bold]")
        if changes:
            self._print(f"[green]✓[/green] Updated {len(changes)} changelog(s)")
            for change in changes:
                self._print(f"  - {change}", "dim")
        else:
            self._print("[yellow]No changelogs were updated[/yellow]")
        
        # Auto-commit if requested and there are changes
        if auto_commit and changes and not dry_run:
            self._print("\n[bold]Committing changes...[/bold]")
            commit_msg = f"chore: sync changelogs for version {version}"
            
            try:
                result = git_commit_and_push(
                    files=changes,
                    message=commit_msg,
                    push=False  # Don't auto-push
                )
                if result:
                    self._print(f"[green]✓[/green] Changes committed: {commit_msg}")
                    self._print("[dim]Run 'git push' to push changes to remote[/dim]")
                else:
                    self._print("[yellow]Failed to commit changes[/yellow]")
            except Exception as e:
                self._print(f"[red]Error committing changes: {e}[/red]")
                logger.error(f"Commit failed: {e}")
        
        return 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Synchronize changelogs across dart, flutter, and rust packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync changelogs for the latest version
  %(prog)s
  
  # Dry run to see what would change
  %(prog)s --dry-run
  
  # Sync and auto-commit changes
  %(prog)s --auto-commit
  
  # Skip validation and sync
  %(prog)s --skip-validation
"""
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--auto-commit',
        action='store_true',
        help='Automatically commit changes after syncing'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip project structure validation'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed output including diffs'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress output except errors'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "ERROR" if args.quiet else ("DEBUG" if args.verbose else "INFO")
    setup_logging("sync_changelogs", level=log_level)
    
    # Check git state unless dry-run
    if not args.dry_run:
        git_state = check_git_state(require_clean=False)
        if git_state['has_uncommitted'] and args.auto_commit:
            console.print("[red]Error: Cannot auto-commit with uncommitted changes[/red]")
            console.print("[dim]Commit or stash your changes first[/dim]")
            return 1
    
    # Create synchronizer and run
    synchronizer = ChangelogSynchronizer(
        skip_validation=args.skip_validation,
        verbose=args.verbose,
        quiet=args.quiet
    )
    
    try:
        return synchronizer.sync_changelogs(
            dry_run=args.dry_run,
            auto_commit=args.auto_commit
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Sync cancelled by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        logger.error(f"Sync failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())