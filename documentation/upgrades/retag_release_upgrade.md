# Upgrade Plan: retag_release.py

## Overview
Deletes current tag and re-releases with updates, handling version mismatches and changelog updates with AI assistance.

## Current State
- **Dependencies**: Standard library + common_config
- **Key Features**: Tag management, version mismatch handling, AI changelog updates
- **Code Quality**: Comprehensive error handling, interactive workflow

## Recommended Upgrades

### 1. Backup and Recovery System
```python
# Comprehensive backup before retagging
import shutil
from datetime import datetime
from pathlib import Path
import json
from typing import Dict, Optional, List
import tarfile

class ReleaseBackupManager:
    def __init__(self, backup_dir: Path = Path('.release_backups')):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_full_backup(self, tag: str) -> Path:
        """Create comprehensive backup before retagging"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"retag_{tag}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir()
        
        # Backup metadata
        metadata = {
            'tag': tag,
            'timestamp': timestamp,
            'original_commit': self._get_tag_commit(tag),
            'files_backed_up': [],
            'git_state': self._capture_git_state()
        }
        
        # Backup all relevant files
        files_to_backup = [
            'CHANGELOG.md',
            'dart/CHANGELOG.md',
            'flutter/CHANGELOG.md',
            'dart/rust/CHANGELOG.md',
            'pubspec.yaml',
            'dart/pubspec.yaml',
            'flutter/pubspec.yaml',
            'dart/rust/Cargo.toml'
        ]
        
        for file in files_to_backup:
            if Path(file).exists():
                dest = backup_path / file
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
                metadata['files_backed_up'].append(file)
        
        # Backup git tag info
        tag_info = self._get_tag_info(tag)
        with open(backup_path / 'tag_info.json', 'w') as f:
            json.dump(tag_info, f, indent=2)
        
        # Save metadata
        with open(backup_path / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Create compressed archive
        archive_path = self._create_archive(backup_path)
        
        return archive_path
    
    def _create_archive(self, backup_path: Path) -> Path:
        """Create compressed archive of backup"""
        archive_path = backup_path.with_suffix('.tar.gz')
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(backup_path, arcname=backup_path.name)
        
        # Remove uncompressed directory
        shutil.rmtree(backup_path)
        
        return archive_path
    
    def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore from backup archive"""
        if not backup_path.exists():
            return False
        
        # Extract archive
        extract_dir = self.backup_dir / 'restore_temp'
        extract_dir.mkdir(exist_ok=True)
        
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(extract_dir)
        
        # Find metadata
        metadata_file = None
        for root, dirs, files in os.walk(extract_dir):
            if 'metadata.json' in files:
                metadata_file = Path(root) / 'metadata.json'
                break
        
        if not metadata_file:
            return False
        
        # Load metadata and restore
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        # Restore files
        backup_root = metadata_file.parent
        for file in metadata['files_backed_up']:
            src = backup_root / file
            if src.exists():
                shutil.copy2(src, file)
        
        # Cleanup
        shutil.rmtree(extract_dir)
        
        return True
    
    def _capture_git_state(self) -> Dict[str, Any]:
        """Capture current git state"""
        import subprocess
        
        return {
            'branch': subprocess.run(
                ['git', 'branch', '--show-current'],
                capture_output=True,
                text=True
            ).stdout.strip(),
            'commit': subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True
            ).stdout.strip(),
            'status': subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True
            ).stdout.strip()
        }
```

### 2. Enhanced Version Mismatch Handling
```python
# Intelligent version mismatch resolution
from enum import Enum
from typing import Optional, Dict, List, Tuple
import semver

class VersionMismatchAction(Enum):
    RETAG_CURRENT = "retag_current"
    CREATE_NEW = "create_new"
    UPDATE_CODE = "update_code"
    SKIP_VERSION = "skip_version"
    CANCEL = "cancel"

class VersionMismatchResolver:
    def __init__(self):
        self.strategies = {
            'code_ahead': self._resolve_code_ahead,
            'code_behind': self._resolve_code_behind,
            'versions_match': self._resolve_versions_match,
            'complex_mismatch': self._resolve_complex_mismatch
        }
    
    def analyze_mismatch(
        self,
        code_version: str,
        tag_version: str,
        changelog_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Comprehensive mismatch analysis"""
        code_v = semver.VersionInfo.parse(code_version)
        tag_v = semver.VersionInfo.parse(tag_version)
        
        analysis = {
            'code_version': code_version,
            'tag_version': tag_version,
            'changelog_version': changelog_version,
            'code_ahead': code_v > tag_v,
            'code_behind': code_v < tag_v,
            'versions_match': code_v == tag_v,
            'situation': self._determine_situation(code_v, tag_v),
            'recommended_actions': [],
            'risks': []
        }
        
        # Get resolution strategy
        strategy = self.strategies.get(
            analysis['situation'],
            self._resolve_complex_mismatch
        )
        
        recommendations = strategy(code_v, tag_v, changelog_version)
        analysis.update(recommendations)
        
        return analysis
    
    def _determine_situation(
        self,
        code_v: semver.VersionInfo,
        tag_v: semver.VersionInfo
    ) -> str:
        """Determine the mismatch situation"""
        if code_v == tag_v:
            return 'versions_match'
        elif code_v > tag_v:
            return 'code_ahead'
        elif code_v < tag_v:
            return 'code_behind'
        else:
            return 'complex_mismatch'
    
    def _resolve_code_ahead(
        self,
        code_v: semver.VersionInfo,
        tag_v: semver.VersionInfo,
        changelog_v: Optional[str]
    ) -> Dict[str, Any]:
        """Resolve when code version is ahead"""
        return {
            'recommended_actions': [
                (VersionMismatchAction.CREATE_NEW, "Create new tag for current code version"),
                (VersionMismatchAction.RETAG_CURRENT, "Update existing tag to match code")
            ],
            'risks': [
                "Retagging may break existing references",
                "Consider if code changes warrant new version"
            ],
            'suggested_version': str(code_v)
        }
    
    def interactive_resolution(
        self,
        analysis: Dict[str, Any]
    ) -> VersionMismatchAction:
        """Interactive resolution with rich UI"""
        from rich.console import Console
        from rich.table import Table
        from rich.prompt import Prompt
        
        console = Console()
        
        # Display analysis
        table = Table(title="Version Mismatch Analysis")
        table.add_column("Component", style="cyan")
        table.add_column("Version", style="yellow")
        
        table.add_row("Code", analysis['code_version'])
        table.add_row("Tag", analysis['tag_version'])
        if analysis['changelog_version']:
            table.add_row("Changelog", analysis['changelog_version'])
        
        console.print(table)
        
        # Show recommendations
        console.print("\n[bold]Recommended Actions:[/bold]")
        for i, (action, desc) in enumerate(analysis['recommended_actions'], 1):
            console.print(f"{i}. {desc}")
        
        # Show risks
        if analysis['risks']:
            console.print("\n[yellow]Risks to consider:[/yellow]")
            for risk in analysis['risks']:
                console.print(f"  ⚠️  {risk}")
        
        # Get user choice
        choice = Prompt.ask(
            "\nSelect action",
            choices=[str(i) for i in range(1, len(analysis['recommended_actions']) + 1)]
        )
        
        return analysis['recommended_actions'][int(choice) - 1][0]
```

### 3. Intelligent Changelog Synchronization
```python
# AI-powered changelog sync with validation
import asyncio
from typing import Dict, List, Optional, Tuple
import difflib

class IntelligentChangelogSync:
    def __init__(self, ai_client: 'AsyncAIClient'):
        self.ai_client = ai_client
        self.changelog_validator = ChangelogValidator()
        
    async def sync_changelogs(
        self,
        tag: str,
        version: str,
        reason: str,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Intelligently sync all changelogs"""
        changelogs = {
            'root': 'CHANGELOG.md',
            'dart': 'dart/CHANGELOG.md',
            'flutter': 'flutter/CHANGELOG.md',
            'rust': 'dart/rust/CHANGELOG.md'
        }
        
        updates = {}
        
        # Analyze existing changelogs
        analysis = await self._analyze_changelogs(changelogs, version)
        
        # Generate updates for each changelog
        tasks = []
        for package, path in changelogs.items():
            if Path(path).exists():
                task = self._update_changelog(
                    package,
                    path,
                    version,
                    reason,
                    context,
                    analysis
                )
                tasks.append((package, task))
        
        # Execute updates in parallel
        for package, task in tasks:
            try:
                updated_content = await task
                if updated_content:
                    updates[package] = updated_content
            except Exception as e:
                print(f"Failed to update {package} changelog: {e}")
        
        return updates
    
    async def _analyze_changelogs(
        self,
        changelogs: Dict[str, str],
        version: str
    ) -> Dict[str, Any]:
        """Analyze existing changelog state"""
        analysis = {
            'has_version': {},
            'version_content': {},
            'missing_entries': {},
            'inconsistencies': []
        }
        
        for package, path in changelogs.items():
            if Path(path).exists():
                content = Path(path).read_text()
                
                # Check if version exists
                has_version = f"## [v{version}]" in content or f"## [{version}]" in content
                analysis['has_version'][package] = has_version
                
                if has_version:
                    # Extract version content
                    version_content = self._extract_version_section(content, version)
                    analysis['version_content'][package] = version_content
        
        # Check for inconsistencies
        if len(set(analysis['has_version'].values())) > 1:
            analysis['inconsistencies'].append(
                "Not all changelogs have the version entry"
            )
        
        return analysis
    
    def _extract_version_section(self, content: str, version: str) -> str:
        """Extract specific version section from changelog"""
        lines = content.split('\n')
        
        start_idx = None
        end_idx = None
        
        for i, line in enumerate(lines):
            if f"[v{version}]" in line or f"[{version}]" in line:
                start_idx = i
            elif start_idx is not None and line.startswith('## '):
                end_idx = i
                break
        
        if start_idx is not None:
            if end_idx is None:
                end_idx = len(lines)
            return '\n'.join(lines[start_idx:end_idx])
        
        return ""
```

### 4. Git Operations Enhancement
```python
# Enhanced git operations for retagging
import git
from git import Repo, Tag
from typing import Optional, Dict, List

class EnhancedGitOperations:
    def __init__(self, repo_path: str = '.'):
        self.repo = Repo(repo_path)
        
    def safe_delete_tag(self, tag_name: str) -> Tuple[bool, Optional[str]]:
        """Safely delete a tag with validation"""
        try:
            # Check if tag exists
            if tag_name not in [tag.name for tag in self.repo.tags]:
                return False, f"Tag {tag_name} does not exist"
            
            # Get tag info before deletion
            tag = self.repo.tags[tag_name]
            tag_info = {
                'name': tag.name,
                'commit': tag.commit.hexsha,
                'message': tag.tag.message if hasattr(tag, 'tag') else None,
                'tagger': tag.tag.tagger if hasattr(tag, 'tag') else None
            }
            
            # Delete local tag
            self.repo.delete_tag(tag_name)
            
            # Try to delete remote tag
            try:
                origin = self.repo.remote('origin')
                origin.push(f":refs/tags/{tag_name}")
            except Exception as e:
                print(f"Warning: Could not delete remote tag: {e}")
            
            return True, json.dumps(tag_info)
            
        except Exception as e:
            return False, str(e)
    
    def create_annotated_tag(
        self,
        tag_name: str,
        message: str,
        commit: Optional[str] = None,
        force: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Create annotated tag with metadata"""
        try:
            # Check if tag already exists
            if not force and tag_name in [tag.name for tag in self.repo.tags]:
                return False, f"Tag {tag_name} already exists"
            
            # Create tag
            if commit:
                ref = self.repo.commit(commit)
            else:
                ref = self.repo.head.commit
            
            tag = self.repo.create_tag(
                tag_name,
                ref=ref,
                message=message,
                force=force
            )
            
            return True, tag.commit.hexsha
            
        except Exception as e:
            return False, str(e)
    
    def get_tag_comparison(
        self,
        old_tag: str,
        new_tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compare tags or tag with current HEAD"""
        old_commit = self.repo.tags[old_tag].commit
        new_commit = self.repo.tags[new_tag].commit if new_tag else self.repo.head.commit
        
        # Get diff statistics
        diff = old_commit.diff(new_commit)
        
        return {
            'commits_between': len(list(self.repo.iter_commits(f"{old_tag}..{new_tag or 'HEAD'}"))),
            'files_changed': len(diff),
            'additions': sum(d.diff.count('+') for d in diff),
            'deletions': sum(d.diff.count('-') for d in diff),
            'changed_files': [d.a_path for d in diff]
        }
```

### 5. Automated Testing Before Retag
```python
# Run tests before retagging
from typing import List, Dict, Tuple
import subprocess
import asyncio

class RetagTestRunner:
    def __init__(self):
        self.test_suites = {
            'dart': ['flutter test', 'dart test'],
            'rust': ['cargo test'],
            'integration': ['./run_integration_tests.sh']
        }
        
    async def run_all_tests(self) -> Tuple[bool, Dict[str, Any]]:
        """Run all test suites before retagging"""
        results = {}
        all_passed = True
        
        # Run test suites in parallel
        tasks = []
        for suite_name, commands in self.test_suites.items():
            task = self._run_test_suite(suite_name, commands)
            tasks.append(task)
        
        suite_results = await asyncio.gather(*tasks)
        
        # Process results
        for suite_name, (passed, details) in zip(self.test_suites.keys(), suite_results):
            results[suite_name] = details
            if not passed:
                all_passed = False
        
        return all_passed, results
    
    async def _run_test_suite(
        self,
        suite_name: str,
        commands: List[str]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Run a test suite"""
        details = {
            'suite': suite_name,
            'commands': commands,
            'results': []
        }
        
        for cmd in commands:
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                result = {
                    'command': cmd,
                    'returncode': proc.returncode,
                    'passed': proc.returncode == 0,
                    'output': stdout.decode() if proc.returncode == 0 else stderr.decode()
                }
                
                details['results'].append(result)
                
                if proc.returncode != 0:
                    return False, details
                    
            except Exception as e:
                details['results'].append({
                    'command': cmd,
                    'error': str(e),
                    'passed': False
                })
                return False, details
        
        return True, details
```

### 6. Release Notes Regeneration
```python
# Regenerate release notes after retag
from pathlib import Path
from typing import Dict, Optional

class ReleaseNotesRegenerator:
    def __init__(self, ai_client: 'AsyncAIClient'):
        self.ai_client = ai_client
        
    async def regenerate_release_notes(
        self,
        version: str,
        changelog_updates: Dict[str, str],
        retag_reason: str
    ) -> str:
        """Generate updated release notes"""
        # Gather all changelog content
        combined_changes = []
        
        for package, content in changelog_updates.items():
            if content:
                combined_changes.append(f"### {package.title()}\n{content}")
        
        # Generate AI summary
        prompt = f"""
        Generate polished release notes for version {version}.
        
        Retag reason: {retag_reason}
        
        Changes by package:
        {chr(10).join(combined_changes)}
        
        Create a concise, user-friendly summary highlighting the most important changes.
        Include a note about this being a retagged release if appropriate.
        """
        
        summary = await self.ai_client.generate(prompt)
        
        # Build final release notes
        release_notes = f"""# Release {version}

{summary}

## Detailed Changes

{chr(10).join(combined_changes)}

---
*Note: This release was retagged on {datetime.now().strftime('%Y-%m-%d')} - {retag_reason}*
"""
        
        return release_notes
    
    def save_release_notes(self, version: str, content: str) -> Path:
        """Save release notes to file"""
        release_dir = Path('releases')
        release_dir.mkdir(exist_ok=True)
        
        file_path = release_dir / f"v{version}.md"
        file_path.write_text(content)
        
        return file_path
```

## Dependencies to Add
```toml
[project.dependencies]
GitPython = "^3.1.40"
semver = "^3.0.2"
rich = "^13.7.0"
aiohttp = "^3.9.0"
asyncio = "^3.4.3"
pyyaml = "^6.0.1"
toml = "^0.10.2"
python-dateutil = "^2.8.2"
tenacity = "^8.2.3"
```

## Migration Strategy
1. Implement backup system first for safety
2. Add enhanced version mismatch handling
3. Improve changelog synchronization
4. Add test automation
5. Implement release notes regeneration

## Expected Benefits
- **Safety**: Comprehensive backup and restore
- **Intelligence**: Smart version mismatch resolution
- **Quality**: Automated testing before retag
- **Consistency**: Synchronized changelog updates
- **Documentation**: Auto-generated release notes