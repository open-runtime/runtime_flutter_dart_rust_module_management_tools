#!/usr/bin/env python3
"""
Comprehensive test runner for all tooling tests
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path
import time
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tooling.cli.cli_utils import print_info, print_success, print_error, print_warning, print_header, console
except ImportError:
    # Fallback for when cli_utils isn't available
    def print_info(msg): print(f"ℹ {msg}")
    def print_success(msg): print(f"✓ {msg}")
    def print_error(msg): print(f"✗ {msg}")
    def print_warning(msg): print(f"⚠ {msg}")
    def print_header(msg): print(f"\n{'='*60}\n{msg}\n{'='*60}\n")
    class Console:
        def print(self, msg, style=None): print(msg)
    console = Console()


class TestRunner:
    """Orchestrates running all test suites"""
    
    def __init__(self, verbose=False, coverage=False, parallel=False):
        self.verbose = verbose
        self.coverage = coverage
        self.parallel = parallel
        self.test_dir = Path(__file__).parent
        self.results = {}
        self.start_time = None
        
    def discover_tests(self):
        """Discover all test files"""
        test_files = []
        
        # Find all test files
        for pattern in ['test_*.py', '*_test.py']:
            test_files.extend(self.test_dir.rglob(pattern))
        
        # Exclude this runner file
        test_files = [f for f in test_files if f.name != 'run_all_tests.py']
        
        # Group by directory
        test_groups = {}
        for test_file in test_files:
            group = test_file.parent.name
            if group not in test_groups:
                test_groups[group] = []
            test_groups[group].append(test_file)
        
        return test_groups
    
    def run_test_file(self, test_file):
        """Run a single test file"""
        print_info(f"Running {test_file.name}...")
        
        cmd = [sys.executable, '-m', 'pytest', str(test_file)]
        
        if self.verbose:
            cmd.append('-v')
        else:
            cmd.append('-q')
        
        if self.coverage:
            cmd.extend(['--cov=tooling', '--cov-append'])
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = time.time() - start
        
        return {
            'file': test_file.name,
            'passed': result.returncode == 0,
            'duration': duration,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    
    def run_test_group(self, group_name, test_files):
        """Run a group of test files"""
        console.print(f"\n{'='*60}", style="magenta")
        console.print(f"Running {group_name} tests", style="magenta")
        console.print(f"{'='*60}\n", style="magenta")
        
        group_results = []
        
        for test_file in sorted(test_files):
            result = self.run_test_file(test_file)
            group_results.append(result)
            
            if result['passed']:
                print_success(f"{result['file']} ({result['duration']:.2f}s)")
            else:
                print_error(f"{result['file']} ({result['duration']:.2f}s)")
                if self.verbose:
                    print(result['stderr'])
        
        return group_results
    
    def run_all_tests(self):
        """Run all discovered tests"""
        self.start_time = time.time()
        test_groups = self.discover_tests()
        
        print_info(f"Discovered {sum(len(files) for files in test_groups.values())} test files in {len(test_groups)} groups")
        
        # Initialize coverage if requested
        if self.coverage:
            subprocess.run([sys.executable, '-m', 'coverage', 'erase'], check=False)
        
        # Run tests by group
        for group_name, test_files in sorted(test_groups.items()):
            group_results = self.run_test_group(group_name, test_files)
            self.results[group_name] = group_results
        
        # Generate coverage report
        if self.coverage:
            self.generate_coverage_report()
        
        # Print summary
        self.print_summary()
        
        # Return exit code
        all_passed = all(
            result['passed'] 
            for group_results in self.results.values() 
            for result in group_results
        )
        return 0 if all_passed else 1
    
    def generate_coverage_report(self):
        """Generate coverage report"""
        print_info("Generating coverage report...")
        
        # Generate terminal report
        subprocess.run([
            sys.executable, '-m', 'coverage', 'report',
            '--include=tooling/*',
            '--omit=*/tests/*,*/test_*'
        ])
        
        # Generate HTML report
        subprocess.run([
            sys.executable, '-m', 'coverage', 'html',
            '--include=tooling/*',
            '--omit=*/tests/*,*/test_*',
            '-d', 'htmlcov'
        ])
        
        print_success("Coverage report generated in htmlcov/")
    
    def print_summary(self):
        """Print test summary"""
        total_duration = time.time() - self.start_time
        
        console.print(f"\n{'='*60}", style="magenta")
        console.print("Test Summary", style="magenta")
        console.print(f"{'='*60}\n", style="magenta")
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        for group_name, group_results in self.results.items():
            group_passed = sum(1 for r in group_results if r['passed'])
            group_total = len(group_results)
            total_tests += group_total
            passed_tests += group_passed
            failed_tests += (group_total - group_passed)
            
            if group_passed == group_total:
                print_success(f"{group_name}: {group_passed}/{group_total} passed")
            else:
                print_error(f"{group_name}: {group_passed}/{group_total} passed")
        
        console.print(f"\n{'─'*60}", style="magenta")
        
        if failed_tests == 0:
            print_success(f"All tests passed! ({passed_tests}/{total_tests})")
        else:
            print_error(f"{failed_tests} tests failed ({passed_tests}/{total_tests} passed)")
        
        print_info(f"Total duration: {total_duration:.2f}s")
        
        # List failed tests
        if failed_tests > 0:
            print_error("Failed tests:")
            for group_name, group_results in self.results.items():
                for result in group_results:
                    if not result['passed']:
                        print_error(f"  - {group_name}/{result['file']}")
    
    def save_results(self, output_file):
        """Save test results to JSON file"""
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'duration': time.time() - self.start_time,
            'results': self.results,
            'summary': {
                'total': sum(len(r) for r in self.results.values()),
                'passed': sum(1 for group in self.results.values() for r in group if r['passed']),
                'failed': sum(1 for group in self.results.values() for r in group if not r['passed'])
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print_success(f"Results saved to {output_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run all tooling tests')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-c', '--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('-p', '--parallel', action='store_true', help='Run tests in parallel (experimental)')
    parser.add_argument('-o', '--output', help='Save results to JSON file')
    parser.add_argument('--group', help='Run only tests in specific group')
    parser.add_argument('--file', help='Run only specific test file')
    
    args = parser.parse_args()
    
    # Check pytest is installed
    try:
        import pytest
    except ImportError:
        print_error("pytest is not installed. Please run: pip install pytest")
        return 1
    
    # Check coverage is installed if requested
    if args.coverage:
        try:
            import coverage
        except ImportError:
            print_error("coverage is not installed. Please run: pip install pytest-cov")
            return 1
    
    runner = TestRunner(
        verbose=args.verbose,
        coverage=args.coverage,
        parallel=args.parallel
    )
    
    # Run specific file if requested
    if args.file:
        test_file = Path(args.file)
        if not test_file.exists():
            print_error(f"Test file not found: {args.file}")
            return 1
        
        result = runner.run_test_file(test_file)
        return 0 if result['passed'] else 1
    
    # Run all tests
    exit_code = runner.run_all_tests()
    
    # Save results if requested
    if args.output:
        runner.save_results(args.output)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main()) 