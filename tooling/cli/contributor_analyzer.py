#!/usr/bin/env python3
"""
Contributor Analysis Tool

Analyzes contributors across GitHub organization repositories using existing
core and utils infrastructure. Builds detailed performance profiles with
AI-powered analysis and parallel processing.

Features:
- Uses existing AsyncGitOperations and AIOperations
- Leverages GeminiClient with model rotation for performance  
- Integrates with existing configuration and logging systems
- Supports parallelized analysis with rate limiting
- Generates markdown profiles with comprehensive contributor data
"""

import asyncio
import argparse
import json
import os
import subprocess
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from rich.prompt import Confirm, Prompt
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Set environment variable early to bypass project structure validation
# This tool is designed to run from any directory (global tool)
os.environ["ANY_STRUCTURE"] = "1"

# Try to import PyGithub
try:
    from github import Github, GithubException
    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False
    Github = None
    GithubException = None

from tooling.cli.cli_tools_base import CLITool
from tooling.cli.cli_utils import print_success, print_error, print_warning
from tooling.core.config_manager import get_config as get_runtime_config
from tooling.core.ai_client import GeminiClient
from tooling.core.logging import get_logger
from tooling.core.performance import track_performance, measure_operation
from tooling.utils.async_git_utils import AsyncGitOperations
from tooling.utils.async_file_utils import AsyncFileOperations
from tooling.utils.prompts import PromptBuilder
from tooling.utils.git_utils import get_git_root
import tempfile
import shutil


logger = get_logger(__name__)


@dataclass
class ContributorProfile:
    """Complete contributor profile data"""
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    total_commits: int = 0
    total_prs: int = 0
    total_issues: int = 0
    repositories: Set[str] = field(default_factory=set)
    languages: Set[str] = field(default_factory=set)
    first_contribution: Optional[datetime] = None
    last_contribution: Optional[datetime] = None
    contribution_frequency: float = 0.0  # commits per week
    avg_pr_size: float = 0.0  # lines changed per PR
    code_review_count: int = 0
    notable_contributions: List[str] = field(default_factory=list)
    ai_analysis: Optional[str] = None
    skill_assessment: Dict[str, str] = field(default_factory=dict)
    activity_pattern: Dict[str, int] = field(default_factory=dict)
    
    # Code quality analysis fields
    code_quality_score: float = 0.0  # AI-assessed code quality (0-10)
    code_patterns: List[str] = field(default_factory=list)  # Common patterns in their code
    primary_languages: Dict[str, int] = field(default_factory=dict)  # Language usage counts
    complexity_analysis: Dict[str, Any] = field(default_factory=dict)  # Code complexity metrics
    architectural_contributions: List[str] = field(default_factory=list)  # Major architectural work
    code_style_assessment: str = ""  # AI assessment of coding style
    recent_code_samples: List[Dict[str, str]] = field(default_factory=list)  # Recent code for analysis
    
    # Performance metrics
    processing_time: float = 0.0
    api_calls_used: int = 0


def confirm_with_timeout(prompt: str, default: bool = True, timeout: int = 5) -> bool:
    """
    Ask for confirmation with a timeout. If no input is received within the timeout,
    return the default value.
    
    Args:
        prompt: The prompt to display
        default: The default value to return after timeout
        timeout: Seconds to wait for input
    
    Returns:
        User's choice or default after timeout
    """
    console = Console()
    
    # Queue to communicate between threads
    result_queue = queue.Queue()
    
    def get_user_input():
        """Get user input in a separate thread"""
        try:
            answer = Confirm.ask(prompt, default=default)
            result_queue.put(answer)
        except Exception:
            result_queue.put(default)
    
    # Start input thread
    input_thread = threading.Thread(target=get_user_input, daemon=True)
    input_thread.start()
    
    # Wait for input with timeout
    try:
        result = result_queue.get(timeout=timeout)
        return result
    except queue.Empty:
        # Timeout - return default
        console.print(f"\n[yellow]No input received within {timeout} seconds, using default: {'yes' if default else 'no'}[/yellow]")
        return default


class ModelRotator:
    """Rotates between multiple Gemini models for load balancing"""
    
    # Prefer better preview models first, fallback to stable when rate limited
    MODELS = [
        "gemini-2.5-pro-preview-06-05",  # Best model first
        "gemini-2.5-pro-preview-05-06",  # Second best
        "gemini-2.5-flash-preview-04-17", # Faster preview
        "gemini-2.0-flash"  # Stable fallback when previews are rate limited
    ]
    
    FALLBACK_MODEL = "gemini-2.0-flash"
    
    def __init__(self, config):
        self.config = config
        self.current_index = 0
        self.clients = {}
        self.model_failures = {}  # Track failures per model
        self.last_failure_time = {}  # Track when models last failed
        self.failure_cooldown = 300  # 5 minutes cooldown for failed models
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize clients for each model"""
        for model in self.MODELS:
            try:
                client = GeminiClient(
                    api_key=self.config.api_key,
                    config=None,  # Pass None to avoid config validation
                    cache_enabled=True
                )
                client.default_model = model
                self.clients[model] = client
                logger.debug(f"Initialized client for {model}")
            except Exception as e:
                logger.warning(f"Failed to initialize client for {model}: {e}")
    
    def get_next_client(self) -> Tuple[GeminiClient, str]:
        """Get next client, preferring better models with smart fallback"""
        if not self.clients:
            raise RuntimeError("No Gemini clients available")
        
        current_time = time.time()
        
        # Try models in order of preference, skipping recently failed ones
        for model in self.MODELS:
            if model not in self.clients:
                continue
                
            # Skip models that failed recently
            if model in self.last_failure_time:
                time_since_failure = current_time - self.last_failure_time[model]
                if time_since_failure < self.failure_cooldown:
                    logger.debug(f"Skipping {model} - cooling down ({time_since_failure:.0f}s ago)")
                    continue
            
            # This model is available and not in cooldown
            logger.debug(f"Using model: {model}")
            return self.clients[model], model
        
        # If all models are in cooldown, use the fallback
        if self.FALLBACK_MODEL in self.clients:
            logger.warning("All preview models in cooldown, using fallback")
            return self.clients[self.FALLBACK_MODEL], self.FALLBACK_MODEL
        
        # Last resort - use any available client
        model = next(iter(self.clients.keys()))
        logger.warning(f"Using last resort model: {model}")
        return self.clients[model], model
    
    def mark_model_failure(self, model: str, error: Exception) -> None:
        """Mark a model as having failed for rate limiting purposes"""
        self.model_failures[model] = self.model_failures.get(model, 0) + 1
        self.last_failure_time[model] = time.time()
        
        # Determine if it's a rate limit error
        error_str = str(error).lower()
        if any(term in error_str for term in ['rate limit', 'quota', 'too many requests']):
            logger.warning(f"Model {model} hit rate limit, cooling down for {self.failure_cooldown}s")
        else:
            logger.warning(f"Model {model} failed: {error}")
    
    def get_model_status(self) -> Dict[str, str]:
        """Get status of all models for debugging"""
        current_time = time.time()
        status = {}
        
        for model in self.MODELS:
            if model not in self.clients:
                status[model] = "unavailable"
            elif model in self.last_failure_time:
                time_since_failure = current_time - self.last_failure_time[model]
                if time_since_failure < self.failure_cooldown:
                    status[model] = f"cooling down ({self.failure_cooldown - time_since_failure:.0f}s left)"
                else:
                    status[model] = "available"
            else:
                status[model] = "available"
        
        return status


class ContributorAnalyzer(CLITool):
    """Main contributor analysis tool leveraging existing infrastructure"""
    
    def __init__(self):
        # Initialize without calling super().__init__() to avoid config validation
        from tooling.cli.cli_utils import console
        self.console = console
        self.config = None  # Will be set in validate_args
        self.logger = None
        self.args = None
        
        # Tool-specific initialization
        self.config_data = None
        self.contributors: Dict[str, ContributorProfile] = {}
        self.git_ops = None
        self.file_ops = None
        self.model_rotator = None
        self.rate_limiter = None  # Will be initialized in validate_args
        self.github_client = None  # PyGithub client
        self.use_pygithub = False  # Flag to use PyGithub instead of GitHub CLI
        
    @property
    def name(self) -> str:
        return "contributors"
    
    @property
    def description(self) -> str:
        return "Analyze contributors across GitHub organizations using AI and parallel processing (global tool - can run from any directory)"
    
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add tool-specific arguments"""
        parser.add_argument(
            '--organizations', '-o',
            nargs='+',
            default=['pieces-app', 'open-runtime'],
            help='GitHub organizations to analyze'
        )
        
        parser.add_argument(
            '--repositories', '-r',
            nargs='*',
            help='Specific repositories to analyze (default: all in organizations)'
        )
        
        parser.add_argument(
            '--since',
            default='6months',
            help='Analyze contributions since this period'
        )
        
        parser.add_argument(
            '--from-scratch',
            action='store_true',
            help='Start analysis from scratch, ignoring existing profiles'
        )
        
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing profiles with new data'
        )
        
        parser.add_argument(
            '--rate-limit',
            type=int,
            default=10,
            help='API rate limit (requests per minute)'
        )
        
        parser.add_argument(
            '--max-workers',
            type=int,
            default=4,
            help='Maximum number of parallel workers'
        )
        
        parser.add_argument(
            '--profiles-dir',
            type=Path,
            default=Path('profiles'),
            help='Directory to store contributor profiles'
        )
        
# Note: --dry-run is automatically added by the base CLITool class
        
        parser.add_argument(
            '--analysis-dir',
            type=Path,
            help='Isolated directory for repository checkouts (default: temp directory)'
        )
        
        parser.add_argument(
            '--max-files-per-contributor',
            type=int,
            default=20,
            help='Maximum number of recent files to analyze per contributor'
        )
        
        parser.add_argument(
            '--skip-code-analysis',
            action='store_true',
            help='Skip detailed code file analysis (faster but less detailed)'
        )
        
        parser.add_argument(
            '--any-structure',
            action='store_true',
            help='Allow running from any directory structure (global tool mode)'
        )
        
        parser.add_argument(
            '--force-inactive',
            action='store_true',
            help='Include repositories without recent commits in the analysis'
        )
        
        parser.add_argument(
            '--use-pygithub',
            action='store_true',
            help='Use PyGithub SDK instead of GitHub CLI (better for private repos)'
        )
        
        parser.add_argument(
            '--github-token',
            help='GitHub personal access token (defaults to GITHUB_TOKEN env var)'
        )
        
        parser.add_argument(
            '--debug-api',
            action='store_true',
            help='Show API requests and responses for debugging'
        )
        
        parser.add_argument(
            '--exclude-repos',
            nargs='+',
            default=['homebrew-core'],
            help='Repository names to exclude from analysis (default: homebrew-core)'
        )
        
        parser.add_argument(
            '--exclude-contributors',
            nargs='+',
            help='Contributor usernames to exclude from analysis (e.g., former employees)'
        )
    
    def validate_args(self) -> bool:
        """Validate arguments and setup configuration"""
        # Contributor analyzer is a global tool - always use any-structure mode by default
        # Create minimal config that doesn't require project structure validation
        self.config_data = type('GlobalConfig', (), {
            'api_key': os.getenv('GEMINI_API_KEY'),
            'development': type('Dev', (), {
                'debug': getattr(self.args, 'debug', False),
                'verbose': getattr(self.args, 'verbose', False),
                'dry_run': getattr(self.args, 'dry_run', False),
                'log_level': 'DEBUG' if getattr(self.args, 'debug', False) else 'INFO'
            })(),
            'ui': type('UI', (), {
                'theme': 'dark',
                'use_color': True
            })(),
            'ai': type('AI', (), {
                'model': 'gemini-2.0-flash',
                'pro_model': 'gemini-2.0-flash'
            })()
        })()
        
        self.config = self.config_data  # Set for compatibility with CLITool methods
        
        # Check for conflicting modes
        if self.args.from_scratch and self.args.update:
            print_error("Cannot use both --from-scratch and --update modes")
            return False
        
        # Default to update mode
        if not self.args.from_scratch and not self.args.update:
            self.args.update = True
        
        # Check if we should use PyGithub
        if self.args.use_pygithub:
            if not PYGITHUB_AVAILABLE:
                print_error("PyGithub is not installed. Install with: pip install PyGithub")
                return False
            
            # Initialize PyGithub client
            github_token = self.args.github_token or os.getenv('GITHUB_TOKEN')
            if not github_token:
                # Try to get token from gh CLI
                try:
                    result = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True)
                    if result.returncode == 0:
                        github_token = result.stdout.strip()
                except:
                    pass
            
            if not github_token:
                print_error("GitHub token required. Set GITHUB_TOKEN env var or use --github-token")
                return False
            
            self.github_client = Github(github_token)
            self.use_pygithub = True
            print_success("Using PyGithub SDK for API access")
        else:
            # Check GitHub CLI availability
            if not self._check_github_cli():
                return False
        
        # Check AI availability
        if not self.config_data.api_key:
            if not self.args.dry_run:
                print_error("Gemini API key required. Set GEMINI_API_KEY environment variable")
                return False
        
        # Parse since date
        since_date = self._parse_since_date(self.args.since)
        if not since_date:
            return False
        
        self.since_date = since_date
        
        # Create directories
        self.args.profiles_dir.mkdir(exist_ok=True)
        
        # Setup isolated analysis directory
        if not self.args.analysis_dir:
            self.args.analysis_dir = Path(tempfile.mkdtemp(prefix="contributor_analysis_"))
            logger.info(f"Created isolated analysis directory: {self.args.analysis_dir}")
        else:
            self.args.analysis_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.git_ops = AsyncGitOperations()
        self.file_ops = AsyncFileOperations()
        
        # Initialize rate limiter
        self.rate_limiter = AsyncRateLimiter(self.args.rate_limit)
        
        # Initialize AI if available  
        if self.config_data.api_key:
            self.model_rotator = ModelRotator(self.config_data)
        
        return True
    
    @track_performance("contributor_analysis")
    def execute(self) -> int:
        """Execute the contributor analysis"""
        try:
            self.show_banner("Contributor Analysis", "Building detailed contributor profiles")
            
            # Show configuration
            self._show_configuration()
            
            # Always build and show comprehensive plan
            plan_result = asyncio.run(self._build_comprehensive_plan())
            
            # If dry run, we're done
            if self.args.dry_run:
                return plan_result
            
            # For real execution, ask for final confirmation after showing plan
            if not confirm_with_timeout(f"\n[bold red]🚀 Execute this analysis plan now?[/bold red]", default=False, timeout=5):
                self.console.print("[yellow]Analysis cancelled[/yellow]")
                return 0
            
            # Run analysis
            return asyncio.run(self._run_analysis())
                
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Analysis interrupted by user[/yellow]")
            return 1
        except Exception as e:
            print_error(f"Analysis failed: {e}")
            logger.exception("Analysis failed")
            return 1
    
    def _check_github_cli(self) -> bool:
        """Check if GitHub CLI is available and authenticated"""
        try:
            # Check if gh is installed
            result = subprocess.run(['gh', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print_error("GitHub CLI (gh) is not installed. Please install it first.")
                return False
            
            # Check if authenticated
            result = subprocess.run(['gh', 'auth', 'status'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print_error("GitHub CLI is not authenticated. Please run 'gh auth login' first.")
                print_error("Output: " + result.stderr)
                return False
            
            # Show authentication status for debugging
            auth_info = result.stdout + result.stderr
            logger.info(f"GitHub CLI authentication status: {auth_info}")
            
            # Check if we have the required scopes for private repos
            if 'repo' not in auth_info:
                print_warning("GitHub token may not have 'repo' scope for private repository access")
                print_warning("You may need to re-authenticate with: gh auth login --scopes repo,read:org")
            
            # Test access to organizations
            for org in self.args.organizations:
                test_result = subprocess.run(['gh', 'api', f'/orgs/{org}'], 
                                           capture_output=True, text=True, timeout=10)
                if test_result.returncode != 0:
                    print_warning(f"Cannot access organization '{org}': {test_result.stderr}")
                    print_warning("This may be due to insufficient permissions or private organization")
                else:
                    logger.info(f"Successfully verified access to organization: {org}")
            
            return True
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print_error("GitHub CLI check failed")
            return False
    
    def _parse_since_date(self, since_str: str) -> Optional[datetime]:
        """Parse since date string into timezone-aware datetime"""
        # Make datetime timezone-aware (UTC)
        now = datetime.now(timezone.utc)
        
        periods = {
            '1week': timedelta(weeks=1),
            '1month': timedelta(days=30),
            '2months': timedelta(days=60),
            '3months': timedelta(days=90),
            '6months': timedelta(days=180),
            '1year': timedelta(days=365),
            '2years': timedelta(days=730),
            '30days': timedelta(days=30),
            '60days': timedelta(days=60),
            '90days': timedelta(days=90),
            '180days': timedelta(days=180),
        }
        
        if since_str in periods:
            return now - periods[since_str]
        
        try:
            # Parse date and make it timezone-aware
            dt = datetime.fromisoformat(since_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            print_error(f"Invalid date format: {since_str}")
            return None
    
    def _show_authentication_help(self):
        """Show help for GitHub authentication issues"""
        from rich.panel import Panel
        
        help_text = """[yellow]GitHub Authentication Help[/yellow]

If you're seeing 404 or 403 errors for private repositories:

1. [cyan]Check your authentication:[/cyan]
   gh auth status

2. [cyan]Re-authenticate with proper scopes:[/cyan]
   gh auth login --scopes repo,read:org,workflow

3. [cyan]For organization access:[/cyan]
   - Make sure you're a member of the organization
   - Check if the organization requires SSO (Single Sign-On)
   - Ask an organization admin for access

4. [cyan]Test organization access:[/cyan]
   gh api /orgs/[ORG_NAME]

5. [cyan]Test repository access:[/cyan]
   gh api /repos/[ORG]/[REPO]"""
        
        panel = Panel(help_text, title="[red]Authentication Issues?[/red]", border_style="yellow")
        self.console.print(panel)

    def _show_configuration(self):
        """Show analysis configuration"""
        from rich.table import Table
        from rich import box
        
        table = Table(title="Analysis Configuration", box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Organizations", ", ".join(self.args.organizations))
        table.add_row("Repositories", 
                     ", ".join(self.args.repositories) if self.args.repositories 
                     else "All in organizations")
        table.add_row("Since Date", self.since_date.strftime("%Y-%m-%d"))
        table.add_row("Mode", "From Scratch" if self.args.from_scratch else "Update Existing")
        table.add_row("Rate Limit", f"{self.args.rate_limit} RPM")
        table.add_row("Max Workers", str(self.args.max_workers))
        table.add_row("Profiles Directory", str(self.args.profiles_dir))
        table.add_row("Analysis Directory", str(self.args.analysis_dir))
        table.add_row("Code Analysis", "Disabled" if self.args.skip_code_analysis else "Enabled")
        table.add_row("Max Files/Contributor", str(self.args.max_files_per_contributor))
        table.add_row("AI Models", "4 model rotation" if self.model_rotator else "None")
        table.add_row("Dry Run", "Yes" if self.args.dry_run else "No")
        
        self.console.print(table)
    

    
    def _dry_run_analysis(self) -> int:
        """Perform comprehensive dry run analysis with detailed plan"""
        return asyncio.run(self._build_comprehensive_plan())
    
    async def _build_comprehensive_plan(self) -> int:
        """Build and display comprehensive analysis plan"""
        from rich.panel import Panel
        from rich.columns import Columns
        from rich.table import Table
        from rich import box
        
        self.console.print("\n")
        self.console.rule("[bold blue]🎯 COMPREHENSIVE ANALYSIS PLAN[/bold blue]", style="blue")
        
        # Test authentication first (only for GitHub CLI mode)
        if not self.use_pygithub:
            auth_test = await self.git_ops.run_command(['gh', 'auth', 'status'])
            if not auth_test.success:
                print_error("GitHub CLI authentication failed!")
                self._show_authentication_help()
                return 1
            
            # Test API access for each organization
            for org in self.args.organizations:
                test_cmd = ['gh', 'api', f'/orgs/{org}']
                test_result = await self.git_ops.run_command(test_cmd)
                
                if not test_result.success:
                    self.console.print(f"[red]✗[/red] Cannot access organization '{org}'")
                    
                    if "404" in test_result.stderr:
                        print_error(f"Organization '{org}' not found or you don't have access")
                    elif "403" in test_result.stderr:
                        print_error(f"Access denied to '{org}' - insufficient permissions")
                    
                    self._show_authentication_help()
                    return 1
                else:
                    self.console.print(f"[green]✓[/green] Verified access to '{org}'")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            discovery_task = progress.add_task("🔍 Building analysis plan...", total=None)
            
            # Phase 1: Discover repositories
            repos = await self._get_repositories_to_analyze()
            progress.update(discovery_task, description="📦 Analyzing repositories...")
            
            # Capture lists of sampled repos
            contrib_sampled_repos = {org: repo_list[:5] for org, repo_list in repos.items() if repo_list}
            pr_issue_sampled_repos = {org: repo_list[:3] for org, repo_list in repos.items() if repo_list}
            
            # Phase 2: Get sample contributors from repos with recent activity
            sample_contributors = await self._get_sample_contributors(repos)
            progress.update(discovery_task, description="👥 Sampling contributors...")
            
            # Update contrib_sampled_repos with repos that actually had contributors
            # This is used for display purposes and PR/issue sampling
            if not self.use_pygithub:
                # For GitHub CLI, find which repos actually had recent activity
                for org in repos:
                    active_repos = []
                    # Check first 5 repos for commits
                    repos_to_check = repos[org][:5]
                    for repo in repos_to_check:
                        since_str = self.since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                        test_result = await self.git_ops.run_command([
                            'gh', 'api', f'/repos/{org}/{repo}/commits',
                            '-F', f'since={since_str}',
                            '-F', 'per_page=1'
                        ])
                        if test_result.success and json.loads(test_result.stdout or '[]'):
                            active_repos.append(repo)
                            if len(active_repos) >= 3:
                                break
                    # Only update if we found active repos, otherwise keep the original
                    if active_repos:
                        contrib_sampled_repos[org] = active_repos
            
            # Phase 3: Get sample PRs and Issues from repos
            # Use contrib_sampled_repos if it has content, otherwise fall back to first 3 repos
            repos_for_pr_sampling = {}
            for org, repo_list in repos.items():
                if contrib_sampled_repos.get(org):
                    repos_for_pr_sampling[org] = contrib_sampled_repos[org]
                else:
                    # Fallback to first 3 repos if no active ones found
                    repos_for_pr_sampling[org] = repo_list[:3]
            
            sample_data = await self._get_sample_pr_and_issue_data(repos, active_repos=repos_for_pr_sampling)
            progress.update(discovery_task, description="📊 Sampling PRs and issues...")
            
            # Use same repos for PR/issue sampling
            pr_issue_sampled_repos = contrib_sampled_repos
            
            progress.update(discovery_task, description="✅ Analysis plan complete", completed=1, total=1)
        
        # Display comprehensive plan
        self._display_comprehensive_plan(repos, sample_contributors, sample_data, contrib_sampled_repos, pr_issue_sampled_repos)
        
        # Check if we found any contributors - if not, show helpful info
        total_contributors = sum(len(contributors) for contributors in sample_contributors.values())
        total_repos = sum(len(repo_list) for repo_list in repos.values())
        
        if total_contributors == 0:
            self.console.print("")
            from rich.panel import Panel
            help_text = f"""[yellow]No Contributors Found in Sample[/yellow]

This could be due to:

1. [cyan]Most repositories being inactive or private[/cyan]
2. [cyan]Time window:[/cyan] Currently checking since {self.since_date.strftime('%Y-%m-%d')}
3. [cyan]Repository access:[/cyan] Some repos might require additional permissions

[green]Try specifying known active repositories:[/green]
For pieces-app:
  --repositories pieces-os-client python-sdk support

For open-runtime:
  --repositories pieces-py runtime_client pieces_os_client

Example:
[dim]python -m tooling.cli.contributor_analyzer --organizations pieces-app --repositories pieces-os-client python-sdk[/dim]

[dim]Note: We sampled {len(contrib_sampled_repos.get('pieces-app', []))} repos from pieces-app and {len(contrib_sampled_repos.get('open-runtime', []))} from open-runtime[/dim]"""
            
            panel = Panel(help_text, title="[blue]ℹ️  Analysis Info[/blue]", border_style="blue")
            self.console.print(panel)
        
        # Get user confirmation for dry run
        if self.args.dry_run:
            if not confirm_with_timeout(f"\n[bold yellow]📋 Does this analysis plan look correct?[/bold yellow]", default=True, timeout=5):
                self.console.print("[yellow]Plan rejected by user[/yellow]")
                return 1
            
            if total_contributors == 0:
                self.console.print("[yellow]⚠️  No contributors found in sample. Try a longer time window or specific repositories.[/yellow]")
            
            self.console.print("[green]✅ Plan looks good! This was a dry run - use without --dry-run to execute.[/green]")
            return 0
        
        # For real execution, just return success (confirmation happens in execute method)
        return 0
    
    async def _get_sample_contributors(self, repos: Dict[str, List[str]], max_repos: int = 3) -> Dict[str, Set[str]]:
        """Get sample contributors from repositories with recent activity"""
        sample_contributors = {}
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
        
        if self.use_pygithub:
            return self._get_sample_contributors_pygithub(repos)
        
        async def get_repo_contributors_sample(org: str, repo: str):
            async with semaphore:
                try:
                    # First check if repo is accessible
                    repo_info_cmd = ['gh', 'api', f'/repos/{org}/{repo}']
                    repo_info_result = await self.git_ops.run_command(repo_info_cmd)
                    
                    if not repo_info_result.success:
                        error_msg = repo_info_result.stderr.strip()
                        if "404" in error_msg:
                            logger.debug(f"Repository {org}/{repo} not found")
                        elif "403" in error_msg:
                            logger.debug(f"Access denied to {org}/{repo}")
                        else:
                            logger.debug(f"Cannot access {org}/{repo}: {error_msg}")
                        return org, repo, set(), False, "inaccessible"
                    
                    # Check if archived
                    repo_info = json.loads(repo_info_result.stdout)
                    if repo_info.get('archived', False):
                        logger.debug(f"Repository {org}/{repo} is archived")
                        return org, repo, set(), False, "archived"
                    
                    # Check for recent commits using GraphQL for better performance
                    # GitHub API needs ISO 8601 format with timezone
                    since_str = self.since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    commits_query = f'''query {{
                        repository(owner: "{org}", name: "{repo}") {{
                            defaultBranchRef {{
                                target {{
                                    ... on Commit {{
                                        history(first: 1, since: "{since_str}") {{
                                            totalCount
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}'''
                    
                    commits_result = await self.git_ops.run_command([
                        'gh', 'api', 'graphql', '-f', f'query={commits_query}'
                    ])
                    
                    has_recent_commits = False
                    if commits_result.success:
                        try:
                            data = json.loads(commits_result.stdout)
                            history = data.get('data', {}).get('repository', {}).get('defaultBranchRef', {}).get('target', {}).get('history', {})
                            has_recent_commits = history.get('totalCount', 0) > 0
                        except:
                            # Fallback to REST API
                            commits_cmd = ['gh', 'api', f'/repos/{org}/{repo}/commits', '-F', f'since={since_str}', '-F', 'per_page=1']
                            commits_result = await self.git_ops.run_command(commits_cmd)
                            if commits_result.success:
                                commits = json.loads(commits_result.stdout or '[]')
                                has_recent_commits = len(commits) > 0
                    
                    if not has_recent_commits:
                        logger.debug(f"No recent commits in {org}/{repo} since {since_str}")
                        # If force-inactive flag is set, still try to get contributors
                        if hasattr(self.args, 'force_inactive') and self.args.force_inactive:
                            # Get contributors anyway
                            cmd = ['gh', 'api', f'/repos/{org}/{repo}/contributors', '-F', 'per_page=10']
                            result = await self.git_ops.run_command(cmd)
                            
                            if result.success:
                                contrib_data = json.loads(result.stdout)
                                contributors = {contrib.get('login') for contrib in contrib_data 
                                             if contrib.get('login')}
                                if contributors:
                                    logger.info(f"✓ Found {len(contributors)} contributors in {org}/{repo} (inactive repo)")
                                    return org, repo, contributors, True, "inactive_with_contributors"
                            
                        return org, repo, set(), False, "no_recent_commits"
                    
                    # Get contributors
                    cmd = ['gh', 'api', f'/repos/{org}/{repo}/contributors', '-F', 'per_page=10']
                    result = await self.git_ops.run_command(cmd)
                    
                    if result.success:
                        contrib_data = json.loads(result.stdout)
                        contributors = {contrib.get('login') for contrib in contrib_data 
                                     if contrib.get('login')}
                        logger.info(f"✓ Found {len(contributors)} contributors in {org}/{repo}")
                        return org, repo, contributors, True, "active"
                    else:
                        logger.warning(f"Failed to get contributors for {org}/{repo}")
                        return org, repo, set(), False, "error"
                    
                except Exception as e:
                    logger.error(f"Error sampling contributors for {org}/{repo}: {e}")
                    return org, repo, set(), False, "error"
        
        # Get repos with recent activity
        repos_with_activity = {}
        for org, repo_list in repos.items():
            sample_contributors[org] = set()
            repos_with_activity[org] = []
            
            # Limit repos to check for sampling (prioritize specified repos)
            repos_to_check = repo_list
            if self.args.repositories:
                # If specific repos are specified, check those first
                specified_repos = [r for r in repo_list if r in self.args.repositories or f"{org}/{r}" in self.args.repositories]
                other_repos = [r for r in repo_list if r not in specified_repos]
                repos_to_check = specified_repos + other_repos
            
            # Limit to first 5 repos for sampling efficiency
            max_sample_repos = 5
            repos_to_check = repos_to_check[:max_sample_repos]
            
            logger.info(f"Checking {len(repos_to_check)} repositories (out of {len(repo_list)}) in {org} for activity...")
            
            # Check repos for recent activity
            tasks = []
            for repo in repos_to_check:
                tasks.append(get_repo_contributors_sample(org, repo))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect repos with activity and analyze status
            active_repos = []
            status_counts = {"active": 0, "no_recent_commits": 0, "archived": 0, "inaccessible": 0, "error": 0}
            
            for result in results:
                if isinstance(result, tuple) and len(result) == 5:
                    org_name, repo_name, contributors, has_activity, status = result
                    status_counts[status] = status_counts.get(status, 0) + 1
                    
                    if has_activity:
                        active_repos.append((repo_name, contributors))
                        sample_contributors[org].update(contributors)
            
            # Log repository status summary
            logger.info(f"Repository status for {org}: {status_counts}")
            
            # Sort by number of contributors and take top 3
            active_repos.sort(key=lambda x: len(x[1]), reverse=True)
            repos_with_activity[org] = [repo[0] for repo in active_repos[:3]]
            
            if len(active_repos) == 0:
                logger.warning(f"⚠️  No active repositories found in {org} out of {len(repo_list)} checked")
                logger.info(f"   - Repositories with no recent commits: {status_counts.get('no_recent_commits', 0)}")
                logger.info(f"   - Archived repositories: {status_counts.get('archived', 0)}")
                logger.info(f"   - Inaccessible repositories: {status_counts.get('inaccessible', 0)}")
            else:
                logger.info(f"✓ Found {len(active_repos)} active repositories in {org}, sampling top 3: {repos_with_activity[org]}")
        
        return sample_contributors
    
    def _get_sample_contributors_pygithub(self, repos: Dict[str, List[str]]) -> Dict[str, Set[str]]:
        """Get sample contributors using PyGithub"""
        sample_contributors = {}
        
        # Get excluded repos list
        excluded_repos = set(self.args.exclude_repos) if self.args.exclude_repos else set()
        
        for org_name, repo_list in repos.items():
            sample_contributors[org_name] = set()
            repos_with_activity = []
            
            try:
                org = self.github_client.get_organization(org_name)
                
                # Filter out excluded repos first
                filtered_repo_list = [r for r in repo_list if r not in excluded_repos]
                
                # Take the 5 most recently active repos (repos are already sorted by activity)
                repos_to_check = filtered_repo_list[:5]
                logger.info(f"Checking {len(repos_to_check)} most recently active repositories in {org_name}...")
                
                status_counts = {"active": 0, "no_recent_commits": 0, "empty": 0, "error": 0}
                
                for repo_name in repos_to_check:
                    try:
                        if self.args.debug_api:
                            self.console.print(f"[dim]Checking {org_name}/{repo_name}...[/dim]")
                        
                        repo = org.get_repo(repo_name)
                        
                        # Check if repo has commits since our date
                        # PyGithub expects timezone-aware datetime
                        since_date = self.since_date
                        if since_date.tzinfo is None:
                            since_date = since_date.replace(tzinfo=timezone.utc)
                        
                        try:
                            commits = list(repo.get_commits(since=since_date))
                        except GithubException as e:
                            if "Git Repository is empty" in str(e):
                                status_counts["empty"] += 1
                                continue
                            raise
                        
                        if commits:
                            # Get contributors who have commits in the time period
                            contributors = set()
                            # Go through the recent commits to find active contributors
                            for commit in repo.get_commits(since=since_date):
                                if commit.author:
                                    contributors.add(commit.author.login)
                                if len(contributors) >= 10:  # Limit to 10 contributors per repo for sampling
                                    break
                            
                            if contributors:
                                repos_with_activity.append((repo_name, len(contributors)))
                                sample_contributors[org_name].update(contributors)
                                status_counts["active"] += 1
                                logger.info(f"✓ Found {len(contributors)} active contributors in {org_name}/{repo_name}")
                        else:
                            status_counts["no_recent_commits"] += 1
                            
                    except GithubException as e:
                        if "empty" in str(e).lower():
                            status_counts["empty"] += 1
                        else:
                            status_counts["error"] += 1
                            logger.debug(f"Error checking {org_name}/{repo_name}: {e}")
                
                # Log repository status summary
                logger.info(f"Repository status for {org_name}: {status_counts}")
                
                if len(repos_with_activity) == 0:
                    logger.warning(f"⚠️  No active repositories found in {org_name} out of {len(repos_to_check)} checked")
                else:
                    # Sort by contributor count and show top 3
                    repos_with_activity.sort(key=lambda x: x[1], reverse=True)
                    top_repos = [r[0] for r in repos_with_activity[:3]]
                    logger.info(f"✓ Found {len(repos_with_activity)} active repositories in {org_name}, top 3: {top_repos}")
                    
            except GithubException as e:
                logger.error(f"Error accessing organization {org_name}: {e}")
                
        return sample_contributors
    
    async def _get_sample_pr_and_issue_data(self, repos: Dict[str, List[str]], active_repos: Dict[str, List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Get sample PR and issue counts from active repositories"""
        sample_data = {}
        
        # Use PyGithub if available for better performance
        if self.use_pygithub:
            return self._get_sample_pr_issue_data_pygithub(repos, active_repos)
        
        semaphore = asyncio.Semaphore(2)
        
        async def get_repo_pr_issue_count(org: str, repo: str):
            async with semaphore:
                try:
                    # Get recent PRs count
                    # GitHub API needs ISO 8601 format with timezone
                    since_str = self.since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    pr_query = f'''query {{
                        repository(owner: "{org}", name: "{repo}") {{
                            pullRequests(first: 100, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
                                totalCount
                                nodes {{
                                    createdAt
                                }}
                            }}
                        }}
                    }}'''
                    pr_result = await self.git_ops.run_command([
                        'gh', 'api', 'graphql', '-f', f'query={pr_query}'
                    ])
                    
                    # Get recent issues count  
                    issue_query = f'''query {{
                        repository(owner: "{org}", name: "{repo}") {{
                            issues(first: 100, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
                                totalCount
                                nodes {{
                                    createdAt
                                }}
                            }}
                        }}
                    }}'''
                    issue_result = await self.git_ops.run_command([
                        'gh', 'api', 'graphql', '-f', f'query={issue_query}'
                    ])
                    
                    pr_count = 0
                    issue_count = 0
                    
                    if pr_result.success:
                        try:
                            pr_data = json.loads(pr_result.stdout)
                            pr_info = pr_data.get('data', {}).get('repository', {}).get('pullRequests', {})
                            # Count PRs created since our date
                            if 'nodes' in pr_info:
                                for pr in pr_info['nodes']:
                                    if pr and 'createdAt' in pr:
                                        pr_date = datetime.fromisoformat(pr['createdAt'].replace('Z', '+00:00'))
                                        if pr_date.replace(tzinfo=None) >= self.since_date:
                                            pr_count += 1
                        except Exception:
                            # Fallback to simple API
                            pr_result = await self.git_ops.run_command([
                                'gh', 'api', f'/repos/{org}/{repo}/pulls', 
                                '-F', 'state=all', '-F', 'per_page=100',
                                '-F', f'since={since_str}'
                            ])
                    if pr_result.success:
                        pr_data = json.loads(pr_result.stdout)
                        pr_count = len(pr_data) if isinstance(pr_data, list) else 0
                    
                    if issue_result.success:
                        try:
                            issue_data = json.loads(issue_result.stdout)
                            issue_info = issue_data.get('data', {}).get('repository', {}).get('issues', {})
                            # Count issues created since our date
                            if 'nodes' in issue_info:
                                for issue in issue_info['nodes']:
                                    if issue and 'createdAt' in issue:
                                        issue_date = datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00'))
                                        if issue_date.replace(tzinfo=None) >= self.since_date:
                                            issue_count += 1
                        except Exception:
                            # Fallback to simple API
                            issue_result = await self.git_ops.run_command([
                                'gh', 'api', f'/repos/{org}/{repo}/issues',
                                '-F', 'state=all', '-F', 'per_page=100',
                                '-F', f'since={since_str}'
                            ])
                    if issue_result.success:
                        issue_data = json.loads(issue_result.stdout)
                        issue_count = len(issue_data) if isinstance(issue_data, list) else 0
                    
                    logger.debug(f"Found {pr_count} PRs and {issue_count} issues in {org}/{repo} since {since_str}")
                    return org, repo, pr_count, issue_count
                    
                except Exception as e:
                    logger.debug(f"Error sampling PR/Issue data for {org}/{repo}: {e}")
                
                return org, repo, 0, 0
        
        # Use active repos if provided, otherwise take first 3 from each org
        repos_to_sample = active_repos if active_repos else {org: repo_list[:3] for org, repo_list in repos.items()}
        
        tasks = []
        for org, repo_list in repos_to_sample.items():
            sample_data[org] = {'prs': 0, 'issues': 0, 'repos_sampled': 0}
            logger.info(f"Sampling PRs/Issues from {org}: {repo_list}")
            for repo in repo_list:
                tasks.append(get_repo_pr_issue_count(org, repo))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, tuple) and len(result) == 4:
                org, repo, pr_count, issue_count = result
                sample_data[org]['prs'] += pr_count
                sample_data[org]['issues'] += issue_count
                sample_data[org]['repos_sampled'] += 1
        
        return sample_data
    
    def _get_sample_pr_issue_data_pygithub(self, repos: Dict[str, List[str]], 
                                           active_repos: Dict[str, List[str]] = None) -> Dict[str, Dict[str, int]]:
        """Get sample PR and issue counts using PyGithub"""
        sample_data = {}
        
        # Use active repos if provided, otherwise take first 3 from each org
        repos_to_sample = active_repos if active_repos else {org: repo_list[:3] for org, repo_list in repos.items()}
        
        for org_name, repo_list in repos_to_sample.items():
            sample_data[org_name] = {'prs': 0, 'issues': 0, 'repos_sampled': 0}
            logger.info(f"Sampling PRs/Issues from {org_name}: {repo_list}")
            
            try:
                org = self.github_client.get_organization(org_name)
                
                for repo_name in repo_list:
                    try:
                        repo = org.get_repo(repo_name)
                        
                        # PyGithub expects timezone-aware datetime
                        since_date = self.since_date
                        if since_date.tzinfo is None:
                            since_date = since_date.replace(tzinfo=timezone.utc)
                        
                        # Count PRs created since our date
                        pr_count = 0
                        try:
                            for pr in repo.get_pulls(state='all', sort='created', direction='desc'):
                                if pr.created_at >= since_date:
                                    pr_count += 1
                                else:
                                    # Since PRs are sorted by created date, we can break early
                                    break
                                if pr_count >= 100:  # Sample limit
                                    break
                        except GithubException as e:
                            logger.debug(f"Error getting PRs for {org_name}/{repo_name}: {e}")
                        
                        # Count issues created since our date
                        issue_count = 0
                        try:
                            for issue in repo.get_issues(state='all', sort='created', direction='desc'):
                                # Skip pull requests (they also appear as issues in GitHub API)
                                if issue.pull_request is None and issue.created_at >= since_date:
                                    issue_count += 1
                                elif issue.created_at < since_date:
                                    # Since issues are sorted by created date, we can break early
                                    break
                                if issue_count >= 100:  # Sample limit
                                    break
                        except GithubException as e:
                            logger.debug(f"Error getting issues for {org_name}/{repo_name}: {e}")
                        
                        logger.debug(f"Found {pr_count} PRs and {issue_count} issues in {org_name}/{repo_name} since {since_date}")
                        
                        sample_data[org_name]['prs'] += pr_count
                        sample_data[org_name]['issues'] += issue_count
                        sample_data[org_name]['repos_sampled'] += 1
                        
                    except GithubException as e:
                        logger.debug(f"Error accessing {org_name}/{repo_name}: {e}")
                        
            except GithubException as e:
                logger.error(f"Error accessing organization {org_name}: {e}")
        
        return sample_data
    
    def _display_comprehensive_plan(self, repos: Dict[str, List[str]], 
                                   sample_contributors: Dict[str, Set[str]], 
                                   sample_data: Dict[str, Dict[str, int]],
                                   contrib_sampled_repos: Dict[str, List[str]],
                                   pr_issue_sampled_repos: Dict[str, List[str]]) -> None:
        """Display the comprehensive analysis plan in rich tables"""
        from rich.panel import Panel
        from rich.columns import Columns
        from rich.table import Table
        from rich import box

        # Repositories table
        repo_table = Table(title="📦 Repository Analysis Scope", box=box.ROUNDED, expand=True)
        repo_table.add_column("Organization", style="cyan", no_wrap=True)
        repo_table.add_column("Repositories", justify="right")
        repo_table.add_column("Sampled For Contributors")
        repo_table.add_column("Est. Contributors", justify="right")

        total_repo_count = 0
        for org, repo_list in repos.items():
            count = len(repo_list)
            total_repo_count += count
            repo_table.add_row(
                org,
                str(count),
                f"[dim]{', '.join(contrib_sampled_repos.get(org, []))}[/dim]",
                "TBD"
            )

        repo_table.add_row("TOTAL", str(total_repo_count), "", "", style="bold")
        
        # Contributors table
        contrib_table = Table(title="👥 Contributor Analysis Preview", box=box.ROUNDED, expand=True)
        contrib_table.add_column("Organization", style="cyan", no_wrap=True)
        contrib_table.add_column("Sample Contributors")
        contrib_table.add_column("Will Analyze")
        
        for org, contributors in sample_contributors.items():
            if contributors:
                contrib_text = f"{len(contributors)} found: [dim]{', '.join(list(contributors)[:5])}...[/dim]"
            else:
                contrib_text = "[yellow]No contributors found in sample[/yellow]"
            
            contrib_table.add_row(
                org,
                contrib_text,
                f"✅ All contributors across {len(repos.get(org, []))} repositories"
            )
            
        # PRs & Issues table
        pr_table = Table(title="📊 PR & Issue Analysis Scope", box=box.ROUNDED, expand=True)
        pr_table.add_column("Organization", style="cyan", no_wrap=True)
        pr_table.add_column("Sample PRs", justify="right")
        pr_table.add_column("Sample Issues", justify="right")
        pr_table.add_column("Sampled For PRs/Issues")
        pr_table.add_column("Full Analysis")

        for org, data in sample_data.items():
            pr_table.add_row(
                org,
                str(data.get('prs', 0)),
                str(data.get('issues', 0)),
                f"[dim]{', '.join(pr_issue_sampled_repos.get(org, []))}[/dim]",
                f"✅ All PRs/Issues since {self.since_date.strftime('%Y-%m-%d')}"
            )
            
        # Analysis scope table
        scope_table = Table(title="📅 Analysis Timeline & Scope", box=box.ROUNDED, expand=True)
        scope_table.add_column("Analysis Parameter", style="cyan", no_wrap=True)
        scope_table.add_column("Value", style="white")
        scope_table.add_column("Impact", style="green")
        
        scope_table.add_row(
            "Time Range",
            f"{self.since_date.strftime('%Y-%m-%d')} to present",
            f"{(datetime.now(timezone.utc) - self.since_date).days} days of activity"
        )
        
        scope_table.add_row(
            "Analysis Mode",
            "From Scratch" if self.args.from_scratch else "Update Existing",
            "Will create new profiles" if self.args.from_scratch else "Will update existing profiles"
        )
        
        scope_table.add_row(
            "Code Analysis",
            "Enabled" if not self.args.skip_code_analysis else "Disabled",
            "Will clone repos & analyze code files" if not self.args.skip_code_analysis else "Metadata only"
        )
        
        scope_table.add_row(
            "Max Files/Contributor",
            str(self.args.max_files_per_contributor),
            f"Up to {self.args.max_files_per_contributor} recent code files per person"
        )
        
        scope_table.add_row(
            "AI Analysis",
            "4 model rotation" if self.model_rotator else "Disabled",
            "Code quality + contributor assessment" if self.model_rotator else "Manual analysis only"
        )
        
        # Resource usage estimates
        resource_table = Table(title="⚡ Resource Usage Estimates", box=box.ROUNDED, expand=True)
        resource_table.add_column("Resource", style="cyan", no_wrap=True)
        resource_table.add_column("Estimated Usage", style="yellow")
        resource_table.add_column("Notes", style="white")
        
        # Calculate estimates
        total_contributors = sum(len(contributors) for contributors in sample_contributors.values())
        estimated_api_calls = total_repo_count * 20 + total_contributors * 10
        estimated_time_minutes = estimated_api_calls / self.args.rate_limit
        estimated_disk_space = total_repo_count * 50 if not self.args.skip_code_analysis else 0  # MB estimate
        
        resource_table.add_row(
            "GitHub API Calls",
            f"~{estimated_api_calls:,}",
            f"Rate limited to {self.args.rate_limit} calls/minute"
        )
        
        resource_table.add_row(
            "Analysis Duration",
            f"~{estimated_time_minutes:.1f} minutes",
            f"With {self.args.max_workers} parallel workers"
        )
        
        if not self.args.skip_code_analysis:
            resource_table.add_row(
                "Disk Space (Temp)",
                f"~{estimated_disk_space} MB",
                f"In isolated directory: {self.args.analysis_dir}"
            )
        
        resource_table.add_row(
            "Output Files",
            f"~{total_contributors} profiles",
            f"In directory: {self.args.profiles_dir}"
        )
        
        # Display tables
        self.console.print(repo_table)
        self.console.print(contrib_table)
        self.console.print(pr_table)
        self.console.print(scope_table)
        self.console.print(resource_table)
    
    async def _get_repositories_to_analyze(self) -> Dict[str, List[str]]:
        """Get list of repositories to analyze"""
        if self.use_pygithub:
            return self._get_repositories_pygithub()
        else:
            return await self._get_repositories_github_cli()
    
    def _get_repositories_pygithub(self) -> Dict[str, List[str]]:
        """Get repositories using PyGithub - only returns repos with activity in the time period"""
        repos = {}
        
        # Get excluded repos list
        excluded_repos = set(self.args.exclude_repos) if self.args.exclude_repos else set()
        
        # PyGithub expects timezone-aware datetime
        since_date = self.since_date
        if since_date.tzinfo is None:
            since_date = since_date.replace(tzinfo=timezone.utc)
        
        for org_name in self.args.organizations:
            try:
                org = self.github_client.get_organization(org_name)
                repos[org_name] = []
                active_repo_count = 0
                checked_repo_count = 0
                
                if self.args.repositories:
                    # Check specific repositories for activity
                    logger.info(f"Checking specified repositories in {org_name} for activity since {since_date.strftime('%Y-%m-%d')}...")
                    for repo_name in self.args.repositories:
                        if '/' in repo_name:
                            # Full repo name provided
                            if repo_name.startswith(f"{org_name}/"):
                                repo_name = repo_name.split('/')[-1]
                            else:
                                continue
                        
                        # Skip excluded repos
                        if repo_name in excluded_repos:
                            logger.debug(f"Excluding repository {repo_name}")
                            continue
                        
                        try:
                            repo = org.get_repo(repo_name)
                            checked_repo_count += 1
                            
                            # Check if repo has commits in the time period
                            try:
                                commits = list(repo.get_commits(since=since_date))
                                if commits:
                                    repos[org_name].append(repo.name)
                                    active_repo_count += 1
                                    logger.info(f"✓ Active repository: {org_name}/{repo.name} ({len(commits)} commits since {since_date.strftime('%Y-%m-%d')})")
                                else:
                                    logger.debug(f"⚪ No activity in {org_name}/{repo.name} since {since_date.strftime('%Y-%m-%d')}")
                            except GithubException as e:
                                if "Git Repository is empty" in str(e):
                                    logger.debug(f"⚪ Empty repository: {org_name}/{repo.name}")
                                else:
                                    logger.warning(f"Error checking activity for {org_name}/{repo.name}: {e}")
                                    
                        except GithubException as e:
                            logger.warning(f"Could not access {org_name}/{repo_name}: {e}")
                else:
                    # Get all repositories and check for activity
                    logger.info(f"Checking all repositories in {org_name} for activity since {since_date.strftime('%Y-%m-%d')}...")
                    excluded_count = 0
                    empty_count = 0
                    no_activity_count = 0
                    
                    # First, get all repos sorted by pushed_at to check most recently active first
                    all_repo_list = []
                    for repo in org.get_repos(sort='pushed', direction='desc'):
                        all_repo_list.append(repo)
                    
                    logger.info(f"Found {len(all_repo_list)} total repositories in {org_name}, checking for activity...")
                    
                    for repo in all_repo_list:
                        if repo.name in excluded_repos:
                            logger.debug(f"Excluding repository {repo.name}")
                            excluded_count += 1
                            continue
                        
                        if repo.archived:
                            logger.debug(f"⚪ Archived repository: {repo.name}")
                            continue
                        
                        checked_repo_count += 1
                        
                        # Quick check: if pushed_at is before our date, skip checking commits
                        if repo.pushed_at and repo.pushed_at < since_date:
                            logger.debug(f"⚪ No recent pushes to {repo.name} (last push: {repo.pushed_at.strftime('%Y-%m-%d')})")
                            no_activity_count += 1
                            continue
                        
                        # Check for commits in the time period
                        try:
                            # Just check if there's at least one commit
                            commits = list(repo.get_commits(since=since_date).get_page(0))
                            if commits:
                                repos[org_name].append(repo.name)
                                active_repo_count += 1
                                logger.debug(f"✓ Active repository: {repo.name}")
                            else:
                                no_activity_count += 1
                                logger.debug(f"⚪ No commits in {repo.name} since {since_date.strftime('%Y-%m-%d')}")
                        except GithubException as e:
                            if "Git Repository is empty" in str(e):
                                empty_count += 1
                                logger.debug(f"⚪ Empty repository: {repo.name}")
                            else:
                                logger.debug(f"Error checking {repo.name}: {e}")
                    
                    # Log summary
                    logger.info(f"Activity summary for {org_name}:")
                    logger.info(f"  - Active repositories: {active_repo_count}")
                    logger.info(f"  - No activity: {no_activity_count}")
                    logger.info(f"  - Empty repositories: {empty_count}")
                    logger.info(f"  - Excluded repositories: {excluded_count}")
                    
                    if repos[org_name]:
                        top_5 = repos[org_name][:5]
                        logger.info(f"  - Top 5 active repos: {', '.join(top_5)}")
                
                if active_repo_count == 0:
                    logger.warning(f"⚠️  No repositories with activity since {since_date.strftime('%Y-%m-%d')} found in {org_name}")
                else:
                    logger.info(f"✅ Found {active_repo_count} active repositories (out of {checked_repo_count} checked) in {org_name}")
                    
            except GithubException as e:
                print_warning(f"Error accessing organization '{org_name}': {e}")
                repos[org_name] = []
        
        return repos
    
    async def _get_repositories_github_cli(self) -> Dict[str, List[str]]:
        """Get list of repositories to analyze using GitHub CLI - only returns repos with activity"""
        repos = {}
        
        # Get excluded repos list
        excluded_repos = set(self.args.exclude_repos) if self.args.exclude_repos else set()
        since_str = self.since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        for org in self.args.organizations:
            repos[org] = []
            active_repo_count = 0
            
            if self.args.repositories:
                # Check specified repositories for activity
                logger.info(f"Checking specified repositories in {org} for activity since {self.since_date.strftime('%Y-%m-%d')}...")
                org_repos = [r for r in self.args.repositories 
                           if '/' not in r or r.startswith(f"{org}/")]
                
                for r in org_repos:
                    repo_name = r.split('/')[-1] if '/' in r else r
                    
                    if repo_name in excluded_repos:
                        logger.debug(f"Excluding repository {repo_name}")
                        continue
                    
                    # Check if repo has commits in time period
                    result = await self.git_ops.run_command([
                        'gh', 'api', f'/repos/{org}/{repo_name}/commits',
                        '-F', f'since={since_str}',
                        '-F', 'per_page=1'
                    ])
                    
                    if result.success and json.loads(result.stdout or '[]'):
                        repos[org].append(repo_name)
                        active_repo_count += 1
                        logger.info(f"✓ Active repository: {org}/{repo_name}")
                    else:
                        logger.debug(f"⚪ No activity in {org}/{repo_name} since {self.since_date.strftime('%Y-%m-%d')}")
            else:
                # Get all repositories and check for activity
                logger.info(f"Checking all repositories in {org} for activity since {self.since_date.strftime('%Y-%m-%d')}...")
                try:
                    # First get all repos with more info
                    result = await self.git_ops.run_command([
                        'gh', 'repo', 'list', org, '--json', 'name,pushedAt,isArchived', '--limit', '1000'
                    ])
                    
                    if result.success:
                        repo_data = json.loads(result.stdout)
                        excluded_count = 0
                        archived_count = 0
                        no_activity_count = 0
                        checked_count = 0
                        
                        # Sort by pushedAt to check most recently active first
                        repo_data.sort(key=lambda x: x.get('pushedAt', ''), reverse=True)
                        
                        logger.info(f"Found {len(repo_data)} total repositories in {org}, checking for activity...")
                        
                        for repo_info in repo_data:
                            repo_name = repo_info['name']
                            
                            if repo_name in excluded_repos:
                                logger.debug(f"Excluding repository {repo_name}")
                                excluded_count += 1
                                continue
                            
                            if repo_info.get('isArchived', False):
                                logger.debug(f"⚪ Archived repository: {repo_name}")
                                archived_count += 1
                                continue
                            
                            checked_count += 1
                            
                            # Check for commits in time period
                            commits_result = await self.git_ops.run_command([
                                'gh', 'api', f'/repos/{org}/{repo_name}/commits',
                                '-F', f'since={since_str}',
                                '-F', 'per_page=1'
                            ])
                            
                            if commits_result.success:
                                commits = json.loads(commits_result.stdout or '[]')
                                if commits:
                                    repos[org].append(repo_name)
                                    active_repo_count += 1
                                    logger.debug(f"✓ Active repository: {repo_name}")
                                else:
                                    no_activity_count += 1
                                    logger.debug(f"⚪ No commits in {repo_name} since {self.since_date.strftime('%Y-%m-%d')}")
                            else:
                                logger.debug(f"Error checking {repo_name}: {commits_result.stderr}")
                        
                        # Log summary
                        logger.info(f"Activity summary for {org}:")
                        logger.info(f"  - Active repositories: {active_repo_count}")
                        logger.info(f"  - No activity: {no_activity_count}")
                        logger.info(f"  - Archived repositories: {archived_count}")
                        logger.info(f"  - Excluded repositories: {excluded_count}")
                        
                        if repos[org]:
                            top_5 = repos[org][:5]
                            logger.info(f"  - Top 5 active repos: {', '.join(top_5)}")
                    else:
                        error_msg = result.stderr.strip()
                        if "404" in error_msg or "Not Found" in error_msg:
                            print_warning(f"Organization '{org}' not found or private. Check organization name and access permissions.")
                        elif "403" in error_msg or "Forbidden" in error_msg:
                            print_warning(f"Access denied to organization '{org}'. You may need additional permissions.")
                        else:
                            print_warning(f"Could not fetch repositories for {org}: {error_msg}")
                        
                except Exception as e:
                    print_warning(f"Error fetching repositories for {org}: {e}")
            
            if active_repo_count == 0:
                logger.warning(f"⚠️  No repositories with activity since {self.since_date.strftime('%Y-%m-%d')} found in {org}")
            else:
                logger.info(f"✅ Found {active_repo_count} active repositories in {org}")
        
        return repos
    
    async def _run_analysis(self) -> int:
        """Run the full contributor analysis"""
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=self.console
            ) as progress:
                
                # Phase 1: Discovery
                discovery_task = progress.add_task("🔍 Discovering repositories...", total=None)
                repos = await self._get_repositories_to_analyze()
                total_repos = sum(len(r) for r in repos.values())
                progress.update(discovery_task, description=f"✅ Found {total_repos} repositories")
                
                # Phase 2: Contributor Discovery
                contributor_task = progress.add_task("👥 Discovering contributors...", total=total_repos)
                contributors = await self._discover_contributors(repos, progress, contributor_task)
                
                # Phase 3: Data Collection
                collection_task = progress.add_task("📊 Collecting contribution data...", total=len(contributors))
                await self._collect_contributor_data(contributors, repos, progress, collection_task)
                
                # Phase 4: Repository Cloning & Code Analysis
                if not self.args.skip_code_analysis:
                    clone_task = progress.add_task("📦 Cloning repositories for code analysis...", total=total_repos)
                    cloned_repos = await self._clone_repositories(repos, progress, clone_task)
                    
                    code_analysis_task = progress.add_task("🔍 Analyzing code files...", total=len(contributors))
                    await self._analyze_code_quality(contributors, cloned_repos, progress, code_analysis_task)
                
                # Phase 5: AI Analysis
                if self.model_rotator:
                    analysis_task = progress.add_task("🤖 AI analysis of contributions...", total=len(contributors))
                    await self._ai_analyze_contributors(contributors, progress, analysis_task)
                
                # Phase 6: Profile Generation
                generation_task = progress.add_task("📝 Generating profiles...", total=len(contributors))
                await self._generate_profiles(contributors, progress, generation_task)
            
            # Show summary
            self._show_analysis_summary()
            
            print_success(f"Analysis complete! Generated {len(self.contributors)} contributor profiles in {self.args.profiles_dir}")
            
            # Cleanup isolated directory if it was auto-created
            if self.args.analysis_dir.name.startswith("contributor_analysis_"):
                try:
                    shutil.rmtree(self.args.analysis_dir)
                    logger.info(f"Cleaned up isolated analysis directory: {self.args.analysis_dir}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup analysis directory: {e}")
            
            return 0
            
        except Exception as e:
            logger.exception("Analysis failed")
            print_error(f"Analysis failed: {e}")
            
            # Cleanup on failure too
            if hasattr(self.args, 'analysis_dir') and self.args.analysis_dir.name.startswith("contributor_analysis_"):
                try:
                    shutil.rmtree(self.args.analysis_dir)
                    logger.info("Cleaned up analysis directory after failure")
                except Exception:
                    pass
            
            return 1
    
    async def _discover_contributors(self, repos: Dict[str, List[str]], 
                                   progress: Progress, task_id) -> Set[str]:
        """Discover contributors who have been active in the time period"""
        contributors = set()
        
        if self.use_pygithub:
            return self._discover_contributors_pygithub(repos, progress, task_id)
        
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.args.max_workers)
        
        async def get_active_repo_contributors(org: str, repo: str):
            async with semaphore:
                try:
                    # Get commits since the date to find active contributors
                    since_str = self.since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    result = await self.git_ops.run_command([
                        'gh', 'api', f'/repos/{org}/{repo}/commits',
                        '-F', f'since={since_str}',
                        '--paginate'
                    ])
                    
                    if result.success:
                        commits_data = json.loads(result.stdout)
                        repo_contributors = set()
                        
                        # Extract unique authors from commits
                        for commit in commits_data:
                            author = commit.get('author')
                            if author and author.get('login'):
                                repo_contributors.add(author['login'])
                            
                            # Also check commit author info
                            commit_author = commit.get('commit', {}).get('author')
                            if commit_author:
                                # Try to get GitHub username from committer
                                committer = commit.get('committer')
                                if committer and committer.get('login'):
                                    repo_contributors.add(committer['login'])
                        
                        if repo_contributors:
                            logger.debug(f"Found {len(repo_contributors)} active contributors in {org}/{repo}")
                        
                        progress.advance(task_id)
                        return repo_contributors
                    
                except Exception as e:
                    logger.warning(f"Error getting active contributors for {org}/{repo}: {e}")
                
                progress.advance(task_id)
                return set()
        
        # Collect all active contributors in parallel
        tasks = []
        for org, repo_list in repos.items():
            for repo in repo_list:
                task = get_active_repo_contributors(org, repo)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, set):
                contributors.update(result)
        
        # Filter out excluded contributors
        if hasattr(self.args, 'exclude_contributors') and self.args.exclude_contributors:
            excluded = set(self.args.exclude_contributors)
            before_count = len(contributors)
            contributors = contributors - excluded
            if before_count > len(contributors):
                logger.info(f"Excluded {before_count - len(contributors)} contributors from analysis")
        
        logger.info(f"Discovered {len(contributors)} unique active contributors since {self.since_date.strftime('%Y-%m-%d')}")
        return contributors
    
    def _discover_contributors_pygithub(self, repos: Dict[str, List[str]], 
                                       progress: Progress, task_id) -> Set[str]:
        """Discover active contributors using PyGithub"""
        contributors = set()
        
        # PyGithub expects timezone-aware datetime
        since_date = self.since_date
        if since_date.tzinfo is None:
            since_date = since_date.replace(tzinfo=timezone.utc)
        
        for org_name, repo_list in repos.items():
            try:
                org = self.github_client.get_organization(org_name)
                
                for repo_name in repo_list:
                    try:
                        repo = org.get_repo(repo_name)
                        
                        # Get commits since the date
                        try:
                            commit_count = 0
                            for commit in repo.get_commits(since=since_date):
                                commit_count += 1
                                
                                # Debug: Check actual commit date
                                commit_date = commit.commit.author.date
                                if self.args.debug_api:
                                    logger.info(f"Commit in {org_name}/{repo_name}: {commit.sha[:7]} by {commit.author.login if commit.author else 'unknown'} on {commit_date}")
                                
                                # Double-check the date is actually within our range
                                if commit_date < since_date:
                                    logger.warning(f"BUG: Got commit from {commit_date} which is before our since_date {since_date} in {org_name}/{repo_name}")
                                    continue
                                
                                # Get author (GitHub user) if available
                                if commit.author:
                                    contributors.add(commit.author.login)
                                    if self.args.debug_api:
                                        logger.info(f"Added contributor: {commit.author.login} from commit on {commit_date}")
                                
                                # Also check committer
                                if commit.committer and commit.committer.login != 'web-flow':
                                    # web-flow is GitHub's merge commit bot
                                    contributors.add(commit.committer.login)
                            
                            if self.args.debug_api and commit_count > 0:
                                logger.info(f"Found {commit_count} commits in {org_name}/{repo_name} since {since_date}")
                        except GithubException as e:
                            if "Git Repository is empty" not in str(e):
                                logger.debug(f"Error getting commits for {org_name}/{repo_name}: {e}")
                        
                        progress.advance(task_id)
                        
                    except GithubException as e:
                        logger.warning(f"Error accessing {org_name}/{repo_name}: {e}")
                        progress.advance(task_id)
                        
            except GithubException as e:
                logger.error(f"Error accessing organization {org_name}: {e}")
        
        # Filter out excluded contributors
        if hasattr(self.args, 'exclude_contributors') and self.args.exclude_contributors:
            excluded = set(self.args.exclude_contributors)
            before_count = len(contributors)
            contributors = contributors - excluded
            if before_count > len(contributors):
                logger.info(f"Excluded {before_count - len(contributors)} contributors from analysis")
        
        logger.info(f"Discovered {len(contributors)} unique active contributors since {since_date.strftime('%Y-%m-%d')}")
        return contributors
    
    async def _collect_contributor_data(self, contributors: Set[str], repos: Dict[str, List[str]], 
                                      progress: Progress, task_id) -> None:
        """Collect detailed data for each contributor"""
        # Process contributors in batches for better performance
        contributor_list = list(contributors)
        batch_size = 10
        
        for i in range(0, len(contributor_list), batch_size):
            batch = contributor_list[i:i+batch_size]
            
            # Process batch using ParallelProcessor
            async def process_contributor(username: str):
                try:
                    profile = ContributorProfile(username=username)
                    
                    # Get user profile
                    await self._get_user_profile(username, profile)
                    
                    # Prepare repos for batch commit fetching
                    repo_pairs = []
                    for org, repo_list in repos.items():
                        for repo in repo_list[:10]:  # Limit repos per contributor
                            repo_pairs.append((org, repo))
                    
                    # Analyze contributions across repositories
                    for org, repo_list in repos.items():
                        for repo in repo_list[:10]:  # Limit repos per contributor
                            await self._analyze_repo_contributions(username, org, repo, profile)
                    
                    # Calculate derived metrics
                    self._calculate_derived_metrics(profile)
                    
                    self.contributors[username] = profile
                    progress.advance(task_id)
                    
                except Exception as e:
                    logger.warning(f"Error collecting data for {username}: {e}")
                    progress.advance(task_id)
        
            # Process batch
            tasks = [process_contributor(username) for username in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Small delay between batches
            if i + batch_size < len(contributor_list):
                await asyncio.sleep(0.1)
    
    async def _get_user_profile(self, username: str, profile: ContributorProfile) -> None:
        """Get basic user profile information"""
        try:
            result = await self.git_ops.run_command([
                'gh', 'api', f'/users/{username}'
            ])
            
            if result.success:
                user_data = json.loads(result.stdout)
                profile.name = user_data.get('name')
                profile.email = user_data.get('email')
                
        except Exception as e:
            logger.debug(f"Error getting profile for {username}: {e}")
    
    async def _analyze_repo_contributions(self, username: str, org: str, repo: str, 
                                        profile: ContributorProfile) -> None:
        """Analyze contributions to a specific repository"""
        try:
            # Get commits since the specified date
            # GitHub API needs ISO 8601 format with timezone
            since_str = self.since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            result = await self.git_ops.run_command([
                'gh', 'api', f'/repos/{org}/{repo}/commits', 
                '-F', f'author={username}',
                '-F', f'since={since_str}',
                '--paginate'
            ])
            
            if result.success:
                commits = json.loads(result.stdout)
                commit_count = len(commits) if isinstance(commits, list) else 0
                profile.total_commits += commit_count
                
                if commit_count > 0:
                    profile.repositories.add(f"{org}/{repo}")
                    
                    # Analyze recent commits for dates and patterns
                    for commit in commits[:10]:  # Sample recent commits
                        commit_date_str = commit.get('commit', {}).get('author', {}).get('date')
                        if commit_date_str:
                            commit_date = datetime.fromisoformat(
                                commit_date_str.replace('Z', '+00:00')
                            ).replace(tzinfo=None)
                            
                            if not profile.first_contribution or commit_date < profile.first_contribution:
                                profile.first_contribution = commit_date
                            if not profile.last_contribution or commit_date > profile.last_contribution:
                                profile.last_contribution = commit_date
            
            # Get PRs
            result = await self.git_ops.run_command([
                'gh', 'api', f'/repos/{org}/{repo}/pulls',
                '-F', 'state=all',
                '-F', f'creator={username}',
                '--paginate'
            ])
            
            if result.success:
                prs = json.loads(result.stdout)
                pr_count = len(prs) if isinstance(prs, list) else 0
                profile.total_prs += pr_count
            
        except Exception as e:
            logger.debug(f"Error analyzing {username} contributions to {org}/{repo}: {e}")
    
    def _calculate_derived_metrics(self, profile: ContributorProfile) -> None:
        """Calculate derived metrics for a contributor"""
        if profile.first_contribution and profile.last_contribution:
            days_active = (profile.last_contribution - profile.first_contribution).days
            if days_active > 0:
                profile.contribution_frequency = (profile.total_commits * 7) / days_active
        
        # Set placeholder for avg PR size (would need detailed PR analysis)
        profile.avg_pr_size = 100.0
    
    async def _clone_repositories(self, repos: Dict[str, List[str]], 
                                 progress: Progress, task_id) -> Dict[str, Path]:
        """Clone repositories to isolated directory for code analysis"""
        cloned_repos = {}
        semaphore = asyncio.Semaphore(self.args.max_workers)
        
        async def clone_single_repo(org: str, repo: str):
            async with semaphore:
                try:
                    repo_path = self.args.analysis_dir / f"{org}_{repo}"
                    
                    # Skip if already cloned
                    if repo_path.exists():
                        logger.debug(f"Repository {org}/{repo} already cloned")
                        progress.advance(task_id)
                        return repo_path
                    
                    # Clone repository
                    clone_result = await self.git_ops.run_command([
                        'gh', 'repo', 'clone', f"{org}/{repo}", str(repo_path),
                        '--', '--depth', '50'  # Shallow clone for performance
                    ])
                    
                    if clone_result.success:
                        cloned_repos[f"{org}/{repo}"] = repo_path
                        logger.debug(f"Successfully cloned {org}/{repo}")
                    else:
                        logger.warning(f"Failed to clone {org}/{repo}: {clone_result.stderr}")
                    
                    progress.advance(task_id)
                    return repo_path if clone_result.success else None
                    
                except Exception as e:
                    logger.error(f"Error cloning {org}/{repo}: {e}")
                    progress.advance(task_id)
                    return None
        
        # Clone all repositories in parallel
        tasks = []
        for org, repo_list in repos.items():
            for repo in repo_list:
                task = clone_single_repo(org, repo)
                tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Cloned {len(cloned_repos)} repositories for analysis")
        return cloned_repos
    
    async def _analyze_code_quality(self, contributors: Set[str], 
                                   cloned_repos: Dict[str, Path],
                                   progress: Progress, task_id) -> None:
        """Analyze code quality for each contributor"""
        semaphore = asyncio.Semaphore(2)  # Limit concurrent file analysis
        
        async def analyze_contributor_code(username: str):
            async with semaphore:
                try:
                    if username not in self.contributors:
                        progress.advance(task_id)
                        return
                    
                    profile = self.contributors[username]
                    code_samples = []
                    language_counts = {}
                    
                    # Analyze code in each repository the contributor works on
                    for repo_key, repo_path in cloned_repos.items():
                        if not repo_path or not repo_path.exists():
                            continue
                        
                        # Get recent commits by this contributor
                        recent_commits = await self._get_recent_commits_by_user(
                            repo_path, username, limit=10
                        )
                        
                        # Analyze changed files in recent commits
                        for commit in recent_commits[:5]:  # Analyze top 5 recent commits
                            changed_files = await self._get_changed_files_in_commit(
                                repo_path, commit['sha']
                            )
                            
                            for file_path in changed_files[:self.args.max_files_per_contributor]:
                                if self._is_code_file(file_path):
                                    file_content = await self._read_file_content(
                                        repo_path / file_path
                                    )
                                    
                                    if file_content:
                                        # Track language usage
                                        lang = self._detect_language(file_path)
                                        language_counts[lang] = language_counts.get(lang, 0) + 1
                                        
                                        # Store code sample for AI analysis
                                        code_samples.append({
                                            'file': file_path,
                                            'content': file_content[:2000],  # First 2000 chars
                                            'language': lang,
                                            'repository': repo_key,
                                            'commit': commit['sha'][:8]
                                        })
                                        
                                        if len(code_samples) >= self.args.max_files_per_contributor:
                                            break
                    
                    # Update profile with code analysis data
                    profile.recent_code_samples = code_samples
                    profile.primary_languages = language_counts
                    
                    # AI analysis of code quality
                    if self.model_rotator and code_samples:
                        await self._ai_analyze_code_quality(profile)
                    
                    progress.advance(task_id)
                    
                except Exception as e:
                    logger.error(f"Error analyzing code for {username}: {e}")
                    progress.advance(task_id)
        
        # Process all contributors
        tasks = [analyze_contributor_code(username) for username in contributors]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _get_recent_commits_by_user(self, repo_path: Path, username: str, 
                                         limit: int = 10) -> List[Dict[str, str]]:
        """Get recent commits by a specific user"""
        try:
            result = await self.git_ops.run_command([
                'git', 'log', '--oneline', f'--author={username}', 
                f'--max-count={limit}', '--format=%H|%s|%ad',
                '--date=iso'
            ], cwd=repo_path)
            
            if result.success:
                commits = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('|', 2)
                        if len(parts) >= 2:
                            commits.append({
                                'sha': parts[0],
                                'message': parts[1],
                                'date': parts[2] if len(parts) > 2 else ''
                            })
                return commits
        except Exception as e:
            logger.debug(f"Error getting commits for {username}: {e}")
        
        return []
    
    async def _get_changed_files_in_commit(self, repo_path: Path, commit_sha: str) -> List[str]:
        """Get files changed in a specific commit"""
        try:
            result = await self.git_ops.run_command([
                'git', 'show', '--name-only', '--format=', commit_sha
            ], cwd=repo_path)
            
            if result.success:
                return [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        except Exception as e:
            logger.debug(f"Error getting changed files for {commit_sha}: {e}")
        
        return []
    
    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a code file worth analyzing"""
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h', '.hpp',
            '.cs', '.go', '.rs', '.php', '.rb', '.swift', '.kt', '.scala',
            '.dart', '.vue', '.svelte', '.sol', '.r', '.m', '.mm', '.cc', '.cxx',
            '.c++', '.hxx', '.h++', '.asm', '.s'
        }
        
        # Skip certain directories and files
        skip_patterns = {
            'node_modules', '.git', '__pycache__', '.pytest_cache',
            'venv', 'env', 'dist', 'build', '.next', 'target'
        }
        
        for pattern in skip_patterns:
            if pattern in file_path:
                return False
        
        return any(file_path.endswith(ext) for ext in code_extensions)
    
    async def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content safely"""
        try:
            if file_path.exists() and file_path.stat().st_size < 100000:  # Skip very large files
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        except Exception as e:
            logger.debug(f"Error reading {file_path}: {e}")
        return None
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        extension_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React',
            '.tsx': 'React TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.cc': 'C++',
            '.cxx': 'C++',
            '.c++': 'C++',
            '.c': 'C',
            '.h': 'C/C++',
            '.hpp': 'C++',
            '.hxx': 'C++',
            '.h++': 'C++',
            '.cs': 'C#',
            '.go': 'Go',
            '.rs': 'Rust',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.dart': 'Dart',
            '.vue': 'Vue.js',
            '.sol': 'Solidity',
            '.asm': 'Assembly',
            '.s': 'Assembly',
            '.m': 'Objective-C',
            '.mm': 'Objective-C++',
            '.scala': 'Scala'
        }
        
        for ext, lang in extension_map.items():
            if file_path.endswith(ext):
                return lang
        
        return 'Unknown'
    
    async def _ai_analyze_code_quality(self, profile: ContributorProfile) -> None:
        """Use AI to analyze code quality and patterns"""
        if not profile.recent_code_samples:
            return
        
        try:
            client, model = self.model_rotator.get_next_client()
            
            # Build code analysis prompt
            prompt = self._build_code_analysis_prompt(profile)
            
            response = await client.generate_content_async(
                prompt=prompt,
                model=model,
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=1500
            )
            
            if response and response.text:
                analysis_data = self._parse_code_analysis_response(response.text)
                
                profile.code_quality_score = analysis_data.get('quality_score', 0.0)
                profile.code_patterns = analysis_data.get('patterns', [])
                profile.code_style_assessment = analysis_data.get('style_assessment', '')
                profile.architectural_contributions = analysis_data.get('architectural_work', [])
                
                logger.debug(f"✅ Code analysis completed for {profile.username} with {model}")
            
        except Exception as e:
            # Mark model failure and try fallback
            if 'model' in locals():
                self.model_rotator.mark_model_failure(model, e)
            logger.warning(f"❌ Code analysis failed for {profile.username}: {e}")
    
    def _build_code_analysis_prompt(self, profile: ContributorProfile) -> str:
        """Build AI prompt for code quality analysis"""
        builder = PromptBuilder()
        
        builder.add_section("Code Quality Analysis Request", 
                          f"Analyze the code quality and patterns for contributor {profile.username}")
        
        # Add code samples
        code_summary = []
        for sample in profile.recent_code_samples[:10]:  # Analyze top 10 samples
            code_summary.append(f"File: {sample['file']} ({sample['language']})")
            code_summary.append(f"Repository: {sample['repository']}")
            code_summary.append(f"Code:\n{sample['content'][:1000]}...")  # First 1000 chars
            code_summary.append("---")
        
        builder.add_context({
            "Total Code Samples": len(profile.recent_code_samples),
            "Primary Languages": ', '.join(profile.primary_languages.keys()),
            "Code Samples": '\n'.join(code_summary)
        })
        
        builder.add_requirements([
            "Assess overall code quality on a scale of 1-10",
            "Identify common patterns and practices in their code",
            "Evaluate code style and consistency", 
            "Identify any architectural or design contributions",
            "Note strengths and areas for improvement",
            "Focus on technical skill level and code craftsmanship"
        ])
        
        builder.add_section("Response Format", """
Please respond in JSON format:
{
  "quality_score": 7.5,
  "patterns": ["uses clean functions", "good error handling", "follows naming conventions"],
  "style_assessment": "Consistent and professional coding style with good documentation",
  "architectural_work": ["designed user authentication system", "implemented caching layer"],
  "strengths": ["strong testing practices", "performance optimization"],
  "improvements": ["could use more comments", "some functions are too long"]
}
""")
        
        return builder.build()
    
    def _parse_code_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse AI code analysis response"""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback parsing for non-JSON responses
            return {
                'quality_score': 5.0,
                'patterns': [],
                'style_assessment': response_text[:500],
                'architectural_work': [],
                'strengths': [],
                'improvements': []
            }
    
    async def _ai_analyze_contributors(self, contributors: Set[str], progress: Progress, task_id) -> None:
        """Use AI to analyze contributors with model rotation"""
        if not self.model_rotator:
            for _ in contributors:
                progress.advance(task_id)
            return
        
        semaphore = asyncio.Semaphore(2)  # Limit concurrent AI requests
        
        async def analyze_single_contributor(username: str):
            async with semaphore:
                try:
                    if username in self.contributors:
                        profile = self.contributors[username]
                        
                        # Get next AI client
                        client, model = self.model_rotator.get_next_client()
                        
                        try:
                            # Build analysis prompt
                            prompt = self._build_ai_analysis_prompt(profile)
                            
                            # Get AI analysis
                            response = await client.generate_content_async(
                                prompt=prompt,
                                model=model,
                                temperature=0.7,
                                max_tokens=1000
                            )
                            
                            if response and response.text:
                                analysis_data = self._parse_ai_response(response.text)
                                profile.ai_analysis = analysis_data.get('analysis', response.text)
                                profile.skill_assessment = analysis_data.get('skills', {})
                                logger.debug(f"✅ AI analysis completed for {username} with {model}")
                            else:
                                logger.warning(f"❌ Empty AI response for {username} from {model}")
                                
                        except Exception as ai_error:
                            # Mark model failure for rate limiting
                            self.model_rotator.mark_model_failure(model, ai_error)
                            logger.warning(f"❌ AI analysis failed for {username} with {model}: {ai_error}")
                            
                            # Try fallback model if primary failed
                            if model != self.model_rotator.FALLBACK_MODEL:
                                try:
                                    fallback_client = self.model_rotator.clients.get(self.model_rotator.FALLBACK_MODEL)
                                    if fallback_client:
                                        logger.info(f"Retrying {username} with fallback model")
                                        prompt = self._build_ai_analysis_prompt(profile)
                                        response = await fallback_client.generate_content_async(
                                            prompt=prompt,
                                            model=self.model_rotator.FALLBACK_MODEL,
                                            temperature=0.7,
                                            max_tokens=1000
                                        )
                                        
                                        if response and response.text:
                                            analysis_data = self._parse_ai_response(response.text)
                                            profile.ai_analysis = analysis_data.get('analysis', response.text)
                                            profile.skill_assessment = analysis_data.get('skills', {})
                                            logger.debug(f"✅ Fallback analysis completed for {username}")
                                        
                                except Exception as fallback_error:
                                    logger.error(f"❌ Fallback AI analysis also failed for {username}: {fallback_error}")
                        
                        progress.advance(task_id)
                        
                        # Small delay for rate limiting
                        await asyncio.sleep(0.1)
                
                except Exception as e:
                    logger.warning(f"Error in AI analysis for {username}: {e}")
                    progress.advance(task_id)
        
        # Process contributors in batches
        tasks = [analyze_single_contributor(username) 
                for username in contributors if username in self.contributors]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def _build_ai_analysis_prompt(self, profile: ContributorProfile) -> str:
        """Build AI analysis prompt for a contributor"""
        builder = PromptBuilder()
        
        builder.add_section("Contributor Analysis Request", 
                          f"Analyze this GitHub contributor's performance and expertise")
        
        builder.add_context({
            "Username": profile.username,
            "Total Commits": profile.total_commits,
            "Total PRs": profile.total_prs,
            "Active Repositories": len(profile.repositories),
            "Repository List": ', '.join(list(profile.repositories)[:10]),
            "Contribution Frequency": f"{profile.contribution_frequency:.1f} commits/week",
            "Activity Span": f"{(profile.last_contribution - profile.first_contribution).days if profile.first_contribution and profile.last_contribution else 0} days"
        })
        
        builder.add_requirements([
            "Provide a brief analysis of their contribution patterns and activity level",
            "Assess their technical skills based on repository types and contribution volume", 
            "Identify notable strengths or areas of expertise",
            "Keep analysis concise and professional",
            "Focus on quantifiable patterns and technical indicators"
        ])
        
        builder.add_section("Response Format", """
Please respond in JSON format:
{
  "analysis": "brief professional analysis of contribution patterns",
  "skills": {
    "backend": "beginner|intermediate|advanced|expert",
    "frontend": "beginner|intermediate|advanced|expert", 
    "devops": "beginner|intermediate|advanced|expert",
    "mobile": "beginner|intermediate|advanced|expert"
  },
  "summary": "one-line summary of their technical profile"
}
""")
        
        return builder.build()
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """Parse AI response, handling both JSON and plain text"""
        try:
            # Try to parse as JSON
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Fallback to plain text
            return {
                'analysis': response_text,
                'skills': {},
                'summary': 'AI analysis available'
            }
    
    async def _generate_profiles(self, contributors: Set[str], progress: Progress, task_id) -> None:
        """Generate markdown profiles for contributors"""
        # Use async file operations for better performance
        profile_data = {}
        
        for username in contributors:
            if username in self.contributors:
                try:
                    profile = self.contributors[username]
                    profile_content = self._generate_profile_markdown(profile)
                    
                    # Store for batch write
                    safe_username = username.replace('@', 'at-').replace('/', '-')
                    profile_file = self.args.profiles_dir / f"{safe_username}.md"
                    profile_data[profile_file] = profile_content
                    
                    progress.advance(task_id)
                    
                except Exception as e:
                    logger.warning(f"Error generating profile for {username}: {e}")
                    progress.advance(task_id)
        
        # Write all profiles in parallel using enhanced batch operations
        if profile_data:
            write_results = await self.file_ops.write_files_batch(profile_data)
            
            # Log any write failures
            failed_writes = [path for path, success in write_results.items() if not success]
            if failed_writes:
                logger.warning(f"Failed to write {len(failed_writes)} profile files")
            else:
                logger.info(f"Successfully wrote {len(profile_data)} profile files")
    
    def _generate_profile_markdown(self, profile: ContributorProfile) -> str:
        """Generate markdown profile for a contributor"""
        name_display = profile.name or profile.username
        
        content = f"""# {name_display} (@{profile.username})

*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Analysis period: {self.since_date.strftime('%Y-%m-%d')} to present*

## Overview

**GitHub Username:** @{profile.username}  
**Name:** {profile.name or 'N/A'}  
**Email:** {profile.email or 'N/A'}  

## Contribution Summary

| Metric | Value |
|--------|-------|
| Total Commits | {profile.total_commits:,} |
| Total Pull Requests | {profile.total_prs:,} |
| Active Repositories | {len(profile.repositories)} |
| First Contribution | {profile.first_contribution.strftime('%Y-%m-%d') if profile.first_contribution else 'N/A'} |
| Last Contribution | {profile.last_contribution.strftime('%Y-%m-%d') if profile.last_contribution else 'N/A'} |
| Contribution Frequency | {profile.contribution_frequency:.1f} commits/week |

## Active Repositories

"""
        
        if profile.repositories:
            for repo in sorted(profile.repositories):
                content += f"- `{repo}`\n"
        else:
            content += "No repositories found in the analysis period.\n"
        
        content += "\n## Skill Assessment\n\n"
        
        if profile.skill_assessment:
            content += "| Skill Area | Level |\n|------------|-------|\n"
            for skill, level in profile.skill_assessment.items():
                content += f"| {skill.title()} | {level.title()} |\n"
        else:
            content += "Skill assessment not available.\n"
        
        content += "\n## AI Analysis\n\n"
        
        if profile.ai_analysis:
            content += profile.ai_analysis
        else:
            content += "AI analysis not available.\n"
        
        content += f"""

## Code Quality Analysis

| Metric | Value |
|--------|-------|
| **Code Quality Score** | {profile.code_quality_score:.1f}/10 |
| **Primary Languages** | {', '.join(f"{lang} ({count})" for lang, count in sorted(profile.primary_languages.items(), key=lambda x: x[1], reverse=True)[:5]) if profile.primary_languages else 'Not analyzed'} |
| **Code Files Analyzed** | {len(profile.recent_code_samples)} |

### Code Style Assessment
{profile.code_style_assessment if profile.code_style_assessment else 'Code style analysis pending.'}

### Code Patterns & Practices
"""
        
        if profile.code_patterns:
            for pattern in profile.code_patterns:
                content += f"- {pattern}\n"
        else:
            content += "- Code pattern analysis pending\n"
        
        content += "\n### Architectural Contributions\n"
        
        if profile.architectural_contributions:
            for contribution in profile.architectural_contributions:
                content += f"- {contribution}\n"
        else:
            content += "- Architectural analysis pending\n"

        content += f"""

## Technical Metrics

- **Average PR Size:** {profile.avg_pr_size:.0f} lines changed (estimated)
- **Code Reviews:** {profile.code_review_count}
- **Legacy Languages:** {', '.join(sorted(profile.languages)) if profile.languages else 'Not analyzed'}

## Notable Contributions

"""
        
        if profile.notable_contributions:
            for contribution in profile.notable_contributions:
                content += f"- {contribution}\n"
        else:
            content += "Notable contributions analysis pending.\n"
        
        content += f"""

---

*Profile generated by Contributor Analyzer on {datetime.now().strftime('%Y-%m-%d')}*  
*Analysis covers activity from {self.since_date.strftime('%Y-%m-%d')} onwards*  
*Powered by GitHub CLI and Gemini AI*
"""
        
        return content
    
    def _show_analysis_summary(self):
        """Show summary of analysis results"""
        from rich.table import Table
        from rich import box
        
        if not self.contributors:
            self.console.print("[yellow]No contributors found[/yellow]")
            return
        
        table = Table(title="Top Contributors", box=box.ROUNDED)
        table.add_column("Contributor", style="cyan")
        table.add_column("Commits", justify="right")
        table.add_column("PRs", justify="right")
        table.add_column("Repositories", justify="right")
        table.add_column("Activity Level", style="green")
        
        # Sort by total commits and show top contributors
        sorted_contributors = sorted(
            self.contributors.values(),
            key=lambda x: x.total_commits,
            reverse=True
        )
        
        for profile in sorted_contributors[:15]:  # Show top 15
            activity = "High" if profile.contribution_frequency > 2 else "Medium" if profile.contribution_frequency > 0.5 else "Low"
            table.add_row(
                profile.username,
                str(profile.total_commits),
                str(profile.total_prs),
                str(len(profile.repositories)),
                activity
            )
        
        self.console.print(table)
        
        # Show summary stats
        total_contributors = len(self.contributors)
        total_commits = sum(p.total_commits for p in self.contributors.values())
        total_prs = sum(p.total_prs for p in self.contributors.values())
        active_contributors = sum(1 for p in self.contributors.values() if p.total_commits > 0)
        
        self.console.print(f"\n[bold green]Analysis Summary:[/bold green]")
        self.console.print(f"  • Total Contributors: {total_contributors}")
        self.console.print(f"  • Active Contributors: {active_contributors}")
        self.console.print(f"  • Total Commits Analyzed: {total_commits:,}")
        self.console.print(f"  • Total PRs Analyzed: {total_prs:,}")


class AsyncRateLimiter:
    """Async rate limiter for API calls"""
    
    def __init__(self, rate_per_minute: int):
        self.rate_per_minute = rate_per_minute
        self.semaphore = asyncio.Semaphore(rate_per_minute)
        self.reset_time = time.time() + 60
        self.lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def acquire(self):
        """Acquire rate limit permit"""
        async with self.lock:
            current_time = time.time()
            if current_time >= self.reset_time:
                # Reset semaphore
                self.semaphore = asyncio.Semaphore(self.rate_per_minute)
                self.reset_time = current_time + 60
        
        await self.semaphore.acquire()
        
        # Release after delay to maintain rate
        delay = 60.0 / self.rate_per_minute
        asyncio.create_task(self._release_after_delay(delay))
    
    async def _release_after_delay(self, delay: float):
        """Release semaphore after delay"""
        await asyncio.sleep(delay)
        self.semaphore.release()


if __name__ == "__main__":
    analyzer = ContributorAnalyzer()
    exit(analyzer.main()) 