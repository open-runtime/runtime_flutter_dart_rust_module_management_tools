#!/usr/bin/env python3
"""
main.py - Main entry point for Runtime FDR Package Tools

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
    from tooling.core.common_config import Colors, print_color
except ImportError:
    from core.common_config import Colors, print_color

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


def display_tool_info(alias: str, command: str, module: str, description: str, show_help: bool = False):
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
            print_color(Colors.GRAY, "    No detailed help available")
        print()


def display_examples():
    """Display common usage examples"""
    print_color(Colors.PURPLE, "\n" + "=" * 60)
    print_color(Colors.PURPLE, "Common Usage Examples")
    print_color(Colors.PURPLE, "=" * 60)
    
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
        print_color(Colors.YELLOW, f"\n{title}:")
        for cmd in commands:
            if cmd.startswith("#"):
                print_color(Colors.GRAY, f"  {cmd}")
            elif cmd:
                print(f"  $ {cmd}")
            else:
                print()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Runtime FDR Package Tools - Unified CLI for multi-package repository management',
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
    print_color(Colors.PURPLE, "=" * 60)
    print_color(Colors.PURPLE, "Runtime FDR Package Tools (rfdr-tools)")
    print_color(Colors.PURPLE, "=" * 60)
    print()
    print_color(Colors.BLUE, "A comprehensive suite of CLI tools for managing multi-package repositories")
    print_color(Colors.BLUE, "with AI-powered commit messages, changelog generation, and release automation.")
    print()
    
    if args.list:
        # Simple list format
        print_color(Colors.YELLOW, "Available Commands:")
        all_commands = []
        for category, tools in TOOL_CATEGORIES.items():
            for alias, command, module, desc in tools:
                all_commands.append((alias, desc))
        
        for cmd, desc in sorted(all_commands):
            print(f"  {cmd:<20} {desc}")
    
    elif args.examples:
        # Show examples only
        display_examples()
    
    else:
        # Show categorized commands
        print_color(Colors.YELLOW, "Available Commands by Category:")
        print()
        
        for category, tools in TOOL_CATEGORIES.items():
            print_color(Colors.PURPLE, f"{category}:")
            for alias, command, module, description in tools:
                display_tool_info(alias, command, module, description, args.detailed)
            print()
        
        # Quick start section
        print_color(Colors.PURPLE, "Quick Start:")
        print_color(Colors.GREEN, "  1. Run 'rt-setup' to configure API keys and install dependencies")
        print_color(Colors.GREEN, "  2. Use 'rtc' for fast AI-powered commit messages")
        print_color(Colors.GREEN, "  3. Use 'rtcl' to generate changelog entries")
        print_color(Colors.GREEN, "  4. Use 'rtr' for the complete release workflow")
        print()
        
        # Show examples if not in detailed mode
        if not args.detailed:
            print_color(Colors.GRAY, "Run 'rfdr-tools --examples' to see usage examples")
            print_color(Colors.GRAY, "Run 'rfdr-tools --detailed' to see detailed help for all commands")
    
    print()
    print_color(Colors.GRAY, "For more information: https://github.com/open-runtime/runtime_flutter_dart_rust_package_management_tools")


if __name__ == "__main__":
    main() 