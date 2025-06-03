# Upgrade Plan: release.py

## Overview
Unified release management tool that orchestrates the entire release workflow. Currently uses subprocess for all operations.

## Current State
- **Dependencies**: Standard library only
- **Key Features**: Interactive release type selection, version management, changelog generation
- **Integration**: Calls other tools via subprocess

## Recommended Upgrades

### 1. Interactive CLI
```python
# Replace basic input() with rich prompts
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.console import Console
from rich.table import Table
import questionary

console = Console()

# Better release type selection
release_type = questionary.select(
    "Select release type:",
    choices=[
        questionary.Choice("🚀 Major Release", value="major"),
        questionary.Choice("✨ Minor Release", value="minor"),
        questionary.Choice("🐛 Patch Release", value="patch"),
        questionary.Choice("🔥 Hotfix", value="hotfix"),
    ],
    use_shortcuts=True
).ask()
```

### 2. Semantic Versioning
```python
# Replace manual version parsing
from semantic_version import Version, Spec
import semver

class ReleaseManager:
    def __init__(self, current_version: str):
        self.version = semver.Version.parse(current_version)
    
    def bump(self, release_type: str) -> str:
        if release_type == 'major':
            return str(self.version.bump_major())
        elif release_type == 'minor':
            return str(self.version.bump_minor())
        elif release_type == 'patch':
            return str(self.version.bump_patch())
        elif release_type == 'hotfix':
            return str(self.version.bump_patch())
```

### 3. GitHub Integration
```python
# Direct GitHub API integration
from github import Github
from github.GithubException import GithubException
import httpx

class GitHubReleaseManager:
    def __init__(self, token: str, repo: str):
        self.gh = Github(token)
        self.repo = self.gh.get_repo(repo)
    
    async def create_release(self, tag: str, body: str, draft: bool = False):
        try:
            release = self.repo.create_git_release(
                tag=tag,
                name=f"Release {tag}",
                message=body,
                draft=draft,
                prerelease="-" in tag
            )
            return release.html_url
        except GithubException as e:
            logger.error("Failed to create release", error=str(e))
            raise
```

### 4. Workflow Orchestration
```python
# Use prefect for workflow management
from prefect import flow, task
from prefect.artifacts import create_markdown_artifact
import asyncio

@task(retries=3, retry_delay_seconds=10)
async def run_tests():
    """Run test suite before release"""
    result = await run_command("pytest")
    return result.success

@task
async def bump_version(release_type: str):
    """Bump version numbers"""
    manager = ReleaseManager(get_current_version())
    new_version = manager.bump(release_type)
    await update_version_files(new_version)
    return new_version

@flow(name="release-workflow")
async def release_flow(release_type: str, skip_tests: bool = False):
    """Complete release workflow"""
    if not skip_tests:
        test_result = await run_tests()
        if not test_result:
            raise ValueError("Tests failed")
    
    new_version = await bump_version(release_type)
    changelog = await generate_changelog(new_version)
    await create_git_tag(new_version)
    await create_github_release(new_version, changelog)
    
    create_markdown_artifact(
        key="release-summary",
        markdown=f"# Released {new_version}\n\n{changelog}"
    )
```

### 5. Rollback Support
```python
# Add rollback functionality
from contextlib import contextmanager
import pickle

class ReleaseCheckpoint:
    def __init__(self):
        self.checkpoints = []
    
    def save(self, name: str, data: dict):
        checkpoint = {
            'name': name,
            'timestamp': datetime.now(),
            'data': data,
            'git_state': self._capture_git_state()
        }
        self.checkpoints.append(checkpoint)
        
    def rollback_to(self, name: str):
        checkpoint = next(c for c in self.checkpoints if c['name'] == name)
        self._restore_git_state(checkpoint['git_state'])
        return checkpoint['data']
```

### 6. Notification System
```python
# Add notifications for release events
from notifiers import get_notifier
import discord_webhook

class ReleaseNotifier:
    def __init__(self, config: dict):
        self.slack = get_notifier('slack')
        self.discord = discord_webhook.DiscordWebhook(url=config['discord_url'])
        
    async def notify_release(self, version: str, changelog: str):
        # Slack notification
        self.slack.notify(
            message=f"🚀 Released version {version}",
            webhook_url=self.config['slack_webhook']
        )
        
        # Discord notification
        embed = discord_webhook.DiscordEmbed(
            title=f"Release {version}",
            description=changelog[:2000],
            color='03b2f8'
        )
        self.discord.add_embed(embed)
        self.discord.execute()
```

## Dependencies to Add
```toml
[project.dependencies]
rich = "^13.7.0"
questionary = "^2.0.1"
semantic-version = "^2.10.0"
semver = "^3.0.2"
PyGithub = "^2.1.1"
httpx = "^0.25.2"
prefect = "^2.14.0"
notifiers = "^1.3.3"
discord-webhook = "^1.3.0"
tenacity = "^8.2.3"
```

## New Features
1. **Dry Run Mode**: Preview all changes before execution
2. **Release Templates**: Predefined release configurations
3. **Approval Workflow**: Require approval for major releases
4. **Metrics Collection**: Track release metrics
5. **Plugin System**: Extensible release hooks

## Migration Strategy
1. Implement new features behind feature flags
2. Create adapter for existing subprocess calls
3. Add comprehensive logging
4. Build rollback capability first
5. Gradually migrate to async operations

## Expected Benefits
- **Reliability**: Automatic rollback on failure
- **Visibility**: Real-time release progress
- **Safety**: Dry run and approval workflows
- **Integration**: Native GitHub/GitLab support
- **Automation**: Reduced manual intervention