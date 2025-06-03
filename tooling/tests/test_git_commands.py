#!/usr/bin/env python3
"""
test_git_commands.py - Test git commands to debug hanging issue

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import subprocess
import time

def run_git_command(cmd):
    """Run a git command and time it"""
    print(f"\nRunning: git {' '.join(cmd)}")
    start = time.time()
    try:
        result = subprocess.run(
            ["git"] + cmd,
            capture_output=True,
            text=True,
            timeout=5  # 5 second timeout
        )
        elapsed = time.time() - start
        print(f"Completed in {elapsed:.2f}s")
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"Output lines: {len(result.stdout.splitlines())}")
            print(f"First line: {result.stdout.splitlines()[0] if result.stdout.splitlines() else 'None'}")
        if result.stderr:
            print(f"Error: {result.stderr}")
        return result
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT after 5 seconds!")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def main():
    print("Testing git commands...")
    
    # Test 1: Basic git log
    run_git_command(["log", "--oneline", "-n", "5"])
    
    # Test 2: Git log with date filter
    run_git_command(["log", "--since=2025-06-01", "--oneline", "-n", "5"])
    
    # Test 3: Git log with format
    run_git_command(["log", "--oneline", "--pretty=format:%H", "-n", "5"])
    
    # Test 4: Check branches
    run_git_command(["branch", "-a"])
    
    # Test 5: Show ref
    run_git_command(["show-ref", "--verify", "--quiet", "refs/heads/main"])
    
    # Test 6: Get current branch
    run_git_command(["branch", "--show-current"])
    
    # Test 7: Log with branch and since
    run_git_command(["log", "main", "--since=2025-06-01", "--oneline", "--pretty=format:%H", "-n", "5"])
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    main() 