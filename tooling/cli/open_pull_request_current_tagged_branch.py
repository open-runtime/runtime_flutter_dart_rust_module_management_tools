#!/usr/bin/env python3
"""
open_pull_request_current_tagged_branch.py - Open or update a PR for the current branch with AI analysis

This script automates opening or updating a pull request for any branch with:
1. AI-powered analysis of changes using Gemini 2.5 Pro
2. Automatic changelog extraction if available
3. Comprehensive file change summary
4. Smart PR title and body generation
5. Update existing PRs with fresh AI-generated content

Features:
- Creates new PRs or updates existing ones
- Shows diff of changes when updating
- Intelligent label detection
- Fallback to basic PR creation if AI unavailable

Requires: Python 3.6+, GitHub CLI (gh), Gemini API (optional)

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import re
import subprocess
import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Add the script directory to Python path for imports
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Import our common configuration
try:
    # Support both direct execution and package imports
import sys
import os

# Add parent directory to path for direct execution
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try package import first (when installed via pip)
    from tooling.core.common_config import *
except ImportError:
    # Fall back to direct import (when running file directly)
    from core.common_config import *
except ImportError:
    print("Error: Could not import common_config.py", file=sys.stderr)
    print("Make sure common_config.py exists in the same directory", file=sys.stderr)
    sys.exit(1)

# ============================================================================
# GEMINI INTEGRATION
# ============================================================================

def run_gemini_command(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Run a command through gemini-cli using stdin like other tools"""
    if not check_gemini_cli():
        return None
    
    # Use provided model or default
    if not model:
        model = GEMINI_MODEL_PRO
    
    try:
        # Use subprocess.Popen for better control like other scripts
        process = subprocess.Popen(
            ['gemini-cli', 'prompt', '-', '--model', model],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send prompt via stdin with timeout
        stdout, stderr = process.communicate(input=prompt, timeout=60)
        
        if process.returncode == 0 and stdout:
            # Clean the response
            response = stdout.strip()
            # Remove any markdown code blocks if present
            response = re.sub(r'^```[a-zA-Z0-9_-]*\s*$', '', response, flags=re.MULTILINE)
            response = response.replace('```', '')
            return response.strip()
        else:
            if stderr:
                print_color(Colors.YELLOW, f"Gemini error: {stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        process.kill()
        print_color(Colors.YELLOW, "Gemini request timed out")
        return None
    except Exception as e:
        print_color(Colors.YELLOW, f"Error calling Gemini: {e}")
        return None

# ============================================================================
# CONSTANTS
# ============================================================================

# Branch patterns for different types
RELEASE_BRANCH_PATTERN = re.compile(r'^chore/release-v(\d+\.\d+\.\d+)$')
FEATURE_BRANCH_PATTERN = re.compile(r'^feature/(.+)$')
FIX_BRANCH_PATTERN = re.compile(r'^fix/(.+)$')
CHORE_BRANCH_PATTERN = re.compile(r'^chore/(.+)$')

# Gemini model for detailed analysis
GEMINI_MODEL_PRO = "gemini-2.5-pro-preview-05-06"

# ============================================================================
# GIT OPERATIONS
# ============================================================================

def run_command(cmd: List[str], capture=True) -> Tuple[int, str, str]:
    """Run a command and return (exit_code, stdout, stderr)"""
    try:
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        else:
            result = subprocess.run(cmd)
            return result.returncode, "", ""
    except Exception as e:
        return 1, "", str(e)

def get_current_branch() -> Optional[str]:
    """Get the current Git branch"""
    code, branch, _ = run_command(['git', 'branch', '--show-current'])
    return branch if code == 0 else None

def get_default_branch() -> str:
    """Get the default branch (main/master)"""
    # Try to get from git config
    code, branch, _ = run_command(['git', 'config', '--get', 'init.defaultBranch'])
    if code == 0 and branch:
        return branch
    
    # Check which exists
    for branch in ['main', 'master']:
        code, _, _ = run_command(['git', 'show-ref', '--verify', f'refs/heads/{branch}'])
        if code == 0:
            return branch
    
    return 'main'  # Default fallback

def get_branch_tag() -> Optional[str]:
    """Get tag associated with current branch if any"""
    code, tag, _ = run_command(['git', 'describe', '--exact-match', '--tags', 'HEAD'])
    if code == 0 and tag:
        return tag
    return None

def get_latest_tag_on_branch() -> Optional[str]:
    """Get the latest tag reachable from current branch"""
    code, tag, _ = run_command(['git', 'describe', '--tags', '--abbrev=0'])
    if code == 0 and tag:
        return tag
    return None

def get_changed_files(base_branch: str) -> List[str]:
    """Get list of files changed compared to base branch"""
    code, output, _ = run_command(['git', 'diff', '--name-only', f'{base_branch}...HEAD'])
    if code == 0 and output:
        return output.strip().split('\n')
    return []

def get_commit_messages(base_branch: str) -> List[str]:
    """Get commit messages between base branch and HEAD"""
    code, output, _ = run_command(['git', 'log', '--oneline', f'{base_branch}..HEAD'])
    if code == 0 and output:
        return output.strip().split('\n')
    return []

def get_diff_summary(base_branch: str) -> str:
    """Get a summary of changes"""
    code, output, _ = run_command(['git', 'diff', '--stat', f'{base_branch}...HEAD'])
    if code == 0 and output:
        return output
    return ""

def check_branch_exists_remote(branch: str) -> bool:
    """Check if branch exists on remote"""
    code, _, _ = run_command(['git', 'ls-remote', '--heads', 'origin', branch])
    return code == 0

def push_branch(branch: str) -> bool:
    """Push branch to remote"""
    print(f"Pushing branch '{branch}' to remote...")
    code, _, err = run_command(['git', 'push', '-u', 'origin', branch])
    if code != 0:
        print_color(Colors.RED, f"Failed to push branch: {err}")
        return False
    return True

# ============================================================================
# AI ANALYSIS
# ============================================================================

def analyze_changes_with_ai(branch: str, base_branch: str, changed_files: List[str], 
                          commit_messages: List[str], diff_summary: str,
                          changelog_summary: str, tag: Optional[str]) -> Dict[str, str]:
    """Use Gemini AI to analyze changes and generate PR content"""
    
    # Get more detailed file analysis
    file_categories = categorize_files(changed_files)
    
    # Get detailed commit analysis
    commit_analysis = analyze_commits(commit_messages)
    
    # Get actual file diffs for key files
    key_diffs = get_key_file_diffs(changed_files[:10], base_branch)
    
    # Prepare comprehensive context for AI
    context = f"""Analyze the following changes for a pull request from branch '{branch}' to '{base_branch}'.

BRANCH INFORMATION:
- Current Branch: {branch}
- Base Branch: {base_branch}
- Associated Tag: {tag if tag else 'No tag associated'}

FILE CHANGES OVERVIEW ({len(changed_files)} files total):
{format_file_categories(file_categories)}

COMMIT ANALYSIS ({len(commit_messages)} commits):
{commit_analysis}

KEY FILE DIFFS:
{key_diffs}

DIFF STATISTICS:
{diff_summary[:1500]}

CHANGELOG ENTRIES:
{changelog_summary if changelog_summary else 'No formal changelog entries found'}

ANALYSIS REQUIREMENTS:
1. Create a clear, professional PR title using conventional commit format when appropriate
2. Write a comprehensive PR description that includes:
   - Executive summary (2-3 sentences about the overall change)
   - Detailed changes by category/package
   - Breaking changes with migration guide (if any)
   - Testing recommendations
   - Performance implications
   - Dependencies affected
   - Related issues or context
   - Review focus areas

3. Structure the description with clear sections using markdown headers
4. Include code examples or configuration changes where relevant
5. Highlight any security considerations

Format the response as JSON with keys: "title", "description"
"""

    # Create enhanced prompt for Gemini
    prompt = f"""You are a senior software engineer and technical writer creating a pull request for a vector search library.
Your task is to create a comprehensive PR that will help reviewers understand the changes quickly and thoroughly.

{context}

Guidelines:
- The title should be concise but descriptive (50-72 chars ideal)
- Use conventional commit format for the title when it makes sense
- The description should be thorough but well-organized
- Use markdown formatting for clarity (headers, lists, code blocks)
- Focus on the impact and value of changes, not just what changed
- Make it easy for reviewers to know what to focus on

Return a JSON object with:
- "title": A clear, professional PR title
- "description": A comprehensive, well-formatted PR description

Output ONLY valid JSON without any markdown code block markers."""

    try:
        # Use Gemini Pro for comprehensive analysis
        result = run_gemini_command(prompt, model=GEMINI_MODEL_PRO)
        
        if result:
            # Try to parse JSON response
            try:
                # Clean up potential JSON formatting issues
                result = result.strip()
                if result.startswith('```'):
                    result = result.split('```')[1]
                    if result.startswith('json'):
                        result = result[4:]
                
                data = json.loads(result)
                
                # Ensure we have good content
                title = data.get('title', '').strip()
                description = data.get('description', '').strip()
                
                if not title:
                    title = generate_fallback_title(branch, file_categories)
                
                if not description:
                    description = generate_fallback_description(
                        branch, base_branch, changed_files, 
                        commit_messages, changelog_summary
                    )
                
                return {
                    'title': title,
                    'description': description
                }
                
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract title and description
                lines = result.strip().split('\n')
                title = lines[0] if lines else f'Update {branch}'
                description = '\n'.join(lines[1:]) if len(lines) > 1 else result
                
                return {
                    'title': title.strip(),
                    'description': description.strip()
                }
    except Exception as e:
        print_color(Colors.YELLOW, f"AI analysis failed: {e}")
    
    # Enhanced fallback
    return {
        'title': generate_fallback_title(branch, file_categories),
        'description': generate_fallback_description(
            branch, base_branch, changed_files, 
            commit_messages, changelog_summary
        )
    }

def categorize_files(files: List[str]) -> Dict[str, List[str]]:
    """Categorize files by type and package"""
    categories = {
        'dart': [],
        'flutter': [],
        'rust': [],
        'documentation': [],
        'configuration': [],
        'tooling': [],
        'tests': [],
        'ci': [],
        'other': []
    }
    
    for file in files:
        if file.startswith('dart/rust/'):
            categories['rust'].append(file)
        elif file.startswith('flutter/'):
            categories['flutter'].append(file)
        elif file.startswith('dart/'):
            categories['dart'].append(file)
        elif file.startswith('tooling/'):
            categories['tooling'].append(file)
        elif file.startswith('.github/') or 'workflow' in file:
            categories['ci'].append(file)
        elif file.endswith(('.md', '.rst', '.txt')):
            categories['documentation'].append(file)
        elif file.endswith(('.yaml', '.yml', '.toml', '.json', '.xml')):
            categories['configuration'].append(file)
        elif 'test' in file.lower():
            categories['tests'].append(file)
        else:
            categories['other'].append(file)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v}

def format_file_categories(categories: Dict[str, List[str]]) -> str:
    """Format file categories for display"""
    lines = []
    for category, files in categories.items():
        if files:
            lines.append(f"{category.upper()} ({len(files)} files):")
            for file in files[:5]:
                lines.append(f"  - {file}")
            if len(files) > 5:
                lines.append(f"  ... and {len(files) - 5} more")
    return '\n'.join(lines)

def analyze_commits(commit_messages: List[str]) -> str:
    """Analyze commit messages for patterns"""
    types = {
        'feat': 0, 'fix': 0, 'docs': 0, 'style': 0,
        'refactor': 0, 'perf': 0, 'test': 0, 'chore': 0,
        'build': 0, 'ci': 0, 'other': 0
    }
    
    for msg in commit_messages:
        # Extract commit type
        if match := re.match(r'^(\w+)(?:\([^)]+\))?:', msg):
            commit_type = match.group(1)
            if commit_type in types:
                types[commit_type] += 1
            else:
                types['other'] += 1
        else:
            types['other'] += 1
    
    # Format analysis
    lines = ["Commit Types:"]
    for type_name, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            lines.append(f"  - {type_name}: {count}")
    
    # Show recent commits
    lines.append("\nRecent Commits:")
    for msg in commit_messages[:10]:
        lines.append(f"  - {msg}")
    
    if len(commit_messages) > 10:
        lines.append(f"  ... and {len(commit_messages) - 10} more")
    
    return '\n'.join(lines)

def get_key_file_diffs(files: List[str], base_branch: str) -> str:
    """Get diffs for key files"""
    diffs = []
    total_size = 0
    max_size = 3000
    
    for file in files:
        if total_size > max_size:
            break
            
        # Get the diff for this file
        code, diff, _ = run_command(['git', 'diff', f'{base_branch}...HEAD', '--', file])
        if code == 0 and diff:
            # Limit diff size
            if len(diff) > 500:
                diff = diff[:500] + "\n... (truncated)"
            
            diffs.append(f"=== {file} ===\n{diff}")
            total_size += len(diff)
    
    return '\n\n'.join(diffs) if diffs else "No key diffs available"

def generate_fallback_title(branch: str, file_categories: Dict[str, List[str]]) -> str:
    """Generate a fallback title based on branch and changes"""
    # Try to determine the main change type
    if 'feat' in branch.lower():
        prefix = 'feat'
    elif 'fix' in branch.lower():
        prefix = 'fix'
    elif 'chore' in branch.lower():
        prefix = 'chore'
    elif 'docs' in branch.lower():
        prefix = 'docs'
    else:
        # Determine from files
        if file_categories.get('documentation'):
            prefix = 'docs'
        elif file_categories.get('tests'):
            prefix = 'test'
        elif file_categories.get('ci'):
            prefix = 'ci'
        else:
            prefix = 'chore'
    
    # Extract a meaningful description from branch name
    desc = branch.replace('/', ' ').replace('-', ' ').replace('_', ' ')
    desc = ' '.join(word.capitalize() for word in desc.split())
    
    return f"{prefix}: {desc}"

def generate_fallback_description(branch: str, base_branch: str, 
                                changed_files: List[str], commit_messages: List[str],
                                changelog_summary: str) -> str:
    """Generate a fallback description"""
    desc = [
        f"## Changes from `{branch}` to `{base_branch}`\n",
        f"This PR includes {len(changed_files)} file changes across {len(commit_messages)} commits.\n"
    ]
    
    if changelog_summary:
        desc.append("### Changelog Summary\n")
        desc.append(changelog_summary)
        desc.append("\n")
    
    desc.extend([
        "### Statistics\n",
        f"- Files changed: {len(changed_files)}",
        f"- Commits: {len(commit_messages)}",
        f"- Branch: `{branch}`",
        f"- Target: `{base_branch}`"
    ])
    
    return '\n'.join(desc)

# ============================================================================
# GITHUB CLI OPERATIONS
# ============================================================================

def check_gh_cli() -> bool:
    """Check if GitHub CLI is installed and authenticated"""
    code, _, _ = run_command(['gh', 'auth', 'status'])
    return code == 0

def check_existing_pr(branch: str) -> Optional[Dict[str, str]]:
    """Check if a PR already exists for this branch"""
    code, output, _ = run_command(['gh', 'pr', 'list', '--head', branch, '--json', 'number,url,title,body'])
    if code == 0 and output:
        try:
            prs = json.loads(output)
            if prs:
                return {
                    'number': str(prs[0]['number']),
                    'url': prs[0]['url'],
                    'title': prs[0].get('title', ''),
                    'body': prs[0].get('body', '')
                }
        except:
            pass
    return None

def create_pull_request(title: str, body: str, base: str, head: str, 
                       draft: bool = False, labels: List[str] = None) -> Optional[str]:
    """Create a pull request using GitHub CLI"""
    cmd = ['gh', 'pr', 'create', 
           '--title', title,
           '--body', body,
           '--base', base,
           '--head', head]
    
    if draft:
        cmd.append('--draft')
    
    if labels:
        cmd.extend(['--label', ','.join(labels)])
    
    code, output, err = run_command(cmd)
    if code != 0:
        # If it failed due to labels, try without them
        if labels and 'label' in err.lower():
            print_color(Colors.YELLOW, "Some labels not found, creating PR without labels...")
            cmd = ['gh', 'pr', 'create', 
                   '--title', title,
                   '--body', body,
                   '--base', base,
                   '--head', head]
            if draft:
                cmd.append('--draft')
            code, output, err = run_command(cmd)
            if code == 0:
                return output
        
        print_color(Colors.RED, f"Failed to create PR: {err}")
        return None
    
    return output  # Returns the PR URL

def update_pull_request(pr_number: str, title: str = None, body: str = None, 
                       labels: List[str] = None) -> bool:
    """Update an existing pull request"""
    # First, try to update without touching labels if they might cause issues
    if labels is not None:
        # Try with labels first
        cmd = ['gh', 'pr', 'edit', pr_number]
        
        if title:
            cmd.extend(['--title', title])
        
        if body:
            cmd.extend(['--body', body])
        
        # Only try to modify labels if we have valid ones
        if labels:
            # Try to add labels without removing existing ones first
            cmd.extend(['--add-label', ','.join(labels)])
        
        code, output, err = run_command(cmd)
        if code != 0 and ('label' in err.lower() or 'not found' in err.lower()):
            # If labels failed, try without them
            print_color(Colors.YELLOW, "Some labels not found, updating PR without label changes...")
            cmd = ['gh', 'pr', 'edit', pr_number]
            if title:
                cmd.extend(['--title', title])
            if body:
                cmd.extend(['--body', body])
            code, output, err = run_command(cmd)
            if code == 0:
                return True
            else:
                print_color(Colors.RED, f"Failed to update PR: {err}")
                return False
        elif code != 0:
            print_color(Colors.RED, f"Failed to update PR: {err}")
            return False
    else:
        # No label changes requested, just update title/body
        cmd = ['gh', 'pr', 'edit', pr_number]
        
        if title:
            cmd.extend(['--title', title])
        
        if body:
            cmd.extend(['--body', body])
        
        code, output, err = run_command(cmd)
        if code != 0:
            print_color(Colors.RED, f"Failed to update PR: {err}")
            return False
    
    return True

# ============================================================================
# CHANGELOG EXTRACTION
# ============================================================================

def extract_version_from_branch(branch: str) -> Optional[str]:
    """Extract version from branch name if it follows a pattern"""
    # Check release branch pattern
    match = RELEASE_BRANCH_PATTERN.match(branch)
    if match:
        return match.group(1)
    
    # Check if branch name contains version pattern
    version_pattern = re.compile(r'v?(\d+\.\d+\.\d+)')
    match = version_pattern.search(branch)
    if match:
        return match.group(1)
    
    return None

def extract_changelog_summary(version: Optional[str] = None) -> str:
    """Extract changelog summary for all packages"""
    if not version:
        # Try to get version from tag or branch
        tag = get_branch_tag()
        if tag:
            version = tag.lstrip('v')
        else:
            branch = get_current_branch()
            version = extract_version_from_branch(branch)
    
    if not version:
        return ""
    
    summary_parts = []
    
    # Define changelog files to check
    changelogs = [
        ("Project Overview", "CHANGELOG.md"),
        ("Dart Package", "dart/CHANGELOG.md"),
        ("Flutter Package", "flutter/CHANGELOG.md"),
        ("Rust Package", "dart/rust/CHANGELOG.md")
    ]
    
    for package_name, changelog_file in changelogs:
        if os.path.exists(changelog_file):
            section = extract_changelog_section(changelog_file, version)
            if section:
                summary_parts.append(f"### {package_name}\n\n{section}")
    
    if not summary_parts:
        return ""
    
    return "\n\n".join(summary_parts)

# ============================================================================
# LABEL DETECTION
# ============================================================================

def determine_labels(branch: str, changed_files: List[str], ai_analysis: Dict[str, str]) -> List[str]:
    """Determine appropriate labels based on branch and changes"""
    labels = []
    
    # Branch-based labels
    if RELEASE_BRANCH_PATTERN.match(branch):
        labels.append('release')
    elif FEATURE_BRANCH_PATTERN.match(branch):
        labels.append('enhancement')
    elif FIX_BRANCH_PATTERN.match(branch):
        labels.append('bug')
    
    # File-based labels
    if any('doc' in f.lower() or f.endswith('.md') for f in changed_files):
        labels.append('documentation')
    
    # AI-based labels
    description_lower = ai_analysis.get('description', '').lower()
    if 'breaking change' in description_lower:
        labels.append('breaking change')  # Use space, more common
    
    # Remove duplicates and filter to most common GitHub labels
    # These are the default labels that GitHub creates for new repos
    common_labels = {'bug', 'documentation', 'enhancement', 'duplicate', 'good first issue', 
                    'help wanted', 'invalid', 'question', 'wontfix', 'breaking change'}
    
    # Only return labels that are in our list AND likely to exist
    # For safety, we'll be conservative and only use the most common ones
    safe_labels = {'bug', 'documentation', 'enhancement'}
    return list(set(labels) & safe_labels)

# ============================================================================
# DIFF DISPLAY
# ============================================================================

def show_pr_diff(old_text: str, new_text: str):
    """Show a diff between old and new PR descriptions"""
    import difflib
    
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile='Current PR Description',
        tofile='New PR Description',
        lineterm=''
    )
    
    print_color(Colors.BLUE, "\n--- Description Diff ---")
    for line in diff:
        if line.startswith('+') and not line.startswith('+++'):
            print_color(Colors.GREEN, line.rstrip())
        elif line.startswith('-') and not line.startswith('---'):
            print_color(Colors.RED, line.rstrip())
        elif line.startswith('@'):
            print_color(Colors.YELLOW, line.rstrip())
        else:
            print(line.rstrip())
    print()

# ============================================================================
# VALIDATION
# ============================================================================

def validate_git_state() -> bool:
    """Validate Git repository state"""
    # Check for uncommitted changes
    code, output, _ = run_command(['git', 'status', '--porcelain'])
    if code == 0 and output:
        print_color(Colors.YELLOW, "Warning: You have uncommitted changes")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # Check if we're up to date with remote
    code, _, _ = run_command(['git', 'fetch'])
    if code != 0:
        print_color(Colors.RED, "Failed to fetch from remote")
        return False
    
    return True

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main entry point"""
    print_header("Open Pull Request with AI Analysis")
    
    # Ensure we're in project root
    ensure_project_root()
    
    # Check prerequisites
    if not check_gh_cli():
        print_color(Colors.RED, "Error: GitHub CLI (gh) is not installed or not authenticated")
        print_color(Colors.YELLOW, "Install: https://cli.github.com/")
        print_color(Colors.YELLOW, "Authenticate: gh auth login")
        return 1
    
    if not check_gemini_cli() or not check_api_key():
        print_color(Colors.YELLOW, "Warning: Gemini AI not available, using basic PR generation")
        print_color(Colors.BLUE, "Run: python tooling/setup_ai_tools.py for AI features")
    
    # Get current branch
    current_branch = get_current_branch()
    if not current_branch:
        print_color(Colors.RED, "Error: Could not determine current branch")
        return 1
    
    print_color(Colors.BLUE, f"Current branch: {current_branch}")
    
    # Get associated tag if any
    tag = get_branch_tag()
    if tag:
        print_color(Colors.GREEN, f"Associated tag: {tag}")
    else:
        latest_tag = get_latest_tag_on_branch()
        if latest_tag:
            print_color(Colors.YELLOW, f"Latest tag on branch: {latest_tag}")
    
    # Get base branch
    base_branch = get_default_branch()
    print_color(Colors.BLUE, f"Base branch: {base_branch}")
    
    # Check if we're trying to PR to ourselves
    if current_branch == base_branch:
        print_color(Colors.RED, f"Error: Cannot create PR from {current_branch} to itself")
        return 1
    
    # Validate git state
    if not validate_git_state():
        return 1
    
    # Check if PR already exists
    existing_pr = check_existing_pr(current_branch)
    if existing_pr:
        print_color(Colors.YELLOW, f"A PR already exists for this branch: {existing_pr['url']}")
        print_color(Colors.BLUE, f"Current title: {existing_pr['title']}")
        print()
        
        print_color(Colors.BLUE, "What would you like to do?")
        print("1. Update the PR with AI-generated content")
        print("2. View the existing PR in browser")
        print("3. Cancel")
        
        choice = input("\nChoice (1-3) [1]: ").strip() or "1"
        
        if choice == "2":
            run_command(['gh', 'pr', 'view', '--web'], capture=False)
            return 0
        elif choice == "3":
            print_color(Colors.YELLOW, "Operation cancelled")
            return 0
        elif choice != "1":
            print_color(Colors.RED, "Invalid choice")
            return 1
        
        # Continue to update the PR
        pr_number = existing_pr['number']
        update_mode = True
    else:
        pr_number = None
        update_mode = False
    
    # Push branch if not on remote
    if not check_branch_exists_remote(current_branch):
        if not push_branch(current_branch):
            return 1
    
    # Gather information about changes
    print_color(Colors.BLUE, "Analyzing changes...")
    changed_files = get_changed_files(base_branch)
    commit_messages = get_commit_messages(base_branch)
    diff_summary = get_diff_summary(base_branch)
    
    print_color(Colors.BLUE, f"Files changed: {len(changed_files)}")
    print_color(Colors.BLUE, f"Commits: {len(commit_messages)}")
    
    # Extract changelog if available
    print_color(Colors.BLUE, "Extracting changelog entries...")
    changelog_summary = extract_changelog_summary()
    
    # Use AI to analyze changes
    print_color(Colors.BLUE, "Generating AI-powered PR description...")
    ai_analysis = analyze_changes_with_ai(
        current_branch, base_branch, changed_files, 
        commit_messages, diff_summary, changelog_summary, tag
    )
    
    # Determine labels
    labels = determine_labels(current_branch, changed_files, ai_analysis)
    
    # Ask user about labels
    if labels:
        print_color(Colors.BLUE, f"Suggested labels: {', '.join(labels)}")
        use_labels = input("Apply these labels? (Y/n/skip): ").strip().lower()
        if use_labels == 'n':
            labels = []
        elif use_labels == 'skip' or use_labels == 's':
            labels = None  # Don't modify labels at all
    
    # Show preview
    print_header("PR Preview")
    print_color(Colors.GREEN, f"Title: {ai_analysis['title']}")
    if labels is not None:
        print_color(Colors.BLUE, f"Labels: {', '.join(labels) if labels else 'None'}")
    else:
        print_color(Colors.YELLOW, "Labels: No changes to labels")
    print()
    print_color(Colors.BLUE, "Description:")
    print(ai_analysis['description'])
    print()
    
    # Show what will change if updating
    if update_mode:
        print_color(Colors.YELLOW, "\nThis will update the existing PR with the above content.")
        if existing_pr['title'] != ai_analysis['title']:
            print_color(Colors.YELLOW, f"Title will change from: {existing_pr['title']}")
        
        # Offer to show diff
        if existing_pr.get('body', '').strip() != ai_analysis['description'].strip():
            show_diff = input("\nShow diff of description changes? (y/N): ")
            if show_diff.lower() == 'y':
                show_pr_diff(existing_pr.get('body', ''), ai_analysis['description'])
    
    # Confirm action
    action_text = "Update" if update_mode else "Create"
    response = input(f"{action_text} this pull request? (Y/n): ")
    if response.lower() == 'n':
        print_color(Colors.YELLOW, f"PR {action_text.lower()} cancelled")
        return 0
    
    # Create or update PR
    if update_mode:
        print_color(Colors.BLUE, f"Updating pull request #{pr_number}...")
        success = update_pull_request(
            pr_number,
            title=ai_analysis['title'],
            body=ai_analysis['description'],
            labels=labels
        )
        
        if success:
            print_color(Colors.GREEN, f"✓ Pull request #{pr_number} updated successfully!")
            pr_url = existing_pr['url']
        else:
            return 1
    else:
        print_color(Colors.BLUE, "Creating pull request...")
        pr_url = create_pull_request(
            title=ai_analysis['title'],
            body=ai_analysis['description'],
            base=base_branch,
            head=current_branch,
            draft=False,
            labels=labels
        )
        
        if pr_url:
            print_color(Colors.GREEN, f"✓ Pull request created successfully!")
        else:
            return 1
    
    if pr_url:
        print_color(Colors.BLUE, f"URL: {pr_url}")
        
        # Optionally open in browser
        response = input("\nOpen PR in browser? (Y/n): ")
        if response.lower() != 'n':
            run_command(['gh', 'pr', 'view', '--web'], capture=False)
    
    return 0

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)