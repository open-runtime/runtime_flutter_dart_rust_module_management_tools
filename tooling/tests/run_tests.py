#!/usr/bin/env python3
"""
Test runner for all tooling tests
"""

import sys
import os
import unittest
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.common_config import Colors, print_color


def discover_and_run_tests():
    """Discover and run all tests in the tests directory"""
    print_color(Colors.PURPLE, "="*60)
    print_color(Colors.PURPLE, "Running All Tooling Tests")
    print_color(Colors.PURPLE, "="*60)
    print()
    
    # Get the tests directory
    tests_dir = Path(__file__).parent
    
    # Discover all test files
    loader = unittest.TestLoader()
    suite = loader.discover(tests_dir, pattern='test_*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print()
    print_color(Colors.PURPLE, "="*60)
    if result.wasSuccessful():
        print_color(Colors.GREEN, f"✓ All tests passed! ({result.testsRun} tests)")
    else:
        print_color(Colors.RED, f"✗ Tests failed!")
        if result.failures:
            print_color(Colors.RED, f"  Failures: {len(result.failures)}")
        if result.errors:
            print_color(Colors.RED, f"  Errors: {len(result.errors)}")
    print_color(Colors.PURPLE, "="*60)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(discover_and_run_tests()) 