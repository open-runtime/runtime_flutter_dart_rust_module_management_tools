# Upgrade Plan: analyze_changelog_history.py

## Overview
Analyzes git history and changelog entries to help users choose backfill range for changelog generation. Currently uses subprocess for git commands and manual parsing.

## Current State
- **Dependencies**: Standard library only
- **Key Features**: Interactive date range selection, gap detection, changelog coverage analysis
- **Code Quality**: Well-structured with ChangelogHistoryAnalyzer class

## Recommended Upgrades

### 1. Enhanced Git Integration
```python
# Replace subprocess with GitPython
import git
from git import Repo
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

class GitHistoryAnalyzer:
    def __init__(self, repo_path: str = '.'):
        self.repo = Repo(repo_path)
    
    def get_commits_by_date_range(
        self, 
        start_date: str, 
        end_date: Optional[str] = None
    ) -> List[git.Commit]:
        """Get commits within date range using GitPython"""
        commits = list(self.repo.iter_commits(
            since=start_date,
            until=end_date or 'HEAD',
            all=True  # Include all branches
        ))
        return commits
    
    def analyze_commit_frequency(self) -> Dict[str, int]:
        """Analyze commit frequency by month"""
        from collections import defaultdict
        frequency = defaultdict(int)
        
        for commit in self.repo.iter_commits():
            month_key = commit.authored_datetime.strftime('%Y-%m')
            frequency[month_key] += 1
        
        return dict(frequency)
```

### 2. Advanced Changelog Parsing
```python
# Use dataclasses and regex patterns
from dataclasses import dataclass
from typing import List, Optional
import re

@dataclass
class VersionInfo:
    version: str
    date: Optional[str]
    has_content: bool
    line_number: int
    
@dataclass
class ChangelogEntry:
    type: str  # Added, Changed, Fixed, etc.
    description: str
    pr_number: Optional[int]
    
class ChangelogParser:
    VERSION_PATTERN = re.compile(
        r'^##\s+\[v?(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)\]\s*(?:-\s*)?(\d{4}-\d{2}-\d{2})?',
        re.MULTILINE
    )
    
    ENTRY_PATTERN = re.compile(
        r'^\s*[-*]\s+(.+?)(?:\s+\(#(\d+)\))?$',
        re.MULTILINE
    )
    
    def parse_changelog(self, content: str) -> List[VersionInfo]:
        """Parse changelog with better structure"""
        versions = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            match = self.VERSION_PATTERN.match(line)
            if match:
                version = match.group(1)
                date = match.group(2)
                
                # Check if version has content
                has_content = self._version_has_content(lines, i)
                
                versions.append(VersionInfo(
                    version=version,
                    date=date,
                    has_content=has_content,
                    line_number=i + 1
                ))
        
        return versions
```

### 3. Interactive UI Enhancement
```python
# Use rich for better terminal UI
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.progress import track

console = Console()

class InteractiveAnalyzer:
    def display_analysis_results(self, results: Dict[str, Any]):
        """Display results with rich formatting"""
        # Create summary table
        table = Table(title="Changelog Coverage Analysis")
        table.add_column("Package", style="cyan", width=15)
        table.add_column("Total Versions", justify="right")
        table.add_column("Empty Versions", justify="right", style="red")
        table.add_column("Coverage %", justify="right", style="green")
        
        for package, stats in results.items():
            coverage = (stats['with_content'] / stats['total']) * 100
            table.add_row(
                package,
                str(stats['total']),
                str(stats['empty']),
                f"{coverage:.1f}%"
            )
        
        console.print(table)
    
    def select_date_range(self, suggestions: List[Tuple[str, str]]) -> Tuple[str, str]:
        """Interactive date range selection with rich"""
        console.print(Panel("📅 Select date range for changelog backfill"))
        
        # Display suggestions
        choices = []
        for i, (start, end) in enumerate(suggestions, 1):
            desc = f"{start} to {end}"
            choices.append(f"{i}. {desc}")
            
        console.print("\n".join(choices))
        
        choice = Prompt.ask(
            "Select an option or enter custom range (YYYY-MM-DD to YYYY-MM-DD)",
            default="1"
        )
        
        # Parse choice
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(suggestions):
                return suggestions[idx]
        
        # Parse custom range
        if " to " in choice:
            parts = choice.split(" to ")
            return parts[0].strip(), parts[1].strip()
        
        return suggestions[0]  # Default
```

### 4. Gap Detection Algorithm
```python
# Improved gap detection with analytics
from datetime import datetime, timedelta
from typing import List, Tuple

class GapDetector:
    def __init__(self, threshold_days: int = 30):
        self.threshold_days = threshold_days
    
    def find_changelog_gaps(
        self,
        commit_dates: List[datetime],
        changelog_dates: List[datetime]
    ) -> List[Tuple[datetime, datetime]]:
        """Find gaps where commits exist but changelog doesn't"""
        gaps = []
        
        # Sort dates
        commit_dates = sorted(commit_dates)
        changelog_dates = set(changelog_dates)
        
        # Group commits by month
        from itertools import groupby
        
        for month, commits in groupby(commit_dates, key=lambda d: d.strftime('%Y-%m')):
            commits_list = list(commits)
            
            # Check if any changelog entry exists for this month
            has_changelog = any(
                d.strftime('%Y-%m') == month 
                for d in changelog_dates
            )
            
            if not has_changelog and len(commits_list) > 5:  # Significant activity
                gaps.append((
                    min(commits_list),
                    max(commits_list)
                ))
        
        return self._merge_adjacent_gaps(gaps)
    
    def _merge_adjacent_gaps(
        self,
        gaps: List[Tuple[datetime, datetime]]
    ) -> List[Tuple[datetime, datetime]]:
        """Merge adjacent gaps within threshold"""
        if not gaps:
            return []
        
        merged = [gaps[0]]
        
        for current in gaps[1:]:
            last = merged[-1]
            
            # Check if gaps are adjacent
            if (current[0] - last[1]).days <= self.threshold_days:
                # Merge
                merged[-1] = (last[0], current[1])
            else:
                merged.append(current)
        
        return merged
```

### 5. Async Parallel Analysis
```python
# Analyze multiple changelogs in parallel
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

class AsyncChangelogAnalyzer:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def analyze_all_changelogs(
        self,
        changelog_paths: Dict[str, str]
    ) -> Dict[str, List[VersionInfo]]:
        """Analyze all changelogs in parallel"""
        tasks = []
        
        for package, path in changelog_paths.items():
            task = asyncio.create_task(
                self.analyze_changelog_async(package, path)
            )
            tasks.append((package, task))
        
        results = {}
        for package, task in tasks:
            results[package] = await task
        
        return results
    
    async def analyze_changelog_async(
        self,
        package: str,
        path: str
    ) -> List[VersionInfo]:
        """Analyze single changelog asynchronously"""
        loop = asyncio.get_event_loop()
        
        # Run blocking I/O in executor
        content = await loop.run_in_executor(
            self.executor,
            self._read_file,
            path
        )
        
        # Parse in executor for CPU-bound work
        versions = await loop.run_in_executor(
            self.executor,
            self._parse_changelog,
            content
        )
        
        return versions
```

### 6. Export and Reporting
```python
# Generate various report formats
from pathlib import Path
import json
import csv

class AnalysisReporter:
    def __init__(self, output_dir: Path = Path('changelog_reports')):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_json_report(self, analysis: Dict[str, Any]) -> Path:
        """Generate JSON report"""
        report_path = self.output_dir / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_path, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        return report_path
    
    def generate_csv_report(self, gaps: List[Tuple[str, str]]) -> Path:
        """Generate CSV report of gaps"""
        report_path = self.output_dir / "changelog_gaps.csv"
        
        with open(report_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Start Date', 'End Date', 'Duration (days)'])
            
            for start, end in gaps:
                duration = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days
                writer.writerow([start, end, duration])
        
        return report_path
    
    def generate_markdown_summary(self, analysis: Dict[str, Any]) -> Path:
        """Generate markdown summary"""
        report_path = self.output_dir / "changelog_analysis.md"
        
        with open(report_path, 'w') as f:
            f.write("# Changelog Analysis Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Coverage summary
            f.write("## Coverage Summary\n\n")
            f.write("| Package | Total Versions | Empty | Coverage |\n")
            f.write("|---------|----------------|-------|----------|\n")
            
            for package, stats in analysis['coverage'].items():
                coverage = (stats['with_content'] / stats['total']) * 100
                f.write(f"| {package} | {stats['total']} | {stats['empty']} | {coverage:.1f}% |\n")
        
        return report_path
```

## Dependencies to Add
```toml
[project.dependencies]
GitPython = "^3.1.40"
rich = "^13.7.0"
click = "^8.1.7"
python-dateutil = "^2.8.2"
pandas = "^2.1.4"  # For advanced date analysis
asyncio = "^3.4.3"
aiofiles = "^23.2.1"
```

## Migration Strategy
1. Add GitPython integration alongside subprocess
2. Implement rich UI as optional enhancement
3. Add async analysis for performance
4. Create comprehensive test suite
5. Add export functionality

## Expected Benefits
- **Performance**: 3x faster with parallel analysis
- **User Experience**: Better interactive UI with rich
- **Accuracy**: More reliable git operations
- **Flexibility**: Multiple export formats
- **Maintainability**: Cleaner code with proper abstractions