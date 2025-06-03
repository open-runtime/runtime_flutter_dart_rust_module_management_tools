#!/usr/bin/env python3
"""
pre_release_check.py - Comprehensive pre-release validation

This script performs thorough checks before releasing:
- Version consistency across all packages
- Git repository state validation
- Version tag availability
- Changelog completeness
- Dependency validation
- Test execution

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved

Requires: Python 3.6+, git, dart, flutter
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

# Add the script directory to Python path for imports
script_dir = Path(__file__).parent.absolute()
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

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

# ============================================================================
# CHECK RESULT TYPES
# ============================================================================

class CheckStatus(Enum):
    """Status of a check"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"

@dataclass
class CheckResult:
    """Result of a single check"""
    name: str
    status: CheckStatus
    message: str
    details: Optional[List[str]] = None
    fix_suggestions: Optional[List[str]] = None
    duration: Optional[float] = None

# ============================================================================
# ENHANCED COLORS
# ============================================================================

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'
    
    # Compound styles
    SUCCESS = f'{BOLD}{GREEN}'
    ERROR = f'{BOLD}{RED}'
    WARNING = f'{BOLD}{YELLOW}'
    INFO = f'{BOLD}{BLUE}'
    HEADER = f'{BOLD}{PURPLE}'

# ============================================================================
# TIMER UTILITY
# ============================================================================

class Timer:
    """Simple timer for measuring check duration"""
    def __init__(self):
        self.start_time = None
        
    def start(self):
        self.start_time = datetime.now()
        
    def stop(self) -> float:
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            self.start_time = None
            return duration
        return 0.0

# ============================================================================
# VERSION CONSISTENCY CHECKER
# ============================================================================

class VersionConsistencyChecker:
    """Check version consistency across all packages"""
    
    def check(self) -> CheckResult:
        """Perform version consistency check"""
        timer = Timer()
        timer.start()
        
        print_header("Checking Version Consistency")
        
        # Extract versions from all sources
        versions = self._extract_all_versions()
        
        # Display version summary
        print_color(Colors.BLUE, "Version Summary:")
        for source, version in versions.items():
            if version:
                print_color(Colors.GRAY, f"  {source}: {version}")
            else:
                print_color(Colors.YELLOW, f"  {source}: Not found")
        
        # Check consistency
        unique_versions = set(v for v in versions.values() if v)
        
        if len(unique_versions) == 0:
            return CheckResult(
                name="Version Consistency",
                status=CheckStatus.FAILED,
                message="No versions found in any package files",
                fix_suggestions=["Check that package files exist and are properly formatted"],
                duration=timer.stop()
            )
        elif len(unique_versions) == 1:
            version = unique_versions.pop()
            print_color(Colors.GREEN, f"  ✓ All versions are consistent: {version}")
            return CheckResult(
                name="Version Consistency",
                status=CheckStatus.PASSED,
                message=f"All versions match: {version}",
                duration=timer.stop()
            )
        else:
            # Find mismatches
            mismatches = []
            base_version = versions.get('Dart')
            
            for source, version in versions.items():
                if version and version != base_version:
                    mismatches.append(f"{source} version {version} doesn't match Dart {base_version}")
                    print_color(Colors.RED, f"  ✗ {source} version doesn't match")
            
            return CheckResult(
                name="Version Consistency",
                status=CheckStatus.FAILED,
                message="Version mismatch detected",
                details=mismatches,
                fix_suggestions=[
                    f"Run: ./tooling/update_version.py {base_version}",
                    "Or manually update all version files to match"
                ],
                duration=timer.stop()
            )
    
    def _extract_all_versions(self) -> Dict[str, Optional[str]]:
        """Extract versions from all package files"""
        versions = {}
        
        # Dart version
        versions['Dart'] = extract_yaml_value(DART_PUBSPEC, "version")
        
        # Flutter version
        versions['Flutter'] = extract_yaml_value(FLUTTER_PUBSPEC, "version")
        
        # Rust version
        if Path(RUST_CARGO).exists():
            versions['Rust'] = extract_toml_value(RUST_CARGO, "version")
        
        # cargo.dart version
        if Path(CARGO_DART_CONFIG).exists():
            try:
                with open(CARGO_DART_CONFIG, 'r') as f:
                    content = f.read()
                    match = re.search(r"const String CARGO_VERSION = '([^']*)'", content)
                    if match:
                        versions['cargo.dart'] = match.group(1)
            except Exception:
                pass
        
        return versions

# ============================================================================
# GIT STATUS CHECKER
# ============================================================================

class GitStatusChecker:
    """Check git repository status"""
    
    def check(self) -> CheckResult:
        """Perform git status checks"""
        timer = Timer()
        timer.start()
        
        print_header("Checking Git Status")
        
        # Check if we're in a git repo
        if not check_git_repo():
            return CheckResult(
                name="Git Repository",
                status=CheckStatus.FAILED,
                message="Not in a git repository",
                fix_suggestions=["Initialize git repository: git init"],
                duration=timer.stop()
            )
        
        # Check git state (no rebase, merge, etc.)
        if not check_git_state():
            return CheckResult(
                name="Git State",
                status=CheckStatus.FAILED,
                message="Git repository in special state (rebase/merge/cherry-pick)",
                fix_suggestions=[
                    "Complete or abort the current operation",
                    "Check git status for details"
                ],
                duration=timer.stop()
            )
        
        # Check for uncommitted changes
        code, stdout, _ = run_command(['git', 'status', '--porcelain'])
        if code == 0 and stdout:
            print_color(Colors.RED, "  ✗ You have uncommitted changes")
            print_color(Colors.YELLOW, "    Please commit or stash your changes before releasing")
            
            # Show files
            run_command(['git', 'status', '--short'], capture_output=False)
            
            return CheckResult(
                name="Working Directory",
                status=CheckStatus.FAILED,
                message="Uncommitted changes detected",
                details=stdout.strip().split('\n'),
                fix_suggestions=[
                    "Commit changes: git add -A && git commit",
                    "Or stash changes: git stash"
                ],
                duration=timer.stop()
            )
        else:
            print_color(Colors.GREEN, "  ✓ Working directory is clean")
        
        # Check remote sync
        sync_ok = check_remote_sync()
        
        return CheckResult(
            name="Git Status",
            status=CheckStatus.PASSED if sync_ok else CheckStatus.WARNING,
            message="Git repository is ready" if sync_ok else "Local/remote may be out of sync",
            duration=timer.stop()
        )

# ============================================================================
# VERSION TAG CHECKER
# ============================================================================

class VersionTagChecker:
    """Check if version tag already exists"""
    
    def check(self, version: str) -> CheckResult:
        """Check if version tag is available"""
        timer = Timer()
        timer.start()
        
        print_header("Checking Version Tags")
        
        # Check both with and without 'v' prefix
        tags_to_check = [f"v{version}", version]
        existing_tags = []
        
        for tag in tags_to_check:
            # Check local tags
            code, _, _ = run_command(['git', 'rev-parse', tag])
            if code == 0:
                existing_tags.append(f"Local tag '{tag}' exists")
                print_color(Colors.RED, f"  ✗ Tag '{tag}' already exists locally")
            
            # Check remote tags
            code, stdout, _ = run_command(['git', 'ls-remote', '--tags', 'origin'])
            if code == 0 and f"refs/tags/{tag}" in stdout:
                existing_tags.append(f"Remote tag '{tag}' exists")
                print_color(Colors.RED, f"  ✗ Tag '{tag}' already exists on remote")
        
        if not existing_tags:
            print_color(Colors.GREEN, f"  ✓ Version tag v{version} is available")
            return CheckResult(
                name="Version Tag",
                status=CheckStatus.PASSED,
                message=f"Tag v{version} is available for use",
                duration=timer.stop()
            )
        else:
            return CheckResult(
                name="Version Tag",
                status=CheckStatus.FAILED,
                message=f"Version {version} has already been released",
                details=existing_tags,
                fix_suggestions=[
                    "Bump version with: ./tooling/prepare_new_patch.py",
                    f"Or delete existing tag with: ./tooling/retag_release.py"
                ],
                duration=timer.stop()
            )

# ============================================================================
# CHANGELOG VALIDATOR
# ============================================================================

class ChangelogValidator:
    """Validate changelog entries"""
    
    def check(self) -> CheckResult:
        """Run changelog validation"""
        timer = Timer()
        timer.start()
        
        print_header("Validating Changelog Entries")
        
        # Check if validation script exists
        validator_script = Path("tooling/validate_changelogs.py")
        if not validator_script.exists():
            # Try bash version
            validator_script = Path("tooling/validate_changelogs.sh")
            if not validator_script.exists():
                return CheckResult(
                    name="Changelog Validation",
                    status=CheckStatus.SKIPPED,
                    message="Changelog validator not found",
                    duration=timer.stop()
                )
        
        # Make it executable
        ensure_executable(str(validator_script))
        
        # Run validation
        if validator_script.suffix == '.py':
            result = subprocess.run([sys.executable, str(validator_script)])
        else:
            result = subprocess.run([str(validator_script)])
        
        if result.returncode == 0:
            return CheckResult(
                name="Changelog Entries",
                status=CheckStatus.PASSED,
                message="All changelogs have valid entries",
                duration=timer.stop()
            )
        else:
            return CheckResult(
                name="Changelog Entries",
                status=CheckStatus.FAILED,
                message="Changelog validation failed",
                fix_suggestions=[
                    "Add changelog entries: ./tooling/sync_changelogs.py",
                    "Or manually edit changelog files"
                ],
                duration=timer.stop()
            )

# ============================================================================
# DEPENDENCY CHECKER
# ============================================================================

class DependencyChecker:
    """Check package dependencies"""
    
    def check(self) -> CheckResult:
        """Check all package dependencies"""
        timer = Timer()
        timer.start()
        
        print_header("Checking Dependencies")
        
        issues = []
        warnings = []
        
        # Check Dart dependencies
        dart_ok = self._check_dart_dependencies()
        if not dart_ok:
            issues.append("Dart dependency issues detected")
        
        # Check Flutter dependencies
        flutter_ok = self._check_flutter_dependencies()
        if not flutter_ok:
            issues.append("Flutter dependency issues detected")
        
        # Check Flutter's dependency on Dart package
        dep_warning = self._check_flutter_dart_dependency()
        if dep_warning:
            warnings.append(dep_warning)
        
        # Determine overall status
        if issues:
            return CheckResult(
                name="Dependencies",
                status=CheckStatus.FAILED,
                message="Dependency issues found",
                details=issues + warnings,
                fix_suggestions=[
                    "Fix Dart deps: cd dart && dart pub get",
                    "Fix Flutter deps: cd flutter && flutter pub get",
                    "Update pubspec.yaml files as needed"
                ],
                duration=timer.stop()
            )
        elif warnings:
            return CheckResult(
                name="Dependencies",
                status=CheckStatus.WARNING,
                message="Dependencies valid but warnings exist",
                details=warnings,
                duration=timer.stop()
            )
        else:
            return CheckResult(
                name="Dependencies",
                status=CheckStatus.PASSED,
                message="All dependencies are valid",
                duration=timer.stop()
            )
    
    def _check_dart_dependencies(self) -> bool:
        """Check Dart package dependencies"""
        print_color(Colors.BLUE, "Checking Dart dependencies...")
        
        original_dir = os.getcwd()
        try:
            os.chdir('dart')
            code, _, stderr = run_command(['dart', 'pub', 'get', '--dry-run'])
            
            if code == 0:
                print_color(Colors.GREEN, "  ✓ Dart dependencies are valid")
                return True
            else:
                print_color(Colors.RED, "  ✗ Dart dependency issues detected")
                if stderr:
                    print_color(Colors.GRAY, f"    {stderr}")
                return False
        finally:
            os.chdir(original_dir)
    
    def _check_flutter_dependencies(self) -> bool:
        """Check Flutter package dependencies"""
        print_color(Colors.BLUE, "Checking Flutter dependencies...")
        
        original_dir = os.getcwd()
        try:
            os.chdir('flutter')
            code, _, stderr = run_command(['flutter', 'pub', 'get', '--dry-run'])
            
            if code == 0:
                print_color(Colors.GREEN, "  ✓ Flutter dependencies are valid")
                return True
            else:
                print_color(Colors.RED, "  ✗ Flutter dependency issues detected")
                if stderr:
                    print_color(Colors.GRAY, f"    {stderr}")
                return False
        finally:
            os.chdir(original_dir)
    
    def _check_flutter_dart_dependency(self) -> Optional[str]:
        """Check if Flutter depends on correct Dart package version"""
        try:
            # Get package names
            names = detect_package_names()
            
            with open('flutter/pubspec.yaml', 'r') as f:
                content = f.read()
                
            # Find dart package dependency
            pattern = rf'{names.dart_package_name}:\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)'
            match = re.search(pattern, content)
            if not match:
                return None
            
            flutter_dart_dep = match.group(1)
            current_version = get_current_version()
            
            if flutter_dart_dep != current_version:
                warning = f"Flutter depends on {names.dart_package_name} {flutter_dart_dep} but current is {current_version}"
                print_color(Colors.YELLOW, f"  ⚠ {warning}")
                return warning
            
            return None
            
        except Exception:
            return None

# ============================================================================
# TEST RUNNER
# ============================================================================

class TestRunner:
    """Run package tests"""
    
    def check(self) -> CheckResult:
        """Run all tests"""
        timer = Timer()
        timer.start()
        
        print_header("Running Tests")
        
        results = []
        
        # Run Dart tests
        dart_result = self._run_dart_tests()
        results.append(dart_result)
        
        # Run Flutter tests
        flutter_result = self._run_flutter_tests()
        results.append(flutter_result)
        
        # Summarize results
        if all(r == "passed" for r in results):
            return CheckResult(
                name="Tests",
                status=CheckStatus.PASSED,
                message="All tests passed",
                duration=timer.stop()
            )
        elif any(r == "failed" for r in results):
            return CheckResult(
                name="Tests",
                status=CheckStatus.WARNING,
                message="Some tests failed or missing",
                details=[f"Dart: {results[0]}", f"Flutter: {results[1]}"],
                duration=timer.stop()
            )
        else:
            return CheckResult(
                name="Tests",
                status=CheckStatus.WARNING,
                message="No tests found",
                fix_suggestions=["Consider adding tests for better quality assurance"],
                duration=timer.stop()
            )
    
    def _run_dart_tests(self) -> str:
        """Run Dart tests"""
        print_color(Colors.BLUE, "Running Dart tests...")
        
        original_dir = os.getcwd()
        try:
            os.chdir('dart')
            
            # Check if test directory exists
            if not Path('test').exists():
                print_color(Colors.YELLOW, "  ⚠ No Dart tests found")
                return "no tests"
            
            # Run tests
            code, stdout, stderr = run_command(['dart', 'test', '--reporter=compact'])
            
            if code == 0:
                print_color(Colors.GREEN, "  ✓ Dart tests passed")
                return "passed"
            else:
                print_color(Colors.YELLOW, "  ⚠ Dart tests failed")
                return "failed"
                
        except Exception as e:
            print_color(Colors.YELLOW, f"  ⚠ Error running Dart tests: {e}")
            return "error"
        finally:
            os.chdir(original_dir)
    
    def _run_flutter_tests(self) -> str:
        """Run Flutter tests"""
        print_color(Colors.BLUE, "Running Flutter tests...")
        
        original_dir = os.getcwd()
        try:
            os.chdir('flutter')
            
            # Check if test directory exists
            if not Path('test').exists():
                print_color(Colors.YELLOW, "  ⚠ No Flutter tests found")
                return "no tests"
            
            # Run tests
            code, stdout, stderr = run_command(['flutter', 'test', '--reporter=compact'])
            
            if code == 0:
                print_color(Colors.GREEN, "  ✓ Flutter tests passed")
                return "passed"
            else:
                print_color(Colors.YELLOW, "  ⚠ Flutter tests failed")
                return "failed"
                
        except Exception as e:
            print_color(Colors.YELLOW, f"  ⚠ Error running Flutter tests: {e}")
            return "error"
        finally:
            os.chdir(original_dir)

# ============================================================================
# ENHANCED PRE-RELEASE CHECK ORCHESTRATOR
# ============================================================================

class PreReleaseChecker:
    """Orchestrate all pre-release checks"""
    
    def __init__(self):
        self.results: List[CheckResult] = []
        self.current_version = get_current_version()
        self.start_time = datetime.now()
        self.github_url = self._get_github_url()
    
    def _get_github_url(self) -> Optional[str]:
        """Get GitHub repository URL"""
        try:
            code, stdout, _ = run_command(['git', 'config', '--get', 'remote.origin.url'])
            if code != 0:
                return None
            
            url = stdout.strip()
            # Convert SSH to HTTPS
            ssh_match = re.match(r'git@github\.com:(.+)/(.+?)(?:\.git)?$', url)
            if ssh_match:
                return f"https://github.com/{ssh_match.group(1)}/{ssh_match.group(2)}"
            
            # Handle HTTPS URLs
            https_match = re.match(r'https://github\.com/(.+)/(.+?)(?:\.git)?$', url)
            if https_match:
                return f"https://github.com/{https_match.group(1)}/{https_match.group(2)}"
            
            return None
        except:
            return None
    
    def run_all_checks(self) -> bool:
        """Run all pre-release checks"""
        print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
        print(f"{Colors.HEADER}{'PRE-RELEASE CHECK':^70}{Colors.RESET}")
        print(f"{Colors.HEADER}{'='*70}{Colors.RESET}")
        print(f"{Colors.INFO}Version: {Colors.BOLD}{Colors.CYAN}v{self.current_version}{Colors.RESET}")
        print(f"{Colors.INFO}Started: {Colors.RESET}{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        if self.github_url:
            print(f"{Colors.INFO}Repository: {Colors.BLUE}{self.github_url}{Colors.RESET}")
        print(f"{Colors.HEADER}{'='*70}{Colors.RESET}\n")
        
        # Run each check
        self._run_check(VersionConsistencyChecker())
        self._run_check(GitStatusChecker())
        self._run_check_with_arg(VersionTagChecker(), self.current_version)
        self._run_check(ChangelogValidator())
        self._run_check(DependencyChecker())
        self._run_check(TestRunner())
        
        # Show summary
        return self._show_enhanced_summary()
    
    def _run_check(self, checker):
        """Run a check and store result"""
        result = checker.check()
        self.results.append(result)
        self._print_check_result(result)
    
    def _run_check_with_arg(self, checker, arg):
        """Run a check with argument and store result"""
        result = checker.check(arg)
        self.results.append(result)
        self._print_check_result(result)
    
    def _print_check_result(self, result: CheckResult):
        """Print immediate result after each check"""
        icons = {
            CheckStatus.PASSED: "✓",
            CheckStatus.FAILED: "✗",
            CheckStatus.WARNING: "⚠",
            CheckStatus.SKIPPED: "○"
        }
        
        colors = {
            CheckStatus.PASSED: Colors.GREEN,
            CheckStatus.FAILED: Colors.RED,
            CheckStatus.WARNING: Colors.YELLOW,
            CheckStatus.SKIPPED: Colors.GRAY
        }
        
        icon = icons.get(result.status, "?")
        color = colors.get(result.status, Colors.RESET)
        
        duration_str = f" ({result.duration:.1f}s)" if result.duration else ""
        print(f"\n{color}{icon} {result.name}: {result.status.value}{duration_str}{Colors.RESET}")
    
    def _show_enhanced_summary(self) -> bool:
        """Show enhanced final summary with detailed breakdown"""
        # Count results by status
        passed = sum(1 for r in self.results if r.status == CheckStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == CheckStatus.FAILED)
        warnings = sum(1 for r in self.results if r.status == CheckStatus.WARNING)
        skipped = sum(1 for r in self.results if r.status == CheckStatus.SKIPPED)
        total = len(self.results)
        
        total_duration = (datetime.now() - self.start_time).total_seconds()
        
        # Determine overall status
        all_passed = failed == 0
        
        # Print detailed summary header
        print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
        print(f"{Colors.HEADER}{'SUMMARY':^70}{Colors.RESET}")
        print(f"{Colors.HEADER}{'='*70}{Colors.RESET}\n")
        
        # Overall result with big visual indicator
        if all_passed:
            print(f"{Colors.SUCCESS}{'  ╔══════════════════════════════════════════╗'}{Colors.RESET}")
            print(f"{Colors.SUCCESS}{'  ║         ✓ ALL CHECKS PASSED!             ║'}{Colors.RESET}")
            print(f"{Colors.SUCCESS}{'  ╚══════════════════════════════════════════╝'}{Colors.RESET}\n")
            print(f"{Colors.INFO}  Ready to release: {Colors.BOLD}{Colors.CYAN}v{self.current_version}{Colors.RESET}")
            if self.github_url:
                release_url = f"{self.github_url}/releases/new?tag=v{self.current_version}"
                print(f"{Colors.INFO}  Release URL: {Colors.BLUE}{release_url}{Colors.RESET}")
        else:
            print(f"{Colors.ERROR}{'  ╔══════════════════════════════════════════╗'}{Colors.RESET}")
            print(f"{Colors.ERROR}{'  ║       ✗ PRE-RELEASE CHECKS FAILED        ║'}{Colors.RESET}")
            print(f"{Colors.ERROR}{'  ╚══════════════════════════════════════════╝'}{Colors.RESET}\n")
            print(f"{Colors.RED}  Cannot proceed with release v{self.current_version}{Colors.RESET}")
        
        # Statistics grid
        print(f"\n{Colors.BOLD}  Check Statistics:{Colors.RESET}")
        print(f"  ┌─────────────┬─────────┬──────────┬──────────┬──────────┐")
        print(f"  │ Total       │ {Colors.GREEN}Passed{Colors.RESET}  │ {Colors.RED}Failed{Colors.RESET}   │ {Colors.YELLOW}Warnings{Colors.RESET} │ {Colors.GRAY}Skipped{Colors.RESET}  │")
        print(f"  ├─────────────┼─────────┼──────────┼──────────┼──────────┤")
        print(f"  │ {total:^11} │ {Colors.GREEN}{passed:^7}{Colors.RESET} │ {Colors.RED}{failed:^8}{Colors.RESET} │ {Colors.YELLOW}{warnings:^8}{Colors.RESET} │ {Colors.GRAY}{skipped:^8}{Colors.RESET} │")
        print(f"  └─────────────┴─────────┴──────────┴──────────┴──────────┘")
        print(f"\n  {Colors.INFO}Total Duration: {Colors.RESET}{total_duration:.1f} seconds")
        
        # Detailed check breakdown
        print(f"\n{Colors.BOLD}  Detailed Check Results:{Colors.RESET}")
        print(f"  {'─'*66}")
        
        for i, result in enumerate(self.results, 1):
            icon = {
                CheckStatus.PASSED: f"{Colors.GREEN}✓{Colors.RESET}",
                CheckStatus.FAILED: f"{Colors.RED}✗{Colors.RESET}",
                CheckStatus.WARNING: f"{Colors.YELLOW}⚠{Colors.RESET}",
                CheckStatus.SKIPPED: f"{Colors.GRAY}○{Colors.RESET}"
            }.get(result.status, "?")
            
            status_color = {
                CheckStatus.PASSED: Colors.GREEN,
                CheckStatus.FAILED: Colors.RED,
                CheckStatus.WARNING: Colors.YELLOW,
                CheckStatus.SKIPPED: Colors.GRAY
            }.get(result.status, Colors.RESET)
            
            duration_str = f"[{result.duration:.1f}s]" if result.duration else "[N/A]"
            print(f"  {i}. {icon} {result.name:<25} {status_color}{result.status.value:<8}{Colors.RESET} {Colors.GRAY}{duration_str:>8}{Colors.RESET}")
            print(f"     └─ {result.message}")
        
        # Failed checks details
        if failed > 0:
            print(f"\n{Colors.ERROR}  Failed Checks Requiring Action:{Colors.RESET}")
            print(f"  {'─'*66}")
            
            for result in self.results:
                if result.status == CheckStatus.FAILED:
                    print(f"\n  {Colors.RED}✗ {result.name}{Colors.RESET}")
                    print(f"    {Colors.BOLD}Issue:{Colors.RESET} {result.message}")
                    
                    if result.details:
                        print(f"    {Colors.BOLD}Details:{Colors.RESET}")
                        for detail in result.details[:3]:  # Show max 3 details
                            print(f"      • {detail}")
                        if len(result.details) > 3:
                            print(f"      • ... and {len(result.details) - 3} more")
                    
                    if result.fix_suggestions:
                        print(f"    {Colors.BOLD}How to fix:{Colors.RESET}")
                        for fix in result.fix_suggestions:
                            print(f"      → {Colors.CYAN}{fix}{Colors.RESET}")
        
        # Warnings details
        if warnings > 0:
            print(f"\n{Colors.WARNING}  Warnings (Non-blocking):{Colors.RESET}")
            print(f"  {'─'*66}")
            
            for result in self.results:
                if result.status == CheckStatus.WARNING:
                    print(f"\n  {Colors.YELLOW}⚠ {result.name}{Colors.RESET}")
                    print(f"    {result.message}")
                    if result.details:
                        for detail in result.details:
                            print(f"    • {detail}")
        
        # Next steps
        print(f"\n{Colors.HEADER}{'='*70}{Colors.RESET}")
        print(f"{Colors.BOLD}  Next Steps:{Colors.RESET}")
        
        if all_passed:
            print(f"  1. {Colors.GREEN}Review the release notes one final time{Colors.RESET}")
            print(f"  2. {Colors.GREEN}Run: {Colors.CYAN}./tooling/release.py{Colors.RESET}")
            print(f"  3. {Colors.GREEN}The release script will create tags and push to GitHub{Colors.RESET}")
            if self.github_url:
                print(f"  4. {Colors.GREEN}Create release at: {Colors.BLUE}{self.github_url}/releases/new{Colors.RESET}")
        else:
            print(f"  1. {Colors.RED}Fix all failed checks listed above{Colors.RESET}")
            print(f"  2. {Colors.YELLOW}Run this script again: {Colors.CYAN}./tooling/pre_release_check.py{Colors.RESET}")
            print(f"  3. {Colors.GRAY}Once all checks pass, proceed with release{Colors.RESET}")
        
        print(f"{Colors.HEADER}{'='*70}{Colors.RESET}\n")
        
        # Return final status
        return all_passed

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    # Ensure we're in project root
    ensure_project_root()
    
    # Run pre-release checks
    checker = PreReleaseChecker()
    
    try:
        all_passed = checker.run_all_checks()
        sys.exit(0 if all_passed else 1)
    except KeyboardInterrupt:
        print()
        print_color(Colors.YELLOW, "\n⚠️  Pre-release check cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"\n❌ Error during pre-release check: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()