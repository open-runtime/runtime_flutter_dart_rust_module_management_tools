#!/usr/bin/env python3
"""
Unified pull request management tools using Click and Rich.
"""
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import json
import webbrowser
import shutil
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
    check_git_repo, get_current_branch, get_remote_url,
    get_commits_since_branch, get_changed_files
)
from tooling.core.logging import get_logger
from tooling.core.performance import track_performance
from tooling.core.ai_operations import get_ai_operations

logger = get_logger(__name__)
console = Console()


class PRTools:
    """Unified pull request management functionality"""
    
    def __init__(self, config=None):
        self.config = config or get_config()
        self.logger = logger
        self.ai_ops = get_ai_operations(self.config)
    
    @track_performance("create_pr")
    def create(
        self,
        title: Optional[str],
        body: Optional[str],
        base: str,
        draft: bool,
        labels: List[str],
        assignees: List[str],
        reviewers: List[str],
        use_ai: bool,
        interactive: bool
    ) -> int:
        """Create a new pull request"""
        try:
            if not check_git_repo():
                console.print("[red]✗[/red] Not in a git repository")
                return 1
            
            # Get current branch
            current_branch = get_current_branch()
            if current_branch == base:
                console.print(f"[red]✗[/red] Cannot create PR from {base} to {base}")
                return 1
            
            # Get repository info
            remote_url = get_remote_url()
            if not remote_url:
                console.print("[red]✗[/red] No remote repository found")
                return 1
            
            repo_info = self._parse_remote_url(remote_url)
            if not repo_info:
                console.print("[red]✗[/red] Could not parse repository URL")
                return 1
            
            console.print(f"[cyan]Repository:[/cyan] {repo_info['owner']}/{repo_info['repo']}")
            console.print(f"[cyan]Branch:[/cyan] {current_branch} → {base}\n")
            
            # Get commits and changes
            commits = get_commits_since_branch(base)
            changed_files = get_changed_files(base)
            
            if not commits:
                console.print("[yellow]⚠[/yellow] No commits found between branches")
                if not Confirm.ask("Continue anyway?"):
                    return 0
            
            # Generate or get title
            if not title:
                if use_ai and self.ai_ops.is_available():
                    title = self._generate_ai_title(commits, changed_files)
                elif interactive:
                    title = Prompt.ask("PR Title", default=current_branch.replace('-', ' ').title())
                else:
                    title = current_branch.replace('-', ' ').title()
            
            # Generate or get body
            if not body:
                if use_ai and self.ai_ops.is_available():
                    body = self._generate_ai_body(title, commits, changed_files)
                elif interactive:
                    body = self._interactive_body_editor(commits, changed_files)
                else:
                    body = self._generate_default_body(commits, changed_files)
            
            # Display PR preview
            self._display_pr_preview(title, body, base, draft, labels, assignees, reviewers)
            
            if interactive and not Confirm.ask("\nCreate this pull request?"):
                return 0
            
            # Create PR using GitHub CLI or API
            result = self._create_pr_github(
                repo_info, current_branch, base, title, body,
                draft, labels, assignees, reviewers
            )
            
            if result:
                console.print(f"\n[green]✓[/green] Pull request created: {result['url']}")
                if Confirm.ask("Open in browser?"):
                    webbrowser.open(result['url'])
                return 0
            else:
                console.print("[red]✗[/red] Failed to create pull request")
                return 1
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"PR creation failed: {e}", exc_info=True)
            return 1
    
    @track_performance("list_prs")
    def list_prs(
        self,
        state: str,
        author: Optional[str],
        assignee: Optional[str],
        label: Optional[str],
        limit: int,
        format: str
    ) -> int:
        """List pull requests"""
        try:
            # Get repository info
            remote_url = get_remote_url()
            if not remote_url:
                console.print("[red]✗[/red] No remote repository found")
                return 1
            
            repo_info = self._parse_remote_url(remote_url)
            if not repo_info:
                console.print("[red]✗[/red] Could not parse repository URL")
                return 1
            
            # Fetch PRs
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Fetching pull requests...", total=None)
                
                prs = self._fetch_prs_github(
                    repo_info, state, author, assignee, label, limit
                )
                
                progress.update(task, completed=True)
            
            if not prs:
                console.print("[yellow]⚠[/yellow] No pull requests found")
                return 0
            
            # Display results
            if format == "table":
                self._display_prs_table(prs)
            elif format == "json":
                console.print_json(data=prs)
            else:  # list
                self._display_prs_list(prs)
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"PR listing failed: {e}", exc_info=True)
            return 1
    
    @track_performance("open_pr")
    def open(
        self,
        pr_number: Optional[int],
        web: bool
    ) -> int:
        """Open a pull request"""
        try:
            # Get repository info
            remote_url = get_remote_url()
            if not remote_url:
                console.print("[red]✗[/red] No remote repository found")
                return 1
            
            repo_info = self._parse_remote_url(remote_url)
            if not repo_info:
                console.print("[red]✗[/red] Could not parse repository URL")
                return 1
            
            # If no PR number, try to find PR for current branch
            if not pr_number:
                current_branch = get_current_branch()
                pr_info = self._find_pr_for_branch(repo_info, current_branch)
                
                if not pr_info:
                    console.print(f"[yellow]⚠[/yellow] No PR found for branch '{current_branch}'")
                    return 1
                
                pr_number = pr_info['number']
            
            # Build PR URL
            pr_url = f"https://github.com/{repo_info['owner']}/{repo_info['repo']}/pull/{pr_number}"
            
            if web:
                console.print(f"[cyan]Opening:[/cyan] {pr_url}")
                webbrowser.open(pr_url)
            else:
                # Display PR info
                pr_info = self._fetch_pr_info(repo_info, pr_number)
                if pr_info:
                    self._display_pr_details(pr_info)
                else:
                    console.print(f"[red]✗[/red] Could not fetch PR #{pr_number}")
                    return 1
            
            return 0
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            logger.error(f"PR open failed: {e}", exc_info=True)
            return 1
    
    def _parse_remote_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub remote URL"""
        import re
        
        # Handle both HTTPS and SSH URLs
        https_pattern = r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$'
        ssh_pattern = r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$'
        
        match = re.match(https_pattern, url) or re.match(ssh_pattern, url)
        if match:
            return {
                'owner': match.group(1),
                'repo': match.group(2)
            }
        return None
    
    def _generate_ai_title(self, commits: List[str], changed_files: List[str]) -> str:
        """Generate PR title using AI"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Generating title with AI...", total=None)
                
                # Prepare context
                context = {
                    'commits': commits[:10],  # Limit to recent commits
                    'files': changed_files[:20],  # Limit files
                    'file_count': len(changed_files),
                    'commit_count': len(commits)
                }
                
                prompt = f"""Generate a concise pull request title based on these changes:

Commits ({len(commits)} total):
{chr(10).join(f'- {c}' for c in commits[:10])}

Files changed ({len(changed_files)} total):
{chr(10).join(f'- {f}' for f in changed_files[:20])}

The title should be clear, descriptive, and follow conventional format.
Maximum 72 characters."""
                
                response = self.ai_ops._generate(prompt)
                progress.update(task, completed=True)
                
                if response:
                    return response.strip().strip('"')
                    
        except Exception as e:
            logger.error(f"AI title generation failed: {e}")
        
        # Fallback
        return get_current_branch().replace('-', ' ').title()
    
    def _generate_ai_body(self, title: str, commits: List[str], changed_files: List[str]) -> str:
        """Generate PR body using AI"""
        try:
            response = self.ai_ops.generate_pr_description(
                title=title,
                changes='\n'.join(changed_files[:30]),
                commits=commits[:20],
                branch=get_current_branch()
            )
            
            if response:
                return response.content
                
        except Exception as e:
            logger.error(f"AI body generation failed: {e}")
        
        return self._generate_default_body(commits, changed_files)
    
    def _generate_default_body(self, commits: List[str], changed_files: List[str]) -> str:
        """Generate default PR body"""
        lines = ["## Summary", ""]
        
        # Add description placeholder
        lines.extend([
            "<!-- Please provide a summary of your changes -->",
            "",
            "## Changes",
            ""
        ])
        
        # Add commits
        if commits:
            lines.append(f"### Commits ({len(commits)})")
            for commit in commits[:10]:
                lines.append(f"- {commit}")
            if len(commits) > 10:
                lines.append(f"- ... and {len(commits) - 10} more")
            lines.append("")
        
        # Add changed files
        if changed_files:
            lines.append(f"### Files Changed ({len(changed_files)})")
            
            # Group by directory
            by_dir = {}
            for file in changed_files:
                dir_name = str(Path(file).parent)
                if dir_name not in by_dir:
                    by_dir[dir_name] = []
                by_dir[dir_name].append(Path(file).name)
            
            for dir_name in sorted(by_dir.keys())[:5]:
                lines.append(f"- `{dir_name}/`")
                for file in sorted(by_dir[dir_name])[:3]:
                    lines.append(f"  - {file}")
                if len(by_dir[dir_name]) > 3:
                    lines.append(f"  - ... and {len(by_dir[dir_name]) - 3} more")
            
            if len(by_dir) > 5:
                lines.append(f"- ... and {len(by_dir) - 5} more directories")
            lines.append("")
        
        # Add checklist
        lines.extend([
            "## Checklist",
            "",
            "- [ ] Tests pass",
            "- [ ] Documentation updated",
            "- [ ] Changelog updated"
        ])
        
        return '\n'.join(lines)
    
    def _interactive_body_editor(self, commits: List[str], changed_files: List[str]) -> str:
        """Interactive PR body editor"""
        default_body = self._generate_default_body(commits, changed_files)
        
        console.print("\n[cyan]PR Body:[/cyan] (Press Ctrl+D when done)")
        console.print("[dim]" + "-" * 60 + "[/dim]")
        
        # In a real implementation, we'd use a proper text editor
        # For now, we'll use a simple prompt
        lines = []
        console.print(default_body)
        console.print("[dim]" + "-" * 60 + "[/dim]")
        
        if Confirm.ask("Use default body?"):
            return default_body
        
        return Prompt.ask("Enter custom body", default=default_body)
    
    def _display_pr_preview(
        self,
        title: str,
        body: str,
        base: str,
        draft: bool,
        labels: List[str],
        assignees: List[str],
        reviewers: List[str]
    ):
        """Display PR preview"""
        # Title panel
        title_panel = Panel(
            title,
            title="Pull Request Title",
            border_style="blue"
        )
        console.print(title_panel)
        
        # Metadata table
        table = Table(box=box.SIMPLE)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        
        table.add_row("Base Branch", base)
        table.add_row("Draft", "Yes" if draft else "No")
        
        if labels:
            table.add_row("Labels", ", ".join(labels))
        if assignees:
            table.add_row("Assignees", ", ".join(assignees))
        if reviewers:
            table.add_row("Reviewers", ", ".join(reviewers))
        
        console.print(table)
        
        # Body preview
        console.print("\n[cyan]Body Preview:[/cyan]")
        console.print(Panel(Markdown(body), border_style="dim"))
    
    def _create_pr_github(
        self,
        repo_info: Dict[str, str],
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool,
        labels: List[str],
        assignees: List[str],
        reviewers: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Create PR using GitHub CLI"""
        # Try GitHub CLI first
        if shutil.which('gh'):
            cmd = ['gh', 'pr', 'create']
            cmd.extend(['--title', title])
            cmd.extend(['--body', body])
            cmd.extend(['--base', base])
            cmd.extend(['--head', head])
            
            if draft:
                cmd.append('--draft')
            
            for label in labels:
                cmd.extend(['--label', label])
            
            for assignee in assignees:
                cmd.extend(['--assignee', assignee])
            
            for reviewer in reviewers:
                cmd.extend(['--reviewer', reviewer])
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    # Extract URL from output
                    url = result.stdout.strip()
                    return {'url': url, 'number': url.split('/')[-1]}
            except Exception as e:
                logger.error(f"GitHub CLI failed: {e}")
        
        # Fallback to API or manual instructions
        console.print("\n[yellow]GitHub CLI not found. Please install 'gh' or create PR manually:[/yellow]")
        console.print(f"1. Go to: https://github.com/{repo_info['owner']}/{repo_info['repo']}/compare/{base}...{head}")
        console.print("2. Click 'Create pull request'")
        console.print("3. Use the title and body shown above")
        
        return None
    
    def _fetch_prs_github(
        self,
        repo_info: Dict[str, str],
        state: str,
        author: Optional[str],
        assignee: Optional[str],
        label: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch PRs using GitHub CLI"""
        import shutil
        
        if not shutil.which('gh'):
            console.print("[yellow]GitHub CLI not found. Please install 'gh'[/yellow]")
            return []
        
        cmd = ['gh', 'pr', 'list', '--json', 'number,title,author,state,createdAt,url']
        cmd.extend(['--limit', str(limit)])
        
        if state != "all":
            cmd.extend(['--state', state])
        
        if author:
            cmd.extend(['--author', author])
        
        if assignee:
            cmd.extend(['--assignee', assignee])
        
        if label:
            cmd.extend(['--label', label])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to fetch PRs: {e}")
        
        return []
    
    def _display_prs_table(self, prs: List[Dict[str, Any]]):
        """Display PRs in a table"""
        table = Table(title="Pull Requests", box=box.ROUNDED)
        table.add_column("#", style="cyan", width=6)
        table.add_column("Title", style="white")
        table.add_column("Author", style="yellow")
        table.add_column("State", justify="center")
        table.add_column("Created", style="dim")
        
        for pr in prs:
            state_style = "green" if pr['state'] == 'OPEN' else "red"
            created = datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))
            created_str = created.strftime('%Y-%m-%d')
            
            table.add_row(
                str(pr['number']),
                pr['title'][:50] + "..." if len(pr['title']) > 50 else pr['title'],
                pr['author']['login'],
                f"[{state_style}]{pr['state']}[/{state_style}]",
                created_str
            )
        
        console.print(table)
    
    def _display_prs_list(self, prs: List[Dict[str, Any]]):
        """Display PRs as a list"""
        for pr in prs:
            state_icon = "🟢" if pr['state'] == 'OPEN' else "🔴"
            console.print(f"{state_icon} #{pr['number']}: {pr['title']}")
            console.print(f"   Author: {pr['author']['login']} | URL: {pr['url']}")
            console.print()
    
    def _find_pr_for_branch(self, repo_info: Dict[str, str], branch: str) -> Optional[Dict[str, Any]]:
        """Find PR for a specific branch"""
        prs = self._fetch_prs_github(repo_info, "open", None, None, None, 100)
        
        for pr in prs:
            # This would need to fetch more PR details to check the head branch
            # For now, we'll just return None
            pass
        
        return None
    
    def _fetch_pr_info(self, repo_info: Dict[str, str], pr_number: int) -> Optional[Dict[str, Any]]:
        """Fetch detailed PR info"""
        import shutil
        
        if not shutil.which('gh'):
            return None
        
        cmd = ['gh', 'pr', 'view', str(pr_number), '--json', 
               'number,title,body,author,state,createdAt,url,headRefName,baseRefName']
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to fetch PR info: {e}")
        
        return None
    
    def _display_pr_details(self, pr_info: Dict[str, Any]):
        """Display detailed PR information"""
        # Header
        state_color = "green" if pr_info['state'] == 'OPEN' else "red"
        console.print(f"\n[bold]PR #{pr_info['number']}:[/bold] {pr_info['title']}")
        console.print(f"[{state_color}]● {pr_info['state']}[/{state_color}] | {pr_info['author']['login']} | {pr_info['createdAt']}")
        console.print(f"[dim]{pr_info['headRefName']} → {pr_info['baseRefName']}[/dim]")
        console.print(f"[link]{pr_info['url']}[/link]\n")
        
        # Body
        if pr_info.get('body'):
            console.print(Panel(Markdown(pr_info['body']), title="Description", border_style="dim"))


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.pass_context
def cli(ctx, debug):
    """Pull request management tools for GitHub repositories."""
    ctx.ensure_object(dict)
    ctx.obj['debug'] = debug


@cli.command('create')
@click.option('--title', '-t', help='PR title')
@click.option('--body', '-b', help='PR body/description')
@click.option('--base', '-B', default='main', help='Base branch (default: main)')
@click.option('--draft', '-d', is_flag=True, help='Create as draft PR')
@click.option('--label', '-l', multiple=True, help='Add labels (can be used multiple times)')
@click.option('--assignee', '-a', multiple=True, help='Add assignees (can be used multiple times)')
@click.option('--reviewer', '-r', multiple=True, help='Request reviewers (can be used multiple times)')
@click.option('--no-ai', is_flag=True, help='Disable AI assistance')
@click.option('--no-interactive', is_flag=True, help='Disable interactive mode')
def create(title, body, base, draft, label, assignee, reviewer, no_ai, no_interactive):
    """Create a new pull request."""
    config = get_config()
    tools = PRTools(config)
    result = tools.create(
        title, body, base, draft,
        list(label), list(assignee), list(reviewer),
        not no_ai, not no_interactive
    )
    sys.exit(result)


@cli.command('list')
@click.option('--state', '-s', type=click.Choice(['open', 'closed', 'merged', 'all']), default='open', help='PR state filter')
@click.option('--author', '-A', help='Filter by author')
@click.option('--assignee', '-a', help='Filter by assignee')
@click.option('--label', '-l', help='Filter by label')
@click.option('--limit', '-n', default=20, help='Maximum number of PRs to show')
@click.option('--format', '-f', type=click.Choice(['table', 'list', 'json']), default='table', help='Output format')
def list_prs(state, author, assignee, label, limit, format):
    """List pull requests."""
    config = get_config()
    tools = PRTools(config)
    result = tools.list_prs(state, author, assignee, label, limit, format)
    sys.exit(result)


@cli.command('open')
@click.argument('pr_number', type=int, required=False)
@click.option('--web', '-w', is_flag=True, help='Open in web browser')
def open_pr(pr_number, web):
    """Open a pull request (current branch or by number)."""
    config = get_config()
    tools = PRTools(config)
    result = tools.open(pr_number, web)
    sys.exit(result)


def main():
    """Main entry point."""
    cli()


if __name__ == '__main__':
    main() 