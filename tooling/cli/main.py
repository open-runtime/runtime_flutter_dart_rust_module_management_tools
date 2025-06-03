#!/usr/bin/env python3
"""
main.py - Main entry point for Runtime FDR (Flutter, Dart, Rust) Package Tools

This provides a unified interface to all the CLI tools in the package.

Author: Tsavo Knott, 2025
License: MIT
"""

import os
import sys
import subprocess
import importlib
from pathlib import Path
from typing import List, Dict, Tuple
import argparse

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tooling.core.logging import setup_logging, get_logger
    from tooling.core.common_config import Colors
except ImportError:
    from core.logging import setup_logging, get_logger
    from core.common_config import Colors

# Tool categories and their commands
TOOL_CATEGORIES = {
    "AI-Powered Commit Tools": [
        ("rtc", "rt-commit-fast", "smart_commit_fast", "Ultra-fast AI commit messages (2-3s)"),
        ("rt-commit", "rt-commit", "smart_commit", "Comprehensive AI commit analysis (30-50s)"),
    ],
    "Changelog Management": [
        ("rtcl", "rt-changelog", "sync_changelogs", "Generate changelog entries with AI"),
        ("rt-changelog-analyze", "rt-changelog-analyze", "analyze_changelog_history", "Analyze changelog history"),
    ],
    "Release Management": [
        ("rtr", "rt-release", "release", "Complete release workflow"),
        ("rt-prepare-patch", "rt-prepare-patch", "prepare_new_patch", "Prepare a new patch version"),
        ("rt-push-patch", "rt-push-patch", "push_new_patch", "Push release and create GitHub release"),
        ("rt-retag", "rt-retag", "retag_release", "Fix/update an existing release tag"),
    ],
    "Version Management": [
        ("rt-version", "rt-version", "update_version", "Update version across all packages"),
        ("rt-next-tag", "rt-next-tag", "get_new_patch_tag", "Calculate next patch version"),
    ],
    "Validation Tools": [
        ("rt-validate", "rt-validate", "validate_changelogs", "Validate changelog entries"),
        ("rt-prerelease-check", "rt-prerelease-check", "pre_release_check", "Pre-release validation"),
    ],
    "GitHub Integration": [
        ("rt-pr", "rt-pr", "open_pull_request_current_tagged_branch", "Create PR with AI analysis"),
        ("rt-release-notes", "rt-release-notes", "generate_release_notes", "Generate release notes"),
    ],
    "Setup and Configuration": [
        ("rt-setup", "rt-setup", "setup_ai_tools", "Complete AI tools setup"),
        ("rt-setup-permissions", "rt-setup-permissions", "setup_permissions", "Fix script permissions"),
        ("rt-install-gemini", "rt-install-gemini", "install_gemini_cli", "Install gemini-cli"),
        ("rt-install-deps", "rt-install-deps", "install_shared_deps", "Install enhanced dependencies"),
    ],
}


def get_tool_help(module_name: str) -> str:
    """Get the help output for a specific tool"""
    try:
        # Try to run the tool with --help
        script_path = Path(__file__).parent / f"{module_name}.py"
        if script_path.exists():
            result = subprocess.run(
                [sys.executable, str(script_path), "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
    except Exception:
        pass
    return "Help not available"


def display_tool_info(alias: str, command: str, module: str, description: str, show_help: bool = False, logger=None):
    """Display information about a tool"""
    # Display basic info
    line = f"  {Colors.GREEN}{alias:<20}{Colors.NC}"
    if alias != command:
        line += f"{Colors.GRAY}({command}){Colors.NC}  "
    else:
        line += " " * (len(command) + 4)
    line += f"{Colors.BLUE}{description}{Colors.NC}"
    print(line)
    
    # Display detailed help if requested
    if show_help:
        print()
        help_text = get_tool_help(module)
        if help_text != "Help not available":
            # Indent the help text
            for line in help_text.split('\n'):
                print("    " + line)
        else:
            print(f"    {Colors.GRAY}No detailed help available{Colors.NC}")
        print()


def display_examples(logger):
    """Display common usage examples"""
    print(f"{Colors.PURPLE}\n{'=' * 60}{Colors.NC}")
    print(f"{Colors.PURPLE}Common Usage Examples{Colors.NC}")
    print(f"{Colors.PURPLE}{'=' * 60}{Colors.NC}")
    
    examples = [
        ("Daily Development Workflow", [
            "# Make your changes",
            "git add .",
            "",
            "# Generate AI commit message (ultra-fast)",
            "rtc",
            "",
            "# Or with comprehensive analysis",
            "rtc --max --enhanced",
            "",
            "# For any repository structure (not just dart/flutter/rust)",
            "rtc --any",
        ]),
        ("Release Workflow", [
            "# Complete release process",
            "rtr",
            "",
            "# Or step by step:",
            "rt-prepare-patch    # Prepare version",
            "rt-push-patch       # Push and create GitHub release",
        ]),
        ("Changelog Management", [
            "# Generate changelog entries",
            "rtcl",
            "",
            "# Analyze changelog history",
            "rt-changelog-analyze",
        ]),
        ("Initial Setup", [
            "# One-time setup",
            "rt-setup",
            "",
            "# This will:",
            "# - Install gemini-cli",
            "# - Configure API keys",
            "# - Set up permissions",
        ]),
    ]
    
    for title, commands in examples:
        print(f"\n{Colors.YELLOW}{title}:{Colors.NC}")
        for cmd in commands:
            if cmd.startswith("#"):
                print(f"  {Colors.GRAY}{cmd}{Colors.NC}")
            elif cmd:
                print(f"  $ {cmd}")
            else:
                print()


def main():
    """Main entry point"""
    # Setup logging with ERROR level for help display to avoid clutter
    logger = setup_logging(tool_name="rfdr-tools", level="ERROR")
    logger.debug("Starting rfdr-tools CLI")
    
    parser = argparse.ArgumentParser(
        description='Runtime FDR (Flutter, Dart, Rust) Package Tools - Unified CLI for multi-package repository management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
For more information on a specific command, run:
  <command> --help

Examples:
  rfdr-tools              # Show this help
  rfdr-tools --detailed   # Show detailed help for all commands
  rtc --help              # Show help for smart commit fast
  rtr --help              # Show help for release tool
        """
    )
    
    parser.add_argument(
        '-d', '--detailed',
        action='store_true',
        help='Show detailed help for all commands'
    )
    
    parser.add_argument(
        '-e', '--examples',
        action='store_true',
        help='Show usage examples'
    )
    
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List all available commands (simple format)'
    )
    
    args = parser.parse_args()
    
    # Header
    print(f"{Colors.PURPLE}{'=' * 60}{Colors.NC}")
    print(f"{Colors.PURPLE}Runtime FDR (Flutter, Dart, Rust) Package Tools (rfdr-tools){Colors.NC}")
    print(f"{Colors.PURPLE}{'=' * 60}{Colors.NC}")
    print()
    print(f"{Colors.BLUE}A comprehensive suite of CLI tools for managing multi-package repositories{Colors.NC}")
    print(f"{Colors.BLUE}with AI-powered commit messages, changelog generation, and release automation.{Colors.NC}")
    print()
    
    logger.debug("Displaying tool help", list_mode=args.list, detailed=args.detailed, examples=args.examples)
    
    if args.list:
        # Simple list format
        print(f"{Colors.YELLOW}Available Commands:{Colors.NC}")
        all_commands = []
        for category, tools in TOOL_CATEGORIES.items():
            for alias, command, module, desc in tools:
                all_commands.append((alias, desc))
        
        logger.debug("Listing commands", command_count=len(all_commands))
        for cmd, desc in sorted(all_commands):
            print(f"  {cmd:<20} {desc}")
    
    elif args.examples:
        # Show examples only
        display_examples(logger)
    
    else:
        # Show categorized commands
        print(f"{Colors.YELLOW}Available Commands by Category:{Colors.NC}")
        print()
        
        for category, tools in TOOL_CATEGORIES.items():
            print(f"{Colors.PURPLE}{category}:{Colors.NC}")
            logger.debug("Displaying category", category=category, tool_count=len(tools))
            for alias, command, module, description in tools:
                display_tool_info(alias, command, module, description, args.detailed, logger)
            print()
        
        # Quick start section
        print(f"{Colors.PURPLE}Quick Start:{Colors.NC}")
        print(f"{Colors.GREEN}  1. Run 'rt-setup' to configure API keys and install dependencies{Colors.NC}")
        print(f"{Colors.GREEN}  2. Use 'rtc' for fast AI-powered commit messages{Colors.NC}")
        print(f"{Colors.GREEN}  3. Use 'rtcl' to generate changelog entries{Colors.NC}")
        print(f"{Colors.GREEN}  4. Use 'rtr' for the complete release workflow{Colors.NC}")
        print()
        
        # Show examples if not in detailed mode
        if not args.detailed:
            print(f"{Colors.GRAY}Run 'rfdr-tools --examples' to see usage examples{Colors.NC}")
            print(f"{Colors.GRAY}Run 'rfdr-tools --detailed' to see detailed help for all commands{Colors.NC}")
    
    print()
    print(f"{Colors.GRAY}For more information: https://github.com/open-runtime/runtime_flutter_dart_rust_package_management_tools{Colors.NC}")
    
    logger.debug("rfdr-tools CLI completed successfully")


if __name__ == "__main__":
    main() 