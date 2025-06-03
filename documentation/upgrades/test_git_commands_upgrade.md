# Upgrade Plan: test_git_commands.py

## Overview
Tests git commands for debugging, identifies hanging issues, and performs basic performance testing.

## Current State
- **Dependencies**: Standard library only  
- **Purpose**: Simple test structure for git command execution
- **Features**: Basic timeout handling

## Recommended Upgrades

### 1. Comprehensive Git Command Test Suite
```python
# Full test coverage for git operations
import pytest
from unittest.mock import patch, MagicMock, call
import git
import subprocess
from pathlib import Path
import time
from typing import List, Dict, Any

class TestGitCommands:
    """Comprehensive test suite for git command execution"""
    
    @pytest.fixture
    def mock_repo(self, tmp_path):
        """Create a mock repository for testing"""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        
        repo = git.Repo.init(repo_path)
        
        # Configure repo
        with repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")
        
        # Create test structure
        self._create_test_commits(repo, repo_path)
        
        yield repo
    
    def _create_test_commits(self, repo: git.Repo, repo_path: Path):
        """Create realistic test commits"""
        # Create files with different patterns
        test_files = [
            ("src/main.py", "print('Hello World')"),
            ("tests/test_main.py", "def test_main(): pass"),
            ("README.md", "# Test Project"),
            (".gitignore", "*.pyc\n__pycache__/"),
            ("docs/api.md", "# API Documentation")
        ]
        
        for file_path, content in test_files:
            full_path = repo_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            repo.index.add([file_path])
        
        repo.index.commit("Initial commit")
        
        # Create branches
        feature_branch = repo.create_head("feature/test")
        develop_branch = repo.create_head("develop")
        
        # Add commits to different branches
        repo.head.reference = feature_branch
        (repo_path / "feature.txt").write_text("Feature content")
        repo.index.add(["feature.txt"])
        repo.index.commit("Add feature")
        
        repo.head.reference = develop_branch
        (repo_path / "develop.txt").write_text("Develop content")
        repo.index.add(["develop.txt"])
        repo.index.commit("Add develop file")
        
        # Return to main/master
        repo.head.reference = repo.heads[0]
    
    @pytest.mark.parametrize("command,expected_in_output", [
        (["git", "status"], "On branch"),
        (["git", "log", "--oneline", "-n", "1"], "Initial commit"),
        (["git", "branch", "-a"], ["develop", "feature/test"]),
        (["git", "diff", "--stat"], ""),
        (["git", "show", "--name-only", "HEAD"], "Initial commit")
    ])
    def test_basic_git_commands(self, mock_repo, command, expected_in_output):
        """Test basic git command execution"""
        result = subprocess.run(
            command,
            cwd=mock_repo.working_dir,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        
        if isinstance(expected_in_output, list):
            for expected in expected_in_output:
                assert expected in result.stdout
        else:
            assert expected_in_output in result.stdout
    
    @pytest.mark.timeout(5)
    def test_command_timeout(self, mock_repo):
        """Test that commands complete within timeout"""
        commands = [
            ["git", "log", "--all", "--oneline"],
            ["git", "rev-list", "--all", "--count"],
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            ["git", "log", "--since=1.year.ago", "--until=now"]
        ]
        
        for cmd in commands:
            start = time.time()
            result = subprocess.run(
                cmd,
                cwd=mock_repo.working_dir,
                capture_output=True,
                timeout=3
            )
            elapsed = time.time() - start
            
            assert result.returncode == 0
            assert elapsed < 3, f"Command {' '.join(cmd)} took {elapsed}s"
```

### 2. Git Performance Profiler
```python
# Profile git command performance
import cProfile
import pstats
from io import StringIO
import matplotlib.pyplot as plt
from typing import Callable, List, Tuple
import numpy as np

class GitCommandProfiler:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.profiles = {}
        self.timing_data = {}
        
    def profile_command(
        self,
        name: str,
        command: List[str],
        iterations: int = 10
    ) -> Dict[str, Any]:
        """Profile a git command"""
        profiler = cProfile.Profile()
        times = []
        
        for _ in range(iterations):
            start = time.perf_counter()
            
            profiler.enable()
            result = subprocess.run(
                command,
                cwd=self.repo_path,
                capture_output=True
            )
            profiler.disable()
            
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        # Store profile
        self.profiles[name] = profiler
        self.timing_data[name] = times
        
        # Generate stats
        stats = self._analyze_profile(profiler)
        
        return {
            'name': name,
            'command': ' '.join(command),
            'mean_time': np.mean(times),
            'std_time': np.std(times),
            'min_time': np.min(times),
            'max_time': np.max(times),
            'profile_stats': stats
        }
    
    def _analyze_profile(self, profiler: cProfile.Profile) -> Dict[str, Any]:
        """Analyze profiling data"""
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(10)  # Top 10 functions
        
        return {
            'top_functions': s.getvalue(),
            'total_calls': ps.total_calls,
            'total_time': ps.total_tt
        }
    
    def compare_commands(self, commands: List[Tuple[str, List[str]]]):
        """Compare performance of multiple commands"""
        results = []
        
        for name, cmd in commands:
            result = self.profile_command(name, cmd)
            results.append(result)
        
        # Generate comparison chart
        self._plot_comparison(results)
        
        return results
    
    def _plot_comparison(self, results: List[Dict[str, Any]]):
        """Plot performance comparison"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        names = [r['name'] for r in results]
        means = [r['mean_time'] for r in results]
        stds = [r['std_time'] for r in results]
        
        # Bar chart with error bars
        x = np.arange(len(names))
        ax1.bar(x, means, yerr=stds, capsize=5)
        ax1.set_xlabel('Command')
        ax1.set_ylabel('Time (seconds)')
        ax1.set_title('Git Command Performance Comparison')
        ax1.set_xticks(x)
        ax1.set_xticklabels(names, rotation=45, ha='right')
        
        # Box plot of timing distributions
        all_times = [self.timing_data[name] for name in names]
        ax2.boxplot(all_times, labels=names)
        ax2.set_xlabel('Command')
        ax2.set_ylabel('Time (seconds)')
        ax2.set_title('Timing Distribution')
        ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig('git_performance_comparison.png')
        plt.close()
```

### 3. Git Command Compatibility Tester
```python
# Test git command compatibility across versions
import re
from packaging import version

class GitCompatibilityTester:
    def __init__(self):
        self.git_version = self._get_git_version()
        self.compatibility_issues = []
        
    def _get_git_version(self) -> str:
        """Get installed git version"""
        result = subprocess.run(
            ['git', '--version'],
            capture_output=True,
            text=True
        )
        
        # Parse version from output
        match = re.search(r'git version (\d+\.\d+\.\d+)', result.stdout)
        if match:
            return match.group(1)
        return "unknown"
    
    def test_command_compatibility(self, repo_path: str):
        """Test commands for version compatibility"""
        # Commands with version requirements
        version_specific_commands = {
            # Command: (min_version, test_command)
            'sparse-checkout': ('2.25.0', ['git', 'sparse-checkout', 'list']),
            'switch': ('2.23.0', ['git', 'switch', '--list']),
            'restore': ('2.23.0', ['git', 'restore', '--help']),
            'main-branch': ('2.28.0', ['git', 'config', 'init.defaultBranch']),
            'maintenance': ('2.31.0', ['git', 'maintenance', 'run', '--auto'])
        }
        
        results = {}
        
        for feature, (min_version, test_cmd) in version_specific_commands.items():
            if version.parse(self.git_version) >= version.parse(min_version):
                # Test if command works
                result = subprocess.run(
                    test_cmd,
                    cwd=repo_path,
                    capture_output=True
                )
                
                results[feature] = {
                    'supported': True,
                    'works': result.returncode == 0,
                    'min_version': min_version
                }
            else:
                results[feature] = {
                    'supported': False,
                    'works': False,
                    'min_version': min_version,
                    'current_version': self.git_version
                }
                
                self.compatibility_issues.append(
                    f"{feature} requires git {min_version}, but {self.git_version} is installed"
                )
        
        return results
    
    def generate_compatibility_report(self) -> str:
        """Generate compatibility report"""
        report = [
            "Git Compatibility Report",
            "=" * 40,
            f"Git Version: {self.git_version}",
            ""
        ]
        
        if self.compatibility_issues:
            report.append("Compatibility Issues:")
            for issue in self.compatibility_issues:
                report.append(f"  - {issue}")
        else:
            report.append("✓ All tested features are compatible")
        
        return "\n".join(report)
```

### 4. Git Command Security Analyzer
```python
# Analyze git commands for security issues
from typing import List, Dict, Set

class GitSecurityAnalyzer:
    def __init__(self):
        self.dangerous_patterns = {
            'force_push': re.compile(r'--force|-f'),
            'clean_untracked': re.compile(r'clean.*-f'),
            'reset_hard': re.compile(r'reset.*--hard'),
            'filter_branch': re.compile(r'filter-branch'),
            'reflog_expire': re.compile(r'reflog.*expire'),
            'credential_store': re.compile(r'credential\.helper.*store')
        }
        
        self.safe_alternatives = {
            'force_push': 'Use --force-with-lease instead',
            'clean_untracked': 'Use -n (dry run) first',
            'reset_hard': 'Consider using --soft or --mixed',
            'filter_branch': 'Use filter-repo instead',
            'reflog_expire': 'Be careful with reflog expiration',
            'credential_store': 'Use credential cache or manager'
        }
    
    def analyze_command(self, command: List[str]) -> Dict[str, Any]:
        """Analyze a git command for security issues"""
        cmd_str = ' '.join(command)
        issues = []
        risk_level = 'low'
        
        for risk_type, pattern in self.dangerous_patterns.items():
            if pattern.search(cmd_str):
                issues.append({
                    'type': risk_type,
                    'suggestion': self.safe_alternatives.get(risk_type, '')
                })
                
                if risk_type in ['force_push', 'filter_branch', 'reset_hard']:
                    risk_level = 'high'
                elif risk_level != 'high':
                    risk_level = 'medium'
        
        return {
            'command': cmd_str,
            'risk_level': risk_level,
            'issues': issues,
            'is_safe': len(issues) == 0
        }
    
    def scan_script(self, script_path: Path) -> List[Dict[str, Any]]:
        """Scan a script for dangerous git commands"""
        risky_commands = []
        
        with open(script_path) as f:
            content = f.read()
        
        # Find git commands in script
        git_commands = re.findall(r'git\s+[^\n]+', content)
        
        for cmd in git_commands:
            analysis = self.analyze_command(cmd.split())
            if not analysis['is_safe']:
                analysis['line'] = self._find_line_number(content, cmd)
                risky_commands.append(analysis)
        
        return risky_commands
    
    def _find_line_number(self, content: str, command: str) -> int:
        """Find line number of command in content"""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if command in line:
                return i
        return -1
```

### 5. Git Command Mocking Framework
```python
# Mock git commands for testing
from unittest.mock import Mock, patch
from typing import Dict, Any, Optional

class GitCommandMocker:
    def __init__(self):
        self.mock_responses = {}
        self.call_history = []
        
    def add_mock_response(
        self,
        command: List[str],
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0
    ):
        """Add a mock response for a git command"""
        cmd_key = ' '.join(command)
        self.mock_responses[cmd_key] = {
            'stdout': stdout,
            'stderr': stderr,
            'returncode': returncode
        }
    
    def mock_subprocess_run(self, *args, **kwargs):
        """Mock subprocess.run for git commands"""
        command = args[0] if args else kwargs.get('args', [])
        cmd_str = ' '.join(command) if isinstance(command, list) else command
        
        # Record call
        self.call_history.append({
            'command': command,
            'kwargs': kwargs,
            'timestamp': time.time()
        })
        
        # Find matching mock response
        for pattern, response in self.mock_responses.items():
            if pattern in cmd_str or cmd_str == pattern:
                return Mock(
                    stdout=response['stdout'],
                    stderr=response['stderr'],
                    returncode=response['returncode']
                )
        
        # Default response
        return Mock(stdout="", stderr="", returncode=0)
    
    def setup_common_mocks(self):
        """Set up common git command mocks"""
        self.add_mock_response(
            ['git', 'status'],
            stdout="On branch main\nnothing to commit, working tree clean"
        )
        
        self.add_mock_response(
            ['git', 'log', '--oneline', '-n', '5'],
            stdout="""abc123 Latest commit
def456 Previous commit
ghi789 Another commit
jkl012 Older commit
mno345 Initial commit"""
        )
        
        self.add_mock_response(
            ['git', 'branch', '-a'],
            stdout="""* main
  develop
  feature/test
  remotes/origin/main
  remotes/origin/develop"""
        )
    
    def assert_command_called(self, command: List[str]) -> bool:
        """Assert a command was called"""
        cmd_str = ' '.join(command)
        
        for call in self.call_history:
            call_str = ' '.join(call['command'])
            if cmd_str in call_str or call_str == cmd_str:
                return True
        
        return False
    
    def get_call_count(self, command: Optional[List[str]] = None) -> int:
        """Get number of times a command was called"""
        if command is None:
            return len(self.call_history)
        
        cmd_str = ' '.join(command)
        count = 0
        
        for call in self.call_history:
            call_str = ' '.join(call['command'])
            if cmd_str in call_str or call_str == cmd_str:
                count += 1
        
        return count

# Example usage in tests
class TestWithMockedGit:
    def test_changelog_sync_with_mocks(self):
        """Test changelog sync with mocked git commands"""
        mocker = GitCommandMocker()
        mocker.setup_common_mocks()
        
        # Add specific mocks for test
        mocker.add_mock_response(
            ['git', 'log', '--since=v1.0.0', '--format=%H|%s|%an|%ae'],
            stdout="""abc123|feat: add new feature|John Doe|john@example.com
def456|fix: resolve issue|Jane Smith|jane@example.com"""
        )
        
        with patch('subprocess.run', mocker.mock_subprocess_run):
            # Run code that uses git commands
            from sync_changelogs import process_changelog
            result = process_changelog()
            
            # Verify commands were called
            assert mocker.assert_command_called(['git', 'log'])
            assert mocker.get_call_count() > 0
```

### 6. Git Command Benchmark Suite
```python
# Comprehensive benchmarking for git operations
from dataclasses import dataclass
from typing import List, Dict, Callable
import json

@dataclass
class BenchmarkScenario:
    name: str
    setup: Callable
    commands: List[Tuple[str, List[str]]]
    teardown: Optional[Callable] = None

class GitBenchmarkSuite:
    def __init__(self):
        self.scenarios = []
        self.results = {}
        
    def add_scenario(self, scenario: BenchmarkScenario):
        """Add a benchmark scenario"""
        self.scenarios.append(scenario)
    
    def run_benchmarks(self, iterations: int = 5) -> Dict[str, Any]:
        """Run all benchmark scenarios"""
        for scenario in self.scenarios:
            print(f"Running scenario: {scenario.name}")
            
            # Setup
            repo_path = scenario.setup()
            
            # Benchmark commands
            scenario_results = {}
            
            for cmd_name, command in scenario.commands:
                times = []
                
                for _ in range(iterations):
                    start = time.perf_counter()
                    subprocess.run(
                        command,
                        cwd=repo_path,
                        capture_output=True
                    )
                    elapsed = time.perf_counter() - start
                    times.append(elapsed)
                
                scenario_results[cmd_name] = {
                    'command': ' '.join(command),
                    'times': times,
                    'mean': np.mean(times),
                    'std': np.std(times),
                    'min': np.min(times),
                    'max': np.max(times)
                }
            
            self.results[scenario.name] = scenario_results
            
            # Teardown
            if scenario.teardown:
                scenario.teardown(repo_path)
        
        return self.results
    
    def save_results(self, filename: str = "benchmark_results.json"):
        """Save benchmark results to file"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
    
    def generate_report(self) -> str:
        """Generate benchmark report"""
        report = ["Git Command Benchmark Report", "=" * 40, ""]
        
        for scenario_name, scenario_results in self.results.items():
            report.append(f"Scenario: {scenario_name}")
            report.append("-" * 30)
            
            # Sort by mean time
            sorted_commands = sorted(
                scenario_results.items(),
                key=lambda x: x[1]['mean']
            )
            
            for cmd_name, stats in sorted_commands:
                report.append(f"  {cmd_name}:")
                report.append(f"    Command: {stats['command']}")
                report.append(f"    Mean: {stats['mean']:.4f}s")
                report.append(f"    Std: {stats['std']:.4f}s")
                report.append(f"    Range: [{stats['min']:.4f}s - {stats['max']:.4f}s]")
            
            report.append("")
        
        return "\n".join(report)

# Define standard benchmark scenarios
def create_standard_benchmarks() -> GitBenchmarkSuite:
    """Create standard benchmark scenarios"""
    suite = GitBenchmarkSuite()
    
    # Small repository scenario
    def setup_small_repo():
        # Create repo with 100 commits
        pass
    
    small_repo_scenario = BenchmarkScenario(
        name="small_repository",
        setup=setup_small_repo,
        commands=[
            ("log_all", ["git", "log", "--all", "--oneline"]),
            ("log_limit", ["git", "log", "--oneline", "-n", "10"]),
            ("status", ["git", "status"]),
            ("diff", ["git", "diff", "HEAD~1"]),
            ("branch_list", ["git", "branch", "-a"])
        ]
    )
    
    suite.add_scenario(small_repo_scenario)
    
    return suite
```

## Dependencies to Add
```toml
[project.dependencies]
pytest = "^7.4.3"
pytest-timeout = "^2.2.0"
pytest-mock = "^3.12.0"
GitPython = "^3.1.40"
matplotlib = "^3.8.2"
numpy = "^1.26.2"
packaging = "^23.2"
psutil = "^5.9.6"
```

## Migration Strategy
1. Keep simple test script for quick checks
2. Build comprehensive test suite
3. Add profiling capabilities
4. Implement security analysis
5. Create benchmarking framework

## Expected Benefits
- **Coverage**: Complete git command testing
- **Performance**: Identify slow operations
- **Security**: Detect risky commands
- **Reliability**: Prevent command failures
- **Benchmarking**: Track performance over time