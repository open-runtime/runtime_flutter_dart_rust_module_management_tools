#!/usr/bin/env python3
"""
Centralized prompt templates for AI operations.
This eliminates duplicate prompt construction across CLI tools.
"""

from string import Template
from typing import Dict, List, Optional, Any


class PromptTemplates:
    """Centralized prompt templates for all AI operations"""
    
    # Commit message generation
    COMMIT_MESSAGE = Template("""
Analyze these changes and generate a commit message:

$changes

Requirements:
- Use conventional commit format (type: description)
- Be concise but descriptive (50-72 chars for subject)
- Focus on the "why" not just the "what"
- If multiple changes, use the most significant one for the type
- Valid types: feat, fix, docs, style, refactor, test, chore, perf

Format:
<type>(<optional scope>): <description>

<optional body>

<optional footer>
""")
    
    COMMIT_MESSAGE_ENHANCED = Template("""
Analyze these code changes in detail:

Repository: $repo_name
Branch: $branch_name
Files changed: $file_count
Insertions: $insertions
Deletions: $deletions

$changes

Context:
$context

Requirements:
- Use conventional commit format
- Include a detailed body explaining the changes
- Reference any related issues or PRs
- Explain the impact and reasoning
""")
    
    # Changelog generation
    CHANGELOG_ENTRY = Template("""
Generate a changelog entry for version $version:

Changes:
$changes

Previous entries for context:
$context

Requirements:
- Follow Keep a Changelog format (https://keepachangelog.com)
- Group by type: Added, Changed, Deprecated, Removed, Fixed, Security
- Be user-focused (what users need to know)
- Include breaking changes prominently
- Reference issues/PRs where relevant
""")
    
    CHANGELOG_ANALYSIS = Template("""
Analyze these commits and categorize them for a changelog:

Commits:
$commits

Package: $package_name
Version: $version

Requirements:
- Group commits by changelog category
- Identify breaking changes
- Highlight important user-facing changes
- Ignore internal/development changes
- Combine related commits
""")
    
    # Code analysis
    CODE_ANALYSIS = Template("""
Analyze this code change:

File: $file_path
Language: $language

Diff:
$diff

Requirements:
- Identify the purpose of the change
- Note any potential issues or improvements
- Assess the impact on the codebase
- Suggest any missing tests or documentation
""")
    
    # Release notes
    RELEASE_NOTES = Template("""
Generate release notes for version $version:

Changelog entries:
$changelog

Statistics:
- Files changed: $files_changed
- Commits: $commit_count
- Contributors: $contributors

Requirements:
- Create user-friendly release notes
- Highlight major features and fixes
- Include migration guide if needed
- Thank contributors
""")
    
    # PR description
    PR_DESCRIPTION = Template("""
Generate a pull request description:

Title: $title
Branch: $branch
Target: $target_branch

Changes:
$changes

Commits:
$commits

Requirements:
- Summarize what changed and why
- List key changes with checkboxes
- Include testing instructions
- Note any breaking changes
- Reference related issues
""")
    
    @classmethod
    def get_commit_prompt(cls, changes: str, enhanced: bool = False, **kwargs) -> str:
        """Get formatted commit message prompt"""
        if enhanced:
            return cls.COMMIT_MESSAGE_ENHANCED.substitute(
                changes=changes,
                **kwargs
            )
        return cls.COMMIT_MESSAGE.substitute(changes=changes)
    
    @classmethod
    def get_changelog_prompt(cls, version: str, changes: str, context: str = "") -> str:
        """Get formatted changelog prompt"""
        return cls.CHANGELOG_ENTRY.substitute(
            version=version,
            changes=changes,
            context=context or "No previous entries"
        )
    
    @classmethod
    def get_code_analysis_prompt(cls, file_path: str, diff: str, language: str = "unknown") -> str:
        """Get formatted code analysis prompt"""
        return cls.CODE_ANALYSIS.substitute(
            file_path=file_path,
            language=language,
            diff=diff
        )
    
    @classmethod
    def get_release_notes_prompt(cls, version: str, changelog: str, **stats) -> str:
        """Get formatted release notes prompt"""
        return cls.RELEASE_NOTES.substitute(
            version=version,
            changelog=changelog,
            files_changed=stats.get('files_changed', 0),
            commit_count=stats.get('commit_count', 0),
            contributors=stats.get('contributors', 'various')
        )
    
    @classmethod
    def get_pr_description_prompt(cls, title: str, branch: str, changes: str, commits: str, target_branch: str = "main") -> str:
        """Get formatted PR description prompt"""
        return cls.PR_DESCRIPTION.substitute(
            title=title,
            branch=branch,
            target_branch=target_branch,
            changes=changes,
            commits=commits
        )


class PromptBuilder:
    """Helper class to build complex prompts"""
    
    def __init__(self):
        self.sections: List[str] = []
    
    def add_section(self, title: str, content: str) -> 'PromptBuilder':
        """Add a section to the prompt"""
        self.sections.append(f"{title}:\n{content}")
        return self
    
    def add_requirements(self, requirements: List[str]) -> 'PromptBuilder':
        """Add requirements section"""
        req_text = "\n".join(f"- {req}" for req in requirements)
        return self.add_section("Requirements", req_text)
    
    def add_context(self, context: Dict[str, Any]) -> 'PromptBuilder':
        """Add context section"""
        ctx_text = "\n".join(f"{k}: {v}" for k, v in context.items())
        return self.add_section("Context", ctx_text)
    
    def build(self) -> str:
        """Build the final prompt"""
        return "\n\n".join(self.sections) 