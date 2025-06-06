"""
Changelog management utilities.

This module provides comprehensive changelog management functionality:
- Parsing and validation
- Generation from commits
- Merging and synchronization
- Conventional commit support
"""

from .parser import ChangelogParser
from .generator import ChangelogGenerator
from .analyzer import CommitAnalyzer, FileAnalyzer
from .git_operations import ChangelogGitOps
from .models import (
    GitCommit, ConventionalCommit, VersionEntry,
    AnalysisMode, AnalysisMetrics, CHANGELOG_SECTIONS, CONVENTIONAL_TYPES
)

__all__ = [
    'ChangelogParser',
    'ChangelogGenerator',
    'CommitAnalyzer',
    'FileAnalyzer',
    'ChangelogGitOps',
    'GitCommit',
    'ConventionalCommit',
    'VersionEntry',
    'AnalysisMode',
    'AnalysisMetrics',
    'CHANGELOG_SECTIONS',
    'CONVENTIONAL_TYPES',
] 