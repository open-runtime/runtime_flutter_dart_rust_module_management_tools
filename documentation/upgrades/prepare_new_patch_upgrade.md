# Upgrade Plan: prepare_new_patch.py

## Overview
Prepares codebase for new patch release by updating versions and creating changelog entries. Features interactive changelog entry collection.

## Current State
- **Dependencies**: Standard library + common_config
- **Key Features**: Version updates, interactive changelog entry, multi-package support
- **Code Quality**: Well-structured with PatchPreparer class

## Recommended Upgrades

### 1. Enhanced Interactive Input
```python
# Use prompt_toolkit for better UX
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.shortcuts import checkboxlist_dialog, input_dialog
from prompt_toolkit.styles import Style
import questionary

class ChangelogEntryValidator(Validator):
    def validate(self, document):
        text = document.text.strip()
        
        # Check for proper capitalization
        if text and not text[0].isupper():
            raise ValidationError(
                message='Entries should start with a capital letter',
                cursor_position=0
            )
        
        # Check for proper punctuation
        if text and text[-1] not in '.!?':
            raise ValidationError(
                message='Entries should end with punctuation',
                cursor_position=len(text)
            )

class InteractiveChangelogCollector:
    def __init__(self):
        self.style = Style.from_dict({
            'prompt': 'bold',
            'package': 'fg:#00aa00 bold',
            'category': 'fg:#0000aa',
        })
        
        self.categories = {
            'added': '✨ Added',
            'changed': '🔄 Changed',
            'fixed': '🐛 Fixed',
            'deprecated': '⚠️ Deprecated',
            'removed': '🗑️ Removed',
            'security': '🔒 Security'
        }
        
        self.common_completions = WordCompleter([
            'Added new feature',
            'Fixed bug in',
            'Updated dependencies',
            'Improved performance',
            'Enhanced error handling',
            'Added tests for',
            'Refactored',
            'Optimized',
            'Documented'
        ])
    
    def collect_entries(self, package: str) -> Dict[str, List[str]]:
        """Collect categorized changelog entries"""
        entries = {cat: [] for cat in self.categories}
        
        print(f"\n📝 Collecting changelog entries for {package}")
        print("Enter entries by category (press Enter with empty input to skip)\n")
        
        for key, label in self.categories.items():
            while True:
                entry = prompt(
                    f'{label} > ',
                    completer=self.common_completions,
                    validator=ChangelogEntryValidator(),
                    style=self.style,
                    bottom_toolbar=f'Enter {key} entries for {package}'
                )
                
                if not entry:
                    break
                    
                entries[key].append(entry)
        
        return {k: v for k, v in entries.items() if v}  # Remove empty categories
    
    def collect_with_suggestions(
        self,
        package: str,
        git_changes: List[str]
    ) -> Dict[str, List[str]]:
        """Collect entries with AI suggestions"""
        # Generate suggestions based on git changes
        suggestions = self._generate_suggestions(package, git_changes)
        
        # Show suggestions
        if suggestions:
            selected = questionary.checkbox(
                f"Select suggested entries for {package}:",
                choices=suggestions
            ).ask()
            
            # Categorize selected suggestions
            categorized = self._categorize_entries(selected or [])
        else:
            categorized = {cat: [] for cat in self.categories}
        
        # Allow manual additions
        print("\nAdd additional entries manually:")
        manual_entries = self.collect_entries(package)
        
        # Merge suggestions and manual entries
        for cat, entries in manual_entries.items():
            categorized.setdefault(cat, []).extend(entries)
        
        return categorized
```

### 2. Template-Based Changelog Generation
```python
# Use templates for consistent formatting
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from typing import Dict, List

class ChangelogTemplateEngine:
    def __init__(self, template_dir: Path = Path('templates')):
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['format_date'] = self._format_date
        self.env.filters['escape_markdown'] = self._escape_markdown
    
    def generate_changelog_section(
        self,
        version: str,
        entries: Dict[str, List[str]],
        template_name: str = 'changelog_section.md.j2'
    ) -> str:
        """Generate changelog section from template"""
        template = self.env.get_template(template_name)
        
        # Ensure all categories are present
        all_entries = {
            'added': entries.get('added', []),
            'changed': entries.get('changed', []),
            'fixed': entries.get('fixed', []),
            'deprecated': entries.get('deprecated', []),
            'removed': entries.get('removed', []),
            'security': entries.get('security', [])
        }
        
        return template.render(
            version=version,
            date=datetime.now().strftime('%Y-%m-%d'),
            entries=all_entries,
            has_entries=any(all_entries.values())
        )
    
    @staticmethod
    def _format_date(date: datetime) -> str:
        """Format date for changelog"""
        return date.strftime('%Y-%m-%d')
    
    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Escape special markdown characters"""
        chars = ['*', '_', '[', ']', '(', ')', '#', '>', '`']
        for char in chars:
            text = text.replace(char, f'\\{char}')
        return text

# Template example (changelog_section.md.j2):
"""
## [v{{ version }}] - {{ date }}
{% if has_entries %}
{% if entries.added %}
### Added
{% for entry in entries.added %}
- {{ entry }}
{% endfor %}
{% endif %}

{% if entries.changed %}
### Changed
{% for entry in entries.changed %}
- {{ entry }}
{% endfor %}
{% endif %}

{% if entries.fixed %}
### Fixed
{% for entry in entries.fixed %}
- {{ entry }}
{% endfor %}
{% endif %}

{% if entries.deprecated %}
### Deprecated
{% for entry in entries.deprecated %}
- {{ entry }}
{% endfor %}
{% endif %}

{% if entries.removed %}
### Removed
{% for entry in entries.removed %}
- {{ entry }}
{% endfor %}
{% endif %}

{% if entries.security %}
### Security
{% for entry in entries.security %}
- {{ entry }}
{% endfor %}
{% endif %}
{% else %}
### Changed
- Version bump only
{% endif %}
"""
```

### 3. Version Management Enhancement
```python
# Better version handling with validation
from packaging import version
import semver
from typing import Dict, Optional, Tuple

class VersionManager:
    def __init__(self):
        self.version_files = {
            'dart': [
                'pubspec.yaml',
                'lib/src/version.dart'
            ],
            'flutter': [
                'pubspec.yaml',
                'lib/version.dart'
            ],
            'rust': [
                'Cargo.toml',
                'src/version.rs'
            ]
        }
    
    def suggest_next_version(
        self,
        current: str,
        changes: Dict[str, List[str]]
    ) -> Dict[str, str]:
        """Suggest version bumps based on changes"""
        v = semver.VersionInfo.parse(current)
        
        suggestions = {
            'patch': str(v.bump_patch()),
            'minor': str(v.bump_minor()),
            'major': str(v.bump_major()),
            'current': current
        }
        
        # Analyze changes to recommend bump type
        recommended = self._analyze_changes_for_version(changes)
        suggestions['recommended'] = suggestions[recommended]
        suggestions['recommended_type'] = recommended
        
        return suggestions
    
    def _analyze_changes_for_version(
        self,
        changes: Dict[str, List[str]]
    ) -> str:
        """Analyze changes to recommend version bump type"""
        # Check for breaking changes
        for entries in changes.values():
            for entry in entries:
                if 'breaking' in entry.lower() or 'BREAKING' in entry:
                    return 'major'
        
        # Check for new features
        if 'added' in changes and changes['added']:
            return 'minor'
        
        # Default to patch
        return 'patch'
    
    def validate_version_consistency(self) -> Tuple[bool, List[str]]:
        """Ensure versions are consistent across all files"""
        issues = []
        versions_by_package = {}
        
        for package, files in self.version_files.items():
            versions = set()
            
            for file in files:
                if Path(file).exists():
                    version = self._extract_version_from_file(file)
                    if version:
                        versions.add(version)
            
            if len(versions) > 1:
                issues.append(
                    f"{package}: Inconsistent versions found: {versions}"
                )
            
            versions_by_package[package] = versions
        
        return len(issues) == 0, issues
```

### 4. AI-Powered Suggestions
```python
# Generate changelog suggestions from git history
import aiohttp
from typing import List, Dict
import asyncio

class AIChangelogSuggester:
    def __init__(self, ai_client: 'AsyncAIClient'):
        self.ai_client = ai_client
        
    async def suggest_entries(
        self,
        package: str,
        git_diff: str,
        commit_messages: List[str]
    ) -> List[str]:
        """Generate changelog entry suggestions"""
        prompt = f"""
        Based on the following changes in the {package} package:
        
        Git diff summary:
        {git_diff[:1000]}  # Truncate for API limits
        
        Recent commit messages:
        {chr(10).join(commit_messages[:10])}
        
        Generate 3-5 changelog entries following these rules:
        1. Start with a capital letter
        2. End with proper punctuation
        3. Be concise but descriptive
        4. Focus on user-visible changes
        5. Use present tense
        
        Format: One entry per line, no bullets or categories.
        """
        
        response = await self.ai_client.generate(prompt)
        
        # Parse response into individual entries
        entries = [
            line.strip()
            for line in response.split('\n')
            if line.strip() and not line.startswith('#')
        ]
        
        return entries[:5]  # Limit to 5 suggestions
    
    async def categorize_entries(
        self,
        entries: List[str]
    ) -> Dict[str, List[str]]:
        """Categorize entries using AI"""
        if not entries:
            return {}
        
        prompt = f"""
        Categorize these changelog entries into the appropriate sections:
        - added: New features
        - changed: Changes to existing functionality
        - fixed: Bug fixes
        - deprecated: Deprecated features
        - removed: Removed features
        - security: Security fixes
        
        Entries:
        {chr(10).join(f"{i+1}. {entry}" for i, entry in enumerate(entries))}
        
        Format response as:
        category: entry_numbers (comma-separated)
        """
        
        response = await self.ai_client.generate(prompt)
        
        # Parse categorization
        categorized = {}
        for line in response.split('\n'):
            if ':' in line:
                category, numbers = line.split(':', 1)
                category = category.strip().lower()
                
                if category in ['added', 'changed', 'fixed', 'deprecated', 'removed', 'security']:
                    indices = [int(n.strip()) - 1 for n in numbers.split(',') if n.strip().isdigit()]
                    categorized[category] = [entries[i] for i in indices if i < len(entries)]
        
        return categorized
```

### 5. Rollback Support
```python
# Add rollback capability
import shutil
from datetime import datetime

class PatchPreparationBackup:
    def __init__(self, backup_dir: Path = Path('.patch_backups')):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(exist_ok=True)
        self.current_backup = None
        
    def create_backup(self, version: str) -> Path:
        """Create backup before making changes"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"patch_{version}_{timestamp}"
        backup_path.mkdir()
        
        # Backup files that will be modified
        files_to_backup = [
            'pubspec.yaml',
            'dart/pubspec.yaml',
            'flutter/pubspec.yaml',
            'dart/rust/Cargo.toml',
            'CHANGELOG.md',
            'dart/CHANGELOG.md',
            'flutter/CHANGELOG.md',
            'dart/rust/CHANGELOG.md'
        ]
        
        for file in files_to_backup:
            if Path(file).exists():
                dest = backup_path / file
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
        
        # Save metadata
        metadata = {
            'version': version,
            'timestamp': timestamp,
            'files': [f for f in files_to_backup if Path(f).exists()]
        }
        
        with open(backup_path / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.current_backup = backup_path
        return backup_path
    
    def rollback(self, backup_path: Optional[Path] = None) -> bool:
        """Rollback to a previous state"""
        backup = backup_path or self.current_backup
        
        if not backup or not backup.exists():
            return False
        
        # Load metadata
        with open(backup / 'metadata.json') as f:
            metadata = json.load(f)
        
        # Restore files
        for file in metadata['files']:
            src = backup / file
            if src.exists():
                shutil.copy2(src, file)
        
        return True
```

### 6. Validation and Pre-checks
```python
# Comprehensive validation before patch preparation
from typing import List, Tuple, Dict

class PatchPreparationValidator:
    def __init__(self):
        self.checks = [
            ('git_status', self._check_git_status),
            ('version_consistency', self._check_version_consistency),
            ('changelog_format', self._check_changelog_format),
            ('dependencies', self._check_dependencies),
            ('branch', self._check_branch)
        ]
        
    def validate(self) -> Tuple[bool, List[str]]:
        """Run all validation checks"""
        issues = []
        
        for check_name, check_func in self.checks:
            try:
                success, message = check_func()
                if not success:
                    issues.append(f"{check_name}: {message}")
            except Exception as e:
                issues.append(f"{check_name}: Error - {str(e)}")
        
        return len(issues) == 0, issues
    
    def _check_git_status(self) -> Tuple[bool, str]:
        """Ensure clean git state"""
        import subprocess
        
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            return False, "Working directory has uncommitted changes"
        
        return True, "Git status clean"
    
    def _check_branch(self) -> Tuple[bool, str]:
        """Check if on appropriate branch"""
        import subprocess
        
        result = subprocess.run(
            ['git', 'branch', '--show-current'],
            capture_output=True,
            text=True
        )
        
        branch = result.stdout.strip()
        
        if branch in ['main', 'master']:
            return True, f"On {branch} branch"
        else:
            return False, f"On {branch} branch (should be on main/master)"
```

## Dependencies to Add
```toml
[project.dependencies]
prompt-toolkit = "^3.0.43"
questionary = "^2.0.1"
jinja2 = "^3.1.2"
packaging = "^23.2"
semver = "^3.0.2"
rich = "^13.7.0"
aiohttp = "^3.9.0"
pyyaml = "^6.0.1"
toml = "^0.10.2"
```

## Migration Strategy
1. Add interactive UI components first
2. Implement template system for changelogs
3. Add AI suggestions as optional feature
4. Implement backup/rollback system
5. Add comprehensive validation

## Expected Benefits
- **User Experience**: Better interactive changelog collection
- **Consistency**: Template-based changelog generation
- **Intelligence**: AI-powered suggestions
- **Safety**: Backup and rollback capability
- **Quality**: Comprehensive validation before changes