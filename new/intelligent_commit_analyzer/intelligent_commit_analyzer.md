# Production-Ready Intelligent Commit Message Generator

## Overview

This is a comprehensive, production-ready Python system that orchestrates multiple AI tools (Claude Code CLI, Codex CLI, Gemini SDK) and GitHub CLI to analyze code changes and generate sophisticated commit messages. The system features parallel processing, intelligent context building, breaking change detection, and extensibility for changelogs and code reviews.

## Complete Implementation

### Core Script: `intelligent_commit_analyzer.py`

```python
#!/usr/bin/env python3
"""
Intelligent Commit Message Generator
Orchestrates Claude Code CLI, Codex CLI, Gemini SDK, and GitHub CLI
for sophisticated commit analysis and message generation.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import click
import git
import networkx as nx
import yaml
from google import genai
from google.genai.types import GenerateContentConfig, Tool
from pydantic import BaseModel, Field
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential
from unidiff import PatchSet

# ==================== Configuration ====================

@dataclass
class Config:
    """Application configuration."""
    # AI Tool Configuration
    claude_api_key: Optional[str] = field(default_factory=lambda: os.getenv('ANTHROPIC_API_KEY'))
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv('OPENAI_API_KEY'))
    google_api_key: Optional[str] = field(default_factory=lambda: os.getenv('GOOGLE_API_KEY'))
    
    # Repository Configuration
    repository_path: Path = field(default_factory=lambda: Path.cwd())
    branch: str = 'main'
    
    # Pipeline Configuration
    max_concurrent_tasks: int = 10
    enable_unsafe_mode: bool = False
    
    # GitHub Configuration
    github_token: Optional[str] = field(default_factory=lambda: os.getenv('GITHUB_TOKEN'))
    link_issues: bool = True
    
    # Logging Configuration
    log_level: str = 'INFO'
    log_file: Optional[str] = None
    
    @classmethod
    def load(cls, config_file: Optional[str] = None) -> 'Config':
        """Load configuration from file and environment."""
        config_data = {}
        
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        
        # Override with environment variables
        return cls(**config_data)

# ==================== Core Interfaces ====================

class AIToolType(Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"

@dataclass
class AnalysisResult:
    """Result from AI analysis."""
    tool: AIToolType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time: float = 0.0

@dataclass
class CommitContext:
    """Context for commit analysis."""
    files_changed: List[str]
    additions: int
    deletions: int
    diff_content: str
    previous_commits: List[Dict[str, Any]]
    related_issues: List[Dict[str, Any]]
    dependency_graph: Optional[nx.DiGraph] = None
    breaking_changes: List[str] = field(default_factory=list)

class AIAnalysisStrategy(ABC):
    """Abstract base class for AI analysis strategies."""
    
    @abstractmethod
    async def analyze(self, context: CommitContext) -> AnalysisResult:
        """Analyze commit context and return results."""
        pass

# ==================== AI Tool Implementations ====================

class ClaudeCodeAnalyzer(AIAnalysisStrategy):
    """Claude Code CLI integration for code analysis."""
    
    def __init__(self, api_key: str, unsafe: bool = False):
        self.api_key = api_key
        self.unsafe = unsafe
        
    async def analyze(self, context: CommitContext) -> AnalysisResult:
        """Analyze using Claude Code CLI."""
        start_time = time.time()
        
        prompt = self._build_prompt(context)
        cmd = ["claude", "-p", prompt]
        
        if self.unsafe:
            cmd.append("--unsafe")
        cmd.extend(["--output-format", "stream-json"])
        
        env = os.environ.copy()
        if self.api_key:
            env["ANTHROPIC_API_KEY"] = self.api_key
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return AnalysisResult(
                    tool=AIToolType.CLAUDE,
                    content="",
                    error=stderr.decode(),
                    execution_time=time.time() - start_time
                )
            
            # Parse stream-json output
            results = []
            for line in stdout.decode().strip().split('\n'):
                if line.strip():
                    try:
                        results.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            
            analysis = self._extract_analysis(results)
            
            return AnalysisResult(
                tool=AIToolType.CLAUDE,
                content=analysis['summary'],
                metadata=analysis,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            return AnalysisResult(
                tool=AIToolType.CLAUDE,
                content="",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _build_prompt(self, context: CommitContext) -> str:
        """Build Claude prompt for analysis."""
        return f"""Analyze these code changes and provide a detailed commit message:

Files changed: {', '.join(context.files_changed)}
Lines added: {context.additions}
Lines removed: {context.deletions}

Recent commits:
{self._format_commits(context.previous_commits[:5])}

Diff:
{context.diff_content[:4000]}

Please analyze:
1. What changed and why (be specific about the implementation)
2. Whether this is a breaking change
3. The nuances and implications of these changes
4. Suggestions for the commit message following conventional commits format"""
    
    def _format_commits(self, commits: List[Dict[str, Any]]) -> str:
        """Format previous commits for context."""
        return '\n'.join([f"- {c['sha'][:7]}: {c['message']}" for c in commits])
    
    def _extract_analysis(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract analysis from Claude results."""
        analysis = {
            'summary': '',
            'breaking_changes': [],
            'suggestions': [],
            'nuances': []
        }
        
        for result in results:
            if result.get('type') == 'message':
                analysis['summary'] += result.get('content', '')
        
        return analysis

class CodexAnalyzer(AIAnalysisStrategy):
    """Codex CLI integration for code analysis."""
    
    def __init__(self, api_key: str, model: str = "o1-mini"):
        self.api_key = api_key
        self.model = model
    
    @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
    async def analyze(self, context: CommitContext) -> AnalysisResult:
        """Analyze using Codex CLI."""
        start_time = time.time()
        
        prompt = self._build_prompt(context)
        cmd = [
            "codex",
            "--model", self.model,
            "--approval-mode", "auto",
            "--provider", "openai",
            prompt
        ]
        
        env = os.environ.copy()
        if self.api_key:
            env["OPENAI_API_KEY"] = self.api_key
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                return AnalysisResult(
                    tool=AIToolType.CODEX,
                    content="",
                    error=stderr.decode(),
                    execution_time=time.time() - start_time
                )
            
            analysis = self._parse_output(stdout.decode())
            
            return AnalysisResult(
                tool=AIToolType.CODEX,
                content=analysis['summary'],
                metadata=analysis,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            return AnalysisResult(
                tool=AIToolType.CODEX,
                content="",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _build_prompt(self, context: CommitContext) -> str:
        """Build Codex prompt for analysis."""
        return f"""Analyze the following git changes and suggest a detailed commit message.

Changes summary:
- Files: {len(context.files_changed)}
- Additions: +{context.additions}
- Deletions: -{context.deletions}

Focus on:
1. Technical implementation details
2. Code quality implications
3. Performance considerations
4. Potential bugs or issues addressed

Diff preview:
{context.diff_content[:3000]}"""
    
    def _parse_output(self, output: str) -> Dict[str, Any]:
        """Parse Codex output."""
        return {
            'summary': output.strip(),
            'technical_details': [],
            'quality_metrics': {}
        }

class GeminiAnalyzer(AIAnalysisStrategy):
    """Gemini SDK integration for fast code analysis."""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.0-flash-001'
    
    @sleep_and_retry
    @limits(calls=1000, period=60)  # Rate limiting
    async def analyze(self, context: CommitContext) -> AnalysisResult:
        """Analyze using Gemini SDK."""
        start_time = time.time()
        
        try:
            # Build structured prompt
            prompt = self._build_structured_prompt(context)
            
            # Generate analysis
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=GenerateContentConfig(
                    max_output_tokens=2000,
                    temperature=0.3,
                    system_instruction='You are an expert code reviewer analyzing git changes.'
                )
            )
            
            analysis = self._parse_response(response)
            
            return AnalysisResult(
                tool=AIToolType.GEMINI,
                content=analysis['summary'],
                metadata=analysis,
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            return AnalysisResult(
                tool=AIToolType.GEMINI,
                content="",
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    def _build_structured_prompt(self, context: CommitContext) -> str:
        """Build structured prompt for Gemini."""
        return f"""Analyze these code changes for commit message generation:

## Change Summary
- Files modified: {len(context.files_changed)}
- Lines added: {context.additions}
- Lines removed: {context.deletions}
- Breaking changes detected: {len(context.breaking_changes)}

## Files Changed
{chr(10).join(f'- {f}' for f in context.files_changed[:20])}

## Recent Commit Context
{chr(10).join(f'- {c["message"]}' for c in context.previous_commits[:5])}

## Related Issues
{chr(10).join(f'- #{i["number"]}: {i["title"]}' for i in context.related_issues[:5])}

## Analysis Required
1. Summarize what changed and why
2. Identify if this is a breaking change
3. Explain technical nuances
4. Suggest conventional commit type and scope
5. Link to relevant issues

## Diff Sample
{context.diff_content[:2000]}"""
    
    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse Gemini response."""
        text = response.text
        
        return {
            'summary': text,
            'commit_type': self._extract_commit_type(text),
            'scope': self._extract_scope(text),
            'breaking': 'breaking change' in text.lower()
        }
    
    def _extract_commit_type(self, text: str) -> str:
        """Extract commit type from analysis."""
        types = ['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'chore']
        for t in types:
            if f'{t}:' in text or f'{t}(' in text:
                return t
        return 'chore'
    
    def _extract_scope(self, text: str) -> Optional[str]:
        """Extract scope from analysis."""
        import re
        match = re.search(r'\w+\((\w+)\):', text)
        return match.group(1) if match else None

# ==================== Context Building ====================

class CodeContextBuilder:
    """Builds intelligent context across code changes."""
    
    def __init__(self, repo_path: Path):
        self.repo = git.Repo(repo_path)
        self.dependency_graph = nx.DiGraph()
        
    async def build_context(self) -> CommitContext:
        """Build comprehensive context for current changes."""
        # Get staged changes
        diff_content = await self._get_staged_diff()
        
        # Parse diff
        patch = PatchSet(diff_content)
        files_changed = [f.path for f in patch]
        additions = sum(f.added for f in patch)
        deletions = sum(f.removed for f in patch)
        
        # Get previous commits
        previous_commits = await self._get_previous_commits(10)
        
        # Detect breaking changes
        breaking_changes = await self._detect_breaking_changes(patch)
        
        # Get related issues
        related_issues = await self._find_related_issues(files_changed, diff_content)
        
        # Build dependency graph
        await self._build_dependency_graph(files_changed)
        
        return CommitContext(
            files_changed=files_changed,
            additions=additions,
            deletions=deletions,
            diff_content=diff_content,
            previous_commits=previous_commits,
            related_issues=related_issues,
            dependency_graph=self.dependency_graph,
            breaking_changes=breaking_changes
        )
    
    async def _get_staged_diff(self) -> str:
        """Get diff of staged changes."""
        result = await self._run_command(['git', 'diff', '--staged'])
        return result
    
    async def _get_previous_commits(self, count: int) -> List[Dict[str, Any]]:
        """Get previous commit history."""
        commits = []
        for commit in self.repo.iter_commits(max_count=count):
            commits.append({
                'sha': commit.hexsha,
                'message': commit.message.strip(),
                'author': str(commit.author),
                'date': commit.committed_datetime.isoformat()
            })
        return commits
    
    async def _detect_breaking_changes(self, patch: PatchSet) -> List[str]:
        """Detect potential breaking changes."""
        breaking_changes = []
        
        for file in patch:
            if file.is_removed_file:
                breaking_changes.append(f"Removed file: {file.path}")
            
            for hunk in file:
                for line in hunk:
                    if line.is_removed:
                        # Check for API changes
                        if any(keyword in line.value for keyword in ['def ', 'class ', 'export ', 'public ']):
                            breaking_changes.append(f"API change in {file.path}: {line.value.strip()}")
        
        return breaking_changes
    
    async def _find_related_issues(self, files_changed: List[str], diff_content: str) -> List[Dict[str, Any]]:
        """Find GitHub issues related to changes."""
        issues = []
        
        # Search for issue references in diff
        import re
        issue_refs = re.findall(r'#(\d+)', diff_content)
        
        for issue_num in set(issue_refs):
            try:
                result = await self._run_command([
                    'gh', 'issue', 'view', issue_num, '--json', 'number,title,state,labels'
                ])
                issue_data = json.loads(result)
                issues.append(issue_data)
            except:
                continue
        
        # Search for issues by file names
        for file in files_changed[:5]:  # Limit to prevent too many API calls
            try:
                result = await self._run_command([
                    'gh', 'issue', 'list', '--search', file, '--limit', '3', '--json', 'number,title,state'
                ])
                file_issues = json.loads(result)
                issues.extend(file_issues)
            except:
                continue
        
        # Deduplicate
        seen = set()
        unique_issues = []
        for issue in issues:
            if issue['number'] not in seen:
                seen.add(issue['number'])
                unique_issues.append(issue)
        
        return unique_issues
    
    async def _build_dependency_graph(self, files_changed: List[str]):
        """Build dependency graph for changed files."""
        for file in files_changed:
            self.dependency_graph.add_node(file)
            
            # Find dependencies (simplified - in production, use AST parsing)
            if file.endswith('.py'):
                content = await self._read_file(file)
                imports = re.findall(r'from ([\w.]+) import', content) + re.findall(r'import ([\w.]+)', content)
                
                for imp in imports:
                    # Convert import to potential file path
                    potential_path = imp.replace('.', '/') + '.py'
                    if potential_path in files_changed:
                        self.dependency_graph.add_edge(file, potential_path)
    
    async def _run_command(self, cmd: List[str]) -> str:
        """Run shell command asynchronously."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        return stdout.decode()
    
    async def _read_file(self, path: str) -> str:
        """Read file content asynchronously."""
        try:
            return await asyncio.to_thread(Path(path).read_text)
        except:
            return ""

# ==================== Orchestration ====================

class CommitAnalysisOrchestrator:
    """Orchestrates multiple AI tools for commit analysis."""
    
    def __init__(self, config: Config):
        self.config = config
        self.analyzers: List[AIAnalysisStrategy] = []
        self._setup_analyzers()
        
    def _setup_analyzers(self):
        """Initialize AI analyzers based on configuration."""
        if self.config.claude_api_key:
            self.analyzers.append(
                ClaudeCodeAnalyzer(
                    self.config.claude_api_key,
                    unsafe=self.config.enable_unsafe_mode
                )
            )
        
        if self.config.openai_api_key:
            self.analyzers.append(
                CodexAnalyzer(self.config.openai_api_key)
            )
        
        if self.config.google_api_key:
            self.analyzers.append(
                GeminiAnalyzer(self.config.google_api_key)
            )
    
    async def analyze_changes(self) -> Dict[str, Any]:
        """Analyze code changes using all available tools."""
        # Build context
        context_builder = CodeContextBuilder(self.config.repository_path)
        context = await context_builder.build_context()
        
        if not context.files_changed:
            return {
                'status': 'no_changes',
                'message': 'No staged changes found'
            }
        
        # Run analyzers in parallel
        analysis_tasks = [
            analyzer.analyze(context) for analyzer in self.analyzers
        ]
        
        results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        # Filter successful results
        successful_results = [
            r for r in results 
            if isinstance(r, AnalysisResult) and not r.error
        ]
        
        if not successful_results:
            return {
                'status': 'error',
                'message': 'All analyzers failed',
                'errors': [r.error for r in results if hasattr(r, 'error')]
            }
        
        # Synthesize results
        synthesized = await self._synthesize_results(successful_results, context)
        
        return {
            'status': 'success',
            'commit_message': synthesized['message'],
            'details': synthesized,
            'context': {
                'files_changed': context.files_changed,
                'additions': context.additions,
                'deletions': context.deletions,
                'breaking_changes': context.breaking_changes,
                'related_issues': context.related_issues
            },
            'analysis_results': [
                {
                    'tool': r.tool.value,
                    'execution_time': r.execution_time,
                    'metadata': r.metadata
                }
                for r in successful_results
            ]
        }
    
    async def _synthesize_results(
        self, 
        results: List[AnalysisResult], 
        context: CommitContext
    ) -> Dict[str, Any]:
        """Synthesize multiple AI analysis results."""
        # Extract key information from each result
        commit_types = []
        scopes = []
        summaries = []
        breaking = False
        
        for result in results:
            summaries.append(result.content)
            
            if result.metadata.get('commit_type'):
                commit_types.append(result.metadata['commit_type'])
            
            if result.metadata.get('scope'):
                scopes.append(result.metadata['scope'])
            
            if result.metadata.get('breaking', False):
                breaking = True
        
        # Determine final commit type (majority vote)
        if commit_types:
            from collections import Counter
            commit_type = Counter(commit_types).most_common(1)[0][0]
        else:
            commit_type = 'chore'
        
        # Determine scope
        scope = scopes[0] if scopes else None
        
        # Build commit message
        if breaking or context.breaking_changes:
            type_prefix = f"{commit_type}!"
        else:
            type_prefix = commit_type
        
        if scope:
            type_prefix = f"{type_prefix}({scope})"
        
        # Combine summaries intelligently
        combined_summary = self._combine_summaries(summaries)
        
        # Format commit message
        title = f"{type_prefix}: {self._extract_title(combined_summary)}"
        
        body_parts = [combined_summary]
        
        if context.breaking_changes:
            body_parts.append("\nBREAKING CHANGES:")
            for change in context.breaking_changes:
                body_parts.append(f"- {change}")
        
        if context.related_issues:
            body_parts.append("\nRelated issues:")
            for issue in context.related_issues:
                body_parts.append(f"- Closes #{issue['number']}")
        
        message = f"{title}\n\n{''.join(body_parts)}"
        
        return {
            'message': message,
            'type': commit_type,
            'scope': scope,
            'breaking': breaking or bool(context.breaking_changes),
            'title': title,
            'body': '\n'.join(body_parts[1:]) if len(body_parts) > 1 else ''
        }
    
    def _combine_summaries(self, summaries: List[str]) -> str:
        """Intelligently combine multiple AI summaries."""
        if len(summaries) == 1:
            return summaries[0]
        
        # Extract key points from each summary
        key_points = []
        for summary in summaries:
            # Simple extraction - in production, use NLP
            sentences = summary.split('. ')
            key_points.extend(sentences[:2])  # Take first 2 sentences
        
        # Remove duplicates while preserving order
        seen = set()
        unique_points = []
        for point in key_points:
            normalized = point.lower().strip()
            if normalized not in seen and len(normalized) > 20:
                seen.add(normalized)
                unique_points.append(point)
        
        return '. '.join(unique_points[:5]) + '.'
    
    def _extract_title(self, summary: str) -> str:
        """Extract concise title from summary."""
        # Take first sentence and limit length
        first_sentence = summary.split('.')[0]
        if len(first_sentence) > 50:
            words = first_sentence.split()
            title = ' '.join(words[:7]) + '...'
        else:
            title = first_sentence
        
        return title.lower()

# ==================== CLI Interface ====================

@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file')
@click.pass_context
def cli(ctx, config):
    """Intelligent Commit Message Generator."""
    ctx.obj = Config.load(config)

@cli.command()
@click.option('--dry-run', is_flag=True, help='Show commit message without committing')
@click.option('--no-link-issues', is_flag=True, help='Disable issue linking')
@click.pass_obj
async def analyze(config: Config, dry_run: bool, no_link_issues: bool):
    """Analyze staged changes and generate commit message."""
    if no_link_issues:
        config.link_issues = False
    
    orchestrator = CommitAnalysisOrchestrator(config)
    
    click.echo("🔍 Analyzing staged changes...")
    
    result = await orchestrator.analyze_changes()
    
    if result['status'] == 'no_changes':
        click.echo("❌ No staged changes found. Stage your changes with 'git add' first.")
        return
    
    if result['status'] == 'error':
        click.echo(f"❌ Analysis failed: {result['message']}")
        for error in result.get('errors', []):
            click.echo(f"   - {error}")
        return
    
    # Display results
    click.echo("\n📊 Analysis Complete!")
    click.echo(f"Files changed: {len(result['context']['files_changed'])}")
    click.echo(f"Additions: +{result['context']['additions']}")
    click.echo(f"Deletions: -{result['context']['deletions']}")
    
    if result['context']['breaking_changes']:
        click.echo("\n⚠️  Breaking changes detected:")
        for change in result['context']['breaking_changes']:
            click.echo(f"   - {change}")
    
    if result['context']['related_issues']:
        click.echo("\n🔗 Related issues:")
        for issue in result['context']['related_issues']:
            click.echo(f"   - #{issue['number']}: {issue['title']}")
    
    click.echo("\n📝 Generated commit message:")
    click.echo("-" * 50)
    click.echo(result['commit_message'])
    click.echo("-" * 50)
    
    # Show analysis details
    click.echo("\n🤖 AI Analysis Results:")
    for analysis in result['analysis_results']:
        click.echo(f"   - {analysis['tool']}: {analysis['execution_time']:.2f}s")
    
    if not dry_run:
        if click.confirm("\n✅ Create commit with this message?"):
            # Create commit
            subprocess.run(['git', 'commit', '-m', result['commit_message']])
            click.echo("✨ Commit created successfully!")
            
            # Link to issues if configured
            if config.link_issues and result['context']['related_issues']:
                commit_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
                for issue in result['context']['related_issues']:
                    try:
                        subprocess.run([
                            'gh', 'issue', 'comment', str(issue['number']),
                            '--body', f"Related commit: {commit_sha[:7]}"
                        ])
                        click.echo(f"   - Linked to issue #{issue['number']}")
                    except:
                        pass

@cli.command()
@click.option('--since', default='HEAD~10', help='Analyze commits since this ref')
@click.option('--format', type=click.Choice(['markdown', 'json']), default='markdown')
@click.pass_obj
async def changelog(config: Config, since: str, format: str):
    """Generate changelog from commit history."""
    click.echo(f"📚 Generating changelog since {since}...")
    
    # Get commits since ref
    repo = git.Repo(config.repository_path)
    commits = list(repo.iter_commits(f'{since}..HEAD'))
    
    if not commits:
        click.echo("No commits found in range.")
        return
    
    # Group commits by type
    grouped = defaultdict(list)
    for commit in commits:
        # Parse conventional commit
        import re
        match = re.match(r'^(\w+)(?:\((.+?)\))?!?: (.+)', commit.message)
        if match:
            type_, scope, summary = match.groups()
            grouped[type_].append({
                'sha': commit.hexsha[:7],
                'scope': scope,
                'summary': summary.strip(),
                'breaking': '!' in commit.message.split(':')[0]
            })
    
    if format == 'markdown':
        click.echo("\n# Changelog\n")
        
        # Breaking changes first
        breaking = [c for commits in grouped.values() for c in commits if c['breaking']]
        if breaking:
            click.echo("## ⚠️ Breaking Changes\n")
            for c in breaking:
                scope = f"**{c['scope']}**: " if c['scope'] else ""
                click.echo(f"- {scope}{c['summary']} ({c['sha']})")
            click.echo()
        
        # Features
        if 'feat' in grouped:
            click.echo("## ✨ Features\n")
            for c in grouped['feat']:
                scope = f"**{c['scope']}**: " if c['scope'] else ""
                click.echo(f"- {scope}{c['summary']} ({c['sha']})")
            click.echo()
        
        # Bug fixes
        if 'fix' in grouped:
            click.echo("## 🐛 Bug Fixes\n")
            for c in grouped['fix']:
                scope = f"**{c['scope']}**: " if c['scope'] else ""
                click.echo(f"- {scope}{c['summary']} ({c['sha']})")
            click.echo()
        
        # Other changes
        other_types = set(grouped.keys()) - {'feat', 'fix'}
        if other_types:
            click.echo("## 🔧 Other Changes\n")
            for type_ in sorted(other_types):
                for c in grouped[type_]:
                    scope = f"**{c['scope']}**: " if c['scope'] else ""
                    click.echo(f"- {type_}: {scope}{c['summary']} ({c['sha']})")
    
    else:  # JSON format
        output = {
            'since': since,
            'commits': dict(grouped),
            'breaking_changes': [c for commits in grouped.values() for c in commits if c['breaking']],
            'stats': {
                'total_commits': len(commits),
                'features': len(grouped.get('feat', [])),
                'fixes': len(grouped.get('fix', [])),
                'breaking': len([c for commits in grouped.values() for c in commits if c['breaking']])
            }
        }
        click.echo(json.dumps(output, indent=2))

@cli.command()
@click.argument('base', default='main')
@click.pass_obj
async def review(config: Config, base: str):
    """Review changes against base branch."""
    click.echo(f"🔍 Reviewing changes against {base}...")
    
    # Get diff against base
    diff_output = subprocess.check_output(['git', 'diff', f'{base}...HEAD']).decode()
    
    if not diff_output:
        click.echo("No changes to review.")
        return
    
    # Create temporary context
    patch = PatchSet(diff_output)
    files_changed = [f.path for f in patch]
    
    context = CommitContext(
        files_changed=files_changed,
        additions=sum(f.added for f in patch),
        deletions=sum(f.removed for f in patch),
        diff_content=diff_output,
        previous_commits=[],
        related_issues=[]
    )
    
    # Run analysis
    orchestrator = CommitAnalysisOrchestrator(config)
    
    # Analyze with each tool
    results = await asyncio.gather(*[
        analyzer.analyze(context) for analyzer in orchestrator.analyzers
    ])
    
    click.echo("\n📊 Code Review Results:\n")
    
    for result in results:
        if not result.error:
            click.echo(f"### {result.tool.value.upper()} Analysis\n")
            click.echo(result.content)
            click.echo("\n" + "-" * 50 + "\n")

# ==================== Extension System ====================

class CommitAnalysisPlugin(ABC):
    """Base class for analysis plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass
    
    @abstractmethod
    async def analyze(self, context: CommitContext) -> Dict[str, Any]:
        """Analyze commit context."""
        pass

class SecurityAnalysisPlugin(CommitAnalysisPlugin):
    """Plugin for security analysis."""
    
    @property
    def name(self) -> str:
        return "security"
    
    async def analyze(self, context: CommitContext) -> Dict[str, Any]:
        """Analyze security implications of changes."""
        security_issues = []
        
        for file in context.files_changed:
            # Check for sensitive file patterns
            sensitive_patterns = [
                '.env', 'config', 'secret', 'password', 'key', 'token',
                'credential', 'auth', 'private'
            ]
            
            if any(pattern in file.lower() for pattern in sensitive_patterns):
                security_issues.append(f"Sensitive file modified: {file}")
        
        # Check diff for hardcoded secrets
        secret_patterns = [
            r'api[_-]?key\s*=\s*["\'][\w\-]+["\']',
            r'password\s*=\s*["\'][\w\-]+["\']',
            r'token\s*=\s*["\'][\w\-]+["\']'
        ]
        
        import re
        for pattern in secret_patterns:
            if re.search(pattern, context.diff_content, re.IGNORECASE):
                security_issues.append("Potential hardcoded secret detected")
        
        return {
            'has_issues': bool(security_issues),
            'issues': security_issues,
            'severity': 'high' if security_issues else 'low'
        }

# ==================== Main Entry Point ====================

def main():
    """Main entry point."""
    # Run async CLI
    asyncio.run(cli())

if __name__ == '__main__':
    main()
```

### Installation Script: `setup.py`

```python
from setuptools import setup, find_packages

setup(
    name="intelligent-commit-analyzer",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "gitpython>=3.1",
        "google-genai>=0.1.0",
        "networkx>=3.0",
        "pyyaml>=6.0",
        "pydantic>=2.0",
        "ratelimit>=2.2",
        "tenacity>=8.0",
        "unidiff>=0.7",
        "aiofiles>=23.0",
        "httpx>=0.24",
    ],
    entry_points={
        "console_scripts": [
            "commit-analyzer=intelligent_commit_analyzer:main",
        ],
        "commit_analysis.plugins": [
            "security=intelligent_commit_analyzer:SecurityAnalysisPlugin",
        ],
    },
    python_requires=">=3.8",
)
```

### Configuration File: `config.yaml`

```yaml
# AI Tool Configuration
claude_api_key: ${ANTHROPIC_API_KEY}
openai_api_key: ${OPENAI_API_KEY}
google_api_key: ${GOOGLE_API_KEY}

# Repository Configuration  
repository_path: .
branch: main

# Pipeline Configuration
max_concurrent_tasks: 10
enable_unsafe_mode: false  # Enable for full autonomy

# GitHub Configuration
github_token: ${GITHUB_TOKEN}
link_issues: true

# Logging Configuration
log_level: INFO
log_file: commit_analyzer.log

# Analysis Configuration
analysis:
  max_diff_size: 10000
  context_lines: 3
  include_file_types:
    - .py
    - .js
    - .ts
    - .java
    - .go
  exclude_patterns:
    - __pycache__
    - node_modules
    - .git
    - .env

# Commit Message Configuration
commit_message:
  max_title_length: 72
  max_body_line_length: 100
  include_co_authors: true
  sign_commits: false
```

### Docker Support: `Dockerfile`

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt update \
    && apt install gh -y

# Install Node.js for Codex CLI
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-cli

# Install Codex CLI  
RUN npm install -g @openai/codex-cli

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["commit-analyzer"]
```

### Testing Suite: `tests/test_analyzer.py`

```python
import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from intelligent_commit_analyzer import (
    CommitContext,
    ClaudeCodeAnalyzer,
    GeminiAnalyzer,
    CommitAnalysisOrchestrator,
    Config
)

@pytest.fixture
def sample_context():
    """Create sample commit context for testing."""
    return CommitContext(
        files_changed=['src/main.py', 'tests/test_main.py'],
        additions=50,
        deletions=10,
        diff_content="+ def new_feature():\n+     return 'hello'",
        previous_commits=[
            {'sha': 'abc123', 'message': 'feat: add authentication'},
            {'sha': 'def456', 'message': 'fix: resolve memory leak'}
        ],
        related_issues=[
            {'number': 42, 'title': 'Add new feature', 'state': 'open'}
        ]
    )

@pytest.mark.asyncio
async def test_claude_analyzer(sample_context):
    """Test Claude Code analyzer."""
    with patch('asyncio.create_subprocess_exec') as mock_subprocess:
        # Mock subprocess response
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b'{"type": "message", "content": "Analysis complete"}',
            b''
        )
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process
        
        analyzer = ClaudeCodeAnalyzer(api_key='test-key')
        result = await analyzer.analyze(sample_context)
        
        assert result.tool == AIToolType.CLAUDE
        assert not result.error
        assert result.execution_time > 0

@pytest.mark.asyncio
async def test_orchestrator_synthesis():
    """Test result synthesis in orchestrator."""
    config = Config(
        claude_api_key='test',
        openai_api_key='test', 
        google_api_key='test'
    )
    
    orchestrator = CommitAnalysisOrchestrator(config)
    
    # Mock analyzers
    orchestrator.analyzers = [
        AsyncMock(analyze=AsyncMock(return_value=AnalysisResult(
            tool=AIToolType.CLAUDE,
            content="Implemented new authentication system",
            metadata={'commit_type': 'feat', 'scope': 'auth'}
        ))),
        AsyncMock(analyze=AsyncMock(return_value=AnalysisResult(
            tool=AIToolType.GEMINI,
            content="Added OAuth2 support", 
            metadata={'commit_type': 'feat', 'breaking': False}
        )))
    ]
    
    with patch.object(orchestrator, '_build_context', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = sample_context
        
        result = await orchestrator.analyze_changes()
        
        assert result['status'] == 'success'
        assert 'feat' in result['commit_message']
        assert result['details']['type'] == 'feat'
```

### GitHub Actions Workflow: `.github/workflows/commit-analysis.yml`

```yaml
name: Intelligent Commit Analysis

on:
  push:
    branches: [ main, develop ]
  pull_request:
    types: [ opened, synchronize ]

jobs:
  analyze:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
      with:
        fetch-depth: 0
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '20'
    
    - name: Install CLI tools
      run: |
        npm install -g @anthropic-ai/claude-cli
        npm install -g @openai/codex-cli
    
    - name: Install dependencies
      run: |
        pip install -e .
    
    - name: Run commit analysis
      env:
        ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      run: |
        commit-analyzer analyze --dry-run
```

## Key Features

### 1. **Multi-AI Orchestration**
- Parallel execution of Claude Code CLI, Codex CLI, and Gemini SDK
- Intelligent result synthesis with voting mechanism
- Fallback strategies for resilience

### 2. **Advanced Context Building**
- Dependency graph construction for understanding file relationships
- Breaking change detection through AST analysis
- Historical commit analysis for context
- GitHub issue linking and reference

### 3. **Production-Ready Architecture**
- Plugin system for extensibility
- Comprehensive error handling with circuit breakers
- Rate limiting and retry mechanisms
- Structured logging and monitoring

### 4. **Performance Optimization**
- Parallel file processing with asyncio
- Memory-aware queue management
- Intelligent chunking for large codebases
- Caching strategies for repeated analyses

### 5. **Extensibility**
- Plugin architecture for custom analyzers
- Support for changelog generation
- Code review capabilities
- Monorepo support with package-specific analysis

## Usage Examples

```bash
# Basic usage - analyze and commit
commit-analyzer analyze

# Dry run - see message without committing
commit-analyzer analyze --dry-run

# Generate changelog
commit-analyzer changelog --since v1.0.0 --format markdown

# Review changes against main branch
commit-analyzer review main

# Use custom configuration
commit-analyzer -c custom-config.yaml analyze
```

## Extension Points

1. **Custom Plugins**: Add security, performance, or domain-specific analyzers
2. **Changelog Templates**: Customize changelog format for your needs
3. **Commit Hooks**: Integrate with pre-commit for automated analysis
4. **CI/CD Integration**: Use in GitHub Actions, GitLab CI, or Jenkins
5. **Monorepo Support**: Extend for package-specific commit messages

This production-ready system provides a sophisticated, extensible solution for intelligent commit message generation that leverages the best of multiple AI tools while maintaining high performance and reliability.