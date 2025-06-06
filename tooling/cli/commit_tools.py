#!/usr/bin/env python3
"""
Intelligent commit message generation tool - Version 2.

Migrated to use the new CLITool base class with enhanced Rich UI.
"""
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Set
import subprocess
import tempfile

from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.markdown import Markdown
from rich import box

from tooling.cli.cli_tools_base import CLITool
from tooling.utils.git_utils import (
    check_git_repo, get_staged_files, get_staged_diff, get_diff_for_files
)
from tooling.core.ai_operations import get_ai_operations
from tooling.core.performance import track_performance


class CommitMode:
    """Commit mode configuration"""
    QUICK = "quick"
    STANDARD = "standard"
    DETAILED = "detailed"
    INTERACTIVE = "interactive"


class CommitTools(CLITool):
    """Intelligent commit message generation tool"""
    
    @property
    def name(self) -> str:
        return "commit"
    
    @property
    def description(self) -> str:
        return "🚀 Generate intelligent commit messages with AI assistance"
    
    def add_arguments(self, parser):
        """Add commit-specific arguments"""
        # Mode selection
        mode_group = parser.add_mutually_exclusive_group()
        mode_group.add_argument(
            '--quick', '-q',
            action='store_true',
            help='Quick mode - analyze subset of files for faster generation'
        )
        mode_group.add_argument(
            '--detailed', '-d',
            action='store_true',
            help='Detailed mode - comprehensive analysis of all changes'
        )
        mode_group.add_argument(
            '--interactive', '-i',
            action='store_true',
            help='Interactive mode - customize message step by step'
        )
        
        # AI options
        parser.add_argument(
            '--no-ai',
            action='store_true',
            help='Use template-based generation instead of AI'
        )
        parser.add_argument(
            '--model',
            choices=['fast', 'balanced', 'quality'],
            default='balanced',
            help='AI model quality/speed tradeoff'
        )
        
        # Commit options
        parser.add_argument(
            '--auto-commit', '-a',
            action='store_true',
            help='Automatically create commit without confirmation'
        )
        parser.add_argument(
            '--push', '-p',
            action='store_true',
            help='Push to remote after commit'
        )
        parser.add_argument(
            '--amend',
            action='store_true',
            help='Amend the previous commit'
        )
        
        # Conventional commit options
        parser.add_argument(
            '--conventional', '-c',
            action='store_true',
            default=True,
            help='Use conventional commit format (default: True)'
        )
        parser.add_argument(
            '--type', '-t',
            choices=['feat', 'fix', 'docs', 'style', 'refactor', 'test', 'chore', 'perf', 'ci', 'build'],
            help='Conventional commit type'
        )
        parser.add_argument(
            '--scope', '-s',
            help='Conventional commit scope (e.g., cli, core, utils)'
        )
        parser.add_argument(
            '--breaking', '-b',
            action='store_true',
            help='Mark as breaking change'
        )
        
        # Advanced options
        parser.add_argument(
            '--max-diff-size',
            type=int,
            default=10000,
            help='Maximum diff size to analyze (default: 10000)'
        )
        parser.add_argument(
            '--template',
            help='Use custom commit message template'
        )
        parser.add_argument(
            '--emoji',
            action='store_true',
            help='Add emoji to commit messages'
        )
    
    def validate_args(self) -> bool:
        """Validate arguments"""
        # Check git repository
        if not check_git_repo():
            self.console.print("[red]✗ Not in a git repository[/red]")
            self.console.print("[dim]Initialize with: git init[/dim]")
            return False
        
        # Check for staged files
        staged_files = get_staged_files()
        if not staged_files:
            self.console.print("[red]✗ No files staged for commit[/red]")
            self.console.print("[yellow]💡 Stage files with:[/yellow] git add <files>")
            self.console.print("[dim]   Or stage all with: git add .[/dim]")
            return False
        
        return True
    
    @track_performance("generate_commit")
    def execute(self) -> int:
        """Execute commit generation"""
        try:
            # Show banner
            self.show_banner(
                title="🚀 Smart Commit Generator",
                subtitle="AI-powered commit messages that follow best practices"
            )
            
            # Determine mode
            if self.args.quick:
                mode = CommitMode.QUICK
            elif self.args.detailed:
                mode = CommitMode.DETAILED
            elif self.args.interactive:
                mode = CommitMode.INTERACTIVE
            else:
                mode = CommitMode.STANDARD
            
            # Get staged files
            staged_files = get_staged_files()
            
            # Show staged files in a beautiful table
            self._show_staged_files(staged_files)
            
            # Interactive mode
            if mode == CommitMode.INTERACTIVE:
                return self._interactive_commit(staged_files)
            
            # Generate commit message
            message = self._generate_message(staged_files, mode)
            
            if not message:
                self.console.print("[red]✗ Failed to generate commit message[/red]")
                return 1
            
            # Show generated message
            self._show_commit_message(message)
            
            # Create commit if not dry run
            if not self.config.development.dry_run:
                if self.args.auto_commit or self.confirm_action("Create commit with this message?", default=True):
                    return self._create_commit(message)
            else:
                self.console.print("\n[yellow]DRY RUN:[/yellow] Would create commit with above message")
            
            return 0
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Commit cancelled by user[/yellow]")
            return 130
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            if self.config.development.debug:
                self.console.print_exception()
            return 1
    
    def _show_staged_files(self, files: List[str]):
        """Display staged files in a beautiful table"""
        # Group files by directory
        file_groups = {}
        for file in files:
            dir_name = os.path.dirname(file) or "."
            if dir_name not in file_groups:
                file_groups[dir_name] = []
            file_groups[dir_name].append(os.path.basename(file))
        
        # Create table
        table = Table(
            title=f"📁 {len(files)} Staged Files",
            box=self.config.get_table_style(),
            title_style="bold cyan",
            show_lines=True
        )
        
        table.add_column("Directory", style="blue", no_wrap=True)
        table.add_column("Files", style="green")
        
        # Add rows
        for directory, dir_files in sorted(file_groups.items())[:10]:
            if len(dir_files) > 3:
                file_list = ", ".join(dir_files[:3]) + f" (+{len(dir_files)-3} more)"
            else:
                file_list = ", ".join(dir_files)
            table.add_row(directory, file_list)
        
        if len(file_groups) > 10:
            table.add_row("[dim]...[/dim]", f"[dim]+{len(file_groups)-10} more directories[/dim]")
        
        self.console.print(table)
        self.console.print()
    
    def _interactive_commit(self, files: List[str]) -> int:
        """Interactive commit message generation"""
        self.console.print("[cyan]🎯 Interactive Commit Mode[/cyan]\n")
        
        # Step 1: Choose commit type
        commit_types = {
            'feat': '✨ New feature',
            'fix': '🐛 Bug fix',
            'docs': '📚 Documentation',
            'style': '💎 Code style',
            'refactor': '♻️  Refactoring',
            'test': '🧪 Tests',
            'chore': '🔧 Maintenance',
            'perf': '⚡ Performance',
            'ci': '👷 CI/CD',
            'build': '📦 Build system'
        }
        
        type_choices = list(commit_types.keys())
        type_descriptions = [commit_types[t] for t in type_choices]
        
        self.console.print("[yellow]Step 1:[/yellow] Select commit type")
        for i, (t, desc) in enumerate(zip(type_choices, type_descriptions), 1):
            self.console.print(f"  {i}. {desc}")
        
        commit_type = self.select_option("Select type", type_choices)
        
        # Step 2: Enter scope (optional)
        self.console.print(f"\n[yellow]Step 2:[/yellow] Enter scope (optional)")
        scope = self.get_input("Scope (e.g., cli, core, utils)", default="")
        
        # Step 3: Breaking change?
        breaking = self.confirm_action("\n[yellow]Step 3:[/yellow] Is this a breaking change?", default=False)
        
        # Step 4: Generate description
        self.console.print(f"\n[yellow]Step 4:[/yellow] Generating description...")
        
        # Get diff for AI
        diffs = self._get_diffs_for_mode(files, CommitMode.STANDARD, self.args.max_diff_size)
        
        # Generate with AI or template
        if not self.args.no_ai and self._get_ai_ops().is_available():
            description = self._generate_ai_description(diffs, files, commit_type)
        else:
            description = self._generate_template_description(files, commit_type)
        
        # Allow editing
        self.console.print(f"\n[green]Generated:[/green] {description}")
        description = self.get_input("Edit description", default=description)
        
        # Step 5: Add body (optional)
        add_body = self.confirm_action("\n[yellow]Step 5:[/yellow] Add detailed body?", default=False)
        body = ""
        if add_body:
            self.console.print("[dim]Enter body (press Ctrl+D when done):[/dim]")
            body_lines = []
            try:
                while True:
                    line = input()
                    body_lines.append(line)
            except EOFError:
                body = "\n".join(body_lines)
        
        # Build final message
        message = self._build_conventional_message(
            commit_type=commit_type,
            scope=scope,
            breaking=breaking,
            description=description,
            body=body
        )
        
        # Show and confirm
        self._show_commit_message(message)
        
        if self.confirm_action("Create commit with this message?", default=True):
            return self._create_commit(message)
        
        return 0
    
    def _generate_message(self, files: List[str], mode: str) -> Optional[str]:
        """Generate commit message based on mode"""
        # Get diffs
        diffs = self._get_diffs_for_mode(files, mode, self.args.max_diff_size)
        
        # Show progress
        def generate():
            if not self.args.no_ai and self._get_ai_ops().is_available():
                return self._generate_ai_message(diffs, mode, files)
            else:
                return self._generate_template_message(files, diffs)
        
        message = self.show_progress("Analyzing changes and generating message...", generate)
        
        # Apply conventional format if needed
        if message and self.args.conventional and self.args.type:
            message = self._format_conventional(message)
        
        # Add emoji if requested
        if message and self.args.emoji:
            message = self._add_emoji(message)
        
        return message
    
    def _get_diffs_for_mode(self, files: List[str], mode: str, max_size: int) -> str:
        """Get diffs based on mode"""
        if mode == CommitMode.QUICK:
            # Sample subset of files
            sample_size = min(5, len(files))
            sample_files = files[:sample_size]
            diffs = get_diff_for_files(sample_files)
            if len(files) > sample_size:
                diffs += f"\n\n... analyzing {sample_size} of {len(files)} files (quick mode)"
        elif mode == CommitMode.DETAILED:
            # Get full diffs with extra context
            diffs = subprocess.run(
                ['git', 'diff', '--staged', '--unified=5'],
                capture_output=True,
                text=True
            ).stdout
        else:
            # Standard mode
            diffs = get_staged_diff()
            if len(diffs) > max_size:
                diffs = diffs[:max_size] + "\n... (truncated)"
        
        return diffs
    
    def _get_ai_ops(self):
        """Get AI operations instance"""
        if not hasattr(self, '_ai_ops'):
            self._ai_ops = get_ai_operations(self.config)
        return self._ai_ops
    
    def _generate_ai_message(self, diffs: str, mode: str, files: List[str]) -> Optional[str]:
        """Generate message using AI"""
        try:
            ai_ops = self._get_ai_ops()
            
            # Build context
            context = {
                'mode': mode,
                'file_count': len(files),
                'files': files[:20],  # Include some file names
                'conventional': self.args.conventional,
                'type': self.args.type,
                'scope': self.args.scope,
                'breaking': self.args.breaking,
                'emoji': self.args.emoji,
                'model_quality': self.args.model
            }
            
            # Use appropriate model based on quality setting
            use_pro = self.args.model == 'quality'
            
            # Generate
            response = ai_ops.generate_commit_message(diffs, context, use_pro=use_pro)
            
            if response:
                return response.content
                
        except Exception as e:
            self.logger.error(f"AI generation failed: {e}")
            self.console.print("[yellow]⚠ AI generation failed, falling back to template[/yellow]")
        
        return None
    
    def _generate_ai_description(self, diffs: str, files: List[str], commit_type: str) -> str:
        """Generate just the description part using AI"""
        try:
            ai_ops = self._get_ai_ops()
            
            prompt = f"""Generate a concise commit description (50 chars or less) for these changes.
Type: {commit_type}
Files changed: {len(files)}

Changes:
{diffs[:2000]}

Return ONLY the description text, no type prefix or punctuation."""
            
            response = ai_ops._query_ai(prompt, use_pro=False)
            if response and response.content:
                return response.content.strip()
                
        except Exception:
            pass
        
        return self._generate_template_description(files, commit_type)
    
    def _generate_template_message(self, files: List[str], diffs: str) -> str:
        """Generate template-based message"""
        # Analyze changes
        file_types = self._analyze_file_types(files)
        change_type = self._guess_change_type(diffs)
        
        # Determine scope
        if len(file_types) == 1:
            scope = list(file_types)[0]
        else:
            scope = "multiple"
        
        # Build message
        if self.args.conventional:
            summary = f"{change_type}({scope}): update {len(files)} file{'s' if len(files) > 1 else ''}"
        else:
            summary = f"Update {len(files)} file{'s' if len(files) > 1 else ''} in {scope}"
        
        # Add body
        body_lines = ["", "Changes:"]
        
        # Group files by type
        for ftype in sorted(file_types):
            type_files = [f for f in files if self._get_file_type(f) == ftype]
            if type_files:
                body_lines.append(f"\n{ftype}:")
                for f in type_files[:5]:
                    body_lines.append(f"  - {f}")
                if len(type_files) > 5:
                    body_lines.append(f"  - ... and {len(type_files) - 5} more")
        
        return summary + "\n".join(body_lines)
    
    def _generate_template_description(self, files: List[str], commit_type: str) -> str:
        """Generate a simple template description"""
        file_count = len(files)
        
        templates = {
            'feat': f"add new functionality to {file_count} file{'s' if file_count > 1 else ''}",
            'fix': f"fix issues in {file_count} file{'s' if file_count > 1 else ''}",
            'docs': f"update documentation in {file_count} file{'s' if file_count > 1 else ''}",
            'style': f"improve code style in {file_count} file{'s' if file_count > 1 else ''}",
            'refactor': f"refactor {file_count} file{'s' if file_count > 1 else ''}",
            'test': f"update tests in {file_count} file{'s' if file_count > 1 else ''}",
            'chore': f"update {file_count} file{'s' if file_count > 1 else ''}",
            'perf': f"improve performance in {file_count} file{'s' if file_count > 1 else ''}",
            'ci': f"update CI configuration",
            'build': f"update build configuration"
        }
        
        return templates.get(commit_type, f"update {file_count} file{'s' if file_count > 1 else ''}")
    
    def _analyze_file_types(self, files: List[str]) -> Set[str]:
        """Analyze file types to determine scope"""
        types = set()
        for file in files:
            types.add(self._get_file_type(file))
        return types
    
    def _get_file_type(self, file: str) -> str:
        """Get type category for a file"""
        if file.startswith('tooling/cli/'):
            return 'cli'
        elif file.startswith('tooling/core/'):
            return 'core'
        elif file.startswith('tooling/utils/'):
            return 'utils'
        elif file.startswith('tooling/tests/') or file.startswith('tests/'):
            return 'tests'
        elif file.endswith('.md'):
            return 'docs'
        elif file.startswith('.'):
            return 'config'
        else:
            return 'other'
    
    def _guess_change_type(self, diffs: str) -> str:
        """Guess the type of change from diffs"""
        diff_lower = diffs.lower()
        
        # Check for test files
        if 'def test_' in diffs or 'class Test' in diffs:
            return 'test'
        # Check for documentation
        elif 'README' in diffs or '.md' in diffs:
            return 'docs'
        # Check for fixes
        elif any(word in diff_lower for word in ['fix', 'bug', 'issue', 'error']):
            return 'fix'
        # Check for new features
        elif 'class' in diffs or 'def ' in diffs or 'function' in diffs:
            return 'feat'
        # Check for performance
        elif any(word in diff_lower for word in ['performance', 'optimize', 'speed']):
            return 'perf'
        # Default
        else:
            return 'chore'
    
    def _format_conventional(self, message: str) -> str:
        """Format message as conventional commit"""
        return self._build_conventional_message(
            commit_type=self.args.type,
            scope=self.args.scope,
            breaking=self.args.breaking,
            description=message.split('\n')[0],
            body='\n'.join(message.split('\n')[1:]) if '\n' in message else ""
        )
    
    def _build_conventional_message(
        self,
        commit_type: str,
        scope: Optional[str],
        breaking: bool,
        description: str,
        body: str = ""
    ) -> str:
        """Build a conventional commit message"""
        # Build header
        result = commit_type
        if scope:
            result += f"({scope})"
        if breaking:
            result += "!"
        result += f": {description}"
        
        # Add body
        if body:
            result += "\n\n" + body.strip()
        
        # Add breaking change footer if needed
        if breaking and "BREAKING CHANGE:" not in body:
            result += "\n\nBREAKING CHANGE: This commit contains breaking changes."
        
        return result
    
    def _add_emoji(self, message: str) -> str:
        """Add emoji to commit message"""
        emoji_map = {
            'feat': '✨',
            'fix': '🐛',
            'docs': '📚',
            'style': '💎',
            'refactor': '♻️',
            'test': '🧪',
            'chore': '🔧',
            'perf': '⚡',
            'ci': '👷',
            'build': '📦'
        }
        
        # Extract type from conventional commit
        if ':' in message:
            parts = message.split(':', 1)
            type_part = parts[0]
            
            # Extract type
            commit_type = type_part.split('(')[0].split('!')[0]
            
            if commit_type in emoji_map:
                # Add emoji after type
                return message.replace(f"{commit_type}", f"{commit_type} {emoji_map[commit_type]}", 1)
        
        return message
    
    def _show_commit_message(self, message: str):
        """Display the commit message beautifully"""
        self.console.print("\n[green]✨ Generated Commit Message:[/green]\n")
        
        # Use syntax highlighting for better readability
        syntax = Syntax(
            message,
            "text",
            theme="monokai",
            line_numbers=False,
            word_wrap=True
        )
        
        panel = Panel(
            syntax,
            title="[bold]Commit Message[/bold]",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def _create_commit(self, message: str) -> int:
        """Create the actual commit"""
        try:
            # Write message to temp file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(message)
                temp_file = f.name
            
            # Build commit command
            cmd = ['git', 'commit', '-F', temp_file]
            if self.args.amend:
                cmd.append('--amend')
            
            # Show what we're doing
            self.console.print(f"\n[cyan]Running:[/cyan] {' '.join(cmd)}")
            
            # Execute commit
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up
            os.unlink(temp_file)
            
            if result.returncode == 0:
                self.console.print("[green]✓ Commit created successfully![/green]")
                
                # Show commit hash
                commit_hash = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    capture_output=True,
                    text=True
                ).stdout.strip()[:8]
                
                self.console.print(f"[dim]Commit: {commit_hash}[/dim]")
                
                # Push if requested
                if self.args.push:
                    return self._push_changes()
                
                return 0
            else:
                self.console.print(f"[red]✗ Commit failed:[/red] {result.stderr}")
                return 1
                
        except Exception as e:
            self.console.print(f"[red]✗ Failed to create commit: {e}[/red]")
            return 1
    
    def _push_changes(self) -> int:
        """Push changes to remote"""
        def push():
            result = subprocess.run(
                ['git', 'push'],
                capture_output=True,
                text=True
            )
            return result
        
        result = self.show_progress("Pushing to remote...", push)
        
        if result.returncode == 0:
            self.console.print("[green]✓ Pushed to remote successfully![/green]")
            
            # Show remote URL
            remote_url = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True
            ).stdout.strip()
            
            if remote_url:
                self.console.print(f"[dim]Remote: {remote_url}[/dim]")
            
            return 0
        else:
            self.console.print(f"[red]✗ Push failed:[/red] {result.stderr}")
            return 1


# For backward compatibility
class CommitToolsWrapper:
    """Wrapper for backward compatibility"""
    
    def main(self, argv=None):
        tool = CommitTools()
        return tool.main(argv)


def main():
    """Main entry point"""
    tool = CommitTools()
    return tool.main()


if __name__ == '__main__':
    sys.exit(main()) 