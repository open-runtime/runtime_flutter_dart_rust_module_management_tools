# Upgrade Plan: validate_changelogs.py

## Overview
Validates changelog format and content across the project. Currently uses basic string parsing and regex.

## Current State
- **Dependencies**: Standard library only
- **Key Features**: Format validation, version checking, content verification
- **Limitations**: Basic parsing, no schema validation

## Recommended Upgrades

### 1. Structured Parsing
```python
# Replace regex with proper markdown parsing
import mistune
from mistune import create_markdown
from mistune.renderers.rst import RSTRenderer
import markdown_it

class ChangelogParser:
    def __init__(self):
        self.md = create_markdown(renderer=None)
        self.parser = markdown_it.MarkdownIt()
        
    def parse_changelog(self, content: str):
        # Parse to AST
        tokens = self.parser.parse(content)
        
        # Extract structured data
        versions = []
        current_version = None
        
        for token in tokens:
            if token.type == 'heading' and token.tag == 'h2':
                # Version header
                current_version = self._parse_version_header(token.content)
                versions.append(current_version)
            elif token.type == 'list' and current_version:
                # Change entries
                current_version.changes.extend(
                    self._parse_changes(token.children)
                )
        
        return versions
```

### 2. Schema Validation
```python
# Define changelog schema with pydantic
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from datetime import date

class ChangeEntry(BaseModel):
    type: Literal['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'chore']
    scope: Optional[str]
    description: str
    breaking: bool = False
    pr_number: Optional[int]
    
class VersionEntry(BaseModel):
    version: str
    date: date
    yanked: bool = False
    changes: List[ChangeEntry]
    
    @validator('version')
    def validate_semver(cls, v):
        if not semver.Version.is_valid(v):
            raise ValueError(f"Invalid version: {v}")
        return v

class Changelog(BaseModel):
    title: str = "Changelog"
    description: Optional[str]
    versions: List[VersionEntry]
    
    def validate_ordering(self):
        """Ensure versions are in descending order"""
        for i in range(1, len(self.versions)):
            v1 = semver.Version.parse(self.versions[i-1].version)
            v2 = semver.Version.parse(self.versions[i].version)
            if v1 <= v2:
                raise ValueError(f"Versions not in descending order: {v1} <= {v2}")
```

### 3. Keep-a-Changelog Compliance
```python
# Validate against keep-a-changelog.com spec
from keep_a_changelog import to_dict, from_dict
import keepachangelog

class KeepAChangelogValidator:
    VALID_SECTIONS = {
        'Added', 'Changed', 'Deprecated', 
        'Removed', 'Fixed', 'Security'
    }
    
    def validate(self, changelog_path: str):
        with open(changelog_path) as f:
            content = f.read()
            
        try:
            # Parse using keep-a-changelog
            changelog = keepachangelog.to_dict(content)
            
            # Validate structure
            issues = []
            for version, data in changelog.items():
                if version != 'Unreleased':
                    # Check version format
                    if not self._is_valid_version(version):
                        issues.append(f"Invalid version format: {version}")
                
                # Check sections
                for section in data.get('sections', {}):
                    if section not in self.VALID_SECTIONS:
                        issues.append(f"Invalid section '{section}' in {version}")
                        
            return issues
            
        except Exception as e:
            return [f"Failed to parse changelog: {e}"]
```

### 4. Cross-Reference Validation
```python
# Validate changelog against Git history
from git import Repo
import github

class CrossReferenceValidator:
    def __init__(self, repo_path: str, github_token: str):
        self.repo = Repo(repo_path)
        self.gh = github.Github(github_token)
        self.gh_repo = self.gh.get_repo(self._get_repo_name())
        
    def validate_pr_references(self, changelog: Changelog):
        """Ensure all PR numbers exist"""
        invalid_prs = []
        
        for version in changelog.versions:
            for change in version.changes:
                if change.pr_number:
                    try:
                        pr = self.gh_repo.get_pull(change.pr_number)
                        if pr.merged_at is None:
                            invalid_prs.append(f"PR #{change.pr_number} not merged")
                    except github.UnknownObjectException:
                        invalid_prs.append(f"PR #{change.pr_number} not found")
                        
        return invalid_prs
    
    def validate_version_tags(self, changelog: Changelog):
        """Ensure all versions have corresponding Git tags"""
        tags = {tag.name for tag in self.repo.tags}
        missing_tags = []
        
        for version in changelog.versions:
            tag_name = f"v{version.version}"
            if tag_name not in tags:
                missing_tags.append(tag_name)
                
        return missing_tags
```

### 5. Automated Fixes
```python
# Auto-fix common issues
class ChangelogFixer:
    def __init__(self):
        self.fixes_applied = []
        
    def fix_formatting(self, content: str) -> str:
        """Fix common formatting issues"""
        # Normalize line endings
        content = content.replace('\r\n', '\n')
        
        # Fix header formatting
        content = re.sub(r'^#\s+', '# ', content, flags=re.MULTILINE)
        content = re.sub(r'^##\s+', '## ', content, flags=re.MULTILINE)
        
        # Ensure blank lines around headers
        content = re.sub(r'(\n##[^\n]+)\n(?!\n)', r'\1\n\n', content)
        
        # Fix list formatting
        content = re.sub(r'^\*\s+', '- ', content, flags=re.MULTILINE)
        
        self.fixes_applied.append("Normalized formatting")
        return content
    
    def sort_entries(self, changelog: Changelog) -> Changelog:
        """Sort entries by type and scope"""
        for version in changelog.versions:
            version.changes.sort(key=lambda c: (c.type, c.scope or ''))
        
        self.fixes_applied.append("Sorted entries")
        return changelog
```

### 6. Reporting
```python
# Generate validation reports
from rich.console import Console
from rich.table import Table
import json

class ValidationReporter:
    def __init__(self):
        self.console = Console()
        
    def generate_report(self, results: List[ValidationResult]):
        # Console output
        table = Table(title="Changelog Validation Results")
        table.add_column("File", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Issues", style="red")
        
        for result in results:
            status = "✅ Valid" if result.is_valid else "❌ Invalid"
            issues = "\n".join(result.issues) if result.issues else "None"
            table.add_row(result.file, status, issues)
            
        self.console.print(table)
        
        # JSON report for CI
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_files": len(results),
            "valid_files": sum(1 for r in results if r.is_valid),
            "issues": [
                {"file": r.file, "issues": r.issues}
                for r in results if not r.is_valid
            ]
        }
        
        with open("changelog-validation-report.json", "w") as f:
            json.dump(report, f, indent=2)
```

## Dependencies to Add
```toml
[project.dependencies]
mistune = "^3.0.2"
markdown-it-py = "^3.0.0"
pydantic = "^2.5.0"
semver = "^3.0.2"
keep-a-changelog = "^2.0.0"
PyGithub = "^2.1.1"
GitPython = "^3.1.40"
rich = "^13.7.0"
click = "^8.1.7"
ruamel.yaml = "^0.18.5"
```

## New Features
1. **Auto-generation**: Generate changelog entries from commits
2. **Multi-format Support**: Validate MD, RST, and JSON changelogs
3. **CI Integration**: GitHub Actions validation
4. **Template Support**: Enforce project-specific templates
5. **Merge Assistance**: Help resolve changelog conflicts

## Migration Strategy
1. Add new parser alongside existing validation
2. Create compatibility mode for gradual adoption
3. Build auto-fix capability with dry-run
4. Generate baseline reports
5. Add pre-commit hooks

## Expected Benefits
- **Accuracy**: Structured parsing vs regex
- **Consistency**: Enforced schema across projects
- **Automation**: Auto-fix common issues
- **Integration**: Git and GitHub validation
- **Developer Experience**: Clear error messages