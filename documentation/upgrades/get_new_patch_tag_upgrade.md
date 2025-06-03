# Upgrade Plan: get_new_patch_tag.py

## Overview
Determines the next patch version tag based on semantic versioning. Currently uses subprocess for git operations and manual version parsing.

## Current State
- **Dependencies**: Standard library only
- **Key Features**: Semantic version handling, GitHub URL generation, tag validation
- **Code Quality**: Clean with dataclasses, good separation with GitOperations

## Recommended Upgrades

### 1. Enhanced Semantic Versioning
```python
# Use semantic versioning libraries
from packaging.version import Version, parse, InvalidVersion
import semver
from typing import Optional, List, Union

class EnhancedSemanticVersion:
    def __init__(self, version_str: str):
        # Remove 'v' prefix if present
        clean_version = version_str.lstrip('v')
        
        # Try semver first (stricter)
        try:
            self.semver = semver.VersionInfo.parse(clean_version)
            self.packaging_version = None
        except ValueError:
            # Fall back to packaging (more flexible)
            self.semver = None
            self.packaging_version = parse(clean_version)
    
    def bump_major(self) -> 'EnhancedSemanticVersion':
        if self.semver:
            return EnhancedSemanticVersion(str(self.semver.bump_major()))
        else:
            # Manual bump for packaging version
            parts = str(self.packaging_version).split('.')
            return EnhancedSemanticVersion(f"{int(parts[0])+1}.0.0")
    
    def bump_minor(self) -> 'EnhancedSemanticVersion':
        if self.semver:
            return EnhancedSemanticVersion(str(self.semver.bump_minor()))
        else:
            parts = str(self.packaging_version).split('.')
            return EnhancedSemanticVersion(f"{parts[0]}.{int(parts[1])+1}.0")
    
    def bump_patch(self) -> 'EnhancedSemanticVersion':
        if self.semver:
            return EnhancedSemanticVersion(str(self.semver.bump_patch()))
        else:
            parts = str(self.packaging_version).split('.')
            return EnhancedSemanticVersion(f"{parts[0]}.{parts[1]}.{int(parts[2])+1}")
    
    def bump_prerelease(self, token: str = 'beta') -> 'EnhancedSemanticVersion':
        if self.semver:
            return EnhancedSemanticVersion(str(self.semver.bump_prerelease(token)))
        else:
            # Handle prerelease for packaging version
            base = str(self.packaging_version).split('-')[0].split('+')[0]
            return EnhancedSemanticVersion(f"{base}-{token}.1")
    
    def compare(self, other: 'EnhancedSemanticVersion') -> int:
        """Compare versions: -1 if self < other, 0 if equal, 1 if self > other"""
        if self.semver and other.semver:
            return self.semver.compare(other.semver)
        else:
            # Use packaging comparison
            if self.packaging_version < other.packaging_version:
                return -1
            elif self.packaging_version > other.packaging_version:
                return 1
            else:
                return 0
```

### 2. Git Integration with Caching
```python
# Use GitPython with caching
from git import Repo
from functools import lru_cache
import pickle
from pathlib import Path
from datetime import datetime, timedelta

class CachedGitOperations:
    def __init__(self, repo_path: str = '.', cache_dir: Path = Path('.git_cache')):
        self.repo = Repo(repo_path)
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self._tag_cache = None
        self._cache_timestamp = None
        
    @property
    def tags(self) -> List[str]:
        """Get all tags with caching"""
        # Check if cache is valid (less than 5 minutes old)
        if self._tag_cache and self._cache_timestamp:
            if datetime.now() - self._cache_timestamp < timedelta(minutes=5):
                return self._tag_cache
        
        # Refresh cache
        self._tag_cache = [tag.name for tag in self.repo.tags]
        self._cache_timestamp = datetime.now()
        
        # Persist to disk
        self._save_cache()
        
        return self._tag_cache
    
    def _save_cache(self):
        """Save cache to disk"""
        cache_file = self.cache_dir / 'tags.pkl'
        with open(cache_file, 'wb') as f:
            pickle.dump({
                'tags': self._tag_cache,
                'timestamp': self._cache_timestamp
            }, f)
    
    def _load_cache(self):
        """Load cache from disk"""
        cache_file = self.cache_dir / 'tags.pkl'
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self._tag_cache = data['tags']
                    self._cache_timestamp = data['timestamp']
            except Exception:
                pass
    
    @lru_cache(maxsize=128)
    def get_tag_commit(self, tag_name: str) -> Optional[str]:
        """Get commit SHA for a tag"""
        try:
            tag = self.repo.tags[tag_name]
            return tag.commit.hexsha
        except (KeyError, AttributeError):
            return None
    
    def get_version_tags(self) -> List[str]:
        """Get only version tags (v1.2.3 format)"""
        import re
        version_pattern = re.compile(r'^v?\d+\.\d+\.\d+')
        return [tag for tag in self.tags if version_pattern.match(tag)]
```

### 3. GitHub Integration
```python
# Direct GitHub API integration
from github import Github
from typing import Optional, Dict, Any
import os

class GitHubIntegration:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.gh = Github(self.token) if self.token else None
        self._repo = None
        self._repo_info = None
    
    @property
    def repo(self):
        """Lazy load repository"""
        if not self._repo and self.gh:
            repo_name = self._get_repo_name_from_remote()
            if repo_name:
                self._repo = self.gh.get_repo(repo_name)
        return self._repo
    
    def _get_repo_name_from_remote(self) -> Optional[str]:
        """Extract repo name from git remote"""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Parse GitHub URL
                if 'github.com' in url:
                    parts = url.split('github.com')[1].strip(':/')
                    return parts.replace('.git', '')
        except Exception:
            pass
        return None
    
    def get_tag_url(self, tag_name: str) -> str:
        """Get GitHub URL for tag"""
        if self.repo:
            return f"{self.repo.html_url}/releases/tag/{tag_name}"
        else:
            # Fallback to manual construction
            return f"https://github.com/OWNER/REPO/releases/tag/{tag_name}"
    
    def create_release_draft(
        self,
        tag_name: str,
        title: str,
        body: str,
        target_commit: Optional[str] = None
    ) -> Optional[str]:
        """Create a draft release"""
        if not self.repo:
            return None
        
        try:
            release = self.repo.create_git_release(
                tag=tag_name,
                name=title,
                message=body,
                draft=True,
                prerelease='-' in tag_name,
                target_commitish=target_commit or 'main'
            )
            return release.html_url
        except Exception as e:
            print(f"Failed to create release: {e}")
            return None
```

### 4. Version Strategy System
```python
# Implement different versioning strategies
from enum import Enum
from abc import ABC, abstractmethod

class VersionStrategy(Enum):
    SEMANTIC = "semantic"
    CALENDAR = "calendar"  # YY.MM.PATCH
    CONTINUOUS = "continuous"  # Single incrementing number
    CUSTOM = "custom"

class VersioningStrategy(ABC):
    @abstractmethod
    def get_next_version(self, current: str) -> str:
        pass
    
    @abstractmethod
    def validate_version(self, version: str) -> bool:
        pass

class SemanticVersioningStrategy(VersioningStrategy):
    def get_next_version(self, current: str, bump_type: str = 'patch') -> str:
        version = EnhancedSemanticVersion(current)
        
        if bump_type == 'major':
            return str(version.bump_major())
        elif bump_type == 'minor':
            return str(version.bump_minor())
        else:
            return str(version.bump_patch())
    
    def validate_version(self, version: str) -> bool:
        try:
            semver.VersionInfo.parse(version.lstrip('v'))
            return True
        except ValueError:
            return False

class CalendarVersioningStrategy(VersioningStrategy):
    def get_next_version(self, current: str) -> str:
        from datetime import datetime
        
        today = datetime.now()
        year = str(today.year)[2:]  # Last 2 digits
        month = f"{today.month:02d}"
        
        # Parse current version
        if '.' in current:
            parts = current.split('.')
            if len(parts) >= 2 and parts[0] == year and parts[1] == month:
                # Same month, increment patch
                patch = int(parts[2]) if len(parts) > 2 else 0
                return f"{year}.{month}.{patch + 1}"
        
        # New month
        return f"{year}.{month}.0"
    
    def validate_version(self, version: str) -> bool:
        import re
        pattern = r'^\d{2}\.\d{2}\.\d+$'
        return bool(re.match(pattern, version))
```

### 5. Validation and Suggestions
```python
# Enhanced validation with suggestions
from typing import List, Tuple, Optional

class VersionValidator:
    def __init__(self):
        self.checks = [
            self._check_format,
            self._check_no_leading_zeros,
            self._check_reasonable_bounds,
            self._check_monotonic_increase
        ]
    
    def validate(
        self,
        version: str,
        existing_versions: List[str]
    ) -> Tuple[bool, List[str]]:
        """Validate version with detailed feedback"""
        errors = []
        
        for check in self.checks:
            result, error = check(version, existing_versions)
            if not result:
                errors.append(error)
        
        return len(errors) == 0, errors
    
    def suggest_corrections(
        self,
        invalid_version: str,
        existing_versions: List[str]
    ) -> List[str]:
        """Suggest valid versions"""
        suggestions = []
        
        # Try to fix common issues
        # Remove v prefix
        if invalid_version.startswith('v'):
            suggestions.append(invalid_version[1:])
        
        # Fix leading zeros
        parts = invalid_version.split('.')
        fixed_parts = [str(int(p)) if p.isdigit() else p for p in parts]
        suggestions.append('.'.join(fixed_parts))
        
        # Suggest next logical version
        if existing_versions:
            latest = max(existing_versions, key=lambda v: EnhancedSemanticVersion(v))
            next_version = EnhancedSemanticVersion(latest).bump_patch()
            suggestions.append(str(next_version))
        
        return list(set(suggestions))  # Remove duplicates
    
    def _check_format(self, version: str, existing: List[str]) -> Tuple[bool, str]:
        """Check version format"""
        import re
        if not re.match(r'^\d+\.\d+\.\d+', version):
            return False, f"Invalid format: {version} (expected X.Y.Z)"
        return True, ""
    
    def _check_no_leading_zeros(self, version: str, existing: List[str]) -> Tuple[bool, str]:
        """Check for leading zeros"""
        parts = version.split('.')
        for part in parts[:3]:  # Major, minor, patch
            if part.startswith('0') and len(part) > 1:
                return False, f"Leading zeros not allowed: {part}"
        return True, ""
```

### 6. CLI Enhancement
```python
# Better CLI with rich output
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

@click.command()
@click.option('--strategy', type=click.Choice(['semantic', 'calendar']), default='semantic')
@click.option('--bump', type=click.Choice(['major', 'minor', 'patch']), default='patch')
@click.option('--dry-run', is_flag=True, help='Show what would be done')
@click.option('--create-draft', is_flag=True, help='Create GitHub draft release')
def get_new_patch_tag(strategy: str, bump: str, dry_run: bool, create_draft: bool):
    """Get next patch tag with enhanced features"""
    
    # Show current state
    table = Table(title="Version Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    git_ops = CachedGitOperations()
    current_version = git_ops.get_latest_version()
    
    table.add_row("Current Version", current_version)
    table.add_row("Strategy", strategy)
    table.add_row("Bump Type", bump)
    
    # Calculate next version
    if strategy == 'semantic':
        strat = SemanticVersioningStrategy()
    else:
        strat = CalendarVersioningStrategy()
    
    next_version = strat.get_next_version(current_version, bump)
    table.add_row("Next Version", next_version)
    
    console.print(table)
    
    if dry_run:
        console.print("\n[yellow]Dry run mode - no changes made[/yellow]")
        return
    
    # Create tag
    if not dry_run:
        console.print(f"\n✨ Creating tag: v{next_version}")
        # Implementation here
    
    # Create draft release if requested
    if create_draft:
        gh = GitHubIntegration()
        url = gh.create_release_draft(
            f"v{next_version}",
            f"Release {next_version}",
            "Draft release notes"
        )
        if url:
            console.print(f"\n📝 Draft release created: {url}")
```

## Dependencies to Add
```toml
[project.dependencies]
semver = "^3.0.2"
packaging = "^23.2"
GitPython = "^3.1.40"
PyGithub = "^2.1.1"
click = "^8.1.7"
rich = "^13.7.0"
cachetools = "^5.3.2"
```

## Migration Strategy
1. Add version libraries alongside existing code
2. Implement caching layer for performance
3. Add GitHub integration features
4. Create comprehensive test suite
5. Add CLI enhancements

## Expected Benefits
- **Flexibility**: Support multiple versioning strategies
- **Performance**: Caching reduces git operations
- **Integration**: Direct GitHub API support
- **Validation**: Better error messages and suggestions
- **User Experience**: Rich CLI output