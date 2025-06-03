#!/usr/bin/env python3
"""
simple_changelog_test.py - Minimal changelog sync test to debug hanging issue

Author: Tsavo Knott, 2025
License: Proprietary - All Rights Reserved
"""

import subprocess
import sys
import os

def main():
    print("Starting minimal changelog sync test...")
    
    # Test 1: Environment variable
    backfill_date = os.environ.get('CHANGELOG_BACKFILL_DATE', '2025-06-01')
    print(f"Backfill date: {backfill_date}")
    
    # Test 2: Get commits
    print("\nGetting commits...")
    try:
        result = subprocess.run(
            ["git", "log", f"--since={backfill_date}", "--oneline", "--pretty=format:%H"],
            capture_output=True,
            text=True,
            timeout=5
        )
        commits = result.stdout.strip().split('\n') if result.stdout else []
        print(f"Found {len(commits)} commits")
        
        # Test 3: Process first commit
        if commits:
            print(f"\nProcessing first commit: {commits[0][:7]}")
            
            # Get commit info
            result = subprocess.run(
                ["git", "show", "-s", "--format=%H%n%s%n%an%n%ae%n%ad", "--date=format:%Y-%m-%d", commits[0]],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                print(f"  Hash: {lines[0][:7]}")
                print(f"  Message: {lines[1]}")
                print(f"  Author: {lines[2]}")
                print(f"  Date: {lines[4] if len(lines) > 4 else 'Unknown'}")
            
            # Get changed files
            result = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commits[0]],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                files = result.stdout.strip().split('\n') if result.stdout else []
                print(f"  Changed files: {len(files)}")
                for f in files[:3]:
                    print(f"    - {f}")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")
                    
    except subprocess.TimeoutExpired:
        print("ERROR: Git command timed out!")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
        
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main() 