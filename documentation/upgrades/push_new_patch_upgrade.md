# Upgrade Plan: push_new_patch.py

## Overview
Commits and pushes new patch release with git tags and optional GitHub releases. Includes validation and safety checks.

## Current State
- **Dependencies**: Standard library + common_config
- **Key Features**: Git operations, tag creation, GitHub release support
- **Safety**: Good validation before operations

## Recommended Upgrades

### 1. Transaction-Based Operations
```python
# Atomic release operations with rollback
from contextlib import contextmanager
import git
from typing import Optional, List, Dict
from dataclasses import dataclass

@dataclass
class ReleaseTransaction:
    """Track all operations in a release"""
    commit_sha: Optional[str] = None
    tag_name: Optional[str] = None
    branch_name: Optional[str] = None
    pushed_commits: List[str] = None
    github_release_id: Optional[int] = None
    
class AtomicReleaseManager:
    def __init__(self, repo_path: str = '.'):
        self.repo = git.Repo(repo_path)
        self.transaction = ReleaseTransaction()
        self.original_head = self.repo.head.commit
        
    @contextmanager
    def atomic_release(self):
        """Ensure all-or-nothing release process"""
        try:
            yield self
        except Exception as e:
            # Rollback on any failure
            self._rollback()
            raise e
        finally:
            # Cleanup
            self._cleanup()
    
    def commit_changes(self, message: str) -> str:
        """Create commit with tracking"""
        # Stage all changes
        self.repo.index.add('*')
        
        # Create commit
        commit = self.repo.index.commit(message)
        self.transaction.commit_sha = commit.hexsha
        
        return commit.hexsha
    
    def create_tag(self, tag_name: str, message: str) -> str:
        """Create annotated tag"""
        tag = self.repo.create_tag(
            tag_name,
            message=message,
            ref=self.repo.head.commit,
            sign=False  # Can be configured
        )
        self.transaction.tag_name = tag_name
        
        return tag.name
    
    def push_changes(self, remote: str = 'origin', branch: Optional[str] = None):
        """Push commits and tags"""
        remote_obj = self.repo.remote(remote)
        
        # Push branch
        if branch:
            push_info = remote_obj.push(f"{branch}:{branch}")
            self.transaction.pushed_commits = [self.transaction.commit_sha]
        else:
            push_info = remote_obj.push()
        
        # Push tags
        if self.transaction.tag_name:
            remote_obj.push(self.transaction.tag_name)
        
        return push_info
    
    def _rollback(self):
        """Rollback all operations"""
        print("🔄 Rolling back release operations...")
        
        # Reset to original commit if we made one
        if self.transaction.commit_sha and self.repo.head.commit.hexsha == self.transaction.commit_sha:
            self.repo.head.reset(self.original_head, index=True, working_tree=True)
            print("  ✓ Reverted commit")
        
        # Delete local tag
        if self.transaction.tag_name:
            try:
                self.repo.delete_tag(self.transaction.tag_name)
                print(f"  ✓ Deleted tag {self.transaction.tag_name}")
            except:
                pass
        
        # Delete remote tag if pushed
        if self.transaction.tag_name and self.transaction.pushed_commits:
            try:
                remote = self.repo.remote('origin')
                remote.push(f":refs/tags/{self.transaction.tag_name}")
                print(f"  ✓ Deleted remote tag")
            except:
                pass
    
    def _cleanup(self):
        """Cleanup temporary resources"""
        pass
```

### 2. Enhanced GitHub Release
```python
# Rich GitHub release creation
from github import Github, GithubException
from pathlib import Path
import mimetypes
from typing import List, Optional, Dict
import asyncio
import aiohttp

class GitHubReleaseManager:
    def __init__(self, token: str):
        self.gh = Github(token)
        self.repo = None
        self._init_repo()
        
    def _init_repo(self):
        """Initialize repository from remote"""
        import subprocess
        
        # Get repo info from git remote
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            url = result.stdout.strip()
            if 'github.com' in url:
                repo_path = url.split('github.com')[1].strip(':/')
                repo_path = repo_path.replace('.git', '')
                self.repo = self.gh.get_repo(repo_path)
    
    async def create_release_with_assets(
        self,
        tag: str,
        name: str,
        body: str,
        assets: List[Path] = None,
        draft: bool = False,
        prerelease: bool = False,
        generate_notes: bool = True
    ) -> Dict[str, Any]:
        """Create release with automatic features"""
        try:
            # Create release
            release = self.repo.create_git_release(
                tag=tag,
                name=name,
                message=body,
                draft=draft,
                prerelease=prerelease or self._is_prerelease(tag),
                generate_release_notes=generate_notes
            )
            
            result = {
                'id': release.id,
                'url': release.html_url,
                'upload_url': release.upload_url,
                'assets': []
            }
            
            # Upload assets in parallel
            if assets:
                upload_tasks = []
                for asset_path in assets:
                    if asset_path.exists():
                        task = self._upload_asset_async(release, asset_path)
                        upload_tasks.append(task)
                
                uploaded = await asyncio.gather(*upload_tasks, return_exceptions=True)
                result['assets'] = [a for a in uploaded if not isinstance(a, Exception)]
            
            return result
            
        except GithubException as e:
            raise Exception(f"Failed to create release: {e}")
    
    async def _upload_asset_async(self, release, asset_path: Path) -> Dict[str, Any]:
        """Upload asset asynchronously"""
        content_type = mimetypes.guess_type(str(asset_path))[0] or 'application/octet-stream'
        
        with open(asset_path, 'rb') as f:
            asset = release.upload_asset(
                path=str(asset_path),
                label=asset_path.name,
                content_type=content_type
            )
        
        return {
            'name': asset.name,
            'size': asset.size,
            'download_url': asset.browser_download_url
        }
    
    def _is_prerelease(self, tag: str) -> bool:
        """Determine if tag indicates prerelease"""
        prerelease_indicators = ['-alpha', '-beta', '-rc', '-pre', '-dev']
        return any(indicator in tag.lower() for indicator in prerelease_indicators)
```

### 3. Pre-Push Validation
```python
# Comprehensive validation before push
from typing import List, Tuple, Dict, Optional
import subprocess
from rich.console import Console
from rich.table import Table

console = Console()

class PrePushValidator:
    def __init__(self, repo: git.Repo):
        self.repo = repo
        self.checks = []
        self._setup_checks()
        
    def _setup_checks(self):
        """Setup validation checks"""
        self.checks = [
            ('uncommitted_changes', self._check_uncommitted_changes),
            ('unpushed_commits', self._check_unpushed_commits),
            ('tag_conflicts', self._check_tag_conflicts),
            ('version_files', self._check_version_files),
            ('changelog_entries', self._check_changelog_entries),
            ('branch_protection', self._check_branch_protection),
            ('tests_passing', self._check_tests_passing),
            ('remote_connectivity', self._check_remote_connectivity)
        ]
    
    def validate(self, tag_name: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """Run all validation checks"""
        results = []
        all_passed = True
        
        # Create progress table
        table = Table(title="Pre-Push Validation")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Details")
        
        for check_name, check_func in self.checks:
            try:
                passed, details = check_func(tag_name)
                status = "✅ Passed" if passed else "❌ Failed"
                
                results.append({
                    'check': check_name,
                    'passed': passed,
                    'details': details
                })
                
                table.add_row(check_name.replace('_', ' ').title(), status, details)
                
                if not passed:
                    all_passed = False
                    
            except Exception as e:
                results.append({
                    'check': check_name,
                    'passed': False,
                    'details': f"Error: {str(e)}"
                })
                table.add_row(
                    check_name.replace('_', ' ').title(),
                    "❌ Error",
                    str(e)
                )
                all_passed = False
        
        console.print(table)
        return all_passed, results
    
    def _check_uncommitted_changes(self, tag_name: str) -> Tuple[bool, str]:
        """Check for uncommitted changes"""
        if self.repo.is_dirty():
            changed_files = [item.a_path for item in self.repo.index.diff(None)]
            return False, f"Uncommitted files: {', '.join(changed_files[:3])}..."
        return True, "Working directory clean"
    
    def _check_tag_conflicts(self, tag_name: str) -> Tuple[bool, str]:
        """Check if tag already exists"""
        existing_tags = [tag.name for tag in self.repo.tags]
        
        if tag_name in existing_tags:
            return False, f"Tag {tag_name} already exists"
        
        # Check remote tags
        try:
            remote_tags = self.repo.git.ls_remote('--tags', 'origin')
            if tag_name in remote_tags:
                return False, f"Tag {tag_name} exists on remote"
        except:
            pass
        
        return True, "No tag conflicts"
    
    def _check_tests_passing(self, tag_name: str) -> Tuple[bool, str]:
        """Run tests before push"""
        # Check for test command in package.json or similar
        test_commands = []
        
        if Path('package.json').exists():
            test_commands.append('npm test')
        if Path('Cargo.toml').exists():
            test_commands.append('cargo test')
        if Path('pubspec.yaml').exists():
            test_commands.append('flutter test')
        
        if not test_commands:
            return True, "No test commands found"
        
        # Run first available test command
        for cmd in test_commands:
            try:
                result = subprocess.run(
                    cmd.split(),
                    capture_output=True,
                    timeout=300  # 5 minute timeout
                )
                if result.returncode == 0:
                    return True, f"Tests passed ({cmd})"
                else:
                    return False, f"Tests failed ({cmd})"
            except subprocess.TimeoutExpired:
                return False, f"Tests timed out ({cmd})"
            except:
                continue
        
        return True, "Test execution skipped"
```

### 4. Progress Tracking
```python
# Real-time progress tracking for push operations
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.live import Live
from typing import Callable
import time

class PushProgressTracker:
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        )
        
    def track_push_operations(self, operations: List[Tuple[str, Callable]]):
        """Track multiple push operations"""
        with Live(self.progress):
            overall_task = self.progress.add_task(
                "Pushing release...",
                total=len(operations)
            )
            
            results = []
            
            for description, operation in operations:
                task = self.progress.add_task(description, total=None)
                
                try:
                    result = operation()
                    self.progress.update(task, completed=True)
                    results.append((description, True, result))
                except Exception as e:
                    self.progress.update(task, completed=True)
                    results.append((description, False, str(e)))
                    # Don't continue on failure
                    break
                
                self.progress.advance(overall_task)
            
            return results
```

### 5. Smart Commit Messages
```python
# Generate rich commit messages with metadata
from typing import Dict, List, Optional
import json

class CommitMessageBuilder:
    def __init__(self, version: str, changes: Dict[str, List[str]]):
        self.version = version
        self.changes = changes
        
    def build_commit_message(self) -> str:
        """Build detailed commit message"""
        # Main subject line
        subject = f"chore(release): prepare v{self.version} release"
        
        # Body with change summary
        body_lines = [
            "",
            f"Release version {self.version}",
            "",
            "Changes in this release:"
        ]
        
        # Add categorized changes
        total_changes = 0
        for package, entries in self.changes.items():
            if entries:
                body_lines.append(f"\n{package}:")
                for entry in entries[:5]:  # Limit to 5 per package
                    body_lines.append(f"  - {entry}")
                    total_changes += 1
                
                if len(entries) > 5:
                    body_lines.append(f"  ... and {len(entries) - 5} more")
        
        # Add metadata
        body_lines.extend([
            "",
            "Metadata:",
            f"- Total changes: {total_changes}",
            f"- Packages affected: {', '.join(self.changes.keys())}",
            f"- Release type: patch"
        ])
        
        # Add co-authors if available
        co_authors = self._get_recent_contributors()
        if co_authors:
            body_lines.extend(["", "Co-authors:"])
            for author in co_authors[:5]:
                body_lines.append(f"Co-authored-by: {author}")
        
        return subject + "\n" + "\n".join(body_lines)
    
    def _get_recent_contributors(self) -> List[str]:
        """Get recent contributors for co-author attribution"""
        try:
            import subprocess
            
            # Get unique authors from last 20 commits
            result = subprocess.run(
                ['git', 'log', '-20', '--format=%aN <%aE>'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                authors = list(set(result.stdout.strip().split('\n')))
                # Remove the current user
                current_user = subprocess.run(
                    ['git', 'config', 'user.name'],
                    capture_output=True,
                    text=True
                ).stdout.strip()
                
                return [a for a in authors if current_user not in a][:5]
        except:
            pass
        
        return []
```

### 6. Post-Push Actions
```python
# Automated post-push tasks
from typing import List, Dict, Optional
import asyncio

class PostPushActions:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.actions = []
        self._setup_actions()
        
    def _setup_actions(self):
        """Configure post-push actions"""
        self.actions = [
            ('notify_team', self._notify_team),
            ('update_documentation', self._update_documentation),
            ('trigger_ci', self._trigger_ci),
            ('create_milestone', self._create_milestone),
            ('update_project_board', self._update_project_board)
        ]
    
    async def execute_actions(self, release_info: Dict[str, Any]):
        """Execute all post-push actions"""
        results = []
        
        tasks = []
        for action_name, action_func in self.actions:
            if self.config.get(f'enable_{action_name}', False):
                task = asyncio.create_task(
                    self._execute_action(action_name, action_func, release_info)
                )
                tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    async def _execute_action(
        self,
        name: str,
        func: Callable,
        release_info: Dict[str, Any]
    ):
        """Execute single action with error handling"""
        try:
            return await func(release_info)
        except Exception as e:
            return {'action': name, 'error': str(e)}
    
    async def _notify_team(self, release_info: Dict[str, Any]):
        """Send notifications about the release"""
        # Implement Slack/Discord/Email notifications
        notifications = []
        
        # Slack webhook
        if self.config.get('slack_webhook'):
            async with aiohttp.ClientSession() as session:
                payload = {
                    'text': f"🚀 Released v{release_info['version']}",
                    'attachments': [{
                        'color': 'good',
                        'fields': [
                            {'title': 'Version', 'value': release_info['version'], 'short': True},
                            {'title': 'Tag', 'value': release_info['tag'], 'short': True},
                            {'title': 'Release URL', 'value': release_info.get('url', 'N/A')}
                        ]
                    }]
                }
                
                await session.post(self.config['slack_webhook'], json=payload)
                notifications.append('slack')
        
        return {'notifications_sent': notifications}
```

## Dependencies to Add
```toml
[project.dependencies]
GitPython = "^3.1.40"
PyGithub = "^2.1.1"
rich = "^13.7.0"
aiohttp = "^3.9.0"
asyncio = "^3.4.3"
click = "^8.1.7"
tenacity = "^8.2.3"
pyyaml = "^6.0.1"
toml = "^0.10.2"
```

## Migration Strategy
1. Implement atomic operations first
2. Add validation framework
3. Enhance GitHub integration
4. Add progress tracking
5. Implement post-push actions

## Expected Benefits
- **Reliability**: Atomic operations with rollback
- **Safety**: Comprehensive pre-push validation
- **Visibility**: Real-time progress tracking
- **Automation**: Post-push actions
- **Integration**: Rich GitHub release features