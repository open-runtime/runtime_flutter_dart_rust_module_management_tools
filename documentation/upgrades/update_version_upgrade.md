# Upgrade Plan: update_version.py

## Overview
Updates version numbers across all packages in the monorepo. Uses common_config for file parsing and version validation.

## Current State
- **Dependencies**: Standard library + common_config
- **Key Features**: Multi-file version updates, format validation
- **Code Quality**: Clean implementation leveraging common utilities

## Recommended Upgrades

### 1. Advanced Version Management
```python
# Comprehensive version management system
from typing import Dict, List, Optional, Tuple
import semver
from packaging import version
from pathlib import Path
import json
from datetime import datetime

class VersionManager:
    def __init__(self):
        self.version_files = {
            'dart': {
                'pubspec.yaml': self._update_pubspec_version,
                'lib/src/version.dart': self._update_dart_version_file
            },
            'flutter': {
                'pubspec.yaml': self._update_pubspec_version,
                'lib/version.dart': self._update_dart_version_file
            },
            'rust': {
                'Cargo.toml': self._update_cargo_version,
                'src/version.rs': self._update_rust_version_file
            },
            'python': {
                'pyproject.toml': self._update_pyproject_version,
                'setup.py': self._update_setup_py_version,
                '__version__.py': self._update_python_version_file
            }
        }
        
        self.version_history = VersionHistory()
        
    def update_version(
        self,
        new_version: str,
        packages: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Dict[str, List[str]]:
        """Update version across specified packages"""
        # Validate version
        if not self._validate_version(new_version):
            raise ValueError(f"Invalid version format: {new_version}")
        
        # Get current versions for history
        current_versions = self._get_current_versions()
        
        # Update packages
        updated_files = {}
        packages = packages or list(self.version_files.keys())
        
        for package in packages:
            if package in self.version_files:
                updated = self._update_package_version(
                    package,
                    new_version,
                    dry_run
                )
                if updated:
                    updated_files[package] = updated
        
        # Record in history
        if not dry_run and updated_files:
            self.version_history.record_update(
                old_versions=current_versions,
                new_version=new_version,
                updated_files=updated_files
            )
        
        return updated_files
    
    def _validate_version(self, version_str: str) -> bool:
        """Validate version format"""
        try:
            # Try semver first (stricter)
            semver.VersionInfo.parse(version_str)
            return True
        except ValueError:
            # Try packaging version (more flexible)
            try:
                version.Version(version_str)
                return True
            except:
                return False
    
    def _update_package_version(
        self,
        package: str,
        new_version: str,
        dry_run: bool
    ) -> List[str]:
        """Update all version files for a package"""
        updated = []
        
        for file_path, update_func in self.version_files[package].items():
            full_path = Path(file_path)
            if package != 'python':  # Adjust path for non-root packages
                full_path = Path(package) / file_path
            
            if full_path.exists():
                if dry_run:
                    print(f"Would update {full_path} to version {new_version}")
                    updated.append(str(full_path))
                else:
                    try:
                        update_func(full_path, new_version)
                        updated.append(str(full_path))
                    except Exception as e:
                        print(f"Failed to update {full_path}: {e}")
        
        return updated
```

### 2. Version History Tracking
```python
# Track version changes over time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class VersionHistory:
    def __init__(self, history_file: Path = Path('.version_history.json')):
        self.history_file = history_file
        self.history = self._load_history()
        
    def _load_history(self) -> List[Dict]:
        """Load version history from file"""
        if self.history_file.exists():
            with open(self.history_file) as f:
                return json.load(f)
        return []
    
    def _save_history(self):
        """Save version history to file"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2, default=str)
    
    def record_update(
        self,
        old_versions: Dict[str, str],
        new_version: str,
        updated_files: Dict[str, List[str]],
        user: Optional[str] = None
    ):
        """Record a version update"""
        import os
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'old_versions': old_versions,
            'new_version': new_version,
            'updated_files': updated_files,
            'user': user or os.getenv('USER', 'unknown'),
            'git_commit': self._get_current_git_commit()
        }
        
        self.history.append(entry)
        self._save_history()
    
    def _get_current_git_commit(self) -> Optional[str]:
        """Get current git commit SHA"""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]
        except:
            pass
        return None
    
    def get_version_timeline(self) -> List[Dict]:
        """Get version timeline with analytics"""
        timeline = []
        
        for i, entry in enumerate(self.history):
            # Calculate time since last update
            time_since_last = None
            if i > 0:
                last_time = datetime.fromisoformat(self.history[i-1]['timestamp'])
                current_time = datetime.fromisoformat(entry['timestamp'])
                time_since_last = (current_time - last_time).days
            
            timeline.append({
                'version': entry['new_version'],
                'date': entry['timestamp'],
                'user': entry['user'],
                'days_since_last': time_since_last,
                'packages_updated': list(entry['updated_files'].keys())
            })
        
        return timeline
    
    def rollback_to_version(self, version: str) -> Dict[str, str]:
        """Get file versions for a specific version"""
        for entry in reversed(self.history):
            if entry['new_version'] == version:
                return entry['old_versions']
        
        raise ValueError(f"Version {version} not found in history")
```

### 3. Version Consistency Checker
```python
# Ensure version consistency across ecosystem
from typing import Dict, List, Tuple, Optional
import re
from pathlib import Path

class VersionConsistencyChecker:
    def __init__(self):
        self.version_patterns = {
            'pubspec.yaml': re.compile(r'^version:\s*(\S+)', re.M),
            'Cargo.toml': re.compile(r'^version\s*=\s*"([^"]+)"', re.M),
            'package.json': re.compile(r'"version":\s*"([^"]+)"'),
            'pyproject.toml': re.compile(r'^version\s*=\s*"([^"]+)"', re.M),
            'setup.py': re.compile(r"version\s*=\s*['\"]([^'\"]+)['\"]"),
            'version.dart': re.compile(r"const\s+String\s+version\s*=\s*['\"]([^'\"]+)['\"]"),
            'version.rs': re.compile(r'const\s+VERSION:\s*&str\s*=\s*"([^"]+)"')
        }
        
    def check_consistency(self) -> Tuple[bool, Dict[str, List[str]]]:
        """Check version consistency across all files"""
        versions_by_package = {}
        inconsistencies = {}
        
        # Scan all packages
        for package in ['dart', 'flutter', 'rust', '.']:
            package_versions = self._scan_package_versions(package)
            
            if package_versions:
                unique_versions = set(package_versions.values())
                
                if len(unique_versions) > 1:
                    inconsistencies[package] = [
                        f"{file}: {version}"
                        for file, version in package_versions.items()
                    ]
                else:
                    versions_by_package[package] = list(unique_versions)[0]
        
        return len(inconsistencies) == 0, inconsistencies
    
    def _scan_package_versions(self, package_dir: str) -> Dict[str, str]:
        """Scan all version files in a package"""
        versions = {}
        base_path = Path(package_dir) if package_dir != '.' else Path()
        
        for pattern_file, pattern in self.version_patterns.items():
            file_path = base_path / pattern_file
            
            if file_path.exists():
                content = file_path.read_text()
                match = pattern.search(content)
                
                if match:
                    versions[str(file_path)] = match.group(1)
        
        return versions
    
    def suggest_fixes(
        self,
        inconsistencies: Dict[str, List[str]]
    ) -> Dict[str, str]:
        """Suggest version to use for each package"""
        suggestions = {}
        
        for package, files in inconsistencies.items():
            # Extract versions
            versions = {}
            for file_info in files:
                file, version = file_info.split(': ')
                versions[version] = versions.get(version, 0) + 1
            
            # Suggest most common version
            most_common = max(versions.items(), key=lambda x: x[1])
            suggestions[package] = most_common[0]
        
        return suggestions
```

### 4. Dependency Version Sync
```python
# Synchronize dependency versions
from typing import Dict, List, Optional
import toml
import yaml
import json

class DependencyVersionSync:
    def __init__(self):
        self.dependency_files = {
            'dart': ('pubspec.yaml', self._update_pubspec_deps),
            'flutter': ('pubspec.yaml', self._update_pubspec_deps),
            'rust': ('Cargo.toml', self._update_cargo_deps),
            'python': ('pyproject.toml', self._update_pyproject_deps),
            'node': ('package.json', self._update_package_json_deps)
        }
        
    def sync_internal_dependencies(self, new_version: str):
        """Update internal package dependencies"""
        updates = {}
        
        for package, (file_name, update_func) in self.dependency_files.items():
            file_path = Path(package) / file_name if package != 'python' else Path(file_name)
            
            if file_path.exists():
                updated_deps = update_func(file_path, new_version)
                if updated_deps:
                    updates[package] = updated_deps
        
        return updates
    
    def _update_pubspec_deps(
        self,
        file_path: Path,
        new_version: str
    ) -> List[str]:
        """Update Dart/Flutter dependencies"""
        with open(file_path) as f:
            data = yaml.safe_load(f)
        
        updated = []
        
        # Check dependencies
        for dep_type in ['dependencies', 'dev_dependencies']:
            if dep_type in data:
                for dep_name, dep_spec in data[dep_type].items():
                    if self._is_internal_package(dep_name):
                        if isinstance(dep_spec, dict) and 'version' in dep_spec:
                            data[dep_type][dep_name]['version'] = f'^{new_version}'
                            updated.append(dep_name)
                        elif isinstance(dep_spec, str):
                            data[dep_type][dep_name] = f'^{new_version}'
                            updated.append(dep_name)
        
        if updated:
            with open(file_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
        
        return updated
    
    def _is_internal_package(self, package_name: str) -> bool:
        """Check if package is internal to the monorepo"""
        internal_packages = [
            'dart_package',
            'flutter_package',
            'rust_bindings',
            'shared_core'
        ]
        return package_name in internal_packages
```

### 5. Version Strategy System
```python
# Support different versioning strategies
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime

class VersionStrategy(Enum):
    SEMANTIC = "semantic"
    CALENDAR = "calendar"
    CONTINUOUS = "continuous"
    MARKETING = "marketing"

class VersioningStrategy(ABC):
    @abstractmethod
    def get_next_version(self, current: str, bump_type: str) -> str:
        pass
    
    @abstractmethod
    def validate_version(self, version: str) -> bool:
        pass

class SemanticVersioning(VersioningStrategy):
    def get_next_version(self, current: str, bump_type: str) -> str:
        v = semver.VersionInfo.parse(current)
        
        if bump_type == 'major':
            return str(v.bump_major())
        elif bump_type == 'minor':
            return str(v.bump_minor())
        elif bump_type == 'patch':
            return str(v.bump_patch())
        elif bump_type == 'prerelease':
            return str(v.bump_prerelease())
        else:
            raise ValueError(f"Unknown bump type: {bump_type}")
    
    def validate_version(self, version: str) -> bool:
        try:
            semver.VersionInfo.parse(version)
            return True
        except:
            return False

class CalendarVersioning(VersioningStrategy):
    def get_next_version(self, current: str, bump_type: str) -> str:
        today = datetime.now()
        
        # Format: YYYY.MM.MICRO
        year = today.year
        month = today.month
        
        # Parse current version
        parts = current.split('.')
        if len(parts) == 3 and int(parts[0]) == year and int(parts[1]) == month:
            # Same month, increment micro
            micro = int(parts[2]) + 1
        else:
            # New month
            micro = 0
        
        return f"{year}.{month}.{micro}"
    
    def validate_version(self, version: str) -> bool:
        parts = version.split('.')
        if len(parts) != 3:
            return False
        
        try:
            year, month, micro = map(int, parts)
            return 2020 <= year <= 2100 and 1 <= month <= 12 and micro >= 0
        except:
            return False

class MarketingVersioning(VersioningStrategy):
    """Marketing-friendly versions like macOS (10.15, 11.0)"""
    
    def get_next_version(self, current: str, bump_type: str) -> str:
        parts = current.split('.')
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        
        if bump_type == 'major':
            return f"{major + 1}.0"
        else:
            return f"{major}.{minor + 1}"
    
    def validate_version(self, version: str) -> bool:
        parts = version.split('.')
        if len(parts) not in [1, 2]:
            return False
        
        try:
            major = int(parts[0])
            if len(parts) == 2:
                minor = int(parts[1])
                return major > 0 and minor >= 0
            return major > 0
        except:
            return False
```

### 6. Interactive Version Update
```python
# Interactive CLI for version updates
import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

console = Console()

@click.command()
@click.option('--version', help='New version to set')
@click.option('--bump', type=click.Choice(['major', 'minor', 'patch', 'prerelease']))
@click.option('--strategy', type=click.Choice(['semantic', 'calendar', 'marketing']), default='semantic')
@click.option('--packages', multiple=True, help='Packages to update')
@click.option('--dry-run', is_flag=True, help='Show what would be updated')
@click.option('--sync-deps', is_flag=True, help='Sync internal dependencies')
def update_version_cli(version, bump, strategy, packages, dry_run, sync_deps):
    """Interactive version update tool"""
    manager = VersionManager()
    
    # Get current versions
    current_versions = manager._get_current_versions()
    
    # Display current state
    table = Table(title="Current Versions")
    table.add_column("Package", style="cyan")
    table.add_column("Version", style="green")
    
    for pkg, ver in current_versions.items():
        table.add_row(pkg, ver)
    
    console.print(table)
    
    # Determine new version
    if not version:
        if bump:
            # Calculate from bump type
            base_version = list(current_versions.values())[0]
            strat = _get_strategy(strategy)
            version = strat.get_next_version(base_version, bump)
            console.print(f"\nCalculated version: [bold green]{version}[/bold green]")
        else:
            # Interactive prompt
            version = Prompt.ask("\nEnter new version")
    
    # Validate version
    strat = _get_strategy(strategy)
    if not strat.validate_version(version):
        console.print(f"[red]Invalid version format: {version}[/red]")
        return
    
    # Show what will be updated
    console.print(Panel(f"Updating to version: [bold]{version}[/bold]"))
    
    # Check consistency first
    checker = VersionConsistencyChecker()
    consistent, issues = checker.check_consistency()
    
    if not consistent:
        console.print("[yellow]Warning: Version inconsistencies detected:[/yellow]")
        for pkg, files in issues.items():
            console.print(f"\n{pkg}:")
            for file in files:
                console.print(f"  - {file}")
        
        if not Confirm.ask("\nContinue anyway?"):
            return
    
    # Update versions
    if dry_run:
        console.print("\n[yellow]Dry run mode - no changes will be made[/yellow]")
    
    updated = manager.update_version(
        version,
        packages=list(packages) if packages else None,
        dry_run=dry_run
    )
    
    # Display results
    if updated:
        result_table = Table(title="Updated Files")
        result_table.add_column("Package", style="cyan")
        result_table.add_column("Files", style="green")
        
        for pkg, files in updated.items():
            result_table.add_row(pkg, '\n'.join(files))
        
        console.print(result_table)
    
    # Sync dependencies if requested
    if sync_deps and not dry_run:
        console.print("\n[yellow]Syncing internal dependencies...[/yellow]")
        dep_sync = DependencyVersionSync()
        dep_updates = dep_sync.sync_internal_dependencies(version)
        
        if dep_updates:
            console.print("[green]Dependencies updated successfully[/green]")
```

## Dependencies to Add
```toml
[project.dependencies]
semver = "^3.0.2"
packaging = "^23.2"
click = "^8.1.7"
rich = "^13.7.0"
pyyaml = "^6.0.1"
toml = "^0.10.2"
GitPython = "^3.1.40"
jsonschema = "^4.20.0"
python-dateutil = "^2.8.2"
```

## Migration Strategy
1. Add version strategy system first
2. Implement history tracking
3. Add consistency checking
4. Build interactive CLI
5. Add dependency synchronization

## Expected Benefits
- **Flexibility**: Support multiple versioning strategies
- **Tracking**: Complete version history with rollback
- **Consistency**: Automated consistency checking
- **Safety**: Dry-run mode and validation
- **Intelligence**: Smart dependency updates