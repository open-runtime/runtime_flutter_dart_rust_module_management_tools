#!/usr/bin/env python3
"""
sync_changelogs.py - Production-ready AI-powered changelog generator for monorepos

Features:
- Tag-based processing (oldest to newest)
- Full GitHub-style attribution with timestamps and PR links
- File content analysis for better context
- Enhanced commit message analysis with LLM
- Diff analysis for deeper understanding
- Empty version detection and backfilling
- Uncommitted changes handling
- Current branch mode (default): processes commits since last tag or recent commits
- Smart historical mode: backfills from last tag
- Full rebuild mode: rebuilds entire changelog history
- Custom starting points with --since
- Package-specific changelog headers
- Preserves existing entries (idempotent)
- Parallel processing with progress tracking
- Comprehensive error handling and recovery
- Caching for performance
- Dry-run mode
- Progress bars
- Conventional commit parsing

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import argparse
import asyncio
import concurrent.futures
import dataclasses
import datetime
import hashlib
import json
import os
import pathlib
import pickle
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from functools import lru_cache
import threading
import fcntl
import errno
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv('DEBUG') else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Note: Install tqdm for better progress display in multi-threaded mode
    # pip install tqdm
    
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Global lock for thread-safe console output
_print_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

VERSION = "7.1.0"

# Get dynamic package definitions
try:
    from tooling.core.common_config import get_package_info
    PACKAGES = get_package_info()
except ImportError:
    from core.common_config import get_package_info
    PACKAGES = get_package_info()

# Keep a Changelog sections in order
CHANGELOG_SECTIONS = ["Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"]

# LLM Configuration
# Model fallback chain - try each model in order
GEMINI_MODELS = [
    "gemini-2.5-flash-preview-05-20",  # Latest 2.5 Flash
    "gemini-2.5-flash-preview-04-17",  # Older 2.5 Flash
    "gemini-2.0-flash",                 # 2.0 Flash (alias for gemini-2.0-flash-001)
]

# Pro model for large context tasks
PRO_MODEL = "gemini-2.5-pro-preview-05-06"

# Default to Flash for most tasks
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", GEMINI_MODELS[0])
FLASH_MODEL = GEMINI_MODELS[0]  # Use latest Flash by default

LLM_TIMEOUT = 60
MAX_RETRIES = 3
RETRY_DELAY = 2

# File analysis limits
MAX_FILES_PER_PACKAGE = 75
MAX_FILE_SIZE_BYTES = 10000  # 10KB per file preview
MAX_TOTAL_BYTES = 2097152    # 2MB total
DEFAULT_MAX_COMMITS = 200    # per package before cutoff

# Parallel processing configuration
MAX_WORKERS = os.cpu_count() or 4  # Use all CPU cores
MAX_LLM_CONCURRENT = 8  # Max concurrent LLM calls - increased from 3
BATCH_SIZE = 10  # Process commits in batches

# Cache configuration
CACHE_DIR = pathlib.Path(".changelog_cache")
CACHE_EXPIRY_DAYS = 7

# Conventional commit types
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

# ═══════════════════════════════════════════════════════════════════════════
# Terminal Colors and UI
# ═══════════════════════════════════════════════════════════════════════════

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    
    # Compound styles
    SUCCESS = f'{BOLD}{GREEN}'
    ERROR = f'{BOLD}{RED}'
    WARNING = f'{BOLD}{YELLOW}'
    INFO = f'{BOLD}{BLUE}'
    HEADER = f'{BOLD}{PURPLE}'

def print_color(color: str, message: str, file=None):
    """Print colored message (thread-safe)"""
    with _print_lock:
        print(f"{color}{message}{Colors.RESET}", file=file or sys.stdout)

def print_header(title: str):
    """Print a formatted header"""
    width = 60
    print_color(Colors.CYAN, "═" * width)
    print_color(Colors.CYAN, f"{title:^{width}}")
    print_color(Colors.CYAN, "═" * width)

class ProgressTracker:
    """Thread-safe progress tracking"""
    def __init__(self, total: int, desc: str = "Processing"):
        self.total = total
        self.desc = desc
        self.current = 0
        self.lock = threading.Lock()
        self.pbar = None
        self.is_multi_threaded = threading.active_count() > 1
        
        if HAS_TQDM:
            self.pbar = tqdm(total=total, desc=desc, unit="items")
    
    def update(self, n: int = 1):
        """Update progress"""
        with self.lock:
            self.current += n
            if self.pbar:
                self.pbar.update(n)
            elif not self.is_multi_threaded:
                # Only show progress in single-threaded mode to avoid display issues
                print(f"\r{self.desc}: {self.current}/{self.total}", end="", flush=True)
    
    def close(self):
        """Close progress bar"""
        if self.pbar:
            self.pbar.close()
        elif not self.is_multi_threaded:
            print()  # New line after progress

# ═══════════════════════════════════════════════════════════════════════════
# Configuration Management
# ═══════════════════════════════════════════════════════════════════════════

class Config:
    """Configuration management with file support"""
    def __init__(self, config_file: Optional[pathlib.Path] = None):
        self.config = {}
        self.config_file = config_file or pathlib.Path(".changelog.yml")
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file"""
        if self.config_file.exists() and HAS_YAML:
            try:
                with open(self.config_file, 'r') as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception as e:
                print_color(Colors.WARNING, f"Failed to load config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def get_package_config(self, package: str) -> Dict[str, Any]:
        """Get package-specific configuration"""
        packages = self.get('packages', {})
        return packages.get(package, {})

# ═══════════════════════════════════════════════════════════════════════════
# Cache Management
# ═══════════════════════════════════════════════════════════════════════════

class CacheManager:
    """Manage caching of LLM responses and analysis results"""
    
    def __init__(self, cache_dir: pathlib.Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self._clean_old_cache()
    
    def _clean_old_cache(self):
        """Remove cache files older than CACHE_EXPIRY_DAYS"""
        expiry_time = time.time() - (CACHE_EXPIRY_DAYS * 24 * 60 * 60)
        for cache_file in self.cache_dir.glob("*.cache"):
            if cache_file.stat().st_mtime < expiry_time:
                cache_file.unlink()
    
    def _get_cache_key(self, data: str) -> str:
        """Generate cache key from data"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value with file locking"""
        cache_file = self.cache_dir / f"{self._get_cache_key(key)}.cache"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    # Try to acquire shared lock (non-blocking)
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                        data = pickle.load(f)
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        return data
                    except (IOError, OSError) as e:
                        if e.errno == errno.EAGAIN:
                            # Lock is held by another process, skip cache
                            return None
                        raise
            except Exception:
                try:
                    cache_file.unlink()  # Remove corrupted cache
                except:
                    pass  # Ignore if already deleted
        return None
    
    def set(self, key: str, value: Any):
        """Set cached value with file locking"""
        cache_file = self.cache_dir / f"{self._get_cache_key(key)}.cache"
        temp_file = cache_file.with_suffix('.tmp')
        
        try:
            # Write to temp file first
            with open(temp_file, 'wb') as f:
                # Acquire exclusive lock
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                pickle.dump(value, f)
                f.flush()
                os.fsync(f.fileno())
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            # Atomic rename
            temp_file.rename(cache_file)
        except Exception as e:
            # Clean up temp file if it exists
            try:
                temp_file.unlink()
            except:
                pass
            # Log error in debug mode
            if os.getenv('DEBUG'):
                print_color(Colors.GRAY, f"[DEBUG] Cache write failed: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════════════

class AnalysisMode(Enum):
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
            
        print_header("Analysis Metrics")
        print_color(Colors.INFO, f"Total commits processed: {self.total_commits}")
        print_color(Colors.INFO, f"Total files analyzed: {self.total_files}")
        print_color(Colors.INFO, f"LLM API calls: {self.llm_calls}")
        
        if self.cache_hits + self.cache_misses > 0:
            cache_rate = (self.cache_hits / (self.cache_hits + self.cache_misses)) * 100
            print_color(Colors.INFO, f"Cache hit rate: {cache_rate:.1f}%")
            
        print_color(Colors.INFO, f"Processing time: {self.processing_time:.1f}s")

# ═══════════════════════════════════════════════════════════════════════════
# Git Operations
# ═══════════════════════════════════════════════════════════════════════════

class GitOps:
    """Git operations wrapper with sanitization"""
    
    @staticmethod
    def run_command(cmd: List[str], **kwargs) -> Tuple[int, str, str]:
        """Run command and return (code, stdout, stderr) with sanitized output"""
        # Extract timeout from kwargs if provided, otherwise use default
        timeout = kwargs.pop('timeout', 30)
        
        # Set up environment to disable Git pager
        env = kwargs.get('env', os.environ.copy())
        env['GIT_PAGER'] = ''  # Disable git pager
        env['PAGER'] = ''      # Disable general pager
        kwargs['env'] = env
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                **kwargs
            )
            # Sanitize ANSI escape sequences
            stdout = re.sub(r'\x1b\[[0-9;]*[mGKHJF]', '', result.stdout)
            stderr = re.sub(r'\x1b\[[0-9;]*[mGKHJF]', '', result.stderr)
            return result.returncode, stdout.strip(), stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    @staticmethod
    def get_current_branch() -> Optional[str]:
        """Get current git branch"""
        code, out, _ = GitOps.run_command(['git', 'branch', '--show-current'])
        return out if code == 0 else None
    
    @staticmethod
    def get_remote_url() -> Optional[str]:
        """Get GitHub remote URL"""
        code, out, _ = GitOps.run_command(['git', 'config', '--get', 'remote.origin.url'])
        if code != 0:
            return None
            
        # Convert SSH to HTTPS
        if ssh_match := re.match(r'git@github\.com:(.+?)(?:\.git)?$', out):
            return f"https://github.com/{ssh_match.group(1)}"
        
        # Clean HTTPS URL
        if https_match := re.match(r'https://github\.com/(.+?)(?:\.git)?$', out):
            return f"https://github.com/{https_match.group(1)}"
            
        return out.rstrip('.git')
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_all_tags() -> List[str]:
        """Get all tags sorted by version (oldest first)"""
        code, out, _ = GitOps.run_command(['git', 'tag', '-l', '--sort=version:refname'])
        if code != 0:
            return []
        return [tag for tag in out.splitlines() if tag.strip()]
    
    @staticmethod
    def get_first_commit() -> Optional[str]:
        """Get the first commit in the repository"""
        code, out, _ = GitOps.run_command(['git', 'rev-list', '--max-parents=0', 'HEAD'])
        return out.strip() if code == 0 else None
    
    @staticmethod
    def get_commits_between(start: Optional[str], end: str = "HEAD", path_glob: Optional[str] = None) -> List[GitCommit]:
        """Get commits between two refs with optimized batching"""
        cmd = ['git', 'log']
        
        if start:
            cmd.append(f"{start}..{end}")
        else:
            cmd.append(end)
            
        cmd.extend([
            '--pretty=format:%H|%h|%s|%an|%ae|%ad|%cd',
            '--date=format:%Y-%m-%d|%l:%M%p %Z',
            '--name-only'  # Include file names in output
        ])
        
        if path_glob:
            cmd.extend(['--', path_glob])
        
        code, out, _ = GitOps.run_command(cmd)
        if code != 0:
            return []
            
        commits = []
        current_commit = None
        
        for line in out.splitlines():
            if not line:
                continue
                
            if '|' in line and len(line.split('|')) >= 7:
                # This is a commit line
                if current_commit:
                    commits.append(current_commit)
                    
                parts = line.split('|')
                current_commit = GitCommit(
                    hash=parts[0],
                    short_hash=parts[1],
                    message=parts[2],  # Will get full message later
                    author_name=parts[3],
                    author_email=parts[4],
                    commit_date=parts[5],
                    commit_time=parts[6],
                    files=[]
                )
            elif current_commit and line.strip():
                # This is a file name
                current_commit.files.append(line.strip())
        
        # Don't forget the last commit
        if current_commit:
            commits.append(current_commit)
        
        # Now batch-fetch full commit messages
        if commits:
            # Get all commit messages in one command
            hashes = [c.hash for c in commits]
            cmd = ['git', 'show', '-s', '--format=%H%n%B%n--END--'] + hashes
            code, out, _ = GitOps.run_command(cmd, timeout=60)
            
            if code == 0:
                # Parse the output
                messages = {}
                current_hash = None
                current_lines = []
                
                for line in out.splitlines():
                    if len(line) == 40 and all(c in '0123456789abcdef' for c in line):
                        # This is a commit hash
                        if current_hash and current_lines:
                            # Remove the --END-- marker
                            if current_lines[-1] == '--END--':
                                current_lines = current_lines[:-1]
                            messages[current_hash] = '\n'.join(current_lines).strip()
                        current_hash = line
                        current_lines = []
                    else:
                        current_lines.append(line)
                
                # Don't forget the last one
                if current_hash and current_lines:
                    if current_lines[-1] == '--END--':
                        current_lines = current_lines[:-1]
                    messages[current_hash] = '\n'.join(current_lines).strip()
                
                # Update commit messages
                for commit in commits:
                    if commit.hash in messages:
                        commit.message = messages[commit.hash]
                        
                        # Extract PR number from message
                        pr_match = re.search(r'(?:Merge pull request |PR |#)(\d+)', commit.message)
                        if pr_match:
                            commit.pr_number = int(pr_match.group(1))
                
        return commits
    
    @staticmethod
    def get_file_content(path: str, max_bytes: int = MAX_FILE_SIZE_BYTES) -> str:
        """Get file content up to max_bytes"""
        try:
            with open(path, 'rb') as f:
                content = f.read(max_bytes)
                return content.decode('utf-8', errors='replace')
        except Exception:
            return "[File not accessible]"
    
    @staticmethod
    def is_dirty() -> bool:
        """Check if working directory has uncommitted changes"""
        code, out, _ = GitOps.run_command(['git', 'status', '--porcelain'])
        return bool(out) if code == 0 else False
    
    @staticmethod
    @lru_cache(maxsize=1000)
    def is_gitignored(file_path: str) -> bool:
        """Check if a file is gitignored"""
        # Use git check-ignore to see if file is ignored
        code, _, _ = GitOps.run_command(['git', 'check-ignore', file_path])
        # Exit code 0 means the file is ignored
        return code == 0

# ═══════════════════════════════════════════════════════════════════════════
# Changelog Parser and Writer
# ═══════════════════════════════════════════════════════════════════════════

class ChangelogManager:
    """Manages changelog reading, parsing, and writing"""
    
    def __init__(self, path: pathlib.Path, package_key: str = "dart"):
        self.path = path
        self.package_key = package_key
        self.content = ""
        self.versions: List[VersionEntry] = []
        self._load()
    
    def _load(self):
        """Load and parse changelog"""
        if not self.path.exists():
            self.content = self._default_header()
            return
            
        self.content = self.path.read_text(encoding='utf-8')
        self._parse_versions()
    
    def _default_header(self) -> str:
        """Default changelog header with package-specific information"""
        pkg_info = PACKAGES.get(self.package_key, {})
        title = pkg_info.get("title", "Changelog")
        description = pkg_info.get("description", "this package")
        
        return f"""# {title}

All notable changes to {description} will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

"""
    
    def _parse_versions(self):
        """Parse version entries from content"""
        version_pattern = re.compile(r'^## \[(v?\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})', re.MULTILINE)
        
        matches = list(version_pattern.finditer(self.content))
        for i, match in enumerate(matches):
            version = match.group(1).lstrip('v')
            date = match.group(2)
            
            # Extract content until next version or end
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self.content)
            content = self.content[start:end].strip()
            
            # Check if empty
            is_empty = self._is_empty_section(content)
            
            self.versions.append(VersionEntry(version, date, content, is_empty))
    
    def _is_empty_section(self, content: str) -> bool:
        """Check if a version section is empty or has only placeholders"""
        if not content:
            return True
            
        # Remove section headers
        for section in CHANGELOG_SECTIONS:
            content = content.replace(f"### {section}", "")
            
        # Check for common placeholders
        placeholders = ['n/a', 'none', 'todo', 'tbd', '...', '-']
        cleaned = content.strip().lower()
        
        return not cleaned or cleaned in placeholders
    
    def get_empty_versions(self) -> List[str]:
        """Get list of empty version numbers"""
        return [v.version for v in self.versions if v.is_empty]
    
    def validate_entry(self, content: str) -> Tuple[bool, List[str]]:
        """Validate changelog entry format"""
        issues = []
        
        # Check for sections
        has_section = any(f"### {section}" in content for section in CHANGELOG_SECTIONS)
        if not has_section:
            issues.append("No standard changelog sections found")
        
        # Check for proper attribution format
        attribution_pattern = r'\[@\w+\]\(https?://[^)]+\),\s*\d{4}-\d{2}-\d{2}'
        if not re.search(attribution_pattern, content):
            issues.append("Missing or incorrect attribution format")
        
        # Check for empty sections
        for section in CHANGELOG_SECTIONS:
            if f"### {section}" in content:
                section_content = content.split(f"### {section}")[1].split("###")[0]
                if not section_content.strip() or section_content.strip() == "-":
                    issues.append(f"Empty {section} section")
        
        return len(issues) == 0, issues
    
    def merge_version(self, version: str, date: str, new_content: str):
        """Merge content for a version, preserving existing entries"""
        # SAFETY: Never process empty new content unless explicitly "NO_CHANGES"
        if not new_content or (new_content.strip() == "" and new_content != "NO_CHANGES"):
            print_color(Colors.WARNING, f"Skipping merge for v{version} - empty new content")
            return
            
        # Validate new content
        is_valid, issues = self.validate_entry(new_content)
        if not is_valid and new_content != "NO_CHANGES":
            # Only show validation warnings in debug mode
            if os.getenv('DEBUG'):
                print_color(Colors.YELLOW, f"Validation issues in changelog entry: {', '.join(issues)}")
        
        clean_version = version.lstrip('v')
        header = f"## [v{clean_version}] - {date}"
        
        # Remove [Unreleased] section if we're adding a new version
        if "## [Unreleased]" in self.content and header not in self.content:
            self.content = re.sub(
                r"## \[Unreleased\].*?(?=^## |\Z)", 
                "", 
                self.content, 
                flags=re.S | re.M
            )
        
        # Check if version exists (with or without GitHub URL)
        version_pattern = re.compile(rf"## \[v{re.escape(clean_version)}\](?:\([^)]+\))? - ", re.MULTILINE)
        if version_pattern.search(self.content):
            # Version exists - merge content
            self._merge_existing_version(clean_version, new_content)
        else:
            # New version - insert after header
            self._insert_new_version(clean_version, date, new_content)
    
    def _merge_existing_version(self, version: str, new_content: str):
        """Merge new content with existing version"""
        # SAFETY: Backup existing content before merge
        original_content = self.content
        
        try:
            # Find version boundaries (with or without GitHub URL)
            version_header_pattern = rf"## \[v{re.escape(version)}\](?:\([^)]+\))? - [^\n]+\n"
            
            # Find the start of this version
            start_match = re.search(version_header_pattern, self.content)
            if not start_match:
                print_color(Colors.WARNING, f"Could not find version v{version} for merging")
                return
                
            start = start_match.end()
            
            # Find next version or end
            next_version = re.search(r'^## \[v?\d+\.\d+\.\d+\]', self.content[start:], re.MULTILINE)
            end = start + next_version.start() if next_version else len(self.content)
            
            existing_content = self.content[start:end].strip()
            
            # SAFETY: Check if we have existing content to preserve
            if existing_content and new_content == "NO_CHANGES":
                print_color(Colors.INFO, f"Preserving existing content for v{version} (no changes)")
                return
                
            merged = self._merge_sections(existing_content, new_content)
            
            # SAFETY: Verify merged content is not empty if we had existing content
            if existing_content and not merged.strip():
                print_color(Colors.ERROR, f"Merge resulted in empty content for v{version}, preserving original")
                self.content = original_content
                return
            
            # Ensure proper spacing - no extra newline if merged already ends with newlines
            if merged.endswith('\n\n'):
                spacing = ""
            elif merged.endswith('\n'):
                spacing = "\n"
            else:
                spacing = "\n\n"
                
            self.content = (
                self.content[:start] +
                merged + spacing +
                self.content[end:]
            )
            
        except Exception as e:
            print_color(Colors.ERROR, f"Error merging version {version}: {e}")
            print_color(Colors.WARNING, "Restoring original content")
            self.content = original_content
    
    def _merge_sections(self, existing: str, new: str) -> str:
        """Merge changelog sections intelligently"""
        # SAFETY: If new content is empty or "NO_CHANGES", preserve existing
        if not new or new == "NO_CHANGES":
            return existing
            
        existing_sections = self._parse_sections(existing)
        new_sections = self._parse_sections(new)
        
        # SAFETY: If no new sections were parsed, preserve existing
        if not new_sections:
            print_color(Colors.WARNING, "No new sections found, preserving existing content")
            return existing
        
        # SAFETY: Create a backup of existing sections
        original_existing_sections = {k: list(v) for k, v in existing_sections.items()}
        
        # Only remove N/A entries if we have real content AND the section only contains N/A
        for section, entries in list(existing_sections.items()):
            if section in new_sections and new_sections[section]:
                # Check if ALL existing entries are N/A
                all_na = all(e.strip().endswith('N/A') for e in entries)
                # Check if new entries are not just N/A
                real_new_entries = [e for e in new_sections[section] if not e.strip().endswith('N/A')]
                if all_na and real_new_entries:
                    # Only then remove the N/A entries
                    existing_sections[section] = []
        
        # Merge entries, avoiding duplicates
        merged_any = False
        for section, entries in new_sections.items():
            if section not in existing_sections:
                existing_sections[section] = []
                
            for entry in entries:
                # Skip N/A entries in new content
                if entry.strip().endswith('N/A'):
                    continue
                    
                # Extract core message without attribution for comparison
                core = re.sub(r': \[@.*$', '', entry).strip()
                
                # SAFETY: Skip empty entries
                if not core:
                    continue
                
                # Check if already exists (fuzzy match)
                exists = False
                for existing_entry in existing_sections[section]:
                    existing_core = re.sub(r': \[@.*$', '', existing_entry).strip()
                    
                    # Use fuzzy matching to detect similar entries
                    if self._similar_entries(core, existing_core):
                        exists = True
                        break
                
                if not exists:
                    existing_sections[section].append(entry)
                    merged_any = True
        
        # SAFETY: If nothing was merged and we had existing content, preserve it
        if not merged_any and existing:
            print_color(Colors.INFO, "No new entries to merge, preserving existing content")
            return existing
        
        # Rebuild in canonical order
        result = []
        for section in CHANGELOG_SECTIONS:
            if section in existing_sections and existing_sections[section]:
                # Filter out any remaining N/A entries
                entries = [e for e in existing_sections[section] if not e.strip().endswith('N/A')]
                if entries:
                    result.append(f"### {section}")
                    result.extend(entries)
                    result.append("")  # Blank line
        
        # SAFETY: Final check - if result is empty but we had content, restore original
        if not result and existing:
            print_color(Colors.ERROR, "Merge produced empty result, restoring original sections")
            # Rebuild from original sections
            for section in CHANGELOG_SECTIONS:
                if section in original_existing_sections and original_existing_sections[section]:
                    result.append(f"### {section}")
                    result.extend(original_existing_sections[section])
                    result.append("")
                
        # Join sections and ensure proper formatting
        merged_content = "\n".join(result).strip()
        
        # Ensure content starts with a newline if it has sections
        # This is important for proper spacing after version headers
        if merged_content and merged_content.startswith('###'):
            merged_content = '\n' + merged_content
            
        return merged_content
    
    def _similar_entries(self, entry1: str, entry2: str) -> bool:
        """Check if two changelog entries are similar (enhanced for better duplicate detection)"""
        # Normalize for comparison
        norm1 = entry1.lower().strip()
        norm2 = entry2.lower().strip()
        
        # Remove common words that don't affect meaning
        stop_words = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'and', 'or'}
        
        # Exact match
        if norm1 == norm2:
            return True
        
        # One contains the other (substring match)
        if norm1 in norm2 or norm2 in norm1:
            return True
        
        # Check for common patterns that indicate the same change
        similar_patterns = [
            ('fix', 'fixed', 'fixes', 'fixing', 'resolve', 'resolved', 'resolves'),
            ('add', 'added', 'adds', 'adding', 'new', 'introduce', 'introduced'),
            ('update', 'updated', 'updates', 'updating', 'change', 'changed', 'modify', 'modified'),
            ('remove', 'removed', 'removes', 'removing', 'delete', 'deleted'),
            ('improve', 'improved', 'improves', 'improving', 'enhance', 'enhanced', 'optimize', 'optimized'),
        ]
        
        # Extract meaningful tokens (excluding stop words)
        tokens1 = set(w for w in re.findall(r'\w+', norm1) if w not in stop_words)
        tokens2 = set(w for w in re.findall(r'\w+', norm2) if w not in stop_words)
        
        # Check if entries use synonyms for the same action
        for pattern_group in similar_patterns:
            if any(p in norm1 for p in pattern_group) and any(p in norm2 for p in pattern_group):
                # Both entries are about the same type of change, increase similarity weight
                tokens1.update(['_action_match_'])
                tokens2.update(['_action_match_'])
        
        if len(tokens1) == 0 or len(tokens2) == 0:
            return False
            
        # Jaccard similarity with lower threshold for better duplicate detection
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        similarity = intersection / union if union > 0 else 0
        
        # Lower threshold to catch more potential duplicates
        return similarity > 0.5
    
    def _parse_sections(self, content: str) -> Dict[str, List[str]]:
        """Parse content into sections and entries"""
        sections = {}
        current_section = None
        
        for line in content.splitlines():
            if match := re.match(r'^### (\w+)', line):
                current_section = match.group(1)
                sections[current_section] = []
            elif current_section and line.strip().startswith('-'):
                sections[current_section].append(line)
                
        return sections
    
    def _insert_new_version(self, version: str, date: str, content: str):
        """Insert a new version entry"""
        # Ensure proper spacing between header and content
        if not content.startswith('\n'):
            header = f"## [v{version}] - {date}\n\n{content}"
        else:
            header = f"## [v{version}] - {date}\n{content}"
        
        # Find insertion point - after the main header section
        header_match = re.search(
            r'^(#[^#].*?\n\n(?:.*?\n\n)*?)(?=^## |\Z)',
            self.content,
            flags=re.S | re.M
        )
        
        if header_match:
            insert_pos = header_match.end()
            self.content = (
                self.content[:insert_pos] +
                header + "\n\n" +
                self.content[insert_pos:]
            )
        else:
            # Fallback - append
            self.content += "\n\n" + header
    
    def save(self, backup: bool = True):
        """Save changelog with optional backup"""
        # SAFETY: Never save empty content over existing file
        if self.path.exists() and not self.content.strip():
            print_color(Colors.ERROR, f"Refusing to save empty content to {self.path}")
            print_color(Colors.WARNING, "This would delete all existing changelog content!")
            return
            
        # SAFETY: Check for suspiciously small content
        if self.path.exists():
            existing_size = self.path.stat().st_size
            new_size = len(self.content.encode('utf-8'))
            
            # If new content is less than 10% of original, warn
            if existing_size > 1000 and new_size < existing_size * 0.1:
                print_color(Colors.WARNING, f"New content ({new_size} bytes) is much smaller than existing ({existing_size} bytes)")
                response = input("This might indicate data loss. Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    print_color(Colors.INFO, "Save cancelled")
                    return
        
        if backup and self.path.exists():
            backup_path = self.path.with_suffix('.md.bak')
            shutil.copy2(self.path, backup_path)
            print_color(Colors.INFO, f"Created backup: {backup_path}")
            
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.content.rstrip() + "\n", encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════════════
# LLM Interface
# ═══════════════════════════════════════════════════════════════════════════

class LLMClient:
    """LLM client with retries, caching, and fallbacks"""
    
    def __init__(self, model: str = DEFAULT_MODEL, cache: Optional[CacheManager] = None):
        self.model = model
        self.cache = cache
        self.metrics = AnalysisMetrics()
        
    def prompt(self, prompt_text: str, model_override: Optional[str] = None, 
               use_pro_for_large_context: bool = False) -> Optional[str]:
        """Send prompt to LLM with caching and retries
        
        Args:
            prompt_text: The prompt to send
            model_override: Override the default model
            use_pro_for_large_context: Use Pro model for large context tasks
        """
        # Determine which models to try
        if use_pro_for_large_context:
            models_to_try = [PRO_MODEL] + GEMINI_MODELS
        elif model_override:
            # If Pro model is specified, try it first then fall back to Flash models
            if model_override == PRO_MODEL:
                models_to_try = [PRO_MODEL] + GEMINI_MODELS
            else:
                models_to_try = [model_override] + [m for m in GEMINI_MODELS if m != model_override]
        else:
            models_to_try = GEMINI_MODELS
        
        # Try each model in the fallback chain
        for model_idx, model in enumerate(models_to_try):
            # Check cache first
            cache_key = f"{model}:{prompt_text}"
            if self.cache:
                cached = self.cache.get(cache_key)
                if cached is not None:
                    self.metrics.cache_hits += 1
                    return cached
                self.metrics.cache_misses += 1
            
            self.metrics.llm_calls += 1
            
            # Try with retries for this model
            for attempt in range(MAX_RETRIES):
                try:
                    response = self._call_gemini(prompt_text, model)
                    if response:
                        if self.cache:
                            self.cache.set(cache_key, response)
                        if model_idx > 0:
                            print_color(Colors.YELLOW, f"  Using fallback model: {model}")
                        return response
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                    else:
                        # Log the error for this model
                        print_color(Colors.YELLOW, f"  Model {model} failed: {str(e)}")
                        break  # Try next model
        
        # All Gemini models failed, try OpenAI as last resort
        if os.getenv("OPENAI_API_KEY"):
            try:
                print_color(Colors.YELLOW, "  Falling back to OpenAI...")
                response = self._call_openai(prompt_text)
                if response:
                    # Cache with a special key
                    if self.cache:
                        cache_key = f"openai:{prompt_text}"
                        self.cache.set(cache_key, response)
                    return response
            except Exception as e:
                print_color(Colors.RED, f"  OpenAI also failed: {e}")
        
        print_color(Colors.RED, f"All LLM models failed after trying {len(models_to_try)} Gemini models")
        return None
    
    def _call_gemini(self, prompt_text: str, model: str) -> str:
        """Call Gemini CLI"""
        code, out, err = GitOps.run_command(
            ['gemini-cli', 'prompt', '-', '--model', model],
            input=prompt_text,
            timeout=LLM_TIMEOUT
        )
        
        if code == 0:
            return out.strip()
        
        raise RuntimeError(f"Gemini error: {err}")
    
    def _call_openai(self, prompt_text: str) -> str:
        """Call OpenAI API as fallback"""
        try:
            import openai
            openai.api_key = os.getenv("OPENAI_API_KEY")
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt_text}],
                timeout=LLM_TIMEOUT
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"OpenAI error: {e}")

# ═══════════════════════════════════════════════════════════════════════════
# Commit Context Analysis
# ═══════════════════════════════════════════════════════════════════════════

class CommitContextAnalyzer:
    """Analyzes commit messages to extract rich context for changelog generation"""
    
    def __init__(self, cache: Optional[CacheManager] = None):
        self.cache = cache
        self.llm = LLMClient(cache=cache)
    
    def analyze_commits(self, commits: List[GitCommit], package: str) -> str:
        """Analyze commit messages and generate detailed context"""
        if not commits:
            return ""
            
        # Group commits for efficient analysis
        commit_batches = self._batch_commits(commits, batch_size=20)
        
        all_analyses = []
        progress = ProgressTracker(len(commit_batches), f"Analyzing {package} commits")
        
        for batch in commit_batches:
            analysis = self._analyze_batch(batch, package)
            if analysis:
                all_analyses.append(analysis)
            progress.update()
        
        progress.close()
        
        # Synthesize all analyses into comprehensive context
        return self._synthesize_context(all_analyses, package)
    
    def _analyze_batch(self, commits: List[GitCommit], package: str) -> Optional[str]:
        """Analyze a batch of commits"""
        prompt = self._build_analysis_prompt(commits, package)
        
        # Use Flash model for speed
        response = self.llm.prompt(prompt, model_override=FLASH_MODEL)
        return response
    
    def _build_analysis_prompt(self, commits: List[GitCommit], package: str) -> str:
        """Build prompt for commit analysis"""
        package_info = PACKAGES.get(package, {})
        package_name = package_info.get('name', package)
        
        prompt_parts = [
            f"You are analyzing commit messages for the {package_name} package.",
            "Extract detailed context that will help generate accurate changelog entries.",
            "",
            "COMMITS TO ANALYZE:",
            ""
        ]
        
        # Add full commit messages
        for commit in commits:
            prompt_parts.extend([
                f"Commit {commit.short_hash} by {commit.author_name}:",
                f"Date: {commit.commit_date} {commit.commit_time}",
                f"Files changed: {len(commit.files)}",
                "Message:",
                "```",
                commit.message,
                "```",
                ""
            ])
        
        prompt_parts.extend([
            "ANALYZE AND EXTRACT:",
            "1. PRIMARY PURPOSE: What is the main goal of each commit?",
            "2. USER IMPACT: How do these changes affect end users?",
            "3. TECHNICAL DETAILS: Key implementation details or architectural changes",
            "4. BREAKING CHANGES: Any backwards compatibility issues and migration steps",
            "5. PERFORMANCE: Performance implications (improvements or regressions)",
            "6. DEPENDENCIES: Changes to dependencies or requirements",
            "7. RELATED ISSUES: Issue numbers, bug reports, feature requests",
            "8. TESTING: Test coverage changes or testing considerations",
            "9. DOCUMENTATION: Documentation updates needed or included",
            "10. FUTURE WORK: Any TODOs, follow-up work mentioned",
            "11. CONTEXT: Why were these changes necessary? What problem do they solve?",
            "12. PATTERNS: Common themes across multiple commits",
            "",
            "Provide a structured analysis that captures the essence and impact of these changes.",
            "Focus on information that would be valuable in a changelog."
        ])
        
        return "\n".join(prompt_parts)
    
    def _synthesize_context(self, analyses: List[str], package: str) -> str:
        """Synthesize multiple analyses into comprehensive context"""
        if not analyses:
            return ""
        
        if len(analyses) == 1:
            return analyses[0]
        
        # Use LLM to synthesize multiple analyses
        synthesis_prompt = f"""You are synthesizing multiple commit analyses for the {package} package.

INDIVIDUAL ANALYSES:
{"="*50}
{("="*50 + "\n").join(analyses)}
{"="*50}

SYNTHESIZE INTO:
1. OVERVIEW: High-level summary of all changes
2. KEY THEMES: Major patterns and themes across commits
3. USER IMPACT: Combined effect on end users
4. TECHNICAL HIGHLIGHTS: Most important technical changes
5. BREAKING CHANGES: Consolidated list with migration guidance
6. PERFORMANCE: Overall performance impact
7. DEPENDENCIES: All dependency changes
8. ISSUES RESOLVED: Complete list of resolved issues
9. FUTURE CONSIDERATIONS: Combined TODOs and follow-up work

Create a cohesive narrative that captures the full scope of changes."""

        # Use Pro model for synthesis of large context
        response = self.llm.prompt(synthesis_prompt, use_pro_for_large_context=True)
        return response or ""
    
    def _batch_commits(self, commits: List[GitCommit], batch_size: int) -> List[List[GitCommit]]:
        """Batch commits to avoid token limits"""
        batches = []
        current_batch = []
        current_size = 0
        
        for commit in commits:
            commit_size = len(commit.message) + 200  # Extra for metadata
            
            if current_batch and current_size + commit_size > 8000:  # Leave room for prompt
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            
            current_batch.append(commit)
            current_size += commit_size
        
        if current_batch:
            batches.append(current_batch)
        
        return batches

# ═══════════════════════════════════════════════════════════════════════════
# Enhanced File Analysis
# ═══════════════════════════════════════════════════════════════════════════

class FileAnalyzer:
    """Analyzes files for changelog context with caching"""
    
    def __init__(self, package: str, commits: List[GitCommit], cache: Optional[CacheManager] = None,
                 include_gitignored: bool = False):
        self.package = package
        self.commits = commits
        self.cache = cache
        self.include_gitignored = include_gitignored
        self.llm = LLMClient(cache=cache)
        
    def analyze_files(self, version: str) -> Tuple[List[str], str]:
        """Analyze files and return selected files + context"""
        # Gather all changed files
        all_files = set()
        for commit in self.commits:
            pattern = PACKAGES[self.package]["path_pattern"]
            exclude_patterns = PACKAGES[self.package].get("exclude_patterns", [])
            
            for file in commit.files:
                if re.match(pattern, file):
                    # Check exclusions
                    excluded = any(re.match(exc, file) for exc in exclude_patterns)
                    if not excluded:
                        # Also check if file is gitignored
                        if self.include_gitignored or not GitOps.is_gitignored(file):
                            all_files.add(file)
                        else:
                            # Log that we're skipping a gitignored file
                            if os.getenv('DEBUG'):
                                print_color(Colors.GRAY, f"  Skipping gitignored file: {file}")
        
        if not all_files:
            return [], ""
        
        # Prioritize files by importance
        prioritized_files = self._prioritize_files(list(all_files))
        
        # Build file inventory
        inventory = self._build_file_inventory(prioritized_files[:MAX_FILES_PER_PACKAGE], version)
        
        # Use Flash model for file selection
        selected = self._select_relevant_files(inventory)
        
        return selected, inventory
    
    def _prioritize_files(self, files: List[str]) -> List[str]:
        """Prioritize files by importance"""
        priority_scores = {}
        
        for file in files:
            score = 0
            
            # Root-level important files (for root package)
            if self.package == "root":
                if file in ['.gitignore', '.github/workflows', 'LICENSE', 'README.md']:
                    score += 9
                elif file.startswith('.github/'):
                    score += 7
                elif file == 'pubspec.yaml' or file == 'Cargo.toml':
                    score += 8
                elif file.startswith('tooling/'):
                    score += 6
                elif file.endswith(('.yml', '.yaml', '.json')) and '/' not in file:
                    score += 5
            
            # Public API files
            if 'lib/' in file and not 'src/' in file:
                score += 10
            
            # Test files (indicate what was changed)
            if 'test/' in file:
                score += 5
                
            # Configuration files
            if file.endswith(('pubspec.yaml', 'Cargo.toml', 'package.json')):
                score += 8
                
            # Documentation
            if file.endswith(('.md', '.rst', '.txt')) and 'README' in file:
                score += 7
                
            # Source files
            if file.endswith(('.dart', '.rs', '.py', '.js', '.ts')):
                score += 3
                
            # Example files
            if 'example/' in file:
                score += 2
                
            priority_scores[file] = score
        
        # Sort by score (descending) and then by name
        return sorted(files, key=lambda f: (-priority_scores[f], f))
    
    def _build_file_inventory(self, files: List[str], version: str) -> str:
        """Build comprehensive file inventory"""
        inventory = [
            f"FILE INVENTORY FOR AI ANALYSIS:",
            f"Package: {self.package}",
            f"Version: {version}",
            f"Files to analyze: {len(files)}",
            ""
        ]
        
        total_bytes = 0
        for i, file in enumerate(files, 1):
            if total_bytes > MAX_TOTAL_BYTES:
                inventory.append(f"[Reached size limit, {len(files) - i + 1} files skipped]")
                break
                
            inventory.append(f"{'=' * 20} FILE {i}: {file} {'=' * 20}")
            
            # Get file metadata
            if os.path.exists(file):
                size = os.path.getsize(file)
                inventory.append(f"Size: {size} bytes")
                total_bytes += size
                
                # File type analysis
                file_type = self._analyze_file_type(file)
                if file_type:
                    inventory.append(f"Type: {file_type}")
                
                # Recent commits
                commits_code, commits_out, _ = GitOps.run_command([
                    'git', 'log', '--oneline', '-n', '5', '--', file
                ])
                if commits_code == 0:
                    inventory.append("Recent commits:")
                    inventory.extend(f"  {line}" for line in commits_out.splitlines())
                
                # File content preview
                inventory.append("\n--- CONTENT PREVIEW ---")
                content = GitOps.get_file_content(file, MAX_FILE_SIZE_BYTES)
                inventory.append(content)
                
                # Changes in commits
                inventory.append("\n--- CHANGES ---")
                for j, commit in enumerate(self.commits[:3]):
                    diff_code, diff_out, _ = GitOps.run_command([
                        'git', 'show', commit.hash, '--', file
                    ])
                    if diff_code == 0 and diff_out:
                        inventory.append(f"Commit {commit.short_hash}:")
                        inventory.append(diff_out[:1000])  # Limit diff size
                        
            else:
                inventory.append("[File no longer exists]")
                
            inventory.append("")
            
        return "\n".join(inventory)
    
    def _analyze_file_type(self, file_path: str) -> Optional[str]:
        """Analyze and categorize file type"""
        path = pathlib.Path(file_path)
        
        # Check by extension
        ext_map = {
            '.dart': 'Dart source',
            '.rs': 'Rust source',
            '.py': 'Python source',
            '.js': 'JavaScript source',
            '.ts': 'TypeScript source',
            '.yaml': 'YAML configuration',
            '.toml': 'TOML configuration',
            '.json': 'JSON data',
            '.md': 'Markdown documentation',
        }
        
        if path.suffix in ext_map:
            return ext_map[path.suffix]
            
        # Check by path patterns
        if 'test/' in str(path):
            return 'Test file'
        elif 'lib/' in str(path):
            return 'Library source'
        elif 'example/' in str(path):
            return 'Example code'
        elif 'doc/' in str(path) or 'docs/' in str(path):
            return 'Documentation'
            
        return None
    
    def _select_relevant_files(self, inventory: str) -> List[str]:
        """Use LLM to select relevant files"""
        package_context = ""
        if self.package == "root":
            package_context = """
This is the root/top-level package. Focus on:
- Project-wide configuration changes
- CI/CD and workflow changes
- Documentation updates
- Tooling and build system changes
- License or legal changes
"""
        else:
            package_info = PACKAGES.get(self.package, {})
            package_desc = package_info.get('description', f'the {self.package} package')
            package_context = f"This is {package_desc}."
            
        prompt = f"""You are analyzing file changes for changelog generation.
{package_context}

{inventory}

SELECTION CRITERIA:
- Files with significant functional changes
- Files affecting the public API
- Bug fixes or new features
- Relevant test files
- Skip minor changes (formatting, comments, refactoring)
- Prioritize user-visible changes

OUTPUT: List ONLY file paths, one per line. Max 20 files.
If no significant changes, output: NO_SIGNIFICANT_CHANGES"""

        response = self.llm.prompt(prompt, model_override=FLASH_MODEL)
        
        if not response or response == "NO_SIGNIFICANT_CHANGES":
            return []
            
        return [f.strip() for f in response.splitlines() if f.strip()]

# ═══════════════════════════════════════════════════════════════════════════
# Enhanced File Analysis with Diff Analysis
# ═══════════════════════════════════════════════════════════════════════════

class EnhancedFileAnalyzer(FileAnalyzer):
    """Analyzes files and diffs with LLM assistance"""
    
    def analyze_files_with_diffs(self, version: str) -> Tuple[List[str], str, str]:
        """Analyze files and generate both inventory and diff analysis"""
        selected_files, inventory = self.analyze_files(version)
        
        if not selected_files:
            return [], "", ""
        
        # Generate detailed diff analysis
        diff_analysis = self._analyze_diffs(selected_files)
        
        return selected_files, inventory, diff_analysis
    
    def _analyze_diffs(self, files: List[str]) -> str:
        """Use LLM to analyze diffs and extract insights"""
        diff_batches = self._collect_diffs(files)
        
        if not diff_batches:
            return ""
        
        analyses = []
        progress = ProgressTracker(len(diff_batches), f"Analyzing {self.package} diffs")
        
        for batch in diff_batches:
            analysis = self._analyze_diff_batch(batch)
            if analysis:
                analyses.append(analysis)
            progress.update()
        
        progress.close()
        
        return "\n\n".join(analyses)
    
    def _collect_diffs(self, files: List[str]) -> List[Dict[str, str]]:
        """Collect diffs for files"""
        batches = []
        current_batch = {}
        current_size = 0
        
        for file in files[:20]:  # Limit files
            # Get diff for this file across all commits
            diff_cmd = ['git', 'diff', '--unified=5']
            
            # Add commit range
            if self.commits:
                first_commit = self.commits[-1].hash
                last_commit = self.commits[0].hash
                diff_cmd.append(f"{first_commit}~1..{last_commit}")
            
            diff_cmd.extend(['--', file])
            
            code, diff_out, _ = GitOps.run_command(diff_cmd)
            
            if code == 0 and diff_out:
                diff_size = len(diff_out)
                
                if current_batch and current_size + diff_size > 10000:
                    batches.append(current_batch)
                    current_batch = {}
                    current_size = 0
                
                current_batch[file] = diff_out[:5000]  # Truncate large diffs
                current_size += len(current_batch[file])
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _analyze_diff_batch(self, diffs: Dict[str, str]) -> Optional[str]:
        """Analyze a batch of diffs"""
        prompt = f"""You are analyzing code diffs for the {self.package} package.

FILE DIFFS:
"""
        for file, diff in diffs.items():
            prompt += f"\n{'='*60}\nFILE: {file}\n{'='*60}\n{diff}\n"
        
        prompt += """
ANALYZE THE DIFFS AND EXTRACT:
1. API CHANGES: New/modified/removed public APIs
2. BEHAVIOR CHANGES: How the code behavior has changed
3. BUG FIXES: Specific bugs that were fixed
4. PERFORMANCE: Performance optimizations or potential regressions
5. REFACTORING: Code structure improvements
6. NEW FEATURES: New functionality added
7. BREAKING CHANGES: Any backwards incompatible changes
8. DEPENDENCIES: Changes in imports or dependencies
9. ERROR HANDLING: Improvements or changes to error handling
10. EDGE CASES: New edge cases handled or potential issues

Focus on changes that would be important for users of this library."""

        response = self.llm.prompt(prompt, model_override=FLASH_MODEL)
        return response

# ═══════════════════════════════════════════════════════════════════════════
# Enhanced Changelog Generator
# ═══════════════════════════════════════════════════════════════════════════

class ChangelogGenerator:
    """Generates changelog entries using LLM with conventional commit support"""
    
    def __init__(self, package: str, version: str, cache: Optional[CacheManager] = None):
        self.package = package
        self.version = version
        self.cache = cache
        self.llm = LLMClient(cache=cache)
        self.remote_url = GitOps.get_remote_url()
        
    def generate(self, commits: List[GitCommit], selected_files: List[str], 
                 context: str, existing_content: str, version_context: str = "") -> str:
        """Generate changelog entries"""
        if not commits:
            return "NO_CHANGES"
        
        # Try intelligent generation first
        prompt = self._build_prompt(commits, selected_files, context, existing_content, version_context)
        
        # Determine if we need Pro model for large context
        prompt_size = len(prompt)
        use_pro = prompt_size > 50000  # Use Pro for prompts over 50KB
        
        # Safety check for very large existing content
        if existing_content and len(existing_content) > 10000:
            print_color(Colors.WARNING, f"  Large existing content ({len(existing_content):,} chars) - using Pro model")
            use_pro = True
        
        if use_pro:
            print_color(Colors.INFO, f"  Using Pro model for large context ({prompt_size:,} chars)")
            response = self.llm.prompt(prompt, use_pro_for_large_context=True)
        else:
            # Use Flash by default for speed
            response = self.llm.prompt(prompt)
        
        if response and response != "ERROR":
            # Clean up the response before returning
            return self._clean_llm_response(response)
            
        # Fallback to conventional commit based generation
        return self._generate_from_conventional(commits)
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean up LLM response by removing code blocks and redundant headers"""
        if not response:
            return response
            
        # SAFETY: Store original length to detect if we accidentally empty the response
        original_length = len(response)
        
        # Remove wrapping markdown code blocks (but not internal ones)
        # Check if the entire response is wrapped in code blocks
        lines = response.split('\n')
        if lines and lines[0].strip().startswith('```'):
            # Find the matching closing code block at the end
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == '```':
                    # Remove first and last code block markers
                    if lines[0].strip() in ['```', '```markdown', '```changelog']:
                        lines = lines[1:i]
                        response = '\n'.join(lines)
                    break
        
        # Remove redundant version headers
        # Pattern: ## v0.0.1 or ## vector_search v0.0.1 (without date)
        package_name = PACKAGES[self.package]["name"]
        patterns_to_remove = [
            rf'^## v?{re.escape(self.version)}\s*$',  # ## v0.0.1 or ## 0.0.1
            rf'^## {re.escape(package_name)} v?{re.escape(self.version)}\s*$',  # ## vector_search v0.0.1
            rf'^# Changelog\s*$',  # Remove any # Changelog headers
            rf'^All notable changes.*$',  # Remove changelog description lines
            rf'^The format is based on.*$',
            rf'^and this project adheres.*$'
        ]
        
        for pattern in patterns_to_remove:
            response = re.sub(pattern, '', response, flags=re.MULTILINE)
        
        # Clean up multiple consecutive blank lines
        response = re.sub(r'\n{3,}', '\n\n', response)
        
        # Trim whitespace
        response = response.strip()
        
        # SAFETY: If we accidentally removed everything, return "NO_CHANGES"
        if original_length > 100 and len(response) < 10:
            print_color(Colors.ERROR, f"Cleaning removed too much content ({original_length} -> {len(response)} chars)")
            return "NO_CHANGES"
        
        return response
    
    def _build_prompt(self, commits: List[GitCommit], selected_files: List[str],
                      context: str, existing_content: str, version_context: str = "") -> str:
        """Build comprehensive prompt for changelog generation"""
        package_name = PACKAGES[self.package]["name"]
        
        # Customize description based on package
        if self.package == "root":
            package_desc = "This is the root/top-level changelog covering project-wide changes, tooling, CI/CD, and documentation."
        else:
            package_info = PACKAGES.get(self.package, {})
            package_desc = f"This is {package_info.get('description', f'the {self.package} package')}."
        
        # Group commits by type if they follow conventional format
        conventional_groups = self._group_conventional_commits(commits)
        
        prompt_parts = [
            f"You are a changelog analyst for {package_name} (version v{self.version}).",
            package_desc,
            "",
            "IMPORTANT FILES WITH CHANGES:",
            "\n".join(f"- {f}" for f in selected_files[:20]),  # Limit to prevent prompt overflow
            "",
        ]
        
        # Add conventional commit summary if available
        if conventional_groups:
            prompt_parts.extend([
                "CONVENTIONAL COMMIT SUMMARY:",
                self._format_conventional_summary(conventional_groups),
                ""
            ])
        
        # Add version history context if available
        if version_context:
            prompt_parts.extend([
                "PREVIOUS VERSION CONTEXT:",
                "This shows what changed in recent versions to maintain continuity:",
                version_context,
                ""
            ])
        
        prompt_parts.extend([
            "CRITICAL INSTRUCTIONS:",
            "1. **NET ADDITIVE ONLY**: The existing entries above show what's ALREADY in the changelog",
            "2. ONLY generate entries for commits that are NOT already documented in existing entries",
            "3. DO NOT repeat or regenerate any existing entries - they will be preserved automatically",
            "4. Include attribution: [@user](link), date, time, [hash](link)[, PR [#](link)]", 
            "5. Focus on user-visible changes from NEW commits only",
            "6. Group by STANDARD sections ONLY: Added, Changed, Deprecated, Removed, Fixed, Security",
            "7. Keep descriptions concise but informative",
            "8. Mark BREAKING CHANGES clearly",
            "9. DO NOT create custom section names like '### v0.0.3' - use standard sections only",
            "10. Each entry MUST have proper attribution format",
            "11. ONLY include sections that have actual changes - omit empty sections entirely",
            "12. NEVER write placeholder entries like '- N/A' or '- None'",
            "",
            "**REDUNDANCY PREVENTION:**",
            "13. Before adding ANY entry, check if the same change is already documented",
            "14. Look for semantic similarity, not just exact matches:",
            "    - 'Fixed memory leak' = 'Memory leak fix' = 'Resolved memory issue'",
            "    - 'Added new API' = 'New API added' = 'Introduced new API'",
            "15. If a commit just refines/continues existing work, don't create a new entry",
            "16. Minor updates to already-documented features should be skipped",
            "17. **IMPORTANT**: If ALL commits are already covered by existing entries, return: NO_CHANGES",
            "18. **RETURNING NOTHING IS PERFECTLY FINE** - better to add nothing than duplicate",
            "",
            "**FORMAT RULES:**",
            "19. DO NOT wrap your entire response in markdown code blocks (no ``` around everything)",
            "20. DO NOT include version headers like '## v0.0.1' or '## vector_search v0.0.1'",
            "21. Start directly with ### Section headers (Added, Changed, etc.)",
            "22. You MAY use inline code blocks `like this` or code blocks within entries for examples",
            ""
        ])
        
        # Add commits with attribution (limit to prevent prompt overflow)
        prompt_parts.append("COMMITS:")
        for commit in commits[:DEFAULT_MAX_COMMITS]:
            attribution = commit.get_attribution(self.remote_url or "")
            prefix = "BREAKING: " if commit.conventional and commit.conventional.breaking else ""
            prompt_parts.append(f"- {prefix}{commit.message.splitlines()[0]}: {attribution}")
            
        if len(commits) > DEFAULT_MAX_COMMITS:
            prompt_parts.append(f"[... and {len(commits) - DEFAULT_MAX_COMMITS} more commits]")
        prompt_parts.append("")
        
        # Add existing content if any
        if existing_content:
            prompt_parts.extend([
                "EXISTING ENTRIES (MUST PRESERVE):",
                "=" * 40,
                existing_content,  # Pass full content - no truncation
                "=" * 40,
                ""
            ])
        
        # Add output format
        prompt_parts.extend([
            "OUTPUT FORMAT (NO WRAPPING CODE BLOCKS!):",
            "### Section",
            "- Description: [@user](link), YYYY-MM-DD, H:MM[AM/PM] TZ, [hash](link)",
            "",
            "EXAMPLE OUTPUT (this is what you should return, no wrapping code blocks):",
            "### Added",
            "- New vector search algorithm for improved performance: [@username](https://github.com/username), 2024-01-15, 10:30AM PST, [abc123](https://github.com/repo/commit/abc123)",
            "- Added `searchWithOptions()` method for advanced queries: [@dev](https://github.com/dev), 2024-01-16, 9:00AM PST, [def456](https://github.com/repo/commit/def456)",
            "",
            "### Fixed", 
            "- Memory leak when processing large datasets: [@otheruser](https://github.com/otheruser), 2024-01-15, 2:45PM PST, [def456](https://github.com/repo/commit/def456), PR [#42](https://github.com/repo/pull/42)",
            "",
            "For breaking changes, prefix with **BREAKING:**",
            "",
            "REDUNDANCY EXAMPLE - DO NOT ADD THESE:",
            "If existing entries contain:",
            "- Fixed memory leak in vector processing",
            "- Added new search API with filtering",
            "",
            "Then SKIP commits like:",
            "- 'fix: additional memory leak fix' (follow-up to existing)",
            "- 'chore: cleanup search API code' (internal change)",
            "- 'docs: update search API docs' (minor update)",
            "- 'fix: typo in search method' (too minor)",
            "",
            "REMEMBER:",
            "- NO wrapping markdown code blocks around your response (no ``` at start/end)",
            "- NO version headers (no ## v0.0.1)",
            "- Start directly with ### Section",
            "- Internal code examples are OK: `code` or ```language...```",
            "- Only include sections with entries",
            "- If no NEW changes to add, output: NO_CHANGES",
            "- **IT'S OKAY TO RETURN NO_CHANGES** - this is expected in smart mode!"
        ])
        
        return "\n".join(prompt_parts)
    
    def _group_conventional_commits(self, commits: List[GitCommit]) -> Dict[str, List[GitCommit]]:
        """Group commits by conventional type"""
        groups = defaultdict(list)
        
        for commit in commits:
            if commit.conventional:
                commit_type = commit.conventional.type
                if commit_type in CONVENTIONAL_TYPES:
                    section = CONVENTIONAL_TYPES[commit_type]
                    groups[section].append(commit)
                else:
                    groups["Changed"].append(commit)
        
        return dict(groups)
    
    def _format_conventional_summary(self, groups: Dict[str, List[GitCommit]]) -> str:
        """Format conventional commit groups for prompt"""
        lines = []
        for section, commits in groups.items():
            lines.append(f"{section}: {len(commits)} commits")
            
            # Count breaking changes
            breaking = sum(1 for c in commits if c.conventional and c.conventional.breaking)
            if breaking > 0:
                lines.append(f"  - {breaking} BREAKING CHANGES")
                
        return "\n".join(lines)
    
    def _generate_from_conventional(self, commits: List[GitCommit]) -> str:
        """Generate changelog from conventional commits"""
        sections = defaultdict(list)
        
        for commit in commits:
            attribution = commit.get_attribution(self.remote_url or "")
            
            if commit.conventional:
                # Use conventional commit data
                section = CONVENTIONAL_TYPES.get(commit.conventional.type, "Changed")
                description = commit.conventional.description
                
                if commit.conventional.breaking:
                    description = f"**BREAKING:** {description}"
                    
                if commit.conventional.scope:
                    description = f"{description} ({commit.conventional.scope})"
                    
            else:
                # Fallback to simple categorization
                msg_lower = commit.message.lower()
                
                if any(word in msg_lower for word in ['add', 'new', 'feature']):
                    section = "Added"
                elif any(word in msg_lower for word in ['fix', 'bug', 'error']):
                    section = "Fixed"
                elif any(word in msg_lower for word in ['remove', 'delete']):
                    section = "Removed"
                elif any(word in msg_lower for word in ['deprecat']):
                    section = "Deprecated"
                elif any(word in msg_lower for word in ['security', 'vulnerability']):
                    section = "Security"
                else:
                    section = "Changed"
                    
                description = commit.message.splitlines()[0]
                
            sections[section].append(f"- {description}: {attribution}")
        
        # Build output
        result = []
        for section in CHANGELOG_SECTIONS:
            if section in sections:
                result.append(f"### {section}")
                result.extend(sections[section])
                result.append("")
                
        return "\n".join(result) if result else "NO_CHANGES"

# ═══════════════════════════════════════════════════════════════════════════
# Enhanced Changelog Generator with Commit Context
# ═══════════════════════════════════════════════════════════════════════════

class EnhancedChangelogGenerator(ChangelogGenerator):
    """Generates changelog entries using comprehensive context from commit analysis"""
    
    def __init__(self, package: str, version: str, cache: Optional[CacheManager] = None,
                 use_enhanced_analysis: bool = True):
        super().__init__(package, version, cache)
        self.use_enhanced_analysis = use_enhanced_analysis
    
    def generate(self, commits: List[GitCommit], selected_files: List[str], 
                 context: str, existing_content: str, version_context: str = "") -> str:
        """Generate changelog entries with enhanced context"""
        
        # If enhanced analysis is disabled, use parent implementation
        if not self.use_enhanced_analysis:
            return super().generate(commits, selected_files, context, existing_content, version_context)
        
        if not commits:
            return "NO_CHANGES"
        
        print_color(Colors.INFO, f"  Using enhanced analysis for {self.package}")
        
        # Step 1: Analyze commit messages
        commit_analyzer = CommitContextAnalyzer(cache=self.cache)
        commit_context = commit_analyzer.analyze_commits(commits, self.package)
        
        # Step 2: Analyze file changes and diffs
        file_analyzer = EnhancedFileAnalyzer(self.package, commits, cache=self.cache, 
                                           include_gitignored=False)
        selected_files_enhanced, file_inventory, diff_analysis = file_analyzer.analyze_files_with_diffs(self.version)
        
        # Use enhanced selected files if available, otherwise use provided ones
        if selected_files_enhanced:
            selected_files = selected_files_enhanced
        
        # Step 3: Build comprehensive prompt with all context
        prompt = self._build_enhanced_prompt(
            commits=commits,
            commit_context=commit_context,
            file_inventory=file_inventory,
            diff_analysis=diff_analysis,
            existing_content=existing_content,
            version_context=version_context,
            selected_files=selected_files
        )
        
        # Step 4: Generate changelog with appropriate model
        prompt_size = len(prompt)
        if prompt_size > 50000:
            print_color(Colors.INFO, f"  Using Pro model for large context ({prompt_size:,} chars)")
            response = self.llm.prompt(prompt, use_pro_for_large_context=True)
        else:
            response = self.llm.prompt(prompt)
        
        if response and response != "ERROR":
            # Clean up the response using parent's method
            return self._clean_llm_response(response)
        
        # Fallback to conventional generation
        print_color(Colors.WARNING, f"  Enhanced generation failed, falling back to conventional")
        return self._generate_from_conventional(commits)
    
    def _build_enhanced_prompt(self, commits: List[GitCommit], commit_context: str,
                               file_inventory: str, diff_analysis: str,
                               existing_content: str, version_context: str,
                               selected_files: List[str]) -> str:
        """Build comprehensive prompt with all context"""
        
        package_name = PACKAGES[self.package]["name"]
        package_desc = PACKAGES[self.package].get("description", "this package")
        
        prompt_parts = [
            f"You are generating a changelog for {package_name} version v{self.version}.",
            f"This is {package_desc}.",
            "",
            "COMPREHENSIVE COMMIT ANALYSIS:",
            "="*60,
            commit_context[:15000],  # Limit to prevent overflow
            "="*60,
            ""
        ]
        
        if diff_analysis:
            prompt_parts.extend([
                "DIFF ANALYSIS:",
                "="*60,
                diff_analysis[:10000],  # Limit to prevent overflow
                "="*60,
                ""
            ])
        
        prompt_parts.extend([
            "FILE CHANGES SUMMARY:",
            f"Total files changed: {len(selected_files)}",
            "Key files:",
            "\n".join(f"- {f}" for f in selected_files[:20]),
            ""
        ])
        
        # Add version history context if available
        if version_context:
            prompt_parts.extend([
                "PREVIOUS VERSION CONTEXT:",
                "This shows what changed in recent versions to maintain continuity:",
                version_context,  # Pass full content - no truncation
                ""
            ])
        
        # Add commit list for attribution
        prompt_parts.extend([
            "COMMITS FOR ATTRIBUTION:",
            "(Use these for proper attribution in changelog entries)"
        ])
        
        for commit in commits[:50]:
            attribution = commit.get_attribution(self.remote_url or "")
            prefix = "BREAKING: " if commit.conventional and commit.conventional.breaking else ""
            prompt_parts.append(f"- {commit.short_hash}: {prefix}{commit.message.splitlines()[0]}: {attribution}")
        
        if len(commits) > 50:
            prompt_parts.append(f"[... and {len(commits) - 50} more commits]")
        
        if existing_content:
            prompt_parts.extend([
                "",
                "EXISTING CHANGELOG ENTRIES (PRESERVE THESE):",
                "="*60,
                existing_content,  # Pass full content - no truncation
                "="*60
            ])
        
        prompt_parts.extend([
            "",
            "CHANGELOG GENERATION INSTRUCTIONS:",
            "Based on the comprehensive analysis above:",
            "1. Create detailed, accurate changelog entries that capture the full impact",
            "2. Group by standard sections: Added, Changed, Deprecated, Removed, Fixed, Security",
            "3. Each entry MUST have proper attribution from the commit list",
            "4. Focus on user impact as revealed by the analysis",
            "5. Highlight breaking changes with **BREAKING:** prefix",
            "6. Include migration guidance for breaking changes",
            "7. Reference issue numbers where identified in the analysis",
            "8. Be specific about performance impacts mentioned in the analysis",
            "9. Note dependency changes identified",
            "10. **NET ADDITIVE**: Preserve ALL existing entries - only add NEW entries for undocumented commits",
            "",
            "**REDUNDANCY PREVENTION (CRITICAL):**",
            "11. Carefully check EVERY commit against existing entries before adding",
            "12. Look for semantic duplicates - same feature described differently:",
            "    - Performance improvements = optimization = speed enhancements",
            "    - Bug fixes = issue resolution = problem solved",
            "13. Skip commits that are:",
            "    - Follow-up fixes to already documented changes",
            "    - Minor tweaks or refinements",
            "    - Internal changes with no user impact",
            "14. **IMPORTANT**: It's BETTER to return NO_CHANGES than add duplicates",
            "15. If unsure whether something is already covered, ERR ON THE SIDE OF NOT ADDING IT",
            "",
            "**FORMAT RULES:**",
            "16. DO NOT wrap your entire response in markdown code blocks (no ``` around everything)",
            "17. DO NOT include version headers like '## v0.0.1' or '## vector_search v0.0.1'",
            "18. Start directly with ### Section headers (Added, Changed, etc.)",
            "19. You MAY use inline code `like this` or code blocks within entries for examples",
            "",
            "FORMAT (NO WRAPPING CODE BLOCKS!):",
            "### Section",
            "- Clear description of change: [@user](link), YYYY-MM-DD, time, [hash](link)[, PR #]",
            "",
            "REMEMBER:",
            "- NO wrapping markdown code blocks around your response (no ``` at start/end)",
            "- NO version headers",
            "- Start directly with ### Section",
            "- Internal code examples are OK: `code` or ```language...```",
            "- Generate comprehensive changelog entries that reflect the deep analysis above."
        ])
        
        return "\n".join(prompt_parts)

# ═══════════════════════════════════════════════════════════════════════════
# Main Sync Engine
# ═══════════════════════════════════════════════════════════════════════════

class ChangelogSync:
    """Main changelog synchronization engine with enhanced features"""
    
    def __init__(self, mode: AnalysisMode, version: Optional[str] = None, 
                 since: Optional[str] = None, max_commits: int = DEFAULT_MAX_COMMITS,
                 dry_run: bool = False, config: Optional[Config] = None,
                 workers: int = MAX_WORKERS, batch_size: int = BATCH_SIZE,
                 include_gitignored: bool = False, force: bool = False,
                 keep_backups: bool = False, no_cleanup: bool = False,
                 no_commit: bool = False):
        self.mode = mode
        self.version = version
        self.since = since
        self.max_commits = max_commits
        self.dry_run = dry_run
        self.config = config or Config()
        self.workers = workers
        self.batch_size = batch_size
        self.include_gitignored = include_gitignored
        self.force = force
        self.keep_backups = keep_backups
        self.no_cleanup = no_cleanup
        self.no_commit = no_commit
        self.remote_url = GitOps.get_remote_url()
        self.current_branch = GitOps.get_current_branch()
        self.cache = CacheManager()
        self.metrics = AnalysisMetrics()
        self.start_time = time.time()
        # Track version history for context between tags
        self.version_history = {pkg: [] for pkg in PACKAGES}
        # Track all processed commits for final cleanup
        self.all_commits = []
        # Track if we're using auto workers
        self.auto_workers = (workers == -1)
    
    def run(self):
        """Main execution"""
        print_header(f"Changelog Sync v{VERSION}")
        print_color(Colors.INFO, f"Mode: {self.mode.value}")
        print_color(Colors.INFO, f"Branch: {self.current_branch}")
        if self.remote_url:
            print_color(Colors.INFO, f"Repository: {self.remote_url}")
        if self.dry_run:
            print_color(Colors.WARNING, "DRY RUN - No files will be modified")
        print()
        
        # Check prerequisites
        if not self._check_prerequisites():
            sys.exit(1)
        
        # Check for uncommitted changes
        if GitOps.is_dirty() and not self.dry_run:
            print_color(Colors.WARNING, "Warning: Working directory has uncommitted changes")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                print_color(Colors.INFO, "Aborting")
                sys.exit(0)
        
        # Get version to work with
        if not self.version:
            self.version = self._get_current_version()
            
        print_color(Colors.INFO, f"Working on version: v{self.version}")
        
        # Process based on mode
        if self.mode == AnalysisMode.REBUILD_ALL:
            self._rebuild_all_changelogs()
        elif self.since:
            self._process_since_ref()
        else:
            self._process_current_or_smart()
        
        # Calculate final metrics
        self.metrics.processing_time = time.time() - self.start_time
        
        # Show summary
        print_color(Colors.SUCCESS, "\n✓ Changelog sync complete!")
        
        if self.dry_run:
            print_color(Colors.WARNING, "This was a dry run - no files were modified")
        
        # Show metrics
        self.metrics.print_summary()
        
        # Run final cleanup pass
        if not self.dry_run and not self.no_cleanup:
            self._final_cleanup_pass()
        elif self.no_cleanup:
            print_color(Colors.INFO, "\nSkipping final cleanup pass (--no-cleanup)")
        
        print_color(Colors.INFO, "\nNext steps:")
        print_color(Colors.INFO, "  1. Review generated changelog entries")
        print_color(Colors.INFO, "  2. Make any manual adjustments")
        print_color(Colors.INFO, "  3. Commit the changes")
        
        # Offer to clean up backup files
        if not self.dry_run and not self.keep_backups:
            self._cleanup_backups()
        
        # Generate smart commit message and offer to commit
        if not self.dry_run and not self.no_commit:
            commit_message = self._generate_smart_commit_message()
            if commit_message:
                self._offer_to_commit(commit_message)
    
    def _check_prerequisites(self) -> bool:
        """Check required tools are available"""
        ok = True
        
        # Check git
        code, _, _ = GitOps.run_command(['git', '--version'])
        if code != 0:
            print_color(Colors.ERROR, "Error: git is not installed")
            ok = False
            
        # Check LLM availability
        gemini_code, _, _ = GitOps.run_command(['gemini-cli', '--help'])
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        
        if gemini_code != 0 and not has_openai:
            print_color(Colors.ERROR, "Error: Neither gemini-cli nor OPENAI_API_KEY available")
            print_color(Colors.INFO, "Install gemini-cli or set OPENAI_API_KEY environment variable")
            ok = False
            
        return ok
    
    def _get_current_version(self) -> str:
        """Get current version from tags or changelog"""
        # First, check if we have tags - use the latest tag version
        tags = GitOps.get_all_tags()
        if tags:
            # Get the latest tag version - this is what we should be updating
            latest_tag = tags[-1].lstrip('v')
            return latest_tag
        
        # Fallback to changelog version if no tags
        for package_key, package_info in PACKAGES.items():
            changelog_path = pathlib.Path(package_info["changelog"])
            if changelog_path.exists():
                manager = ChangelogManager(changelog_path, package_key)
                if manager.versions:
                    return manager.versions[0].version
        return "0.0.1"
    
    def _rebuild_all_changelogs(self):
        """Rebuild all changelogs from git history"""
        print_color(Colors.WARNING, "Rebuilding all changelogs from git history...")
        
        # Warn user about destructive operation
        if not self.dry_run and not self.force:
            print_color(Colors.WARNING, "\n⚠️  WARNING: This will DELETE all existing changelogs!")
            print_color(Colors.WARNING, "Backups will be created with .bak.rebuild extension")
            response = input("\nAre you sure you want to continue? (yes/N): ")
            if response.lower() != 'yes':
                print_color(Colors.INFO, "Rebuild cancelled")
                sys.exit(0)
        
        # Clear existing changelogs for fresh rebuild
        if not self.dry_run:
            print_color(Colors.WARNING, "Clearing existing changelogs for fresh rebuild...")
            for package_key, package_info in PACKAGES.items():
                changelog_path = pathlib.Path(package_info["changelog"])
                if changelog_path.exists():
                    # Backup the old changelog
                    backup_path = changelog_path.with_suffix('.md.bak.rebuild')
                    shutil.copy2(changelog_path, backup_path)
                    print_color(Colors.INFO, f"  Backed up {changelog_path} to {backup_path}")
                    
                    # Delete the existing file to ensure clean slate
                    changelog_path.unlink()
                    print_color(Colors.INFO, f"  Deleted {changelog_path}")
                    
                    # Create fresh changelog with just the header
                    manager = ChangelogManager(changelog_path, package_key)
                    # The manager will create a new file with default header since file doesn't exist
                    manager.save(backup=False)
                    print_color(Colors.INFO, f"  Created fresh {changelog_path}")
        
        # Get all tags
        tags = GitOps.get_all_tags()
        
        if not tags:
            print_color(Colors.WARNING, "No tags found, processing all commits")
            first_commit = GitOps.get_first_commit()
            self._process_version_range(first_commit, "HEAD", self.version)
            return
            
        # Process each tag range with progress
        print_color(Colors.INFO, f"Found {len(tags)} tags to process")
        progress = ProgressTracker(len(tags) + 2, "Processing tags")
        
        # Process from first commit to first tag
        first_commit = GitOps.get_first_commit()
        if first_commit:
            print()
            print_color(Colors.CYAN, f"Processing initial commits to {tags[0]}...")
            version = tags[0].lstrip('v')
            self._process_version_range(first_commit, tags[0], version)
            progress.update()
        
        # Process between tags
        for i in range(len(tags) - 1):
            version = tags[i + 1].lstrip('v')
            print()
            print_color(Colors.CYAN, f"Processing {tags[i]} → {tags[i + 1]}...")
            self._process_version_range(tags[i], tags[i + 1], version)
            progress.update()
            
        # Process commits after last tag
        if tags:
            print()
            print_color(Colors.CYAN, "Processing commits after last tag...")
            self._process_version_range(tags[-1], "HEAD", self.version)
            progress.update()
            
        progress.close()
    
    def _process_since_ref(self):
        """Process commits since a specific ref"""
        if self.since == "initial":
            first_commit = GitOps.get_first_commit()
            start_ref = first_commit
            print_color(Colors.INFO, "Processing from initial commit...")
        else:
            start_ref = self.since
            print_color(Colors.INFO, f"Processing commits since {self.since}...")
            
        self._process_version_range(start_ref, "HEAD", self.version)
    
    def _process_current_or_smart(self):
        """Process current branch or smart historical mode"""
        # First, always check for last changelog sync
        last_sync_commit = self._find_last_changelog_sync_commit()
        
        if self.mode == AnalysisMode.CURRENT_BRANCH:
            # Get commits not in main/master
            main_branch = self._find_main_branch()
            if main_branch and main_branch != self.current_branch:
                start_ref = main_branch
            else:
                # If we're on main/master or can't find it, only process recent commits
                if last_sync_commit:
                    # Use the last sync commit as starting point
                    start_ref = f"{last_sync_commit}~3"
                    print_color(Colors.INFO, f"On main branch, using last changelog sync: {start_ref}")
                else:
                    # Look for the last tag to use as a starting point
                    tags = GitOps.get_all_tags()
                    if tags:
                        # Use smart analysis to check if we should include commits before the tag
                        enhanced_ref = self._find_missed_commits_after_tag(tags[-1])
                        start_ref = enhanced_ref or tags[-1]
                        print_color(Colors.INFO, f"On main branch, processing commits since: {start_ref}")
                    else:
                        # No tags found, use smart lookback
                        start_ref = self._determine_smart_lookback(self.version)
                        print_color(Colors.INFO, f"On main branch with no tags, using smart lookback: {start_ref}")
        else:
            # Smart mode - process commits since last tag for the CURRENT version
            if last_sync_commit:
                # Use the last sync commit as starting point
                start_ref = f"{last_sync_commit}~3"
                print_color(Colors.INFO, f"Smart mode: using last changelog sync: {start_ref}")
            else:
                tags = GitOps.get_all_tags()
                if tags:
                    # Use smart analysis to check if we should include commits before the tag
                    enhanced_ref = self._find_missed_commits_after_tag(tags[-1])
                    start_ref = enhanced_ref or tags[-1]
                    print_color(Colors.INFO, f"Smart mode: processing commits since: {start_ref}")
                else:
                    # No tags, use smart lookback
                    start_ref = self._determine_smart_lookback(self.version)
                    print_color(Colors.INFO, f"Smart mode: no tags found, using smart lookback: {start_ref}")
            
        self._process_version_range(start_ref, "HEAD", self.version)
    
    def _find_main_branch(self) -> Optional[str]:
        """Find main/master branch"""
        for branch in ['main', 'master', 'origin/main', 'origin/master']:
            code, _, _ = GitOps.run_command(['git', 'show-ref', '--verify', f'refs/heads/{branch}'])
            if code == 0:
                return branch
            # Also check remote refs
            code, _, _ = GitOps.run_command(['git', 'show-ref', '--verify', f'refs/remotes/{branch}'])
            if code == 0:
                return branch
        return None
    
    def _calculate_optimal_workers(self, num_commits: int, num_packages: int) -> int:
        """Calculate optimal number of workers based on workload"""
        # Base calculation on CPU cores
        cpu_cores = os.cpu_count() or 4
        
        # Estimate workload
        # Each package with commits needs LLM calls
        active_packages = num_packages  # Packages that will be processed
        
        # For small workloads, use fewer workers to avoid overhead
        if num_commits < 10 or active_packages <= 1:
            return 1
        elif num_commits < 50 and active_packages <= 2:
            return min(2, cpu_cores)
        elif num_commits < 100 and active_packages <= 3:
            return min(3, cpu_cores)
        
        # For larger workloads, scale up but respect limits
        # LLM calls are the bottleneck, not CPU
        if active_packages <= MAX_LLM_CONCURRENT:
            # If we have fewer packages than LLM limit, use one worker per package
            return active_packages
        else:
            # Otherwise use LLM limit to avoid API throttling
            return MAX_LLM_CONCURRENT
    
    def _process_version_range(self, start_ref: Optional[str], end_ref: str, version: str):
        """Process commits in a version range"""
        # Get commits
        commits = GitOps.get_commits_between(start_ref, end_ref)
        
        if not commits:
            print_color(Colors.YELLOW, "No commits found in range")
            return
        
        self.metrics.total_commits += len(commits)
        print_color(Colors.INFO, f"Found {len(commits)} commits")
        
        # Store commits for final cleanup
        self.all_commits.extend(commits)
        
        # Limit commits if needed
        if len(commits) > self.max_commits:
            print_color(Colors.WARNING, f"Limiting to most recent {self.max_commits} commits")
            commits = commits[:self.max_commits]
        
        # Group commits by package
        package_commits = self._group_commits_by_package(commits)
        
        # Show package summary
        print_color(Colors.INFO, "\nCommits by package:")
        for package, pkg_commits in package_commits.items():
            if pkg_commits:
                print_color(Colors.CYAN, f"  {package}: {len(pkg_commits)} commits")
        
        # Process each package in parallel with more workers
        num_packages = len([p for p, c in package_commits.items() if c])
        
        # Calculate optimal workers
        if self.auto_workers:
            max_workers = self._calculate_optimal_workers(len(commits), num_packages)
            print_color(Colors.INFO, f"\nAuto-selected {max_workers} workers based on workload")
        else:
            # Use manual setting but respect limits
            max_workers = min(self.workers, num_packages, MAX_LLM_CONCURRENT)
        
        print_color(Colors.INFO, f"Processing {num_packages} packages with {max_workers} workers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            
            for package, pkg_commits in package_commits.items():
                if pkg_commits:
                    future = executor.submit(
                        self._process_package,
                        package,
                        pkg_commits,
                        version
                    )
                    futures[future] = package
                    
            # Collect results
            results = {}
            completed = 0
            total = len(futures)
            
            for future in concurrent.futures.as_completed(futures):
                package = futures[future]
                completed += 1
                
                try:
                    status = future.result()
                    results[package] = status
                except Exception as e:
                    results[package] = "error"
                    print_color(Colors.ERROR, f"  [{completed}/{total}] ✗ {package} failed: {e}")
                    if os.getenv('DEBUG'):
                        traceback.print_exc()
        
        # Display results summary
        print_color(Colors.INFO, "\nChangelog Update Summary:")
        print_color(Colors.GRAY, "─" * 50)
        
        # Define status messages and colors
        status_info = {
            "updated": ("✓ Updated with new entries", Colors.GREEN),
            "would_update": ("✓ Would update (dry run)", Colors.CYAN),
            "no_new_commits": ("- No new commits", Colors.GRAY),
            "no_changes": ("- No significant changes", Colors.GRAY),
            "no_commits": ("- No commits in range", Colors.GRAY),
            "error": ("✗ Error occurred", Colors.RED)
        }
        
        # Display in consistent order
        for package in ["root", "dart", "flutter", "rust"]:
            if package in results:
                status = results[package]
                msg, color = status_info.get(status, ("? Unknown status", Colors.YELLOW))
                print_color(color, f"  {package:8} {msg}")
                
                # Create N/A entry for packages with no changes
                if status in ["no_changes", "no_commits"] and not self.dry_run:
                    self._create_na_entry(package, version)
            elif package in package_commits and not package_commits[package]:
                print_color(Colors.GRAY, f"  {package:8} - No commits in range")
                # Create N/A entry for this package
                if not self.dry_run:
                    self._create_na_entry(package, version)
        
        print_color(Colors.GRAY, "─" * 50)
    
    def _should_skip_file(self, file_path: str) -> bool:
        """Check if a file should be skipped based on gitignore settings"""
        if self.include_gitignored:
            return False  # Don't skip any files
        return GitOps.is_gitignored(file_path)
    
    def _group_commits_by_package(self, commits: List[GitCommit]) -> Dict[str, List[GitCommit]]:
        """Group commits by package based on files changed"""
        package_commits = {pkg: [] for pkg in PACKAGES}
        
        for commit in commits:
            # Track which packages this commit affects
            affected_packages = set()
            
            for package, info in PACKAGES.items():
                pattern = info["path_pattern"]
                exclude_patterns = info.get("exclude_patterns", [])
                
                # Check if any file matches this package
                for file in commit.files:
                    # Skip gitignored files
                    if self._should_skip_file(file):
                        continue
                        
                    # Check positive match
                    if re.match(pattern, file):
                        # Check exclusions
                        excluded = any(re.match(exc, file) for exc in exclude_patterns)
                        if not excluded:
                            affected_packages.add(package)
                            break
            
            # Add commit to each affected package
            for package in affected_packages:
                package_commits[package].append(commit)
                    
        return package_commits
    
    def _process_package(self, package: str, commits: List[GitCommit], version: str):
        """Process changelog for a single package"""
        if not commits:
            return "no_commits"
        
        self.metrics.total_files += sum(len(c.files) for c in commits)
        
        changelog_path = pathlib.Path(PACKAGES[package]["changelog"])
        manager = ChangelogManager(changelog_path, package)
        
        # Check if already has content for this version
        existing = None
        for v in manager.versions:
            if v.version == version:
                existing = v.content
                if existing:
                    print_color(Colors.INFO, f"  Found existing content for v{version}: {len(existing)} chars")
                break
                
        # Skip if no new commits and version already has content
        if existing and not any(c for c in commits if c.hash not in existing):
            return "no_new_commits"
        
        # Determine whether to use enhanced analysis
        use_enhanced = os.getenv('USE_ENHANCED_ANALYSIS', 'true').lower() == 'true'
        
        if use_enhanced:
            # Use enhanced generator with commit context analysis
            generator = EnhancedChangelogGenerator(package, version, cache=self.cache)
            
            # Get version history for context
            version_context = "\n".join(self.version_history[package][-3:]) if self.version_history[package] else ""
            
            # Generate with enhanced analysis (files will be analyzed internally)
            new_content = generator.generate(commits, [], "", existing or "", version_context)
        else:
            # Use original approach
            # Analyze files
            analyzer = FileAnalyzer(package, commits, cache=self.cache, include_gitignored=self.include_gitignored)
            selected_files, context = analyzer.analyze_files(version)
            
            if not selected_files:
                # Still generate a basic entry
                selected_files = [f for c in commits for f in c.files][:10]
                
            # Generate changelog
            generator = ChangelogGenerator(package, version, cache=self.cache)
            
            # Get version history for context
            version_context = "\n".join(self.version_history[package][-3:]) if self.version_history[package] else ""
            
            new_content = generator.generate(commits, selected_files, context, existing or "", version_context)
        
        # SAFETY: Handle empty or None responses from LLM
        if not new_content:
            print_color(Colors.ERROR, f"LLM returned empty response for {package}")
            return "no_changes"
            
        if new_content == "NO_CHANGES":
            print_color(Colors.INFO, f"  No new changes to add for {package} (all commits already documented)")
            return "no_changes"
        
        # SAFETY: Double-check we're not about to save empty content
        if new_content.strip() == "":
            print_color(Colors.ERROR, f"Generated content is empty for {package}, skipping")
            return "no_changes"
        
        # Update version history
        if new_content != "NO_CHANGES":
            self.version_history[package].append(f"v{version}: {new_content[:200]}...")
        
        # Update metrics
        self.metrics.llm_calls += generator.llm.metrics.llm_calls
        self.metrics.cache_hits += generator.llm.metrics.cache_hits
        self.metrics.cache_misses += generator.llm.metrics.cache_misses
        
        # Save if not dry run
        if not self.dry_run:
            # SAFETY: Log what we're about to do
            print_color(Colors.INFO, f"  Merging {len(new_content)} chars of new content for {package} v{version}")
            
            # Merge and save
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            manager.merge_version(version, today, new_content)
            manager.save()
            return "updated"
        else:
            return "would_update"
    
    def _final_cleanup_pass(self):
        """Do a final pass to fix all broken GitHub links and formatting issues"""
        print_header("Final Cleanup Pass")
        print_color(Colors.INFO, "Running final cleanup to fix links, formatting, and consistency...")
        
        cleanup_start = time.time()
        
        # Build commit reference map once
        commit_map = {}
        for commit in self.all_commits[-200:]:  # Last 200 commits
            commit_map[commit.short_hash] = {
                'full_hash': commit.hash,
                'pr_number': commit.pr_number
            }
        
        print_color(Colors.INFO, f"Built commit map with {len(commit_map)} commits")
        
        # Get all tags for version linking
        all_tags = GitOps.get_all_tags()
        tag_set = set(tag.lstrip('v') for tag in all_tags)
        
        # Process all packages in parallel
        packages_to_process = []
        for package_key, package_info in PACKAGES.items():
            changelog_path = pathlib.Path(package_info["changelog"])
            if changelog_path.exists():
                packages_to_process.append((package_key, package_info, changelog_path))
        
        if not packages_to_process:
            print_color(Colors.YELLOW, "No changelogs found to clean up")
            return
        
        print_color(Colors.INFO, f"Processing {len(packages_to_process)} changelogs...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for package_key, package_info, changelog_path in packages_to_process:
                # Submit cleanup task for parallel execution
                future = executor.submit(
                    self._cleanup_package_changelog,
                    package_key,
                    package_info,
                    changelog_path,
                    commit_map,
                    tag_set
                )
                futures.append((package_key, future))
            
            # Wait for all cleanups to complete and report results
            fixed_count = 0
            for package_key, future in futures:
                try:
                    result = future.result(timeout=60)  # 60 second timeout per package
                    if result['status'] == 'fixed':
                        fixed_count += 1
                        if not self.dry_run:
                            print_color(Colors.GREEN, f"  ✓ Fixed formatting in {package_key} changelog")
                            if 'message' in result:
                                print_color(Colors.GRAY, f"    ({result['message']})")
                        else:
                            print_color(Colors.CYAN, f"  ✓ Would fix formatting in {package_key} changelog (dry run)")
                    elif result['status'] == 'no_changes':
                        print_color(Colors.GRAY, f"  - No fixes needed for {package_key}")
                    elif result['status'] == 'error':
                        print_color(Colors.YELLOW, f"  ⚠ {result['message']} for {package_key}")
                except Exception as e:
                    print_color(Colors.RED, f"  ✗ Error cleaning {package_key}: {e}")
        
        cleanup_time = time.time() - cleanup_start
        print_color(Colors.INFO, f"\nCleanup completed in {cleanup_time:.1f}s")
        if fixed_count > 0:
            print_color(Colors.SUCCESS, f"Fixed {fixed_count} changelog(s)")
    
    def _cleanup_package_changelog(self, package_key: str, package_info: dict, 
                                   changelog_path: pathlib.Path, commit_map: dict, 
                                   tag_set: set) -> dict:
        """Clean up a single package changelog (thread-safe)"""
        try:
            print_color(Colors.INFO, f"\nCleaning up {package_key} changelog...")
            
            # Read current content
            content = changelog_path.read_text(encoding='utf-8')
            original_content = content
            
            # Step 1: Apply fast regex-based link fixes first
            content = self._fast_fix_links(content, commit_map)
            
            # Step 2: Apply formatting fixes
            content = self._apply_formatting_fixes(content, tag_set)
            
            # Step 3: Remove N/A entries
            content = self._remove_na_entries(content)
            
            # Check if we've already fixed everything with regex
            if content != original_content:
                # Save the fast-fixed version
                if not self.dry_run:
                    changelog_path.write_text(content, encoding='utf-8')
                
                # Check if there are still broken links that need LLM fixing
                has_broken_links = any(pattern in content for pattern in [
                    '...)', '](link)', 'github.com/...',
                    '[link_to_', '[text](link'
                ])
                
                if not has_broken_links:
                    # No need for expensive LLM processing!
                    return {'status': 'fixed', 'message': 'Fixed with fast regex'}
            
            # Step 4: Only use LLM for complex cases that regex couldn't handle
            # Split into versions for chunked processing
            version_pattern = re.compile(r'^(## \[v[0-9]+\.[0-9]+\.[0-9]+\].*?)(?=^## \[v|\Z)', re.MULTILINE | re.DOTALL)
            header_match = re.match(r'^(#[^#].*?\n\n(?:.*?\n\n)*?)(?=^## |\Z)', content, re.S | re.M)
            
            if not header_match:
                return {'status': 'error', 'message': 'Could not parse changelog header'}
                
            header = header_match.group(1)
            versions_content = content[len(header):]
            
            # Process each version separately to stay within token limits
            fixed_versions = []
            versions = version_pattern.findall(versions_content)
            
            needs_llm_fix = False
            for i, version_content in enumerate(versions):
                # Check if this version needs LLM fixing
                if any(pattern in version_content for pattern in ['...)', '](link)', '[link_to_']):
                    needs_llm_fix = True
                    if len(version_content) > 6000:  # Leave room for prompt
                        # This version is too large, process in sections
                        fixed_version = self._fix_large_version(version_content, commit_map)
                    else:
                        # Process entire version
                        fixed_version = self._fix_version_links(version_content, commit_map)
                    
                    if fixed_version:
                        fixed_versions.append(fixed_version)
                    else:
                        fixed_versions.append(version_content)  # Keep original if fix failed
                else:
                    # No broken links in this version, keep as is
                    fixed_versions.append(version_content)
            
            if not needs_llm_fix:
                # Everything was fixed by regex
                return {'status': 'fixed', 'message': 'Fixed with fast regex'}
            
            # Reconstruct the changelog with proper spacing
            if fixed_versions:
                # Join versions with double newlines for proper spacing
                fixed_content = header + '\n\n'.join(fixed_versions)
                
                # Ensure consistent newlines at end
                fixed_content = fixed_content.rstrip() + "\n"
                
                if fixed_content != original_content:
                    if not self.dry_run:
                        changelog_path.write_text(fixed_content, encoding='utf-8')
                    return {'status': 'fixed'}
                else:
                    return {'status': 'no_changes'}
            else:
                return {'status': 'error', 'message': 'No versions found to process'}
                
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def _apply_formatting_fixes(self, content: str, tag_set: Set[str]) -> str:
        """Apply formatting fixes to the entire changelog"""
        # Fix version header hyperlinking consistency
        content = self._fix_version_header_links(content, tag_set)
        
        # Ensure proper spacing between versions
        content = self._ensure_version_spacing(content)
        
        return content
    
    def _fix_version_header_links(self, content: str, tag_set: Set[str]) -> str:
        """Ensure all version headers are consistently hyperlinked"""
        # Pattern to match version headers (with or without links)
        version_pattern = re.compile(
            r'^## \[v?([0-9]+\.[0-9]+\.[0-9]+)\](?:\([^)]+\))? - (\d{4}-\d{2}-\d{2})',
            re.MULTILINE
        )
        
        def replace_version(match):
            version = match.group(1)
            date = match.group(2)
            
            # Check if this version has a tag
            if version in tag_set:
                # Add hyperlink
                return f"## [v{version}]({self.remote_url}/releases/tag/v{version}) - {date}"
            else:
                # No tag, no link
                return f"## [v{version}] - {date}"
        
        return version_pattern.sub(replace_version, content)
    
    def _ensure_version_spacing(self, content: str) -> str:
        """Ensure proper spacing between version sections"""
        # Split by version headers
        lines = content.split('\n')
        fixed_lines = []
        
        for i, line in enumerate(lines):
            fixed_lines.append(line)
            
            # If this is a version header
            if line.startswith('## [v'):
                # Check if next line exists and is not empty
                if i + 1 < len(lines) and lines[i + 1].strip():
                    # Always ensure there's a blank line after version header
                    # This includes when the next line is a section header (###)
                    fixed_lines.append('')
        
        return '\n'.join(fixed_lines)
    
    def _remove_na_entries(self, version_content: str) -> str:
        """Remove N/A entries from a version section"""
        lines = version_content.split('\n')
        filtered_lines = []
        skip_na = False
        
        for line in lines:
            # Check if this is an N/A entry
            if line.strip() == '- N/A':
                skip_na = True
                continue
            
            # If we're in a section with only N/A, skip the section header too
            if skip_na and line.startswith('###'):
                # Check if the next non-empty line is N/A
                next_content_line = None
                for j in range(lines.index(line) + 1, len(lines)):
                    if lines[j].strip():
                        next_content_line = lines[j].strip()
                        break
                
                if next_content_line == '- N/A':
                    continue  # Skip this section header
                else:
                    skip_na = False
            
            filtered_lines.append(line)
        
        # Clean up any empty sections
        content = '\n'.join(filtered_lines)
        
        # Remove sections that have no content
        section_pattern = re.compile(r'^### (\w+)\s*\n(?=###|\Z)', re.MULTILINE)
        content = section_pattern.sub('', content)
        
        # Remove multiple consecutive blank lines
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    def _fix_version_links(self, version_content: str, commit_map: Dict[str, Dict[str, str]]) -> Optional[str]:
        """Fix links in a single version section"""
        # Build prompt
        prompt = f"""You are a changelog link fixer. Fix ALL broken GitHub links in this version section.

VERSION CONTENT:
{version_content}

REPOSITORY INFO:
- GitHub URL: {self.remote_url}

COMMIT REFERENCE:
"""
        # Add relevant commits from the map
        for short_hash, info in list(commit_map.items())[:50]:  # Limit to keep prompt small
            prompt += f"\n{short_hash} -> {info['full_hash']}"
            if info['pr_number']:
                prompt += f" (PR #{info['pr_number']})"
        
        prompt += """

TYPES OF BROKEN LINKS TO FIX:
1. Truncated links ending with "..." 
2. Placeholder links like [link_to_hash](link)
3. Malformed GitHub URLs (missing parts, wrong format)
4. Broken commit links (404s, wrong repo, etc.)
5. Broken PR links
6. Any GitHub link that doesn't work

INSTRUCTIONS:
- Fix ALL broken GitHub links
- Use the commit reference to expand short hashes to full hashes
- Ensure all URLs point to the correct repository
- Preserve ALL other content exactly including formatting
- Do NOT add any markdown code blocks or backticks
- Do NOT change the structure or spacing
- Return ONLY the fixed version content
- NO ``` or ```markdown blocks!

OUTPUT: The version content with all GitHub links fixed, preserving exact formatting."""

        # Use Flash model for speed and to avoid timeouts
        llm = LLMClient(cache=self.cache)
        fixed_content = llm.prompt(prompt, model_override=FLASH_MODEL)
        
        if fixed_content and "## [v" in fixed_content:
            # Clean up any backticks that might have been added
            fixed_content = fixed_content.strip()
            if fixed_content.startswith('```'):
                # Remove markdown code block markers
                fixed_content = re.sub(r'^```\w*\n?', '', fixed_content)
                fixed_content = re.sub(r'\n?```$', '', fixed_content)
            return fixed_content
        return None
    
    def _fix_large_version(self, version_content: str, commit_map: Dict[str, Dict[str, str]]) -> str:
        """Handle large version sections by processing in chunks"""
        # Split by sections (Added, Changed, etc.)
        section_pattern = re.compile(r'^(### \w+.*?)(?=^### |\Z)', re.MULTILINE | re.DOTALL)
        
        # Extract version header
        header_match = re.match(r'^(## \[v[0-9]+\.[0-9]+\.[0-9]+\].*?\n\n)', version_content)
        if not header_match:
            return version_content
            
        header = header_match.group(1)
        sections_content = version_content[len(header):]
        
        # Process each section separately
        fixed_sections = []
        sections = section_pattern.findall(sections_content)
        
        for section in sections:
            if len(section) > 5000:
                # Section is still too large, process line by line
                fixed_section = self._fix_section_incrementally(section, commit_map)
            else:
                fixed_section = self._fix_section_links(section, commit_map)
            
            if fixed_section:
                fixed_sections.append(fixed_section)
            else:
                fixed_sections.append(section)
        
        # Reconstruct the version with proper spacing between sections
        return header + '\n\n'.join(fixed_sections)
    
    def _fix_section_links(self, section_content: str, commit_map: Dict[str, Dict[str, str]]) -> Optional[str]:
        """Fix links in a changelog section"""
        prompt = f"""Fix ALL broken GitHub links in this changelog section:

{section_content}

Repository: {self.remote_url}

Commit map (short->full):
"""
        for short_hash, info in list(commit_map.items())[:30]:
            prompt += f"\n{short_hash}->{info['full_hash']}"
        
        prompt += """

Fix these types of broken links:
- Truncated URLs ending with "..."
- Placeholder links like [text](link)
- Malformed GitHub URLs
- Wrong repository references
- Any non-working GitHub link

IMPORTANT:
- Return the section with ALL GitHub links fixed
- Change NOTHING else
- Do NOT add backticks or code blocks
- NO ``` or ```markdown blocks!
- Preserve exact formatting and spacing"""
        
        llm = LLMClient(cache=self.cache)
        result = llm.prompt(prompt, model_override=FLASH_MODEL)
        
        if result:
            # Clean up any backticks that might have been added
            result = result.strip()
            if result.startswith('```'):
                result = re.sub(r'^```\w*\n?', '', result)
                result = re.sub(r'\n?```$', '', result)
        
        return result
    
    def _fix_section_incrementally(self, section_content: str, commit_map: Dict[str, Dict[str, str]]) -> str:
        """Process a very large section line by line"""
        lines = section_content.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Check if line contains any markdown links that might be broken
            if '[' in line and ']' in line and '(' in line and ')' in line:
                # Check for various broken link patterns
                if any(pattern in line for pattern in ['...', 'link)', 'github.com', 'PR #']):
                    fixed_line = self._fix_single_line(line, commit_map)
                    fixed_lines.append(fixed_line if fixed_line else line)
                else:
                    # Also try to fix lines with commit hashes
                    has_commit = any(short_hash in line for short_hash in commit_map.keys())
                    if has_commit:
                        fixed_line = self._fix_single_line(line, commit_map)
                        fixed_lines.append(fixed_line if fixed_line else line)
                    else:
                        fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)
    
    def _fix_single_line(self, line: str, commit_map: Dict[str, Dict[str, str]]) -> Optional[str]:
        """Fix links in a single line - optimized version"""
        if not self.remote_url:
            return None
            
        # Quick check if line needs fixing
        if not any(pattern in line for pattern in ['[', ']', '(', ')', '...', 'link)', 'PR #']):
            return None
            
        original_line = line
        fixed_line = line
        
        # Process all commits in the map at once
        for short_hash, info in commit_map.items():
            if short_hash not in fixed_line:
                continue
                
            full_hash = info['full_hash']
            pr_number = info.get('pr_number')
            
            # All patterns for this commit
            patterns_replacements = [
                # Truncated commit links
                (rf'\[{short_hash}\]\(https://github\.com/[^)]*\.\.\..*?\)',
                 f'[{short_hash}]({self.remote_url}/commit/{full_hash})'),
                
                # Placeholder commit links
                (f'[{short_hash}](link)',
                 f'[{short_hash}]({self.remote_url}/commit/{full_hash})'),
                
                # Malformed commit links
                (rf'\[{short_hash}\]\([^)]+\)',
                 f'[{short_hash}]({self.remote_url}/commit/{full_hash})'),
            ]
            
            # Apply all patterns
            for pattern, replacement in patterns_replacements:
                if isinstance(pattern, str) and pattern in fixed_line:
                    fixed_line = fixed_line.replace(pattern, replacement)
                else:
                    fixed_line = re.sub(pattern, replacement, fixed_line)
            
            # Fix PR links if we have PR number
            if pr_number:
                pr_patterns = [
                    # Truncated PR
                    (rf'PR \[#{pr_number}\]\([^)]*\.\.\..*?\)',
                     f'PR [#{pr_number}]({self.remote_url}/pull/{pr_number})'),
                    
                    # Placeholder PR
                    (f'PR [#{pr_number}](link)',
                     f'PR [#{pr_number}]({self.remote_url}/pull/{pr_number})'),
                    
                    # Plain text PR (but not if already linked)
                    (rf'PR #{pr_number}(?!\])',
                     f'PR [#{pr_number}]({self.remote_url}/pull/{pr_number})'),
                ]
                
                for pattern, replacement in pr_patterns:
                    if isinstance(pattern, str) and pattern in fixed_line:
                        fixed_line = fixed_line.replace(pattern, replacement)
                    else:
                        fixed_line = re.sub(pattern, replacement, fixed_line)
        
        # Fix any remaining truncated GitHub URLs
        fixed_line = re.sub(
            r'\[([^\]]+)\]\(https://github\.com/[^)]*\.\.\..*?\)',
            rf'[\1]({self.remote_url})',
            fixed_line
        )
        
        return fixed_line if fixed_line != original_line else None
    
    def _create_na_entry(self, package: str, version: str):
        """Create a N/A entry for a package with no commits"""
        if self.dry_run:
            return
            
        changelog_path = pathlib.Path(PACKAGES[package]["changelog"])
        manager = ChangelogManager(changelog_path, package)
        
        # Check if version already has content
        for v in manager.versions:
            if v.version == version:
                # Don't create N/A if there's already content
                if v.content and not v.is_empty:
                    print_color(Colors.GRAY, f"    → Skipping N/A entry for v{version} (already has content)")
                    return
        
        # Create N/A content
        na_content = """### Changed
- N/A"""
        
        # Add the version with N/A content
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        manager.merge_version(version, today, na_content)
        manager.save()
        
        print_color(Colors.GRAY, f"    → Created N/A entry for v{version}")
    
    def _cleanup_backups(self):
        """Offer to clean up backup files"""
        # Find all backup files
        backup_files = []
        for package_key, package_info in PACKAGES.items():
            changelog_path = pathlib.Path(package_info["changelog"])
            changelog_dir = changelog_path.parent
            
            # Look for backup files specifically for this changelog
            base_name = changelog_path.name
            for suffix in ['.bak', '.bak.rebuild']:
                backup_path = changelog_dir / f"{base_name}{suffix}"
                if backup_path.exists():
                    backup_files.append(backup_path)
        
        if not backup_files:
            return
        
        print_header("Backup File Cleanup")
        print_color(Colors.INFO, f"Found {len(backup_files)} backup file(s):")
        
        for backup in backup_files:
            # Get file size
            size = backup.stat().st_size
            size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
            print_color(Colors.GRAY, f"  - {backup} ({size_str})")
        
        # Ask user if they want to clean up (default yes)
        should_delete = True
        if not self.force:
            response = input("\nDelete backup files? (Y/n): ").strip()
            # Debug output
            if os.getenv('DEBUG'):
                print_color(Colors.GRAY, f"[DEBUG] User response: '{response}'")
            
            # Check response - default is yes (empty response or y/yes)
            if response.lower() in ['n', 'no']:
                should_delete = False
                print_color(Colors.INFO, "Keeping backup files")
        
        # Only delete if user confirmed or force mode
        if should_delete:
            # Delete backup files
            deleted_count = 0
            for backup in backup_files:
                try:
                    backup.unlink()
                    deleted_count += 1
                except Exception as e:
                    print_color(Colors.WARNING, f"  Failed to delete {backup}: {e}")
            
            if deleted_count > 0:
                print_color(Colors.SUCCESS, f"✓ Deleted {deleted_count} backup file(s)")
    
    def _find_last_changelog_sync_commit(self) -> Optional[str]:
        """Find the last commit where all 4 changelogs were modified together with meaningful additions"""
        print_color(Colors.INFO, "Looking for last synchronized changelog update...")
        
        # Get all changelog paths
        changelog_paths = [pathlib.Path(pkg["changelog"]) for pkg in PACKAGES.values()]
        
        # Search through recent commits to find when all changelogs were modified together
        code, log_output, _ = GitOps.run_command([
            'git', 'log', '--pretty=format:%H', '-n', '200', '--',
            *[str(p) for p in changelog_paths]
        ])
        
        if code != 0 or not log_output:
            return None
        
        # Check each commit to see if it modified all changelogs
        for commit_hash in log_output.splitlines():
            # Get the list of files changed in this commit
            code, files_output, _ = GitOps.run_command([
                'git', 'diff-tree', '--no-commit-id', '--name-only', '-r', commit_hash
            ])
            
            if code == 0:
                changed_files = set(files_output.splitlines())
                changelog_files = set(str(p) for p in changelog_paths)
                
                # Check if all changelog files were modified
                if changelog_files.issubset(changed_files):
                    # Analyze the nature of changes - were they additions or deletions?
                    if self._is_meaningful_changelog_sync(commit_hash, changelog_paths):
                        # Get commit info
                        code, commit_info, _ = GitOps.run_command([
                            'git', 'log', '-1', '--pretty=format:%h %s', commit_hash
                        ])
                        if code == 0:
                            print_color(Colors.SUCCESS, f"Found last meaningful sync commit: {commit_info}")
                        return commit_hash
                    else:
                        # This was likely a cleanup/deletion commit, keep looking
                        code, commit_info, _ = GitOps.run_command([
                            'git', 'log', '-1', '--pretty=format:%h %s', commit_hash
                        ])
                        if code == 0:
                            print_color(Colors.YELLOW, f"Skipping cleanup/deletion commit: {commit_info}")
        
        return None
    
    def _is_meaningful_changelog_sync(self, commit_hash: str, changelog_paths: List[pathlib.Path]) -> bool:
        """Check if a changelog sync commit contains meaningful additions (not just deletions/cleanup)"""
        total_additions = 0
        total_deletions = 0
        
        # Analyze each changelog file's changes
        for changelog_path in changelog_paths:
            # Get the diff stats for this file in this commit
            code, diff_output, _ = GitOps.run_command([
                'git', 'diff', '--numstat', f'{commit_hash}~1', commit_hash, '--', str(changelog_path)
            ])
            
            if code == 0 and diff_output:
                # Parse numstat output: additions deletions filename
                parts = diff_output.strip().split('\t')
                if len(parts) >= 2:
                    try:
                        additions = int(parts[0])
                        deletions = int(parts[1])
                        total_additions += additions
                        total_deletions += deletions
                    except ValueError:
                        # Binary file or other issue, skip
                        continue
        
        # Consider it meaningful if:
        # 1. There are more additions than deletions (net positive change)
        # 2. OR there are significant additions (>20 lines) even if deletions exist
        # 3. AND it's not purely deletions
        if total_additions == 0 and total_deletions > 0:
            # Pure deletion - likely cleanup
            return False
        elif total_additions > total_deletions:
            # Net positive change
            return True
        elif total_additions >= 20:
            # Significant additions even if some deletions
            return True
        else:
            # Check commit message for clues
            code, commit_msg, _ = GitOps.run_command([
                'git', 'log', '-1', '--pretty=format:%s', commit_hash
            ])
            if code == 0:
                msg_lower = commit_msg.lower()
                # Skip if it's clearly a cleanup/deletion commit
                if any(word in msg_lower for word in ['cleanup', 'remove', 'delete', 'n/a', 'na entries']):
                    return False
                # Consider meaningful if it mentions updates/additions
                if any(word in msg_lower for word in ['update', 'add', 'changelog', 'sync']):
                    return True
            
            # Default to considering it meaningful if we're unsure
            return total_additions > 0
    
    def _determine_smart_lookback(self, current_tag: str) -> str:
        """Intelligently determine how far back to look for commits"""
        # First, try to find the last commit where all changelogs were updated with meaningful content
        last_sync_commit = self._find_last_changelog_sync_commit()
        
        if last_sync_commit:
            # Count how many commits back this is
            code, count_output, _ = GitOps.run_command([
                'git', 'rev-list', '--count', f'{last_sync_commit}..HEAD'
            ])
            
            if code == 0 and count_output.strip().isdigit():
                commits_since = int(count_output.strip())
                if commits_since > 0:
                    print_color(Colors.INFO, f"Last meaningful changelog sync was {commits_since} commits ago")
                    # Add a few extra commits to be safe (in case some were missed)
                    return f"{last_sync_commit}~3"
        else:
            # No meaningful sync found, check if there was a recent deletion/cleanup
            print_color(Colors.INFO, "No recent meaningful sync found, checking for cleanup commits...")
            
            # Look for any changelog modifications (including deletions)
            changelog_paths = [pathlib.Path(pkg["changelog"]) for pkg in PACKAGES.values()]
            code, log_output, _ = GitOps.run_command([
                'git', 'log', '--pretty=format:%H', '-n', '50', '--',
                *[str(p) for p in changelog_paths]
            ])
            
            if code == 0 and log_output:
                for commit_hash in log_output.splitlines():
                    # Check if this was a deletion/cleanup
                    code, commit_msg, _ = GitOps.run_command([
                        'git', 'log', '-1', '--pretty=format:%s', commit_hash
                    ])
                    if code == 0:
                        msg_lower = commit_msg.lower()
                        if any(word in msg_lower for word in ['cleanup', 'remove n/a', 'delete', 'revert']):
                            print_color(Colors.WARNING, f"Found recent cleanup commit: {commit_msg}")
                            print_color(Colors.INFO, "Looking further back to find the original content...")
                            # Look back further - at least 100 commits or to the previous tag
                            tags = GitOps.get_all_tags()
                            if len(tags) >= 2:
                                # Use the tag before the current one
                                return tags[-2]
                            else:
                                return "HEAD~100"
        
        # Fallback to LLM-based analysis
        print_color(Colors.INFO, "Using LLM analysis to determine lookback...")
        
        # Get recent commit history
        code, log_output, _ = GitOps.run_command([
            'git', 'log', '--oneline', '--no-decorate', '-n', '100', 'HEAD'
        ])
        
        if code != 0:
            # Fallback to default
            return "HEAD~50"
        
        # Build prompt for Gemini Flash
        prompt = f"""You are analyzing git commit history to determine the optimal lookback range for changelog generation.

Current tag being updated: {current_tag}

Recent commit history (newest first):
{log_output}

TASK: Determine how many commits back we should look to capture all relevant changes for the {current_tag} changelog.

IMPORTANT CONSIDERATIONS:
1. Look for patterns that indicate the start of work for this version
2. Find commits that mention the previous version tag
3. Identify where feature work for {current_tag} likely began
4. Consider commit message patterns (e.g., "prepare for X", "bump version", "release X")
5. If you see a commit that mentions releasing or tagging a previous version, that's likely where to stop
6. Be generous - it's better to include too many commits than too few

OUTPUT: Return ONLY a number (e.g., 25, 50, 75) representing how many commits back to look.
Do not include any explanation, just the number."""

        # Use Flash model for speed
        llm = LLMClient(cache=self.cache)
        response = llm.prompt(prompt, model_override=FLASH_MODEL)
        
        if response and response.strip().isdigit():
            lookback = int(response.strip())
            # Sanity check - cap at 200
            lookback = min(lookback, 200)
            print_color(Colors.INFO, f"Smart analysis suggests looking back {lookback} commits")
            return f"HEAD~{lookback}"
        else:
            # Fallback to default
            print_color(Colors.YELLOW, "Could not determine optimal range, using default")
            return "HEAD~50"

    def _find_missed_commits_after_tag(self, tag: str) -> Optional[str]:
        """Check if there are commits after the tag that should be included"""
        # First, check if there are any commits after the tag
        code, count_output, _ = GitOps.run_command([
            'git', 'rev-list', '--count', f'{tag}..HEAD'
        ])
        
        if code != 0 or not count_output.strip().isdigit():
            return None
            
        commit_count = int(count_output.strip())
        if commit_count == 0:
            print_color(Colors.INFO, f"No commits found after {tag}")
            return None
        
        # First, try to find the last changelog sync commit
        last_sync_commit = self._find_last_changelog_sync_commit()
        
        if last_sync_commit:
            # Check if this sync commit is after the tag
            code, is_after, _ = GitOps.run_command([
                'git', 'merge-base', '--is-ancestor', tag, last_sync_commit
            ])
            
            if code == 0:  # Tag is ancestor of sync commit (sync is after tag)
                # Use the sync commit as the starting point
                print_color(Colors.INFO, f"Using last changelog sync as starting point")
                return f"{last_sync_commit}~3"
        
        if commit_count <= 5:
            # For small number of commits, just use the tag
            print_color(Colors.INFO, f"Found {commit_count} commits after {tag}")
            return tag
        
        # For larger number of commits, analyze if we should look further back
        print_color(Colors.INFO, f"Found {commit_count} commits after {tag}, analyzing...")
        
        # Get commit history including and after the tag
        code, log_output, _ = GitOps.run_command([
            'git', 'log', '--oneline', '--no-decorate', '-n', '50', f'{tag}~5..HEAD'
        ])
        
        if code != 0:
            return tag
        
        prompt = f"""Analyze these git commits to determine if we should look back further than tag {tag} for changelog generation.

Tag being updated: {tag}
Commits after tag: {commit_count}

Recent commits (including some before the tag):
{log_output}

TASK: Should we look back further than {tag} to capture related work?

Look for:
1. Commits right before the tag that are part of the same feature/fix work
2. Related commits that were made in preparation for {tag}
3. Commits that mention "prepare", "setup", or reference {tag}

OUTPUT: Return ONLY one of:
- "TAG" if we should start from {tag}
- A number (e.g., "10") indicating how many commits BEFORE {tag} to include
Do not include any explanation."""

        llm = LLMClient(cache=self.cache)
        response = llm.prompt(prompt, model_override=FLASH_MODEL)
        
        if response:
            response = response.strip()
            if response == "TAG":
                return tag
            elif response.isdigit():
                lookback = int(response)
                lookback = min(lookback, 20)  # Cap at 20 commits before tag
                if lookback > 0:
                    print_color(Colors.INFO, f"Including {lookback} commits before {tag}")
                    return f"{tag}~{lookback}"
        
        return tag

    def _fast_fix_links(self, content: str, commit_map: Dict[str, Dict[str, str]]) -> str:
        """Fast regex-based link fixing - no LLM calls"""
        if not self.remote_url:
            return content
        
        fixed_content = content
        
        # Fix truncated commit links
        for short_hash, info in commit_map.items():
            # Pattern: [hash](https://github.com/...
            truncated_pattern = rf'\[{short_hash}\]\(https://github\.com/[^)]*\.\.\..*?\)'
            if re.search(truncated_pattern, fixed_content):
                fixed_content = re.sub(
                    truncated_pattern + r'[^)]*\)',
                    f'[{short_hash}]({self.remote_url}/commit/{info["full_hash"]})',
                    fixed_content
                )
            
            # Pattern: [hash](link)
            placeholder_pattern = rf'\[{short_hash}\]\(link\)'
            if placeholder_pattern in fixed_content:
                fixed_content = fixed_content.replace(
                    placeholder_pattern,
                    f'[{short_hash}]({self.remote_url}/commit/{info["full_hash"]})'
                )
            
            # Fix PR links if we have PR number
            if info.get('pr_number'):
                pr_num = info['pr_number']
                
                # Truncated PR links
                pr_truncated = rf'PR \[#{pr_num}\]\([^)]*\.\.\.'
                if re.search(pr_truncated, fixed_content):
                    fixed_content = re.sub(
                        pr_truncated + r'[^)]*\)',
                        f'PR [#{pr_num}]({self.remote_url}/pull/{pr_num})',
                        fixed_content
                    )
                
                # Placeholder PR links
                pr_placeholder = f'PR [#{pr_num}](link)'
                if pr_placeholder in fixed_content:
                    fixed_content = fixed_content.replace(
                        pr_placeholder,
                        f'PR [#{pr_num}]({self.remote_url}/pull/{pr_num})'
                    )
                
                # Plain text PR references
                plain_pr = f'PR #{pr_num}'
                if plain_pr in fixed_content and f'[#{pr_num}]' not in fixed_content:
                    fixed_content = fixed_content.replace(
                        plain_pr,
                        f'PR [#{pr_num}]({self.remote_url}/pull/{pr_num})'
                    )
        
        # Fix any remaining generic truncated GitHub URLs
        fixed_content = re.sub(
            r'\[([^\]]+)\]\(https://github\.com/[^)]*\.\.\..*?\)',
            rf'[\1]({self.remote_url})',
            fixed_content
        )
        
        return fixed_content

    def _generate_smart_commit_message(self) -> Optional[str]:
        """Generate a smart commit message based on changelog changes"""
        if self.dry_run:
            return None
            
        print_header("Smart Commit Message Generation")
        print_color(Colors.INFO, "Analyzing changelog changes to generate commit message...")
        
        # Get the diff of all changelog files
        changelog_diffs = {}
        for package_key, package_info in PACKAGES.items():
            changelog_path = pathlib.Path(package_info["changelog"])
            if changelog_path.exists():
                # Get the diff for this changelog
                # First try staged changes
                code, diff_out, _ = GitOps.run_command([
                    'git', 'diff', '--cached', '--', str(changelog_path)
                ])
                
                # If no staged changes, try unstaged
                if code == 0 and not diff_out.strip():
                    code, diff_out, _ = GitOps.run_command([
                        'git', 'diff', '--', str(changelog_path)
                    ])
                
                if code == 0 and diff_out.strip():
                    changelog_diffs[package_key] = diff_out
        
        if not changelog_diffs:
            print_color(Colors.YELLOW, "No changelog changes detected")
            return None
        
        # Build prompt for commit message generation
        prompt = f"""You are generating a git commit message for changelog updates.

CHANGELOG CHANGES BY PACKAGE:
"""
        
        for package, diff in changelog_diffs.items():
            prompt += f"\n{'='*60}\nPACKAGE: {package}\n{'='*60}\n"
            # Limit diff size to avoid token limits
            prompt += diff[:8000] + "\n" if len(diff) > 8000 else diff + "\n"
        
        prompt += """
INSTRUCTIONS:
1. Analyze what was added to each changelog
2. Identify the key changes, features, fixes, and improvements
3. Generate a comprehensive commit message following conventional commit format

COMMIT MESSAGE FORMAT:
- First line: type(scope): concise summary (max 72 chars)
- Blank line
- Body: Detailed explanation of changes, organized by package
- Use bullet points for multiple changes
- Include version number being updated
- Mention any breaking changes

TYPES: feat, fix, docs, style, refactor, perf, test, build, ci, chore

EXAMPLE:
chore(changelog): update changelogs for v0.0.8

Update changelogs across all packages with recent changes:

root:
- Add smart commit message generation
- Improve parallel processing performance
- Fix Git pager screen clearing issue

dart:
- Add new vector search algorithm
- Fix memory leak in large datasets
- Improve error handling

flutter:
- Add Flutter-specific optimizations
- Update dependencies

rust:
- Optimize FFI bindings
- Add new compression support

Generated by sync_changelogs.py

OUTPUT: Return ONLY the commit message, no explanations or markdown."""

        # Use LLM to generate commit message
        llm = LLMClient(cache=self.cache)
        commit_message = llm.prompt(prompt, model_override=FLASH_MODEL)
        
        if not commit_message:
            print_color(Colors.ERROR, "Failed to generate commit message")
            return None
            
        return commit_message.strip()
    
    def _offer_to_commit(self, commit_message: str) -> bool:
        """Offer to commit the changes with the generated message"""
        print_header("Commit Changes")
        print_color(Colors.INFO, "Generated commit message:")
        print_color(Colors.CYAN, "─" * 60)
        print(commit_message)
        print_color(Colors.CYAN, "─" * 60)
        
        # Check if there are changes to commit
        if not GitOps.is_dirty():
            print_color(Colors.YELLOW, "\nNo changes to commit")
            return False
        
        # Show what will be committed
        print_color(Colors.INFO, "\nFiles to be committed:")
        code, status_out, _ = GitOps.run_command(['git', 'status', '--short'])
        if code == 0:
            for line in status_out.splitlines():
                if line.strip():
                    print_color(Colors.GRAY, f"  {line}")
        
        # Ask user
        print()
        response = input("Would you like to commit these changes? (y/N): ")
        
        if response.lower() in ['y', 'yes']:
            # Stage all changelog files
            changelog_files = []
            for package_info in PACKAGES.values():
                changelog_path = pathlib.Path(package_info["changelog"])
                if changelog_path.exists():
                    changelog_files.append(str(changelog_path))
            
            # Stage the files
            print_color(Colors.INFO, "Staging changelog files...")
            code, _, err = GitOps.run_command(['git', 'add'] + changelog_files)
            if code != 0:
                print_color(Colors.ERROR, f"Failed to stage files: {err}")
                return False
            
            # Create commit
            print_color(Colors.INFO, "Creating commit...")
            # Write commit message to temp file to handle multi-line messages
            import tempfile
            
            # Use context manager to ensure cleanup
            temp_fd, temp_file = tempfile.mkstemp(suffix='.txt', text=True)
            try:
                # Write commit message
                with os.fdopen(temp_fd, 'w') as f:
                    f.write(commit_message)
                
                # Create commit
                code, _, err = GitOps.run_command(['git', 'commit', '-F', temp_file])
                if code == 0:
                    print_color(Colors.SUCCESS, "✓ Changes committed successfully!")
                    
                    # Show the commit hash
                    code, commit_hash, _ = GitOps.run_command(['git', 'rev-parse', 'HEAD'])
                    if code == 0:
                        print_color(Colors.INFO, f"Commit: {commit_hash[:8]}")
                    return True
                else:
                    print_color(Colors.ERROR, f"Failed to commit: {err}")
                    return False
            finally:
                # Always clean up temp file
                try:
                    os.unlink(temp_file)
                except:
                    pass
        else:
            print_color(Colors.INFO, "Commit cancelled")
            return False

# ═══════════════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="AI-powered changelog generator for monorepos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Changelog Structure:
  CHANGELOG.md               # Root - project-wide changes, tooling, CI/CD
  dart/CHANGELOG.md          # Dart package changes
  flutter/CHANGELOG.md       # Flutter package changes  
  dart/rust/CHANGELOG.md     # Rust FFI binding changes

Examples:
  %(prog)s                           # Process commits since last tag (or recent commits)
  %(prog)s --smart                   # Smart historical mode (backfill empty versions from last tag)
  %(prog)s --rebuild-all             # Rebuild all changelogs from scratch
  %(prog)s --since HEAD~50           # Process last 50 commits
  %(prog)s --since abc123            # Process since specific commit
  %(prog)s --since initial           # Process entire history
  %(prog)s --version 1.2.3           # Specify target version
  %(prog)s --max 100                 # Limit commits per package
  %(prog)s --dry-run                 # Preview without modifying files
  %(prog)s --config custom.yml       # Use custom configuration
  %(prog)s --workers 20              # Use more parallel workers
  %(prog)s --workers -1              # Auto-select workers based on workload
  %(prog)s --include-gitignored     # Include files that are currently gitignored
  %(prog)s --no-enhanced-analysis   # Use original analysis (faster)
  %(prog)s --no-cleanup             # Skip final cleanup pass for broken links (faster but may leave some broken links)
        """
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--smart',
        action='store_const',
        dest='mode',
        const=AnalysisMode.SMART_HISTORICAL,
        default=AnalysisMode.CURRENT_BRANCH,
        help='Smart historical mode (backfill empty versions from last tag)'
    )
    mode_group.add_argument(
        '--rebuild-all',
        action='store_const',
        dest='mode',
        const=AnalysisMode.REBUILD_ALL,
        help='Rebuild all changelogs from git history (WARNING: destructive)'
    )
    
    # Other options
    parser.add_argument(
        '--since',
        help='Git ref to start from (e.g., HEAD~100, commit hash, or "initial")'
    )
    parser.add_argument(
        '--version',
        help='Target version (default: detect from changelog)'
    )
    parser.add_argument(
        '--max',
        type=int,
        default=DEFAULT_MAX_COMMITS,
        help=f'Max commits to process per package (default: {DEFAULT_MAX_COMMITS})'
    )
    parser.add_argument(
        '--model',
        default=DEFAULT_MODEL,
        help=f'LLM model to use (default: {DEFAULT_MODEL})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    parser.add_argument(
        '--config',
        type=pathlib.Path,
        help='Path to configuration file (default: .changelog.yml)'
    )
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable caching'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts (use with --rebuild-all)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=MAX_WORKERS,
        help=f'Number of parallel workers (default: {MAX_WORKERS}, use -1 for auto)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=BATCH_SIZE,
        help=f'Batch size for processing commits (default: {BATCH_SIZE})'
    )
    parser.add_argument(
        '--include-gitignored',
        action='store_true',
        help='Include files that are currently gitignored (default: exclude them)'
    )
    parser.add_argument(
        '--keep-backups',
        action='store_true',
        help='Keep backup files after successful run (default: offer to delete)'
    )
    parser.add_argument(
        '--no-enhanced-analysis',
        action='store_true',
        help='Disable enhanced commit context analysis (use original approach)'
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Skip final cleanup pass for broken links (faster but may leave some broken links)'
    )
    parser.add_argument(
        '--no-commit',
        action='store_true',
        help='Skip the smart commit message generation and commit prompt'
    )
    
    args = parser.parse_args()
    
    # Handle --rebuild-all and --since conflict
    if args.mode == AnalysisMode.REBUILD_ALL and args.since:
        parser.error("--rebuild-all and --since cannot be used together")
    
    # Set debug mode if verbose
    if args.verbose:
        os.environ['DEBUG'] = '1'
    
    # Set LLM model
    if args.model:
        os.environ['GEMINI_MODEL'] = args.model
    
    # Set enhanced analysis mode
    if args.no_enhanced_analysis:
        os.environ['USE_ENHANCED_ANALYSIS'] = 'false'
    
    # Load configuration
    config = Config(args.config) if args.config else Config()
    
    # Disable cache if requested
    if args.no_cache:
        CACHE_DIR.mkdir(exist_ok=True)
        for cache_file in CACHE_DIR.glob("*.cache"):
            cache_file.unlink()
    
    try:
        sync = ChangelogSync(
            mode=args.mode,
            version=args.version,
            since=args.since,
            max_commits=args.max,
            dry_run=args.dry_run,
            config=config,
            workers=args.workers,
            batch_size=args.batch_size,
            include_gitignored=args.include_gitignored,
            force=args.force,
            keep_backups=args.keep_backups,
            no_cleanup=args.no_cleanup,
            no_commit=args.no_commit
        )
        sync.run()
    except KeyboardInterrupt:
        print_color(Colors.YELLOW, "\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.ERROR, f"\nError: {e}")
        if os.getenv('DEBUG'):
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()