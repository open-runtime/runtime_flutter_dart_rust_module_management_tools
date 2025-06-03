# Upgrade Plan: open_pull_request_current_tagged_branch.py

## Overview
Opens or updates PR for current branch with AI-powered analysis, changelog extraction, and GitHub CLI integration.

## Current State
- **Dependencies**: Standard library + common_config
- **Key Features**: AI PR analysis, changelog integration, GitHub CLI usage
- **Complexity**: High but well-organized

## Recommended Upgrades

### 1. Direct GitHub API Integration
```python
# Replace gh CLI with PyGithub
from github import Github, PullRequest, GithubException
from typing import Optional, Dict, List, Tuple
import os

class GitHubPRManager:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv('GITHUB_TOKEN')
        if not self.token:
            raise ValueError("GitHub token required")
        
        self.gh = Github(self.token)
        self.repo = self._init_repo()
        
    def _init_repo(self):
        """Initialize repository from git remote"""
        import subprocess
        
        # Get remote URL
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise ValueError("Not a git repository or no origin remote")
        
        # Parse GitHub repo from URL
        url = result.stdout.strip()
        
        # Handle different URL formats
        if 'github.com' in url:
            if url.startswith('https://'):
                # https://github.com/owner/repo.git
                parts = url.split('/')[-2:]
                owner = parts[0]
                repo = parts[1].replace('.git', '')
            else:
                # git@github.com:owner/repo.git
                parts = url.split(':')[1].split('/')
                owner = parts[0]
                repo = parts[1].replace('.git', '')
            
            return self.gh.get_repo(f"{owner}/{repo}")
        else:
            raise ValueError("Not a GitHub repository")
    
    def create_or_update_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str = 'main',
        draft: bool = False,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
        team_reviewers: Optional[List[str]] = None
    ) -> Tuple[PullRequest, bool]:
        """Create or update pull request"""
        
        # Check for existing PR
        existing_pr = self._find_existing_pr(head, base)
        
        if existing_pr:
            # Update existing PR
            existing_pr.edit(
                title=title,
                body=body,
                state='open' if existing_pr.state == 'closed' else existing_pr.state
            )
            
            # Update labels if provided
            if labels:
                existing_pr.set_labels(*labels)
            
            # Update assignees if provided
            if assignees:
                existing_pr.edit(assignees=assignees)
            
            # Update reviewers if provided
            if reviewers or team_reviewers:
                existing_pr.create_review_request(
                    reviewers=reviewers or [],
                    team_reviewers=team_reviewers or []
                )
            
            return existing_pr, False  # PR updated
        
        else:
            # Create new PR
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=head,
                base=base,
                draft=draft
            )
            
            # Set labels
            if labels:
                pr.add_to_labels(*labels)
            
            # Set assignees
            if assignees:
                pr.add_to_assignees(*assignees)
            
            # Request reviews
            if reviewers or team_reviewers:
                pr.create_review_request(
                    reviewers=reviewers or [],
                    team_reviewers=team_reviewers or []
                )
            
            return pr, True  # PR created
    
    def _find_existing_pr(self, head: str, base: str) -> Optional[PullRequest]:
        """Find existing PR for branch"""
        # Search open PRs
        for pr in self.repo.get_pulls(state='open', base=base, head=head):
            return pr
        
        # Search closed PRs (in case we need to reopen)
        for pr in self.repo.get_pulls(state='closed', base=base, head=head):
            # Only consider recently closed PRs
            if (datetime.now() - pr.closed_at).days < 7:
                return pr
        
        return None
```

### 2. Enhanced Diff Analysis
```python
# Advanced diff analysis with semantic understanding
from unidiff import PatchSet
from typing import Dict, List, Any
import re

class DiffAnalyzer:
    def __init__(self):
        self.file_categories = {
            'source': ['.py', '.js', '.ts', '.dart', '.rs', '.go', '.java'],
            'config': ['.json', '.yaml', '.yml', '.toml', '.ini'],
            'docs': ['.md', '.rst', '.txt', '.adoc'],
            'test': ['test_', '_test.', '.test.', 'spec.'],
            'build': ['Makefile', 'CMakeLists.txt', '.gradle', 'pom.xml'],
            'ci': ['.github/', '.gitlab-ci', '.travis', 'Jenkinsfile']
        }
        
    def analyze_diff(self, diff_text: str) -> Dict[str, Any]:
        """Comprehensive diff analysis"""
        patch = PatchSet(diff_text)
        
        analysis = {
            'summary': {
                'files_changed': len(patch),
                'additions': 0,
                'deletions': 0,
                'files_added': [],
                'files_removed': [],
                'files_modified': []
            },
            'by_category': {},
            'complexity': self._calculate_complexity(patch),
            'risk_assessment': self._assess_risk(patch),
            'suggested_reviewers': self._suggest_reviewers(patch)
        }
        
        # Analyze each file
        for patched_file in patch:
            file_path = patched_file.path
            
            # Categorize file
            category = self._categorize_file(file_path)
            if category not in analysis['by_category']:
                analysis['by_category'][category] = []
            
            analysis['by_category'][category].append(file_path)
            
            # Count changes
            analysis['summary']['additions'] += patched_file.added
            analysis['summary']['deletions'] += patched_file.removed
            
            # Track file status
            if patched_file.is_added_file:
                analysis['summary']['files_added'].append(file_path)
            elif patched_file.is_removed_file:
                analysis['summary']['files_removed'].append(file_path)
            else:
                analysis['summary']['files_modified'].append(file_path)
        
        return analysis
    
    def _categorize_file(self, file_path: str) -> str:
        """Categorize file based on path and extension"""
        path_lower = file_path.lower()
        
        for category, patterns in self.file_categories.items():
            for pattern in patterns:
                if pattern in path_lower:
                    return category
        
        return 'other'
    
    def _calculate_complexity(self, patch: PatchSet) -> Dict[str, Any]:
        """Calculate change complexity"""
        total_hunks = sum(len(f.hunks) for f in patch)
        
        # Calculate churn (additions + deletions)
        total_churn = sum(f.added + f.removed for f in patch)
        
        # Complexity score
        complexity_score = (len(patch) * 0.3 + total_hunks * 0.3 + total_churn * 0.4) / 100
        
        return {
            'score': min(complexity_score, 10),  # Cap at 10
            'level': self._get_complexity_level(complexity_score),
            'hunks': total_hunks,
            'churn': total_churn
        }
    
    def _get_complexity_level(self, score: float) -> str:
        """Convert complexity score to level"""
        if score < 2:
            return 'trivial'
        elif score < 5:
            return 'low'
        elif score < 8:
            return 'medium'
        else:
            return 'high'
    
    def _assess_risk(self, patch: PatchSet) -> Dict[str, Any]:
        """Assess risk of changes"""
        risks = []
        risk_score = 0
        
        for patched_file in patch:
            # High risk file patterns
            high_risk_patterns = [
                'security', 'auth', 'crypto', 'password', 'token',
                'database', 'migration', '.env', 'config'
            ]
            
            file_lower = patched_file.path.lower()
            
            for pattern in high_risk_patterns:
                if pattern in file_lower:
                    risks.append(f"Changes to sensitive file: {patched_file.path}")
                    risk_score += 3
                    break
            
            # Check for large changes
            if patched_file.added + patched_file.removed > 500:
                risks.append(f"Large change in {patched_file.path}")
                risk_score += 2
        
        return {
            'score': min(risk_score, 10),
            'level': self._get_risk_level(risk_score),
            'risks': risks
        }
    
    def _get_risk_level(self, score: int) -> str:
        """Convert risk score to level"""
        if score < 3:
            return 'low'
        elif score < 6:
            return 'medium'
        else:
            return 'high'
    
    def _suggest_reviewers(self, patch: PatchSet) -> List[str]:
        """Suggest reviewers based on file ownership"""
        # This would integrate with CODEOWNERS or git blame
        # For now, return empty list
        return []
```

### 3. AI-Enhanced PR Generation
```python
# Advanced AI integration for PR content
import asyncio
from typing import Dict, List, Optional
import aiohttp

class AIEnhancedPRGenerator:
    def __init__(self, ai_client: 'AsyncAIClient'):
        self.ai_client = ai_client
        self.templates = self._load_templates()
        
    async def generate_pr_content(
        self,
        branch_name: str,
        diff_analysis: Dict[str, Any],
        changelog_content: Optional[str] = None,
        commit_messages: List[str] = None
    ) -> Dict[str, str]:
        """Generate comprehensive PR content"""
        
        # Gather context
        context = await self._gather_context(
            branch_name,
            diff_analysis,
            changelog_content,
            commit_messages
        )
        
        # Generate different sections in parallel
        tasks = [
            self._generate_title(context),
            self._generate_summary(context),
            self._generate_description(context),
            self._generate_testing_plan(context),
            self._generate_checklist(context)
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {
            'title': results[0],
            'summary': results[1],
            'description': results[2],
            'testing_plan': results[3],
            'checklist': results[4],
            'full_body': self._assemble_pr_body(results[1:])
        }
    
    async def _generate_title(self, context: Dict) -> str:
        """Generate PR title"""
        prompt = f"""
        Generate a concise PR title (max 72 chars) for these changes:
        
        Branch: {context['branch_name']}
        Files changed: {context['files_changed']}
        Main changes: {context['main_changes']}
        
        Follow conventional format: type(scope): description
        """
        
        return await self.ai_client.generate(prompt, max_tokens=50)
    
    async def _generate_summary(self, context: Dict) -> str:
        """Generate executive summary"""
        prompt = f"""
        Write a 2-3 sentence executive summary of this PR:
        
        Changes: {context['change_summary']}
        Impact: {context['impact']}
        Risk: {context['risk_level']}
        
        Be concise and focus on the why, not the what.
        """
        
        return await self.ai_client.generate(prompt, max_tokens=150)
    
    async def _generate_testing_plan(self, context: Dict) -> str:
        """Generate testing recommendations"""
        prompt = f"""
        Based on these changes, suggest a testing plan:
        
        Modified files: {context['files_by_category']}
        Complexity: {context['complexity']}
        Risk areas: {context['risks']}
        
        Format as a checklist with specific test scenarios.
        """
        
        return await self.ai_client.generate(prompt, max_tokens=300)
    
    def _assemble_pr_body(self, sections: List[str]) -> str:
        """Assemble full PR body from sections"""
        template = """## Summary
{summary}

## Description
{description}

## Testing Plan
{testing_plan}

## Checklist
{checklist}

---
*Generated with AI assistance*
"""
        
        return template.format(
            summary=sections[0],
            description=sections[1],
            testing_plan=sections[2],
            checklist=sections[3]
        )
```

### 4. Changelog Integration
```python
# Enhanced changelog extraction and formatting
from typing import Dict, List, Optional, Tuple
import re
from pathlib import Path

class ChangelogExtractor:
    def __init__(self):
        self.version_pattern = re.compile(
            r'^##\s*\[?v?(\d+\.\d+\.\d+[^]]*)\]?\s*(?:-\s*)?(\d{4}-\d{2}-\d{2})?',
            re.MULTILINE
        )
        
    def extract_unreleased_changes(
        self,
        changelog_paths: List[str]
    ) -> Dict[str, str]:
        """Extract unreleased changes from multiple changelogs"""
        changes = {}
        
        for path in changelog_paths:
            if Path(path).exists():
                content = Path(path).read_text()
                unreleased = self._extract_unreleased_section(content)
                
                if unreleased:
                    # Determine package name from path
                    package = self._get_package_name(path)
                    changes[package] = unreleased
        
        return changes
    
    def _extract_unreleased_section(self, content: str) -> Optional[str]:
        """Extract unreleased section from changelog"""
        lines = content.split('\n')
        
        in_unreleased = False
        unreleased_lines = []
        
        for line in lines:
            # Check for unreleased header
            if re.match(r'^##?\s*\[?Unreleased\]?', line, re.IGNORECASE):
                in_unreleased = True
                continue
            
            # Check for version header (end of unreleased)
            if in_unreleased and self.version_pattern.match(line):
                break
            
            if in_unreleased:
                unreleased_lines.append(line)
        
        # Clean up and return
        if unreleased_lines:
            return '\n'.join(unreleased_lines).strip()
        
        return None
    
    def _get_package_name(self, changelog_path: str) -> str:
        """Determine package name from changelog path"""
        path_parts = Path(changelog_path).parts
        
        if 'dart' in path_parts:
            if 'rust' in path_parts:
                return 'rust'
            return 'dart'
        elif 'flutter' in path_parts:
            return 'flutter'
        
        return 'root'
    
    def format_for_pr(self, changes: Dict[str, str]) -> str:
        """Format changelog entries for PR description"""
        if not changes:
            return "*No unreleased changes found in changelogs*"
        
        formatted = []
        
        for package, content in changes.items():
            formatted.append(f"### {package.title()}")
            formatted.append(content)
            formatted.append("")
        
        return '\n'.join(formatted)
```

### 5. PR Metadata and Labels
```python
# Automatic PR labeling and metadata
from typing import List, Dict, Set
import re

class PRMetadataGenerator:
    def __init__(self):
        self.label_rules = {
            'bug': ['fix', 'bug', 'issue', 'error'],
            'enhancement': ['feat', 'feature', 'enhance', 'add'],
            'documentation': ['docs', 'readme', 'comment'],
            'dependencies': ['deps', 'dependency', 'package', 'upgrade'],
            'breaking-change': ['breaking', 'BREAKING'],
            'performance': ['perf', 'performance', 'optimize'],
            'refactor': ['refactor', 'cleanup', 'reorganize'],
            'test': ['test', 'spec', 'testing'],
            'ci': ['ci', 'cd', 'github-actions', 'workflow']
        }
        
        self.size_thresholds = {
            'XS': 10,
            'S': 50,
            'M': 250,
            'L': 500,
            'XL': 1000
        }
    
    def generate_labels(
        self,
        title: str,
        body: str,
        diff_analysis: Dict[str, Any],
        commit_messages: List[str]
    ) -> List[str]:
        """Generate appropriate labels for PR"""
        labels = set()
        
        # Analyze content for labels
        combined_text = f"{title} {body} {' '.join(commit_messages)}".lower()
        
        for label, keywords in self.label_rules.items():
            for keyword in keywords:
                if keyword in combined_text:
                    labels.add(label)
                    break
        
        # Add size label
        total_changes = diff_analysis['summary']['additions'] + \
                       diff_analysis['summary']['deletions']
        
        for size, threshold in self.size_thresholds.items():
            if total_changes <= threshold:
                labels.add(f'size/{size}')
                break
        else:
            labels.add('size/XXL')
        
        # Add category labels based on files
        for category, files in diff_analysis['by_category'].items():
            if files and category != 'other':
                labels.add(f'area/{category}')
        
        # Add risk/complexity labels
        if diff_analysis['risk_assessment']['level'] == 'high':
            labels.add('needs-careful-review')
        
        if diff_analysis['complexity']['level'] in ['high', 'medium']:
            labels.add('complex')
        
        return list(labels)
    
    def generate_metadata(
        self,
        branch_name: str,
        diff_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate PR metadata"""
        return {
            'estimated_review_time': self._estimate_review_time(diff_analysis),
            'suggested_reviewers': self._suggest_reviewers(diff_analysis),
            'related_issues': self._extract_issue_references(branch_name),
            'deployment_notes': self._generate_deployment_notes(diff_analysis)
        }
    
    def _estimate_review_time(self, diff_analysis: Dict[str, Any]) -> str:
        """Estimate review time based on complexity"""
        complexity = diff_analysis['complexity']['score']
        
        if complexity < 2:
            return "5-10 minutes"
        elif complexity < 5:
            return "15-30 minutes"
        elif complexity < 8:
            return "30-60 minutes"
        else:
            return "1+ hours"
    
    def _extract_issue_references(self, text: str) -> List[str]:
        """Extract issue references from text"""
        # Match #123, GH-123, fixes #123, etc.
        pattern = re.compile(r'(?:(?:fix|fixes|close|closes|resolve|resolves)\s+)?(?:#|GH-)(\d+)', re.IGNORECASE)
        
        matches = pattern.findall(text)
        return [f"#{num}" for num in matches]
```

### 6. Interactive PR Builder
```python
# Interactive PR creation with preview
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import questionary

console = Console()

class InteractivePRBuilder:
    def __init__(
        self,
        github_manager: GitHubPRManager,
        ai_generator: AIEnhancedPRGenerator
    ):
        self.github = github_manager
        self.ai = ai_generator
        
    async def build_pr_interactively(
        self,
        branch_name: str,
        diff_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build PR interactively with user input"""
        
        # Generate AI suggestions
        console.print("[yellow]Generating AI suggestions...[/yellow]")
        
        ai_content = await self.ai.generate_pr_content(
            branch_name,
            diff_analysis
        )
        
        # Let user customize
        pr_data = {}
        
        # Title
        pr_data['title'] = questionary.text(
            "PR Title:",
            default=ai_content['title']
        ).ask()
        
        # Type of PR
        pr_type = questionary.select(
            "PR Type:",
            choices=[
                "Feature",
                "Bug Fix",
                "Refactor",
                "Documentation",
                "Other"
            ]
        ).ask()
        
        # Body sections
        console.print("\n[bold]PR Description[/bold]")
        console.print(Panel(ai_content['full_body'], title="AI Suggestion"))
        
        if questionary.confirm("Use AI-generated description?").ask():
            pr_data['body'] = ai_content['full_body']
        else:
            # Custom sections
            sections = []
            
            sections.append("## Summary")
            sections.append(questionary.text(
                "Summary (2-3 sentences):",
                multiline=True
            ).ask())
            
            sections.append("\n## Changes")
            sections.append(questionary.text(
                "Describe changes:",
                multiline=True
            ).ask())
            
            if questionary.confirm("Add testing section?").ask():
                sections.append("\n## Testing")
                sections.append(questionary.text(
                    "Testing plan:",
                    multiline=True
                ).ask())
            
            pr_data['body'] = '\n'.join(sections)
        
        # Labels
        suggested_labels = PRMetadataGenerator().generate_labels(
            pr_data['title'],
            pr_data['body'],
            diff_analysis,
            []
        )
        
        pr_data['labels'] = questionary.checkbox(
            "Select labels:",
            choices=suggested_labels + ['WIP', 'help-wanted', 'good-first-issue'],
            default=suggested_labels
        ).ask()
        
        # Reviewers
        if questionary.confirm("Request reviews?").ask():
            pr_data['reviewers'] = questionary.text(
                "Reviewers (comma-separated usernames):"
            ).ask().split(',')
        
        # Draft status
        pr_data['draft'] = questionary.confirm(
            "Create as draft PR?",
            default=pr_type == "Feature"
        ).ask()
        
        # Preview
        self._preview_pr(pr_data)
        
        if questionary.confirm("Create PR with these settings?").ask():
            return pr_data
        else:
            # Recursive call to edit
            return await self.build_pr_interactively(branch_name, diff_analysis)
    
    def _preview_pr(self, pr_data: Dict[str, Any]):
        """Preview PR before creation"""
        console.clear()
        console.print("[bold]PR Preview[/bold]\n")
        
        console.print(f"[cyan]Title:[/cyan] {pr_data['title']}")
        console.print(f"[cyan]Draft:[/cyan] {'Yes' if pr_data.get('draft') else 'No'}")
        console.print(f"[cyan]Labels:[/cyan] {', '.join(pr_data.get('labels', []))}")
        
        if pr_data.get('reviewers'):
            console.print(f"[cyan]Reviewers:[/cyan] {', '.join(pr_data['reviewers'])}")
        
        console.print("\n[cyan]Description:[/cyan]")
        console.print(Panel(Markdown(pr_data['body'])))
```

## Dependencies to Add
```toml
[project.dependencies]
PyGithub = "^2.1.1"
unidiff = "^0.7.5"
aiohttp = "^3.9.0"
rich = "^13.7.0"
questionary = "^2.0.1"
jinja2 = "^3.1.2"
python-frontmatter = "^1.0.1"
```

## Migration Strategy
1. Add GitHub API integration first
2. Implement enhanced diff analysis
3. Add AI content generation
4. Build interactive PR builder
5. Deprecate gh CLI usage

## Expected Benefits
- **Reliability**: Direct API instead of CLI
- **Features**: Rich PR metadata and labeling
- **Intelligence**: AI-powered content generation
- **User Experience**: Interactive PR building
- **Analysis**: Deep diff understanding