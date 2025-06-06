"""
Analyzers for commits and files to generate changelog content.
"""
import os
import pathlib
import re
import subprocess
from typing import Dict, List, Optional, Set, Tuple
from functools import lru_cache

from .models import GitCommit
from tooling.core.logging import get_logger

logger = get_logger(__name__)


class CommitAnalyzer:
    """Analyze git commits for changelog generation."""
    
    def __init__(self, package: str):
        self.package = package
    
    def analyze_commits(self, commits: List[GitCommit]) -> str:
        """Analyze commits and return context summary"""
        if not commits:
            return "No commits to analyze."
        
        # Group commits by type
        by_type = self._group_by_type(commits)
        
        # Build context
        context_parts = []
        
        # Summary
        context_parts.append(f"Analyzed {len(commits)} commits for {self.package}:")
        context_parts.append("")
        
        # Type breakdown
        for commit_type, type_commits in by_type.items():
            context_parts.append(f"- {commit_type}: {len(type_commits)} commits")
        
        context_parts.append("")
        
        # Key changes by type
        context_parts.append("Key changes by type:")
        for commit_type, type_commits in by_type.items():
            if type_commits:
                context_parts.append(f"\n{commit_type}:")
                # Show first few commits of each type
                for commit in type_commits[:3]:
                    msg = commit.message.split('\n')[0]
                    if len(msg) > 80:
                        msg = msg[:77] + "..."
                    context_parts.append(f"  - {msg}")
                if len(type_commits) > 3:
                    context_parts.append(f"  ... and {len(type_commits) - 3} more")
        
        return '\n'.join(context_parts)
    
    def _group_by_type(self, commits: List[GitCommit]) -> Dict[str, List[GitCommit]]:
        """Group commits by their conventional type"""
        groups = {
            'Features': [],
            'Bug Fixes': [],
            'Documentation': [],
            'Refactoring': [],
            'Tests': [],
            'Build/CI': [],
            'Other': []
        }
        
        for commit in commits:
            if commit.conventional:
                commit_type = commit.conventional.type
                if commit_type in ['feat', 'feature']:
                    groups['Features'].append(commit)
                elif commit_type in ['fix', 'bugfix']:
                    groups['Bug Fixes'].append(commit)
                elif commit_type in ['docs', 'doc']:
                    groups['Documentation'].append(commit)
                elif commit_type in ['refactor', 'refact']:
                    groups['Refactoring'].append(commit)
                elif commit_type in ['test', 'tests']:
                    groups['Tests'].append(commit)
                elif commit_type in ['build', 'ci', 'chore']:
                    groups['Build/CI'].append(commit)
                else:
                    groups['Other'].append(commit)
            else:
                # Try to infer from message
                msg_lower = commit.message.lower()
                if any(word in msg_lower for word in ['add', 'feature', 'implement']):
                    groups['Features'].append(commit)
                elif any(word in msg_lower for word in ['fix', 'bug', 'issue']):
                    groups['Bug Fixes'].append(commit)
                elif any(word in msg_lower for word in ['doc', 'readme']):
                    groups['Documentation'].append(commit)
                elif any(word in msg_lower for word in ['refactor', 'clean']):
                    groups['Refactoring'].append(commit)
                elif any(word in msg_lower for word in ['test', 'spec']):
                    groups['Tests'].append(commit)
                else:
                    groups['Other'].append(commit)
        
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}


class FileAnalyzer:
    """Analyze files changed in commits."""
    
    def __init__(self, package: str, commits: List[GitCommit], 
                 include_gitignored: bool = False):
        self.package = package
        self.commits = commits
        self.include_gitignored = include_gitignored
        self._all_files = self._collect_all_files()
    
    def _collect_all_files(self) -> Set[str]:
        """Collect all unique files from commits"""
        files = set()
        for commit in self.commits:
            files.update(commit.files)
        return files
    
    def analyze_files(self, version: str) -> Tuple[List[str], str]:
        """Analyze files and return (selected_files, context)
        
        Returns:
            Tuple of (list of relevant files, analysis context)
        """
        # Filter files by package
        package_files = self._filter_by_package(list(self._all_files))
        
        if not package_files:
            return [], f"No files changed in {self.package} for version {version}"
        
        # Prioritize files
        prioritized = self._prioritize_files(package_files)
        
        # Select most relevant files (limit to avoid token limits)
        selected = prioritized[:50]  # Top 50 files
        
        # Build file inventory
        inventory = self._build_file_inventory(selected, version)
        
        return selected, inventory
    
    def _filter_by_package(self, files: List[str]) -> List[str]:
        """Filter files belonging to this package"""
        # Package patterns (simplified from original)
        patterns = {
            'root': r'^(?!dart/|flutter/).*$',
            'dart': r'^dart/(?!rust/).*$',
            'flutter': r'^flutter/.*$',
            'rust': r'^dart/rust/.*$'
        }
        
        pattern = patterns.get(self.package, r'.*')
        regex = re.compile(pattern)
        
        filtered = []
        for file in files:
            if regex.match(file):
                # Skip gitignored unless requested
                if not self.include_gitignored and self._is_gitignored(file):
                    continue
                # Skip hidden files
                if file.startswith('.') or '/.git/' in file:
                    continue
                filtered.append(file)
        
        return filtered
    
    @lru_cache(maxsize=1000)
    def _is_gitignored(self, file_path: str) -> bool:
        """Check if file is gitignored"""
        try:
            result = subprocess.run(
                ['git', 'check-ignore', file_path],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _prioritize_files(self, files: List[str]) -> List[str]:
        """Prioritize files by importance"""
        def score_file(file_path: str) -> int:
            score = 0
            path = pathlib.Path(file_path)
            
            # File type scoring
            if path.suffix in ['.py', '.dart', '.rs', '.go', '.js', '.ts']:
                score += 10
            elif path.suffix in ['.yaml', '.yml', '.toml', '.json']:
                score += 8
            elif path.suffix in ['.md', '.txt', '.rst']:
                score += 5
            
            # Special files
            name_lower = path.name.lower()
            if name_lower in ['readme.md', 'changelog.md', 'setup.py', 'pyproject.toml',
                              'pubspec.yaml', 'cargo.toml', 'package.json']:
                score += 20
            elif name_lower.startswith('test_') or name_lower.endswith('_test.py'):
                score += 3
            
            # Directory importance
            parts = path.parts
            if 'src' in parts or 'lib' in parts:
                score += 5
            elif 'test' in parts or 'tests' in parts:
                score += 2
            elif 'docs' in parts or 'documentation' in parts:
                score += 3
            
            # Penalize deeply nested files
            score -= len(parts) // 3
            
            return score
        
        # Sort by score (highest first)
        return sorted(files, key=score_file, reverse=True)
    
    def _build_file_inventory(self, files: List[str], version: str) -> str:
        """Build a summary of file changes"""
        if not files:
            return f"No file changes for {self.package} in version {version}"
        
        inventory_parts = [
            f"File changes for {self.package} version {version}:",
            f"Total files changed: {len(self._all_files)}",
            f"Package files: {len(files)}",
            "",
            "Key files changed:"
        ]
        
        # Group by directory
        by_dir = {}
        for file in files[:30]:  # Show first 30
            dir_path = os.path.dirname(file) or 'root'
            if dir_path not in by_dir:
                by_dir[dir_path] = []
            by_dir[dir_path].append(os.path.basename(file))
        
        # Show files by directory
        for dir_path in sorted(by_dir.keys()):
            inventory_parts.append(f"\n{dir_path}/")
            for filename in sorted(by_dir[dir_path])[:5]:  # Max 5 per dir
                inventory_parts.append(f"  - {filename}")
            if len(by_dir[dir_path]) > 5:
                inventory_parts.append(f"  ... and {len(by_dir[dir_path]) - 5} more")
        
        if len(files) > 30:
            inventory_parts.append(f"\n... and {len(files) - 30} more files")
        
        # Add file type summary
        inventory_parts.extend([
            "",
            "File types changed:"
        ])
        
        # Count extensions
        ext_counts = {}
        for file in files:
            ext = pathlib.Path(file).suffix or 'no extension'
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        
        # Show top extensions
        for ext, count in sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            inventory_parts.append(f"  - {ext}: {count} files")
        
        return '\n'.join(inventory_parts) 