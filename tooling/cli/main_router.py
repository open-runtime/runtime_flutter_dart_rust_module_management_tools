#!/usr/bin/env python3
"""
main_router.py - Main router for Runtime FDR Package Tools

This provides a unified interface using subcommands for all CLI tools.
Commands map directly to Python files in the tooling/cli directory.

Usage:
    runtime_fdr_tools <command> [options]
    
Examples:
    runtime_fdr_tools smart_commit_fast         # Fast AI commit message
    runtime_fdr_tools smart_commit              # Detailed commit analysis
    runtime_fdr_tools release                   # Complete release workflow
    runtime_fdr_tools validate_changelogs       # Validate changelog entries

Author: Tsavo Knott, 2025
License: MIT
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from tooling.core.common_config import Colors, print_color
except ImportError:
    from core.common_config import Colors, print_color


def discover_commands() -> Dict[str, Dict[str, str]]:
    """Automatically discover all CLI commands from Python files"""
    commands = {}
    cli_dir = Path(__file__).parent
    
    # Files to exclude from command discovery
    exclude_files = {'__init__.py', 'main.py', 'main_router.py', '__pycache__'}
    
    # Scan for Python files
    for file_path in cli_dir.glob('*.py'):
        if file_path.name in exclude_files:
            continue
            
        command_name = file_path.stem  # filename without .py extension
        
        # Try to extract description from the file's docstring
        description = get_file_description(file_path)
        
        commands[command_name] = {
            "module": command_name,
            "description": description,
            "file": str(file_path)
        }
    
    return commands


def get_file_description(file_path: Path) -> str:
    """Extract description from file's module docstring"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for module docstring
        if content.startswith('"""') or content.startswith("'''"):
            # Extract first line of docstring
            quote = '"""' if content.startswith('"""') else "'''"
            end_idx = content.find(quote, 3)
            if end_idx > 0:
                docstring = content[3:end_idx].strip()
                # Get first line as description
                first_line = docstring.split('\n')[0].strip()
                # Remove common prefixes
                for prefix in [file_path.stem + '.py -', file_path.stem + ' -', file_path.stem + ':']:
                    if first_line.startswith(prefix):
                        first_line = first_line[len(prefix):].strip()
                return first_line or f"Run {file_path.stem} tool"
    except Exception:
        pass
    
    # Default descriptions for known tools
    default_descriptions = {
        "smart_commit_fast": "Generate AI-powered commit message (fast mode)",
        "smart_commit": "Generate comprehensive commit analysis",
        "sync_changelogs": "Synchronize and generate changelog entries",
        "analyze_changelog_history": "Analyze changelog history and patterns",
        "release": "Execute complete release workflow",
        "prepare_new_patch": "Prepare a new patch release",
        "push_new_patch": "Push release and create GitHub release",
        "retag_release": "Fix or update an existing release tag",
        "update_version": "Update version across all packages",
        "get_new_patch_tag": "Calculate next patch version",
        "validate_changelogs": "Validate changelog entries and format",
        "pre_release_check": "Run pre-release validation checks",
        "open_pull_request_current_tagged_branch": "Create pull request with AI analysis",
        "generate_release_notes": "Generate release notes from commits",
        "setup_ai_tools": "Complete setup for AI tools and API keys",
        "setup_permissions": "Fix file permissions for scripts",
        "install_gemini_cli": "Install Gemini CLI tool",
    }
    
    return default_descriptions.get(file_path.stem, f"Run {file_path.stem} tool")


# Discover all available commands
COMMANDS = discover_commands()

# Define command aliases for convenience
ALIASES = {
    # Commit aliases
    "commit": "smart_commit_fast",
    "c": "smart_commit_fast",
    "commit_detailed": "smart_commit",
    "cd": "smart_commit",
    
    # Changelog aliases
    "changelog": "sync_changelogs",
    "cl": "sync_changelogs",
    "analyze": "analyze_changelog_history",
    
    # Release aliases
    "r": "release",
    "prepare": "prepare_new_patch",
    "push": "push_new_patch",
    "retag": "retag_release",
    
    # Version aliases
    "version": "update_version",
    "v": "update_version",
    "next": "get_new_patch_tag",
    
    # Validation aliases
    "validate": "validate_changelogs",
    "check": "pre_release_check",
    
    # GitHub aliases
    "pr": "open_pull_request_current_tagged_branch",
    "notes": "generate_release_notes",
    
    # Setup aliases
    "setup": "setup_ai_tools",
    "s": "setup_ai_tools",
    "permissions": "setup_permissions",
    "gemini": "install_gemini_cli",
}


def get_command_groups():
    """Organize commands by category for display"""
    # Group commands by their purpose
    groups = {
        "Commit Management": [],
        "Changelog Management": [],
        "Release Management": [],
        "Version Management": [],
        "Validation": [],
        "GitHub Integration": [],
        "Setup & Configuration": [],
    }
    
    # Categorize based on command name patterns
    for cmd in sorted(COMMANDS.keys()):
        if 'commit' in cmd:
            groups["Commit Management"].append(cmd)
        elif 'changelog' in cmd or cmd == 'sync_changelogs':
            groups["Changelog Management"].append(cmd)
        elif 'release' in cmd or cmd == 'retag_release' or 'patch' in cmd:
            groups["Release Management"].append(cmd)
        elif 'version' in cmd or cmd == 'get_new_patch_tag':
            groups["Version Management"].append(cmd)
        elif 'validate' in cmd or 'check' in cmd:
            groups["Validation"].append(cmd)
        elif 'pull_request' in cmd or 'generate_release_notes' in cmd:
            groups["GitHub Integration"].append(cmd)
        elif 'setup' in cmd or 'install' in cmd or 'permissions' in cmd:
            groups["Setup & Configuration"].append(cmd)
    
    # Remove empty groups
    return {k: v for k, v in groups.items() if v}


def run_command(command: str, args: List[str]):
    """Run the specified command with arguments"""
    # Resolve aliases
    if command in ALIASES:
        command = ALIASES[command]
    
    if command not in COMMANDS:
        print_color(Colors.RED, f"Error: Unknown command '{command}'")
        print_color(Colors.YELLOW, "\nAvailable commands:")
        list_commands()
        sys.exit(1)
    
    module_name = COMMANDS[command]["module"]
    script_path = Path(__file__).parent / f"{module_name}.py"
    
    if not script_path.exists():
        print_color(Colors.RED, f"Error: Command implementation not found: {script_path}")
        sys.exit(1)
    
    # Run the command
    cmd = [sys.executable, str(script_path)] + args
    try:
        result = subprocess.run(cmd)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print_color(Colors.YELLOW, "\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print_color(Colors.RED, f"Error running command: {e}")
        sys.exit(1)


def list_commands(detailed: bool = False):
    """List all available commands"""
    groups = get_command_groups()
    
    # Build reverse alias mapping
    reverse_aliases = {}
    for alias, cmd in ALIASES.items():
        if cmd not in reverse_aliases:
            reverse_aliases[cmd] = []
        reverse_aliases[cmd].append(alias)
    
    for group_name, commands in groups.items():
        print_color(Colors.PURPLE, f"\n{group_name}:")
        
        for cmd in commands:
            if cmd in COMMANDS:
                info = COMMANDS[cmd]
                
                # Get aliases for this command
                aliases = reverse_aliases.get(cmd, [])
                alias_str = f" (aliases: {', '.join(sorted(aliases))})" if aliases else ""
                
                # Format command name for display
                display_cmd = cmd.replace('_', ' ')
                
                print(f"  {Colors.GREEN}{cmd:<40}{Colors.NC} {info['description']}{Colors.GRAY}{alias_str}{Colors.NC}")
                
                if detailed:
                    # Show command usage
                    print(f"    Usage: runtime_fdr_tools {cmd} [options]")
                    if aliases:
                        print(f"    Also: runtime_fdr_tools {aliases[0]} [options]")
                    print()


def show_examples():
    """Show usage examples"""
    examples = [
        ("Daily Development", [
            ("smart_commit_fast", "Generate fast AI commit message"),
            ("smart_commit --max --enhanced", "Comprehensive commit analysis"),
            ("sync_changelogs", "Update changelog entries"),
        ]),
        ("Release Workflow", [
            ("release", "Complete release process"),
            ("prepare_new_patch", "Prepare new version"),
            ("push_new_patch", "Push and create GitHub release"),
        ]),
        ("Validation", [
            ("validate_changelogs", "Check changelog format"),
            ("pre_release_check", "Pre-release validation"),
        ]),
        ("Setup", [
            ("setup_ai_tools", "Configure AI tools and API keys"),
            ("install_gemini_cli", "Install Gemini CLI"),
        ]),
        ("Using Aliases", [
            ("commit", "Same as smart_commit_fast"),
            ("c --max", "Fast commit with maximum analysis"),
            ("r", "Same as release"),
            ("validate", "Same as validate_changelogs"),
        ]),
    ]
    
    print_color(Colors.PURPLE, "\nUsage Examples:")
    
    for category, cmds in examples:
        print_color(Colors.YELLOW, f"\n{category}:")
        for cmd, desc in cmds:
            print(f"  $ runtime_fdr_tools {cmd:<35} # {desc}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        prog='runtime_fdr_tools',
        description='Runtime FDR Package Tools - Unified CLI for multi-package repository management',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands map directly to Python files in the tooling/cli directory.

For help on a specific command:
  runtime_fdr_tools <command> --help

Examples:
  runtime_fdr_tools smart_commit_fast         # Fast AI commit message
  runtime_fdr_tools validate_changelogs       # Validate changelogs
  runtime_fdr_tools release                   # Complete release workflow
  
Using aliases:
  runtime_fdr_tools commit                    # Alias for smart_commit_fast
  runtime_fdr_tools c --max                   # Fast commit with max analysis
  runtime_fdr_tools validate                  # Alias for validate_changelogs
        """
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        help='Command to run'
    )
    
    parser.add_argument(
        'args',
        nargs=argparse.REMAINDER,
        help='Arguments for the command'
    )
    
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List all available commands'
    )
    
    parser.add_argument(
        '-e', '--examples',
        action='store_true',
        help='Show usage examples'
    )
    
    # Parse known args to handle our flags
    args, remaining = parser.parse_known_args()
    
    # Header
    if not args.command or args.list or args.examples:
        print_color(Colors.PURPLE, "=" * 60)
        print_color(Colors.PURPLE, "Runtime FDR Package Tools (runtime_fdr_tools)")
        print_color(Colors.PURPLE, "=" * 60)
        print()
    
    # Handle special flags
    if args.list:
        list_commands(detailed=True)
        print()
        return
    
    if args.examples:
        show_examples()
        print()
        return
    
    # If no command specified, show help
    if not args.command:
        print_color(Colors.BLUE, "A comprehensive suite of CLI tools for managing multi-package repositories")
        print_color(Colors.BLUE, "with AI-powered commit messages, changelog generation, and release automation.")
        list_commands()
        print()
        print_color(Colors.GRAY, "Run 'runtime_fdr_tools --examples' for usage examples")
        print_color(Colors.GRAY, "Run 'runtime_fdr_tools <command> --help' for command-specific help")
        print()
        return
    
    # Run the specified command
    # Combine remaining args with args.args
    all_args = remaining + (args.args or [])
    run_command(args.command, all_args)


if __name__ == "__main__":
    main() 