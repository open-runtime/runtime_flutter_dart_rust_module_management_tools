#!/usr/bin/env python3
"""
Analyze git history and changelog entries to help users choose backfill range

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import subprocess
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict
import argparse

class ChangelogHistoryAnalyzer:
    def __init__(self):
        self.changelogs = {
            'dart': 'dart/CHANGELOG.md',
            'flutter': 'flutter/CHANGELOG.md', 
            'rust': 'dart/rust/CHANGELOG.md'
        }
        
    def get_git_history_range(self):
        """Get the date range of all commits in the repository"""
        try:
            # Get first commit date - get ALL commits and take the first one
            first_commit_result = subprocess.run(
                ['git', 'log', '--reverse', '--format=%ad', '--date=short'],
                capture_output=True, text=True
            )
            first_commit = first_commit_result.stdout.strip().split('\n')[0] if first_commit_result.stdout else None
            
            # Get last commit date
            last_commit = subprocess.run(
                ['git', 'log', '--format=%ad', '--date=short', '-1'],
                capture_output=True, text=True
            ).stdout.strip()
            
            return first_commit, last_commit
        except:
            return None, None
    
    def get_version_dates(self, changelog_path):
        """Extract all version numbers and their dates from a changelog"""
        versions = []
        
        if not os.path.exists(changelog_path):
            return versions
            
        with open(changelog_path, 'r') as f:
            content = f.read()
            
        # Find all version headers with dates
        pattern = r'^##\s+\[v(\d+\.\d+\.\d+)\]\s*-\s*(\d{4}-\d{2}-\d{2})'
        matches = re.findall(pattern, content, re.MULTILINE)
        
        for version, date in matches:
            versions.append({
                'version': f'v{version}',
                'date': date,
                'has_content': self._check_version_has_content(content, version)
            })
            
        return sorted(versions, key=lambda x: x['date'], reverse=True)
    
    def _check_version_has_content(self, content, version):
        """Check if a version section has meaningful content"""
        # Extract the version section
        pattern = rf'^##\s+\[v{re.escape(version)}\].*?\n(.*?)(?=^##\s+\[v|\Z)'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        
        if not match:
            return False
            
        section_content = match.group(1).strip()
        
        # Count non-empty lines (excluding section headers)
        content_lines = [line for line in section_content.split('\n') 
                        if line.strip() and not line.startswith('###')]
        
        return len(content_lines) > 1
    
    def get_commits_by_date_range(self, start_date, end_date=None):
        """Get commit count between dates
        
        If end_date is provided: count commits between start_date and end_date
        If end_date is None: count commits from start_date to now
        """
        if end_date:
            # Specific range: from start_date to end_date
            cmd = ['git', 'log', '--oneline', f'--since={start_date}', f'--until={end_date}']
        else:
            # From start_date to now
            cmd = ['git', 'log', '--oneline', f'--since={start_date}']
            
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
            return len(commits)
        except:
            return 0
    
    def get_all_commits_count(self):
        """Get total count of all commits in the repository"""
        try:
            result = subprocess.run(['git', 'log', '--oneline'], capture_output=True, text=True)
            commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
            return len(commits)
        except:
            return 0
    
    def analyze_undocumented_periods(self):
        """Analyze periods that might need documentation"""
        analysis = {}
        
        for package, changelog_path in self.changelogs.items():
            versions = self.get_version_dates(changelog_path)
            
            undocumented_periods = []
            
            # Check for empty versions
            for v in versions:
                if not v['has_content']:
                    undocumented_periods.append({
                        'type': 'empty_version',
                        'version': v['version'],
                        'date': v['date']
                    })
            
            # Check for gaps between versions
            for i in range(len(versions) - 1):
                current = datetime.strptime(versions[i]['date'], '%Y-%m-%d')
                next_ver = datetime.strptime(versions[i + 1]['date'], '%Y-%m-%d')
                
                gap_days = (current - next_ver).days
                
                if gap_days > 30:  # Significant gap
                    commits = self.get_commits_by_date_range(
                        versions[i + 1]['date'], 
                        versions[i]['date']
                    )
                    
                    if commits > 5:  # Significant activity
                        undocumented_periods.append({
                            'type': 'gap',
                            'start_date': versions[i + 1]['date'],
                            'end_date': versions[i]['date'],
                            'gap_days': gap_days,
                            'commits': commits
                        })
            
            analysis[package] = {
                'versions': versions,
                'undocumented_periods': undocumented_periods
            }
            
        return analysis
    
    def present_backfill_options(self):
        """Present interactive backfill options to the user"""
        print("\n" + "="*60)
        print("CHANGELOG BACKFILL ANALYZER")
        print("="*60)
        
        # Get repository date range
        first_commit, last_commit = self.get_git_history_range()
        if first_commit:
            print(f"\nRepository history: {first_commit} to {last_commit}")
        
        # Analyze each package
        analysis = self.analyze_undocumented_periods()
        
        print("\n" + "-"*60)
        print("PACKAGE ANALYSIS")
        print("-"*60)
        
        suggested_dates = set()
        
        for package, data in analysis.items():
            print(f"\n{package.upper()} Package:")
            
            versions = data['versions']
            if versions:
                print(f"  Latest version: {versions[0]['version']} ({versions[0]['date']})")
                print(f"  Oldest version: {versions[-1]['version']} ({versions[-1]['date']})")
                print(f"  Total versions: {len(versions)}")
                
                # Add oldest version date as a suggestion
                suggested_dates.add(versions[-1]['date'])
            
            undoc = data['undocumented_periods']
            if undoc:
                print(f"\n  Potential gaps:")
                for period in undoc:
                    if period['type'] == 'empty_version':
                        print(f"    - Empty version: {period['version']} ({period['date']})")
                        suggested_dates.add(period['date'])
                    else:
                        print(f"    - Gap: {period['start_date']} to {period['end_date']} "
                              f"({period['gap_days']} days, {period['commits']} commits)")
                        suggested_dates.add(period['start_date'])
        
        # Present backfill options
        print("\n" + "="*60)
        print("BACKFILL OPTIONS")
        print("="*60)
        
        options = []
        
        # Add common time-based options
        today = datetime.now()
        options.extend([
            ('1 week ago', (today - timedelta(days=7)).strftime('%Y-%m-%d')),
            ('1 month ago', (today - timedelta(days=30)).strftime('%Y-%m-%d')),
            ('3 months ago', (today - timedelta(days=90)).strftime('%Y-%m-%d')),
            ('6 months ago', (today - timedelta(days=180)).strftime('%Y-%m-%d')),
            ('1 year ago', (today - timedelta(days=365)).strftime('%Y-%m-%d')),
        ])
        
        # Add suggested dates based on analysis
        for date in sorted(suggested_dates, reverse=True):
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            days_ago = (today - date_obj).days
            
            if days_ago > 7:  # Don't duplicate recent dates
                label = f"Since {date} ({days_ago} days ago)"
                options.append((label, date))
        
        # Add "all history" option
        if first_commit:
            options.append(('All history', first_commit))
        
        # Remove duplicates and sort by date
        seen_dates = set()
        unique_options = []
        all_history_option = None
        
        for label, date in options:
            if date not in seen_dates:
                seen_dates.add(date)
                if 'All history' in label:
                    # Save "All history" option to add at the end
                    all_history_option = (label, date)
                else:
                    unique_options.append((label, date))
        
        # Sort by date (newest first)
        unique_options.sort(key=lambda x: x[1], reverse=True)
        
        # Add "All history" at the end if it exists
        if all_history_option:
            unique_options.append(all_history_option)
        
        print("\nChoose how far back to analyze for changelog updates:\n")
        
        for i, (label, date) in enumerate(unique_options, 1):
            if 'All history' in label:
                # For "All history", show total commit count
                commits = self.get_all_commits_count()
            else:
                # For date-based options, show commits from that date to now
                commits = self.get_commits_by_date_range(date)
            print(f"  {i}. {label:<40} (~{commits} commits)")
        
        print(f"\n  0. Cancel")
        
        # Get user choice
        while True:
            try:
                choice = input("\nEnter your choice (0-{}): ".format(len(unique_options)))
                choice_num = int(choice)
                
                if choice_num == 0:
                    print("Cancelled.")
                    return None
                elif 1 <= choice_num <= len(unique_options):
                    selected_date = unique_options[choice_num - 1][1]
                    print(f"\nSelected: Backfill from {selected_date}")
                    return selected_date
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")
            except KeyboardInterrupt:
                print("\nCancelled.")
                return None

def main():
    parser = argparse.ArgumentParser(
        description="Analyze changelog history and present backfill options"
    )
    parser.add_argument(
        '--auto-run',
        action='store_true',
        help='Automatically run sync_changelogs.py with selected date'
    )
    
    args = parser.parse_args()
    
    analyzer = ChangelogHistoryAnalyzer()
    selected_date = analyzer.present_backfill_options()
    
    if selected_date and args.auto_run:
        print(f"\nRunning sync_changelogs.py with backfill from {selected_date}...")
        
        # Set environment variable for the sync script
        env = os.environ.copy()
        env['CHANGELOG_BACKFILL_DATE'] = selected_date
        
        # Run the sync script
        cmd = ['python3', 'tooling/sync_changelogs.py', '--smart-historical']
        subprocess.run(cmd, env=env)

if __name__ == "__main__":
    main() 