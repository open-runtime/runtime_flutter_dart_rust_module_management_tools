# Upgrade Plan: simple_changelog_test.py

## Overview
Minimal test script for debugging changelog sync issues. Currently used to isolate hanging problems.

## Current State
- **Dependencies**: Standard library only
- **Purpose**: Debug tool for testing basic git operations
- **Scope**: Very limited, focused on specific debugging

## Recommended Upgrades

### 1. Comprehensive Test Suite
```python
# Convert to proper test suite with pytest
import pytest
import subprocess
from pathlib import Path
import tempfile
import shutil
from typing import Dict, List, Any
import git

class TestChangelogOperations:
    """Comprehensive test suite for changelog operations"""
    
    @pytest.fixture
    def test_repo(self, tmp_path):
        """Create a test git repository"""
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        
        # Initialize repo
        repo = git.Repo.init(repo_dir)
        
        # Configure git
        repo.config_writer().set_value("user", "name", "Test User").release()
        repo.config_writer().set_value("user", "email", "test@example.com").release()
        
        # Create test commits
        for i in range(5):
            file_path = repo_dir / f"file{i}.txt"
            file_path.write_text(f"Content {i}")
            repo.index.add([str(file_path)])
            repo.index.commit(f"Test commit {i}")
        
        # Create tags
        repo.create_tag("v1.0.0", message="Version 1.0.0")
        
        # Add more commits
        for i in range(5, 10):
            file_path = repo_dir / f"file{i}.txt"
            file_path.write_text(f"Content {i}")
            repo.index.add([str(file_path)])
            repo.index.commit(f"Test commit {i}")
        
        repo.create_tag("v1.1.0", message="Version 1.1.0")
        
        yield repo_dir
        
        # Cleanup
        shutil.rmtree(repo_dir)
    
    def test_git_log_basic(self, test_repo):
        """Test basic git log operation"""
        result = subprocess.run(
            ['git', 'log', '--oneline', '-n', '5'],
            cwd=test_repo,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert len(result.stdout.strip().split('\n')) == 5
    
    def test_git_log_date_range(self, test_repo):
        """Test git log with date range"""
        result = subprocess.run(
            ['git', 'log', '--since=1.year.ago', '--oneline'],
            cwd=test_repo,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert result.stdout.strip() != ""
    
    @pytest.mark.timeout(5)
    def test_git_log_no_hang(self, test_repo):
        """Ensure git log doesn't hang"""
        # This test will fail if it takes more than 5 seconds
        result = subprocess.run(
            ['git', 'log', '--all', '--oneline'],
            cwd=test_repo,
            capture_output=True,
            text=True,
            timeout=3
        )
        
        assert result.returncode == 0
    
    def test_changelog_sync_components(self, test_repo):
        """Test individual components of changelog sync"""
        # Test getting commits between tags
        result = subprocess.run(
            ['git', 'log', 'v1.0.0..v1.1.0', '--oneline'],
            cwd=test_repo,
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        commits = result.stdout.strip().split('\n')
        assert len(commits) == 5  # Should have 5 commits between tags
```

### 2. Performance Testing
```python
# Performance benchmarks for changelog operations
import time
import statistics
from typing import List, Callable, Dict
import matplotlib.pyplot as plt
from dataclasses import dataclass

@dataclass
class BenchmarkResult:
    name: str
    times: List[float]
    mean: float
    median: float
    std_dev: float
    min_time: float
    max_time: float

class ChangelogPerformanceTester:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.results = {}
        
    def benchmark_operation(
        self,
        name: str,
        operation: Callable,
        iterations: int = 10,
        warmup: int = 2
    ) -> BenchmarkResult:
        """Benchmark a changelog operation"""
        # Warmup runs
        for _ in range(warmup):
            operation()
        
        # Timed runs
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            operation()
            end = time.perf_counter()
            times.append(end - start)
        
        result = BenchmarkResult(
            name=name,
            times=times,
            mean=statistics.mean(times),
            median=statistics.median(times),
            std_dev=statistics.stdev(times) if len(times) > 1 else 0,
            min_time=min(times),
            max_time=max(times)
        )
        
        self.results[name] = result
        return result
    
    def run_all_benchmarks(self):
        """Run all performance benchmarks"""
        # Benchmark git log operations
        self.benchmark_operation(
            "git_log_simple",
            lambda: subprocess.run(
                ['git', 'log', '--oneline', '-n', '100'],
                cwd=self.repo_path,
                capture_output=True
            )
        )
        
        self.benchmark_operation(
            "git_log_with_grep",
            lambda: subprocess.run(
                ['git', 'log', '--grep=fix', '--oneline'],
                cwd=self.repo_path,
                capture_output=True
            )
        )
        
        self.benchmark_operation(
            "git_diff_tree",
            lambda: subprocess.run(
                ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True
            )
        )
        
        # Benchmark Python git operations
        import git
        repo = git.Repo(self.repo_path)
        
        self.benchmark_operation(
            "python_git_log",
            lambda: list(repo.iter_commits(max_count=100))
        )
        
        self.benchmark_operation(
            "python_git_tags",
            lambda: [tag.name for tag in repo.tags]
        )
    
    def generate_report(self) -> str:
        """Generate performance report"""
        report = ["Changelog Performance Report", "=" * 40, ""]
        
        for name, result in self.results.items():
            report.append(f"{name}:")
            report.append(f"  Mean: {result.mean:.4f}s")
            report.append(f"  Median: {result.median:.4f}s")
            report.append(f"  Std Dev: {result.std_dev:.4f}s")
            report.append(f"  Min: {result.min_time:.4f}s")
            report.append(f"  Max: {result.max_time:.4f}s")
            report.append("")
        
        return "\n".join(report)
    
    def plot_results(self, output_file: str = "performance_results.png"):
        """Plot performance results"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Bar chart of mean times
        names = list(self.results.keys())
        means = [r.mean for r in self.results.values()]
        
        ax1.bar(names, means)
        ax1.set_xlabel('Operation')
        ax1.set_ylabel('Time (seconds)')
        ax1.set_title('Mean Execution Time')
        ax1.tick_params(axis='x', rotation=45)
        
        # Box plot of all times
        all_times = [r.times for r in self.results.values()]
        ax2.boxplot(all_times, labels=names)
        ax2.set_xlabel('Operation')
        ax2.set_ylabel('Time (seconds)')
        ax2.set_title('Execution Time Distribution')
        ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(output_file)
        plt.close()
```

### 3. Hang Detection and Diagnosis
```python
# Advanced hang detection and diagnosis
import threading
import signal
import traceback
import faulthandler
from typing import Optional, Callable
import psutil

class HangDetector:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.timer = None
        self.process = None
        self.operation_stack = []
        
    def monitor_operation(
        self,
        operation: Callable,
        name: str,
        timeout: Optional[int] = None
    ):
        """Monitor an operation for hangs"""
        timeout = timeout or self.timeout
        
        # Start monitoring
        self.operation_stack.append(name)
        self.timer = threading.Timer(timeout, self._handle_timeout)
        self.timer.start()
        
        try:
            # Run operation
            result = operation()
            
            # Cancel timer if operation completed
            self.timer.cancel()
            self.operation_stack.pop()
            
            return result
            
        except Exception as e:
            self.timer.cancel()
            self.operation_stack.pop()
            raise e
    
    def _handle_timeout(self):
        """Handle operation timeout"""
        print(f"\n!!! HANG DETECTED !!!")
        print(f"Operation: {self.operation_stack[-1] if self.operation_stack else 'Unknown'}")
        print(f"Timeout: {self.timeout}s exceeded")
        
        # Dump Python stack traces
        print("\nPython stack traces:")
        faulthandler.dump_traceback()
        
        # Get process info
        if self.process:
            self._dump_process_info()
        
        # Force exit
        os._exit(1)
    
    def _dump_process_info(self):
        """Dump process information"""
        try:
            p = psutil.Process(self.process.pid)
            
            print(f"\nProcess info:")
            print(f"  PID: {p.pid}")
            print(f"  Status: {p.status()}")
            print(f"  CPU: {p.cpu_percent()}%")
            print(f"  Memory: {p.memory_info().rss / 1024 / 1024:.2f} MB")
            
            # Get child processes
            children = p.children(recursive=True)
            if children:
                print(f"\nChild processes ({len(children)}):")
                for child in children:
                    print(f"  - PID {child.pid}: {child.name()}")
                    
        except Exception as e:
            print(f"Error getting process info: {e}")

class ChangelogHangTester:
    def __init__(self):
        self.detector = HangDetector()
        self.test_results = []
        
    def test_git_operations(self, repo_path: str):
        """Test various git operations for hangs"""
        operations = [
            ("simple_log", lambda: subprocess.run(
                ['git', 'log', '--oneline', '-n', '10'],
                cwd=repo_path,
                capture_output=True
            )),
            
            ("log_with_date", lambda: subprocess.run(
                ['git', 'log', '--since=2020-01-01', '--oneline'],
                cwd=repo_path,
                capture_output=True
            )),
            
            ("log_all_branches", lambda: subprocess.run(
                ['git', 'log', '--all', '--oneline'],
                cwd=repo_path,
                capture_output=True
            )),
            
            ("diff_tree", lambda: subprocess.run(
                ['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'],
                cwd=repo_path,
                capture_output=True
            )),
            
            ("rev_list", lambda: subprocess.run(
                ['git', 'rev-list', '--all', '--count'],
                cwd=repo_path,
                capture_output=True
            ))
        ]
        
        for name, operation in operations:
            print(f"Testing {name}...", end='', flush=True)
            
            try:
                result = self.detector.monitor_operation(
                    operation,
                    name,
                    timeout=5
                )
                
                print(f" OK ({result.returncode if hasattr(result, 'returncode') else 'success'})")
                self.test_results.append((name, 'passed', None))
                
            except Exception as e:
                print(f" FAILED: {e}")
                self.test_results.append((name, 'failed', str(e)))
    
    def generate_report(self) -> str:
        """Generate test report"""
        report = ["Hang Test Report", "=" * 40, ""]
        
        passed = sum(1 for _, status, _ in self.test_results if status == 'passed')
        failed = sum(1 for _, status, _ in self.test_results if status == 'failed')
        
        report.append(f"Total tests: {len(self.test_results)}")
        report.append(f"Passed: {passed}")
        report.append(f"Failed: {failed}")
        report.append("")
        
        if failed > 0:
            report.append("Failed tests:")
            for name, status, error in self.test_results:
                if status == 'failed':
                    report.append(f"  - {name}: {error}")
        
        return "\n".join(report)
```

### 4. Integration Testing
```python
# Integration tests for changelog sync
import tempfile
import shutil
from pathlib import Path

class ChangelogIntegrationTester:
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.test_dir) / "test_repo"
        
        # Create test repository with realistic structure
        self._create_test_repository()
        
    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)
    
    def _create_test_repository(self):
        """Create realistic test repository"""
        import git
        
        # Initialize repo
        repo = git.Repo.init(self.repo_path)
        
        # Create package structure
        packages = ['dart', 'flutter', 'rust']
        
        for package in packages:
            pkg_dir = self.repo_path / package
            pkg_dir.mkdir()
            
            # Create files
            (pkg_dir / 'README.md').write_text(f"# {package.title()} Package")
            (pkg_dir / 'CHANGELOG.md').write_text("# Changelog\n\n## [Unreleased]\n\n")
            
            if package == 'dart':
                (pkg_dir / 'pubspec.yaml').write_text(f"name: {package}\nversion: 1.0.0\n")
            elif package == 'rust':
                (pkg_dir / 'Cargo.toml').write_text(f'[package]\nname = "{package}"\nversion = "1.0.0"\n')
        
        # Initial commit
        repo.index.add('*')
        repo.index.commit("Initial commit")
        repo.create_tag("v1.0.0")
        
        # Make changes
        for i in range(5):
            package = packages[i % len(packages)]
            file_path = self.repo_path / package / f"feature_{i}.txt"
            file_path.write_text(f"Feature {i}")
            repo.index.add(str(file_path))
            repo.index.commit(f"feat({package}): add feature {i}")
        
        return repo
    
    def test_full_changelog_sync(self):
        """Test complete changelog sync workflow"""
        from sync_changelogs import ChangelogProcessor
        
        processor = ChangelogProcessor()
        
        # Test tag-based processing
        result = processor.process_repository(
            self.repo_path,
            since_tag="v1.0.0"
        )
        
        assert result is not None
        assert 'entries' in result
        assert len(result['entries']) > 0
    
    def test_incremental_sync(self):
        """Test incremental changelog updates"""
        # First sync
        self.test_full_changelog_sync()
        
        # Add more commits
        repo = git.Repo(self.repo_path)
        
        for i in range(3):
            file_path = self.repo_path / f"new_feature_{i}.txt"
            file_path.write_text(f"New feature {i}")
            repo.index.add(str(file_path))
            repo.index.commit(f"feat: add new feature {i}")
        
        # Incremental sync
        from sync_changelogs import ChangelogProcessor
        
        processor = ChangelogProcessor()
        result = processor.process_repository(
            self.repo_path,
            incremental=True
        )
        
        assert len(result['entries']) == 3  # Only new commits
```

### 5. Debugging Tools
```python
# Enhanced debugging tools for changelog issues
import logging
import sys
from typing import Any

class ChangelogDebugger:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.setup_logging()
        
    def setup_logging(self):
        """Set up detailed logging"""
        level = logging.DEBUG if self.verbose else logging.INFO
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('changelog_debug.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Enable git command logging
        git_logger = logging.getLogger('git.cmd')
        git_logger.setLevel(logging.DEBUG)
        
        # Enable subprocess logging
        subprocess_logger = logging.getLogger('subprocess')
        subprocess_logger.setLevel(logging.DEBUG)
    
    def trace_git_command(self, cmd: List[str], cwd: str = None):
        """Trace git command execution"""
        logger = logging.getLogger('git.trace')
        
        logger.debug(f"Executing: {' '.join(cmd)}")
        logger.debug(f"Working directory: {cwd or os.getcwd()}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True
            )
            
            elapsed = time.time() - start_time
            
            logger.debug(f"Completed in {elapsed:.3f}s")
            logger.debug(f"Return code: {result.returncode}")
            
            if result.stdout:
                logger.debug(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                logger.debug(f"STDERR:\n{result.stderr}")
            
            return result
            
        except Exception as e:
            logger.error(f"Command failed: {e}")
            raise
    
    def analyze_repository(self, repo_path: str):
        """Analyze repository for potential issues"""
        import git
        
        logger = logging.getLogger('repo.analysis')
        
        try:
            repo = git.Repo(repo_path)
            
            # Check repo state
            logger.info(f"Repository: {repo_path}")
            logger.info(f"Current branch: {repo.active_branch}")
            logger.info(f"Is dirty: {repo.is_dirty()}")
            logger.info(f"Untracked files: {len(repo.untracked_files)}")
            
            # Count objects
            commit_count = len(list(repo.iter_commits()))
            tag_count = len(repo.tags)
            branch_count = len(list(repo.branches))
            
            logger.info(f"Commits: {commit_count}")
            logger.info(f"Tags: {tag_count}")
            logger.info(f"Branches: {branch_count}")
            
            # Check for large history
            if commit_count > 10000:
                logger.warning(f"Large repository: {commit_count} commits")
                logger.warning("Consider using --shallow-since or limiting date range")
            
            # Check for problematic patterns
            self._check_for_issues(repo)
            
        except Exception as e:
            logger.error(f"Repository analysis failed: {e}")
            raise
    
    def _check_for_issues(self, repo: git.Repo):
        """Check for common issues"""
        logger = logging.getLogger('repo.issues')
        
        # Check for merge commits
        merge_commits = [
            c for c in repo.iter_commits(max_count=100)
            if len(c.parents) > 1
        ]
        
        if len(merge_commits) > 20:
            logger.warning(f"Many merge commits found: {len(merge_commits)}/100")
            logger.warning("This may slow down processing")
```

## Dependencies to Add
```toml
[project.dependencies]
pytest = "^7.4.3"
pytest-timeout = "^2.2.0"
pytest-benchmark = "^4.0.0"
matplotlib = "^3.8.2"
psutil = "^5.9.6"
faulthandler = "^3.2"  # Built-in but for clarity
GitPython = "^3.1.40"
```

## Migration Strategy
1. Keep simple test for basic debugging
2. Build comprehensive test suite separately
3. Add performance benchmarking
4. Implement hang detection
5. Create debugging toolkit

## Expected Benefits
- **Testing**: Comprehensive test coverage
- **Performance**: Identify bottlenecks
- **Reliability**: Detect and diagnose hangs
- **Debugging**: Better tools for troubleshooting
- **Quality**: Prevent regressions