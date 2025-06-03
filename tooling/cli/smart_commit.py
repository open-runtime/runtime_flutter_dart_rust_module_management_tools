#!/usr/bin/env python3
"""
smart_commit.py - AI-powered commit message generator
Uses Gemini to analyze changes and create conventional commit messages

This script performs comprehensive analysis across multiple packages,
identifies cross-package dependencies, and generates detailed commit messages.

Requires: Python 3.6+, git, gemini-cli

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import os
import sys
import subprocess
import tempfile
import threading
import time
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil

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
# TEXT SANITIZATION
# ============================================================================

class TextSanitizer:
    """Handles cleaning of text from ANSI codes and control characters"""
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Remove ANSI escape sequences and control characters"""
        if not text:
            return ""
        
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'''
            \x1b     # ESC
            (?:
                \[[\?0-9;]*[mGKHJFlh]  |  # CSI sequences
                \([AB]                  |  # Designate character set
                \][0-9];[^\x07]*\x07       # OSC sequences
            )
        ''', re.VERBOSE)
        text = ansi_escape.sub('', text)
        
        # Remove spinner characters
        text = re.sub(r'[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', '', text)
        text = re.sub(r'[\|\/\-\\]+ ', '', text)
        
        # Remove control characters but keep newlines and tabs
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Remove carriage returns
        text = text.replace('\r', '')
        
        return text
    
    @staticmethod
    def clean_git_output(output: str) -> str:
        """Clean and validate git output"""
        if not output:
            return ""
        
        output = TextSanitizer.sanitize_text(output)
        output = output.strip()
        return output
    
    @staticmethod
    def clean_ai_response(response: str) -> str:
        """Clean AI responses from artifacts"""
        if not response:
            return ""
        
        response = TextSanitizer.sanitize_text(response)
        
        # Remove markdown code blocks
        response = re.sub(r'^```[a-zA-Z0-9_-]*\s*$', '', response, flags=re.MULTILINE)
        response = re.sub(r'^```\s*$', '', response, flags=re.MULTILINE)
        response = re.sub(r'\s*```\s*$', '', response, flags=re.MULTILINE)
        
        # Remove progress indicators
        response = '\n'.join(line for line in response.split('\n') 
                           if not re.match(r'^\s*[\|\/\-\\⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]', line))
        
        # Trim empty lines from beginning and end
        lines = response.split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)

# ============================================================================
# PROGRESS TRACKING
# ============================================================================

@dataclass
class PackageStatus:
    """Track status of package analysis"""
    name: str
    status: str = "pending"  # pending, analyzing, complete, error, skipped
    result: Optional[str] = None

class ProgressTracker:
    """Handle progress display with spinner animation"""
    
    def __init__(self, packages: List[str]):
        self.packages = {pkg: PackageStatus(pkg) for pkg in packages}
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_idx = 0
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def update_status(self, package: str, status: str, result: Optional[str] = None):
        """Update package status"""
        with self.lock:
            if package in self.packages:
                self.packages[package].status = status
                if result:
                    self.packages[package].result = result
    
    def start(self):
        """Start progress display"""
        self.running = True
        self.thread = threading.Thread(target=self._run_display)
        self.thread.daemon = True
        self.thread.start()
        # Initial display
        time.sleep(0.1)
    
    def stop(self):
        """Stop progress display"""
        self.running = False
        if self.thread:
            self.thread.join()
        # Final display
        self._display_progress(final=True)
    
    def _run_display(self):
        """Run the progress display loop"""
        while self.running:
            self._display_progress()
            time.sleep(0.1)
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
    
    def _display_progress(self, final: bool = False):
        """Display current progress"""
        with self.lock:
            # Move cursor up to overwrite previous display
            if hasattr(self, '_displayed_once'):
                print(f"\033[{len(self.packages)}A", end='', file=sys.stderr)
            else:
                self._displayed_once = True
            
            # Display each package status
            for pkg_name, pkg_status in self.packages.items():
                icon = ""
                color = Colors.GRAY
                
                if pkg_status.status == "pending":
                    icon = self.spinner_chars[self.spinner_idx]
                    color = Colors.GRAY
                elif pkg_status.status == "analyzing":
                    icon = self.spinner_chars[self.spinner_idx]
                    color = Colors.YELLOW
                elif pkg_status.status == "complete":
                    icon = "✓"
                    color = Colors.GREEN
                elif pkg_status.status == "error":
                    icon = "✗"
                    color = Colors.RED
                elif pkg_status.status == "skipped":
                    icon = "-"
                    color = Colors.GRAY
                
                # Clear line and print status
                print(f"\r\033[K  {color}{icon}{Colors.NC} {color}{pkg_name:<20}{Colors.NC}", 
                      file=sys.stderr)
            
            # Check if all complete
            if final or all(p.status in ["complete", "error", "skipped"] 
                          for p in self.packages.values()):
                self.running = False

# ============================================================================
# FILE CATEGORIZATION
# ============================================================================

class FileCategorizer:
    """Categorize files by package and scope"""
    
    @staticmethod
    def categorize_files(files: List[str]) -> Dict[str, List[str]]:
        """Categorize files into packages"""
        categories = {
            "Dart": [],
            "Flutter": [],
            "Rust": [],
            "Tooling": [],
            "Docs": [],
            "Config": [],
            "Tests": [],
            "Top-Level": [],
            "Other": []
        }
        
        for file in files:
            if not file:
                continue
            
            # Extract filename from git status format
            clean_file = re.sub(r'^[MADRCU?!]\s+', '', file.strip())
            
            # Categorize by location and type
            if clean_file.startswith("dart/rust/"):
                categories["Rust"].append(clean_file)
            elif clean_file.startswith("flutter/"):
                categories["Flutter"].append(clean_file)
            elif clean_file.startswith("dart/"):
                categories["Dart"].append(clean_file)
            elif clean_file.startswith("tooling/"):
                categories["Tooling"].append(clean_file)
            elif re.match(r'^(README|LICENSE|CHANGELOG|CONTRIBUTING)', clean_file) or \
                 (clean_file.endswith(('.md', '.txt')) and '/' not in clean_file):
                categories["Docs"].append(clean_file)
            elif re.match(r'^(Makefile|\.github/|\.gitignore|\.editorconfig)', clean_file) or \
                 (clean_file.endswith(('.yml', '.yaml', '.json', '.toml')) and '/' not in clean_file):
                categories["Config"].append(clean_file)
            elif clean_file.endswith(('_test.dart', '_test.rs', '_test.py')) or \
                 clean_file.startswith('test/'):
                categories["Tests"].append(clean_file)
            elif '/' not in clean_file:
                categories["Top-Level"].append(clean_file)
            else:
                categories["Other"].append(clean_file)
        
        return categories

# ============================================================================
# GIT OPERATIONS
# ============================================================================

class GitOperations:
    """Handle git operations"""
    
    @staticmethod
    def get_all_changed_files() -> List[str]:
        """Get all changed files"""
        all_files = []
        
        # Staged files
        code, stdout, _ = run_command(['git', 'diff', '--cached', '--name-status'])
        if code == 0 and stdout:
            all_files.extend(stdout.strip().split('\n'))
        
        # Modified files
        code, stdout, _ = run_command(['git', 'diff', '--name-status'])
        if code == 0 and stdout:
            all_files.extend(stdout.strip().split('\n'))
        
        # Untracked files
        code, stdout, _ = run_command(['git', 'ls-files', '--others', '--exclude-standard'])
        if code == 0 and stdout:
            for file in stdout.strip().split('\n'):
                if file:
                    all_files.append(f"?  {file}")
        
        # Clean and deduplicate
        cleaned_files = []
        seen = set()
        for file in all_files:
            if file and file not in seen:
                cleaned = TextSanitizer.clean_git_output(file)
                if cleaned:
                    cleaned_files.append(cleaned)
                    seen.add(file)
        
        return cleaned_files
    
    @staticmethod
    def get_package_diff(package: str, files: List[str]) -> str:
        """Get diff for specific package files"""
        if not files:
            return ""
        
        diff_content = []
        
        for file in files:
            if not file:
                continue
            
            # Get staged changes
            code, staged_diff, _ = run_command(['git', 'diff', '--cached', '--', file])
            
            # Get unstaged changes
            code2, unstaged_diff, _ = run_command(['git', 'diff', '--', file])
            
            if staged_diff or unstaged_diff:
                diff_content.append(f"File: {file}")
                diff_content.append("=" * 40)
                
                if staged_diff:
                    diff_content.append("STAGED CHANGES:")
                    diff_content.append(staged_diff)
                
                if unstaged_diff:
                    diff_content.append("UNSTAGED CHANGES:")
                    diff_content.append(unstaged_diff)
                
                diff_content.append("")
        
        return '\n'.join(diff_content)
    
    @staticmethod
    def check_status() -> Tuple[bool, bool, bool]:
        """Check git status (has_staged, has_unstaged, has_untracked)"""
        code, stdout, _ = run_command(['git', 'diff', '--cached', '--name-status'])
        has_staged = bool(code == 0 and stdout.strip())
        
        code, stdout, _ = run_command(['git', 'diff', '--name-status'])
        has_unstaged = bool(code == 0 and stdout.strip())
        
        code, stdout, _ = run_command(['git', 'ls-files', '--others', '--exclude-standard'])
        has_untracked = bool(code == 0 and stdout.strip())
        
        return has_staged, has_unstaged, has_untracked
    
    @staticmethod
    def get_github_url() -> Optional[str]:
        """Extract GitHub URL from git remote"""
        code, stdout, _ = run_command(['git', 'config', '--get', 'remote.origin.url'])
        if code != 0 or not stdout:
            return None
        
        repo_url = stdout.strip()
        
        # Handle various URL formats
        patterns = [
            r'^https://github.com/([^/]+)/([^/.]+)',
            r'^git@github.com:([^/]+)/([^/.]+)',
            r'github.com[:/]([^/]+)/([^/.]+)'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, repo_url)
            if match:
                return f"https://github.com/{match.group(1)}/{match.group(2)}"
        
        return None

# ============================================================================
# AI ANALYSIS
# ============================================================================

class AIAnalyzer:
    """Handle AI-powered analysis using Gemini"""
    
    def __init__(self, model: str = None):
        self.model = model or os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-exp')
        self.sanitizer = TextSanitizer()
    
    def analyze_package_changes(self, package: str, files: List[str], diff: str) -> str:
        """Analyze changes for a specific package"""
        if not files or not diff:
            return "NO_CHANGES"
        
        files_list = '\n'.join(files)
        
        prompt = f"""You are analyzing code changes for the {package} package in a vector search library.

Files changed:
{files_list}

Detailed changes:
{diff}

Please provide a comprehensive analysis of these changes:
1. What was changed (be specific about functions, classes, features)
2. Why these changes were made (the purpose/goal)
3. How the changes work (technical details)
4. Impact on the package (performance, API changes, bug fixes, etc.)
5. Any dependencies or related changes that might affect other packages
6. Any interfaces or contracts with other packages that changed

Format your response as a structured summary, not a commit message. Be thorough and technical.

IMPORTANT: Output your analysis as plain text. Do NOT wrap it in markdown code blocks (three backticks). Do NOT include any escape sequences or formatting codes."""

        try:
            # Call gemini-cli
            process = subprocess.Popen(
                ['gemini-cli', 'prompt', '-', '--model', self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=prompt, timeout=60)
            
            if process.returncode != 0:
                return f"ERROR: Failed to analyze {package} changes"
            
            return self.sanitizer.clean_ai_response(stdout)
            
        except subprocess.TimeoutExpired:
            process.kill()
            return f"ERROR: Analysis timeout for {package}"
        except Exception as e:
            return f"ERROR: {str(e)}"
    
    def analyze_cross_package_impacts(self, all_analyses: str) -> str:
        """Analyze cross-package dependencies and impacts"""
        prompt = f"""You are analyzing cross-package impacts and dependencies in a vector search library.

Individual package analyses have been completed:
{all_analyses}

Based on these individual analyses, please identify:

1. **Cross-Package Dependencies**: Which changes in one package affect other packages?
2. **Interface Changes**: What APIs or contracts between packages have changed?
3. **Integration Points**: How do the changes work together across packages?
4. **Potential Conflicts**: Are there any changes that might conflict or need coordination?
5. **Overall Architecture Impact**: How do these changes affect the system as a whole?
6. **Migration Requirements**: Do any changes require updates in dependent packages?

Focus on the relationships and interactions between packages, not individual package details.

IMPORTANT: Output your analysis as plain text. Do NOT wrap it in markdown code blocks (three backticks). Do NOT include any escape sequences or formatting codes."""

        try:
            process = subprocess.Popen(
                ['gemini-cli', 'prompt', '-', '--model', self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=prompt, timeout=60)
            
            if process.returncode != 0:
                return ""
            
            return self.sanitizer.clean_ai_response(stdout)
            
        except Exception:
            return ""
    
    def generate_commit_message(self, individual_analyses: str, 
                              cross_package_analysis: str, 
                              repo_level_changes: str) -> str:
        """Generate the final commit message"""
        prompt = f"""You are creating a comprehensive git commit message for a vector search library with multiple packages.

INDIVIDUAL PACKAGE ANALYSES:
{individual_analyses}

CROSS-PACKAGE ANALYSIS:
{cross_package_analysis}

REPOSITORY-LEVEL CHANGES:
{repo_level_changes}

Based on these analyses, create a detailed conventional commit message that:

1. Uses the appropriate type (feat/fix/docs/style/refactor/perf/test/build/ci/chore)
2. Includes a concise but descriptive subject line (50 chars max)
3. Provides a comprehensive body that explains:
   - The overall goal/purpose of these changes
   - What was changed in each affected package
   - How packages interact and depend on each other
   - Repository-wide impacts (build, CI, docs, etc.)
   - Why these changes were necessary
   - Technical details of the implementation
   - Any breaking changes or important notes

Format:
<type>(<scope>): <subject>

<comprehensive body explaining all changes>

<footer with breaking changes or references if any>

The body should be organized hierarchically:
- Start with the main purpose and overall impact
- Then detail package-specific changes
- Include cross-package dependencies and impacts
- End with any repo-wide changes or notes

Use bullet points for clarity. Be thorough - this commit message should serve as complete documentation of the changes.

IMPORTANT: Output the commit message as plain text. Do NOT wrap it in markdown code blocks (three backticks). Do NOT include any escape sequences or formatting codes."""

        try:
            process = subprocess.Popen(
                ['gemini-cli', 'prompt', '-', '--model', self.model],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=prompt, timeout=60)
            
            if process.returncode != 0:
                raise Exception("Failed to generate commit message")
            
            return self.sanitizer.clean_ai_response(stdout)
            
        except Exception as e:
            raise Exception(f"Failed to generate commit message: {str(e)}")

# ============================================================================
# MAIN SMART COMMIT CLASS
# ============================================================================

class SmartCommit:
    """Main class for smart commit functionality"""
    
    def __init__(self):
        self.git_ops = GitOperations()
        self.categorizer = FileCategorizer()
        self.ai_analyzer = AIAnalyzer()
        self.progress_tracker = None
    
    def check_prerequisites(self):
        """Check all prerequisites"""
        print_header("Checking Prerequisites")
        
        # Check gemini-cli
        if not check_gemini_cli():
            sys.exit(1)
        
        # Check API key
        if not check_api_key():
            sys.exit(1)
        
        print_color(Colors.GREEN, "✓ All prerequisites met")
    
    def stage_files_interactive(self, has_unstaged: bool, has_untracked: bool):
        """Interactive staging of files"""
        if has_unstaged or has_untracked:
            print_color(Colors.YELLOW, "\nYou have unstaged changes and/or untracked files.")
            print("Would you like to:")
            print("  1) Stage all changes (git add .)")
            print("  2) Stage specific files")
            print("  3) Continue with only currently staged files")
            print("  4) Exit")
            
            choice = input("Choose option (1-4): ")
            
            if choice == '1':
                run_command(['git', 'add', '.'])
                print_color(Colors.GREEN, "✓ Staged all changes")
            elif choice == '2':
                print_color(Colors.BLUE, "Current status:")
                run_command(['git', 'status', '--short'], capture_output=False)
                print()
                files = input("Enter files to stage (space-separated): ")
                if files:
                    run_command(['git', 'add'] + files.split())
                    print_color(Colors.GREEN, "✓ Staged specified files")
            elif choice == '3':
                print_color(Colors.YELLOW, "Continuing with currently staged files only")
            elif choice == '4':
                print_color(Colors.YELLOW, "Exiting...")
                sys.exit(0)
            else:
                print_color(Colors.RED, "Invalid option. Exiting...")
                sys.exit(1)
    
    def analyze_all_packages(self, categorized: Dict[str, List[str]]) -> str:
        """Analyze all packages in parallel and generate commit message"""
        # Setup progress tracker
        packages = list(categorized.keys())
        self.progress_tracker = ProgressTracker(packages)
        
        print_color(Colors.BLUE, "\nAnalyzing changes by package...")
        print()
        
        # Print initial empty lines for progress display
        for _ in packages:
            print("", file=sys.stderr)
        
        # Start progress display
        self.progress_tracker.start()
        
        # Prepare analysis tasks
        analyses = {}
        
        with ThreadPoolExecutor(max_workers=len(packages)) as executor:
            # Submit all analysis tasks
            futures = {}
            for package, files in categorized.items():
                if files:
                    self.progress_tracker.update_status(package, "analyzing")
                    diff = self.git_ops.get_package_diff(package, files)
                    future = executor.submit(
                        self.ai_analyzer.analyze_package_changes, 
                        package, files, diff
                    )
                    futures[future] = package
                else:
                    self.progress_tracker.update_status(package, "skipped")
            
            # Process completed analyses
            for future in as_completed(futures):
                package = futures[future]
                try:
                    result = future.result()
                    if result == "NO_CHANGES":
                        self.progress_tracker.update_status(package, "skipped")
                    elif result.startswith("ERROR"):
                        self.progress_tracker.update_status(package, "error")
                        analyses[package] = result
                    else:
                        self.progress_tracker.update_status(package, "complete")
                        analyses[package] = result
                except Exception as e:
                    self.progress_tracker.update_status(package, "error")
                    analyses[package] = f"ERROR: {str(e)}"
        
        # Stop progress display
        self.progress_tracker.stop()
        
        # Compile individual analyses
        all_individual_analyses = []
        for package in ["Dart", "Flutter", "Rust", "Tooling", "Docs", 
                       "Config", "Tests", "Top-Level", "Other"]:
            if package in analyses and analyses[package] != "NO_CHANGES":
                all_individual_analyses.append(f"{package.upper()} PACKAGE:")
                all_individual_analyses.append(analyses[package])
                all_individual_analyses.append("")
        
        all_analyses_text = '\n'.join(all_individual_analyses)
        
        # Analyze cross-package impacts
        print_color(Colors.BLUE, "\nAnalyzing cross-package dependencies and impacts...")
        cross_package_analysis = ""
        if all_analyses_text:
            cross_package_analysis = self.ai_analyzer.analyze_cross_package_impacts(all_analyses_text)
        
        # Compile repository-level changes
        repo_level_changes = []
        if "Top-Level" in analyses and analyses["Top-Level"] != "NO_CHANGES":
            repo_level_changes.append("Top-level files changed affecting overall repository structure.")
        if "Config" in analyses and analyses["Config"] != "NO_CHANGES":
            repo_level_changes.append("Configuration changes affecting build/CI/development setup.")
        if "Docs" in analyses and analyses["Docs"] != "NO_CHANGES":
            repo_level_changes.append("Documentation updates.")
        
        repo_level_text = '\n'.join(repo_level_changes)
        
        # Generate final commit message
        print_color(Colors.BLUE, "\nGenerating comprehensive commit message...")
        return self.ai_analyzer.generate_commit_message(
            all_analyses_text, cross_package_analysis, repo_level_text
        )
    
    def run(self):
        """Main execution"""
        print_color(Colors.PURPLE, "╔════════════════════════════════════════╗")
        print_color(Colors.PURPLE, "║   AI-Powered Smart Commit Tool v3.0    ║")
        print_color(Colors.PURPLE, "║   Real-time Cross-Package Analysis     ║")
        print_color(Colors.PURPLE, "╚════════════════════════════════════════╝")
        print()
        
        # Check prerequisites
        self.check_prerequisites()
        
        # Check for changes
        print_color(Colors.BLUE, "\nAnalyzing repository changes...")
        has_staged, has_unstaged, has_untracked = self.git_ops.check_status()
        
        if not has_staged and not has_unstaged and not has_untracked:
            print_color(Colors.YELLOW, "No changes detected. Nothing to commit.")
            return
        
        # Show current status
        print_color(Colors.BLUE, "\nCurrent git status:")
        run_command(['git', 'status', '--short'], capture_output=False)
        
        # Handle staging
        self.stage_files_interactive(has_unstaged, has_untracked)
        
        # Get all changed files
        all_files = self.git_ops.get_all_changed_files()
        if not all_files:
            print_color(Colors.YELLOW, "No changes to analyze.")
            return
        
        # Categorize files
        print_color(Colors.BLUE, "\nCategorizing changes by package and scope...")
        categorized = self.categorizer.categorize_files(all_files)
        
        # Analyze and generate commit message
        try:
            commit_message = self.analyze_all_packages(categorized)
        except Exception as e:
            print_color(Colors.RED, f"\nFailed to generate commit message: {str(e)}")
            return
        
        # Show the generated message
        print_color(Colors.GREEN, "\nGenerated comprehensive commit message:")
        print_color(Colors.PURPLE, "━" * 40)
        print(commit_message)
        print_color(Colors.PURPLE, "━" * 40)
        
        # Interactive options
        print("\nWhat would you like to do?")
        print("  1) Use this message and commit")
        print("  2) Edit the message")
        print("  3) Regenerate message")
        print("  4) Cancel")
        
        choice = input("Choose option (1-4): ")
        
        if choice == '1':
            # Commit with generated message
            code, _, stderr = run_command(['git', 'commit', '-m', commit_message])
            if code == 0:
                print_color(Colors.GREEN, "✓ Changes committed successfully!")
                
                # Ask about pushing
                push = input("Push to origin? (Y/n): ")
                if not push.lower().startswith('n'):
                    code, branch, _ = run_command(['git', 'branch', '--show-current'])
                    if code == 0 and branch:
                        run_command(['git', 'push', 'origin', branch])
                        print_color(Colors.GREEN, f"✓ Pushed to origin/{branch}")
                        
                        # Show GitHub URL if available
                        github_url = self.git_ops.get_github_url()
                        if github_url:
                            print_color(Colors.BLUE, f"\n🔗 View on GitHub: {github_url}")
            else:
                print_color(Colors.RED, f"Commit failed: {stderr}")
                
        elif choice == '2':
            # Edit message
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(commit_message)
                temp_file = f.name
            
            editor = os.environ.get('EDITOR', 'vim')
            subprocess.call([editor, temp_file])
            
            with open(temp_file, 'r') as f:
                edited_message = f.read().strip()
            
            os.unlink(temp_file)
            
            if edited_message:
                code, _, stderr = run_command(['git', 'commit', '-m', edited_message])
                if code == 0:
                    print_color(Colors.GREEN, "✓ Changes committed with edited message!")
                    
                    push = input("Push to origin? (Y/n): ")
                    if not push.lower().startswith('n'):
                        code, branch, _ = run_command(['git', 'branch', '--show-current'])
                        if code == 0 and branch:
                            run_command(['git', 'push', 'origin', branch])
                            print_color(Colors.GREEN, f"✓ Pushed to origin/{branch}")
                            
                            # Show GitHub URL if available
                            github_url = self.git_ops.get_github_url()
                            if github_url:
                                print_color(Colors.BLUE, f"\n🔗 View on GitHub: {github_url}")
                else:
                    print_color(Colors.RED, f"Commit failed: {stderr}")
            else:
                print_color(Colors.RED, "Empty message. Commit cancelled.")
                
        elif choice == '3':
            # Regenerate
            print_color(Colors.YELLOW, "Regenerating commit message...")
            self.run()
            
        elif choice == '4':
            print_color(Colors.YELLOW, "Commit cancelled.")
        else:
            print_color(Colors.RED, "Invalid option. Commit cancelled.")
        
        print_color(Colors.BLUE, "\n✓ Smart commit completed!")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    committer = SmartCommit()
    
    try:
        committer.run()
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error: {str(e)}")
        sys.exit(1)
    finally:
        # Cleanup
        cleanup_temp_files()

if __name__ == "__main__":
    main()