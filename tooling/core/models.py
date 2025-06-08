"""
Core data models for the tooling system.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class AnalysisMode(Enum):
    """Analysis modes for changelog generation"""
    CURRENT_BRANCH = "current-branch-only"
    SMART_HISTORICAL = "smart-historical"
    REBUILD_ALL = "rebuild-all"


@dataclass
class ConventionalCommit:
    """Represents a parsed conventional commit"""
    type: str
    scope: Optional[str]
    breaking: bool
    description: str
    body: Optional[str]
    footers: Dict[str, str]


@dataclass
class GitCommit:
    """Represents a git commit with full metadata"""
    hash: str
    short_hash: str
    message: str
    author_name: str
    author_email: str
    commit_date: str
    commit_time: str
    files: List[str]
    pr_number: Optional[int] = None
    conventional: Optional[ConventionalCommit] = None
    
    def __post_init__(self):
        """Parse conventional commit format"""
        self.conventional = self._parse_conventional_commit()
    
    def _parse_conventional_commit(self) -> Optional[ConventionalCommit]:
        """Parse commit message as conventional commit"""
        # Pattern: type(scope)!: description
        pattern = r'^(\w+)(?:\(([^)]+)\))?(!)?:\s*(.+)$'
        match = re.match(pattern, self.message, re.MULTILINE)
        
        if not match:
            return None
            
        commit_type = match.group(1)
        scope = match.group(2)
        breaking = bool(match.group(3))
        description = match.group(4)
        
        # Parse body and footers
        lines = self.message.split('\n')
        body_lines = []
        footers = {}
        
        in_footer = False
        for line in lines[1:]:
            if re.match(r'^[A-Z][\w-]+:\s*.+$', line):
                in_footer = True
                key, value = line.split(':', 1)
                footers[key.strip()] = value.strip()
            elif in_footer and line.startswith(' '):
                # Continuation of previous footer
                last_key = list(footers.keys())[-1]
                footers[last_key] += ' ' + line.strip()
            else:
                body_lines.append(line)
        
        # Check for BREAKING CHANGE footer
        if 'BREAKING CHANGE' in footers or 'BREAKING-CHANGE' in footers:
            breaking = True
            
        body = '\n'.join(body_lines).strip() if body_lines else None
        
        return ConventionalCommit(
            type=commit_type,
            scope=scope,
            breaking=breaking,
            description=description,
            body=body,
            footers=footers
        )
    
    def get_attribution(self, remote_url: str) -> str:
        """Generate GitHub-style attribution string"""
        # Extract GitHub username
        username = self._extract_github_username()
        
        # Format: [@username](link), YYYY-MM-DD, H:MM[AM/PM] TZ, [hash](link)[, PR [#num](link)]
        parts = []
        
        if remote_url:
            parts.append(f"[@{username}](https://github.com/{username})")
        else:
            parts.append(f"@{username}")
            
        parts.append(self.commit_date)
        parts.append(self.commit_time)
        
        if remote_url:
            parts.append(f"[{self.short_hash}]({remote_url}/commit/{self.hash})")
        else:
            parts.append(self.short_hash)
            
        if self.pr_number and remote_url:
            parts.append(f"PR [#{self.pr_number}]({remote_url}/pull/{self.pr_number})")
        elif self.pr_number:
            parts.append(f"PR #{self.pr_number}")
            
        return ", ".join(parts)
    
    def _extract_github_username(self) -> str:
        """Extract GitHub username from email or author name"""
        # Check for GitHub noreply email
        if match := re.match(r'^(\d+\+)?([^@]+)@users\.noreply\.github\.com$', self.author_email):
            return match.group(2)
        
        # Check for + notation in email
        if '+' in self.author_email:
            parts = self.author_email.split('+')
            if len(parts) > 1:
                return parts[1].split('@')[0]
        
        # Fallback to author name
        return self.author_name.lower().replace(' ', '-')


@dataclass
class VersionEntry:
    """Represents a changelog version entry"""
    version: str
    date: str
    content: str
    is_empty: bool = False


@dataclass
class AnalysisMetrics:
    """Metrics for analysis performance"""
    total_commits: int = 0
    total_files: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    llm_calls: int = 0
    processing_time: float = 0.0
    
    def print_summary(self):
        """Print metrics summary"""
        if self.total_commits == 0:
            return
            
        from tooling.cli.cli_utils import print_header, print_info
        
        print_header("Analysis Metrics")
        print_info(f"Total commits processed: {self.total_commits}")
        print_info(f"Total files analyzed: {self.total_files}")
        print_info(f"LLM API calls: {self.llm_calls}")
        
        if self.cache_hits + self.cache_misses > 0:
            cache_rate = (self.cache_hits / (self.cache_hits + self.cache_misses)) * 100
            print_info(f"Cache hit rate: {cache_rate:.1f}%")
            
        print_info(f"Processing time: {self.processing_time:.1f}s")


# Conventional commit type mapping
CONVENTIONAL_TYPES = {
    "feat": "Added",
    "fix": "Fixed",
    "docs": "Changed",
    "style": "Changed",
    "refactor": "Changed",
    "perf": "Changed",
    "test": "Changed",
    "build": "Changed",
    "ci": "Changed",
    "chore": "Changed",
    "revert": "Changed",
    "security": "Security",
    "breaking": "Changed",  # Will be marked as BREAKING CHANGE
}

# Keep a Changelog sections in order
CHANGELOG_SECTIONS = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"] 