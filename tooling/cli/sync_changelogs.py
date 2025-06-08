#!/usr/bin/env python3
"""Legacy wrapper for backward compatibility - calls changelog_tools.py"""
import sys
import argparse
from pathlib import Path
from typing import NoReturn

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tooling.cli.changelog_tools import ChangelogTools
from tooling.core.base_config import get_config


def main() -> int:
    """Main entry point - maintains CLI compatibility"""
    parser = argparse.ArgumentParser(
        description="Synchronize changelogs across dart, flutter, and rust packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync changelogs for the latest version
  %(prog)s
  
  # Dry run to see what would change
  %(prog)s --dry-run
  
  # Sync and auto-commit changes
  %(prog)s --auto-commit
  
  # Skip validation and sync
  %(prog)s --skip-validation
"""
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--auto-commit',
        action='store_true',
        help='Automatically commit changes after syncing'
    )
    
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip project structure validation'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed output including diffs'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress output except errors'
    )
    
    args = parser.parse_args()
    
    # Create config with overrides
    config = get_config(
        verbose=args.verbose,
        quiet=args.quiet,
        dry_run=args.dry_run
    )
    
    # Create tools instance
    tools = ChangelogTools(config)
    
    # Call sync with "packages" target to trigger package sync
    return tools.sync(
        source=None,
        target_pattern="packages",  # Special pattern that triggers package sync
        version=None,
        dry_run=args.dry_run,
        force=False,
        auto_commit=args.auto_commit,
        skip_validation=args.skip_validation
    )


if __name__ == '__main__':
    sys.exit(main())